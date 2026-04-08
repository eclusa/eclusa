"""Ship stage handler — parse generated code, persist to object store + git, build + run in Docker.

After the Generate stage resolves with a code blob, the Ship stage:
1. Parses the LLM output into individual named files
2. Writes each file to LocalObjectStore (content-addressed, blake3)
3. Commits files to a per-cascade git repo under workspaces/
4. Builds a Docker image and runs a container on a dynamic port
5. Health-checks the container and creates deployment artifacts

Artifact types used: file_created, git_commit, deployment
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import socket
from pathlib import Path
from typing import Any

import asyncpg
import httpx

from executor.scc_handlers import _resolve_stage_immediately
from storage.object_store import LocalObjectStore

logger = logging.getLogger(__name__)

SYSTEM_SCHEMA_VERSION = "0002"
SHIP_TIMEOUT_SECONDS = 120
HEALTH_CHECK_RETRIES = 10
HEALTH_CHECK_INTERVAL = 2
WORKSPACES_DIR = os.environ.get("ECLUSA_WORKSPACES_DIR", "./workspaces")

_LANG_TO_FILENAME: dict[str, str] = {
    "python": "main.py",
    "py": "main.py",
    "html": "index.html",
    "css": "style.css",
    "javascript": "app.js",
    "js": "app.js",
    "typescript": "app.ts",
    "ts": "app.ts",
    "dockerfile": "Dockerfile",
    "json": "data.json",
    "yaml": "config.yaml",
    "yml": "config.yml",
    "sql": "schema.sql",
    "sh": "run.sh",
    "bash": "run.sh",
}

_FILENAME_PATTERN = re.compile(
    r"^(?:#|//|<!--|--)\s*(?:filename:\s*)?(\S+\.\w+)\s*(?:-->)?$"
)


def parse_generated_code(text: str) -> list[tuple[str, str]]:
    """Parse LLM-generated code text into individual (filename, content) pairs.

    Handles triple-backtick fenced blocks with optional language tags and
    filename comments. Falls back to treating the entire text as a single file.
    """
    blocks = re.findall(r"```(\w*)\n(.*?)```", text, re.DOTALL)
    if not blocks:
        return [("main.py", text.strip())]

    files: list[tuple[str, str]] = []
    seen_names: set[str] = set()
    counter = 0

    for lang, content in blocks:
        content = content.strip()
        lines = content.split("\n")
        filename = None

        # Try to extract filename from first line comment
        if lines:
            match = _FILENAME_PATTERN.match(lines[0].strip())
            if match:
                filename = match.group(1)
                content = "\n".join(lines[1:]).strip()

        # Fall back to language-based name
        if not filename:
            filename = _LANG_TO_FILENAME.get(lang.lower(), "")

        # Fall back to generic name
        if not filename:
            counter += 1
            filename = f"file_{counter}.txt"

        # Deduplicate filenames
        base = filename
        dedup = 1
        while filename in seen_names:
            stem, ext = os.path.splitext(base)
            filename = f"{stem}_{dedup}{ext}"
            dedup += 1
        seen_names.add(filename)

        files.append((filename, content))

    return files


async def write_files_to_object_store(
    files: list[tuple[str, str]],
    conn: asyncpg.Connection,
    stage: dict[str, Any],
    actor_id: str,
) -> list[tuple[str, str]]:
    """Write parsed files to LocalObjectStore and create file_created artifacts.

    Returns list of (filename, blake3_key) tuples.
    """
    store = LocalObjectStore()
    results: list[tuple[str, str]] = []
    cascade_id = str(stage["cascade_id"])
    stage_id = str(stage["id"])

    for filename, content in files:
        data = content.encode("utf-8")
        blake3_key = store.put(data)
        results.append((filename, blake3_key))

        await conn.execute(
            """
            INSERT INTO artifact (id, intent_id, cascade_id, stage_id, type, external_ref, external_sys, payload)
            SELECT gen_random_uuid(), c.intent_id, $1::uuid, $2::uuid, 'file_created', $3::text, 'object_store',
                   jsonb_build_object('filename', $4::text, 'blake3_key', $3::text, 'size_bytes', $5::int)
            FROM cascade c WHERE c.id = $1::uuid
            """,
            cascade_id,
            stage_id,
            blake3_key,
            filename,
            len(data),
        )

    return results


async def _run_subprocess(
    *args: str,
    cwd: str | None = None,
    env: dict[str, str] | None = None,
    timeout: int = SHIP_TIMEOUT_SECONDS,
) -> tuple[int, str]:
    """Run a subprocess and return (returncode, combined output)."""
    full_env = dict(os.environ)
    if env:
        full_env.update(env)

    proc = await asyncio.create_subprocess_exec(
        *args,
        cwd=cwd,
        env=full_env,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        return -1, f"Subprocess timed out after {timeout}s"

    output = (stdout + stderr).decode("utf-8", errors="replace")
    return proc.returncode or 0, output


_GIT_ENV = {
    "GIT_AUTHOR_NAME": "eclusa",
    "GIT_AUTHOR_EMAIL": "eclusa@system",
    "GIT_COMMITTER_NAME": "eclusa",
    "GIT_COMMITTER_EMAIL": "eclusa@system",
}


async def init_and_commit_git(
    cascade_id: str,
    files: list[tuple[str, str]],
    conn: asyncpg.Connection,
    stage: dict[str, Any],
    actor_id: str,
) -> str:
    """Create a per-cascade git repo, write files, commit, create artifact.

    Returns the commit hash (40 hex chars).
    """
    workspace_dir = str(Path(WORKSPACES_DIR) / cascade_id)
    Path(workspace_dir).mkdir(parents=True, exist_ok=True)

    # Write files to workspace
    for filename, content in files:
        filepath = Path(workspace_dir) / filename
        filepath.parent.mkdir(parents=True, exist_ok=True)
        filepath.write_text(content, encoding="utf-8")

    # Git init + add + commit
    await _run_subprocess("git", "init", cwd=workspace_dir, env=_GIT_ENV)
    await _run_subprocess("git", "add", ".", cwd=workspace_dir, env=_GIT_ENV)
    rc, output = await _run_subprocess(
        "git", "commit", "-m",
        f"eclusa: generated code for cascade {cascade_id}",
        cwd=workspace_dir,
        env=_GIT_ENV,
    )
    if rc != 0:
        logger.warning("Git commit returned %d: %s", rc, output)

    # Get commit hash
    rc, commit_hash = await _run_subprocess(
        "git", "rev-parse", "HEAD", cwd=workspace_dir, env=_GIT_ENV
    )
    commit_hash = commit_hash.strip()

    # Create git_commit artifact
    await conn.execute(
        """
        INSERT INTO artifact (id, intent_id, cascade_id, stage_id, type, external_ref, external_sys, payload)
        SELECT gen_random_uuid(), c.intent_id, $1::uuid, $2::uuid, 'git_commit', $3::text, 'local_git',
               jsonb_build_object('workspace_dir', $4::text, 'file_count', $5::int)
        FROM cascade c WHERE c.id = $1::uuid
        """,
        str(stage["cascade_id"]),
        str(stage["id"]),
        commit_hash,
        workspace_dir,
        len(files),
    )

    return commit_hash


def _find_free_port(start: int = 9000) -> int:
    """Find an available TCP port starting from `start`."""
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"No free port found in range {start}-{start + 100}")


def _detect_app_port(workspace_dir: str, files: list[tuple[str, str]]) -> int:
    """Detect the application port from Dockerfile or code conventions."""
    dockerfile_path = Path(workspace_dir) / "Dockerfile"
    if dockerfile_path.exists():
        content = dockerfile_path.read_text()
        expose_match = re.search(r"EXPOSE\s+(\d+)", content)
        if expose_match:
            return int(expose_match.group(1))

    # Check if any Python file imports Flask
    for filename, content in files:
        if filename.endswith(".py") and "flask" in content.lower():
            return 5000

    return 8080


_DEFAULT_FLASK_DOCKERFILE = """\
FROM python:3.12-slim
WORKDIR /app
COPY . .
RUN pip install --no-cache-dir flask 2>/dev/null; true
RUN if [ -f requirements.txt ]; then pip install --no-cache-dir -r requirements.txt 2>/dev/null; true; fi
EXPOSE 5000
CMD ["python", "{main_file}"]
"""

_DEFAULT_PYTHON_DOCKERFILE = """\
FROM python:3.12-slim
WORKDIR /app
COPY . .
EXPOSE 8080
CMD ["python", "{main_file}"]
"""


async def build_and_run_container(
    cascade_id: str,
    workspace_dir: str,
    files: list[tuple[str, str]],
    conn: asyncpg.Connection,
    stage: dict[str, Any],
    actor_id: str,
) -> str:
    """Build Docker image, run container, health-check, create deployment artifact.

    Returns the deployment URL.
    """
    filenames = [f for f, _ in files]

    # Generate Dockerfile if not present
    if "Dockerfile" not in filenames:
        main_file = next(
            (f for f in filenames if f.endswith(".py")), filenames[0]
        )
        has_flask = any(
            "flask" in content.lower()
            for f, content in files
            if f.endswith(".py")
        )
        template = _DEFAULT_FLASK_DOCKERFILE if has_flask else _DEFAULT_PYTHON_DOCKERFILE
        dockerfile_content = template.format(main_file=main_file)
        Path(workspace_dir, "Dockerfile").write_text(dockerfile_content)

    app_port = _detect_app_port(workspace_dir, files)
    image_name = f"eclusa-app-{cascade_id[:8]}"
    container_name = f"eclusa-ship-{cascade_id[:8]}"

    # Build
    rc, output = await _run_subprocess(
        "docker", "build", "-t", image_name, workspace_dir,
        timeout=SHIP_TIMEOUT_SECONDS,
    )
    if rc != 0:
        raise RuntimeError(f"Docker build failed: {output}")

    host_port = _find_free_port()

    # Run
    rc, output = await _run_subprocess(
        "docker", "run", "-d",
        "--name", container_name,
        "-p", f"{host_port}:{app_port}",
        image_name,
    )
    if rc != 0:
        raise RuntimeError(f"Docker run failed: {output}")

    # Health check
    url = f"http://localhost:{host_port}"
    healthy = False
    async with httpx.AsyncClient(verify=False) as client:
        for attempt in range(HEALTH_CHECK_RETRIES):
            try:
                resp = await client.get(url + "/", timeout=5)
                if resp.status_code < 500:
                    healthy = True
                    break
            except (httpx.ConnectError, httpx.ReadTimeout):
                pass
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

    if not healthy:
        logger.warning("Container %s not healthy after %d checks", container_name, HEALTH_CHECK_RETRIES)

    # Create deployment artifact
    await conn.execute(
        """
        INSERT INTO artifact (id, intent_id, cascade_id, stage_id, type, external_ref, external_sys, payload)
        SELECT gen_random_uuid(), c.intent_id, $1::uuid, $2::uuid, 'deployment', $3::text, 'docker',
               jsonb_build_object('container_name', $4::text, 'image_name', $5::text, 'host_port', $6::int, 'app_port', $7::int, 'healthy', $8::bool)
        FROM cascade c WHERE c.id = $1::uuid
        """,
        str(stage["cascade_id"]),
        str(stage["id"]),
        url,
        container_name,
        image_name,
        host_port,
        app_port,
        healthy,
    )

    return url


def _read_workspace_files(workspace_dir: str) -> list[tuple[str, str]]:
    """Read all files from workspace directory, returning (relative_path, content) pairs."""
    base = Path(workspace_dir)
    if not base.exists():
        return []
    files: list[tuple[str, str]] = []
    for filepath in sorted(base.rglob("*")):
        if filepath.is_file() and not filepath.name.startswith("."):
            # Skip __pycache__, .git, etc
            rel = str(filepath.relative_to(base))
            if any(part.startswith(".") or part == "__pycache__" for part in filepath.parts):
                continue
            try:
                content = filepath.read_text(encoding="utf-8")
                files.append((rel, content))
            except (UnicodeDecodeError, PermissionError):
                continue
    return files


async def dispatch_scc_ship(
    conn: asyncpg.Connection,
    stage: dict[str, Any],
    actor_id: str,
) -> None:
    """Ship stage entry point — read workspace, store, commit, build, run.

    Primary path: reads files from workspaces/{cascade_id}/ written by the generate agent.
    Fallback: parses generated_code text blob if workspace is empty (backward compat).
    """
    stage_input = stage.get("input") or {}
    if isinstance(stage_input, str):
        stage_input = json.loads(stage_input)

    cascade_id = str(stage["cascade_id"])
    workspace_dir = stage_input.get("workspace_dir") or str(Path(WORKSPACES_DIR) / cascade_id)

    # Primary path: read from workspace written by generate agent
    files = _read_workspace_files(workspace_dir)

    # Fallback: parse text blob (backward compat for old-style generate)
    if not files:
        generated_code = stage_input.get("generated_code", "")
        if generated_code:
            files = parse_generated_code(generated_code)
            logger.info("Ship stage: parsed %d files from text blob (fallback)", len(files))
            # Write parsed files to workspace for git/docker
            Path(workspace_dir).mkdir(parents=True, exist_ok=True)
            for filename, content in files:
                filepath = Path(workspace_dir) / filename
                filepath.parent.mkdir(parents=True, exist_ok=True)
                filepath.write_text(content, encoding="utf-8")

    if not files:
        await _resolve_stage_immediately(
            conn, stage, actor_id,
            note="scc_ship_skipped",
            output_payload={"skipped": True, "reason": "no files in workspace and no generated_code"},
        )
        return

    logger.info("Ship stage: %d files from workspace %s", len(files), workspace_dir)

    # 1. Object store
    stored = await write_files_to_object_store(files, conn, stage, actor_id)

    # 2. Git commit
    commit_hash = await init_and_commit_git(cascade_id, files, conn, stage, actor_id)
    logger.info("Ship stage: committed %d files, hash=%s", len(files), commit_hash[:8])

    # 3. Docker build + run
    try:
        deployment_url = await build_and_run_container(
            cascade_id, workspace_dir, files, conn, stage, actor_id
        )
        logger.info("Ship stage: container running at %s", deployment_url)
    except (RuntimeError, FileNotFoundError, OSError) as exc:
        logger.warning("Ship stage Docker build/run failed: %s — resolving without deployment", exc)
        deployment_url = None

    # 4. Resolve
    await _resolve_stage_immediately(
        conn, stage, actor_id,
        note="scc_ship",
        output_payload={
            "files": [f for f, _ in files],
            "blake3_keys": {f: k for f, k in stored},
            "commit_hash": commit_hash,
            "deployment_url": deployment_url,
            "workspace_dir": workspace_dir,
        },
    )
