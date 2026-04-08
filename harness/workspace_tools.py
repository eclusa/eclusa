"""harness/workspace_tools.py — Workspace tools for pydantic-ai agents.

Provides tools that give agents a real filesystem to work in:
write_file, read_file, run_command, list_files.

Agent builders: build_derive_agent, build_generate_agent.
"""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic_ai import Agent, RunContext

logger = logging.getLogger(__name__)

COMMAND_TIMEOUT = 60


@dataclass
class WorkspaceContext:
    workspace_dir: str
    cascade_id: str
    stage_name: str
    upstream_context: dict[str, Any] = field(default_factory=dict)


def _safe_path(workspace_dir: str, path: str) -> Path | None:
    """Resolve path within workspace. Returns None if path escapes."""
    base = Path(workspace_dir).resolve()
    target = (base / path).resolve()
    if not str(target).startswith(str(base)):
        return None
    return target


def _register_workspace_tools(agent: Agent[WorkspaceContext, str]) -> None:
    """Register the 4 workspace tools on an agent."""

    @agent.tool
    async def write_file(ctx: RunContext[WorkspaceContext], path: str, content: str) -> str:
        """Write content to a file in the workspace. Creates parent directories."""
        target = _safe_path(ctx.deps.workspace_dir, path)
        if target is None:
            return f"Error: path '{path}' escapes workspace. Use relative paths only."
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        return f"Wrote {len(content)} bytes to {path}"

    @agent.tool
    async def read_file(ctx: RunContext[WorkspaceContext], path: str) -> str:
        """Read a file from the workspace."""
        target = _safe_path(ctx.deps.workspace_dir, path)
        if target is None:
            return f"Error: path '{path}' escapes workspace."
        if not target.exists():
            return f"Error: file '{path}' not found."
        try:
            return target.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            return f"Error: file '{path}' is binary, cannot read as text."

    @agent.tool
    async def run_command(ctx: RunContext[WorkspaceContext], command: str) -> str:
        """Run a shell command in the workspace directory. Returns stdout+stderr with exit code."""
        env = dict(os.environ)
        venv_bin = Path(ctx.deps.workspace_dir) / ".venv" / "bin"
        if venv_bin.exists():
            env["PATH"] = f"{venv_bin}:{env.get('PATH', '')}"
            env["VIRTUAL_ENV"] = str(Path(ctx.deps.workspace_dir) / ".venv")

        proc = await asyncio.create_subprocess_shell(
            command,
            cwd=ctx.deps.workspace_dir,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=COMMAND_TIMEOUT
            )
        except asyncio.TimeoutError:
            proc.kill()
            return f"[exit_code=-1]\nCommand timed out after {COMMAND_TIMEOUT}s"

        output = (stdout + stderr).decode("utf-8", errors="replace")
        return f"[exit_code={proc.returncode}]\n{output}"

    @agent.tool
    async def list_files(ctx: RunContext[WorkspaceContext], path: str = ".") -> str:
        """List files in the workspace directory. Returns tree-like output."""
        target = _safe_path(ctx.deps.workspace_dir, path)
        if target is None:
            return f"Error: path '{path}' escapes workspace."
        if not target.exists():
            return f"Error: directory '{path}' not found."

        lines: list[str] = []
        _walk_tree(target, Path(ctx.deps.workspace_dir).resolve(), lines, depth=0, max_depth=3)
        return "\n".join(lines) if lines else "(empty directory)"


def _walk_tree(
    path: Path, base: Path, lines: list[str], depth: int, max_depth: int
) -> None:
    if depth > max_depth:
        lines.append("  " * depth + "...")
        return
    try:
        entries = sorted(path.iterdir(), key=lambda p: (p.is_file(), p.name))
    except PermissionError:
        return
    for entry in entries:
        if entry.name.startswith(".") and entry.name not in (".env",):
            continue
        rel = entry.relative_to(base)
        prefix = "  " * depth
        if entry.is_dir():
            lines.append(f"{prefix}{rel}/")
            _walk_tree(entry, base, lines, depth + 1, max_depth)
        else:
            size = entry.stat().st_size
            lines.append(f"{prefix}{rel} ({size}b)")


def _format_upstream_context(ctx: dict[str, Any]) -> str:
    """Format upstream context dict into a readable prompt section."""
    parts: list[str] = []
    for key, value in ctx.items():
        if value is None or value == "" or value == [] or value == {}:
            continue
        if isinstance(value, (dict, list)):
            import json
            parts.append(f"### {key}\n```json\n{json.dumps(value, indent=2, default=str)[:2000]}\n```")
        else:
            text = str(value)[:2000]
            parts.append(f"### {key}\n{text}")
    return "\n\n".join(parts) if parts else "(no upstream context available)"


def build_derive_agent(model: str) -> Agent[WorkspaceContext, str]:
    """Build a pydantic-ai agent for the Derive stage with workspace tools."""
    agent = Agent(
        model,
        system_prompt=(
            "You are a test specification expert working in a real workspace. "
            "You have tools to write files, read files, run commands, and list files.\n\n"
            "Your job: derive BDD/E2E test scenarios as executable pytest test files from "
            "the upstream context (scope document, matched sources, constraints).\n\n"
            "Workflow:\n"
            "1. Read the upstream context provided in the user message\n"
            "2. Write test files to the workspace using write_file (e.g., test_app.py)\n"
            "3. Run 'python -m pytest --collect-only' to verify tests are syntactically valid\n"
            "4. Fix any syntax errors and re-run until tests collect cleanly\n"
            "5. Respond with a summary of the test suite you created\n\n"
            "Write practical, runnable tests. If the scope is a web app, write tests that "
            "import the app, make requests, and check responses. Include a requirements.txt "
            "if tests need dependencies (pytest, flask, etc).\n\n"
            "Available tools: write_file, read_file, run_command, list_files"
        ),
        deps_type=WorkspaceContext,
    )
    _register_workspace_tools(agent)
    return agent


def build_generate_agent(model: str) -> Agent[WorkspaceContext, str]:
    """Build a pydantic-ai agent for the Generate stage with workspace tools."""
    agent = Agent(
        model,
        system_prompt=(
            "You are a code generator working in a real workspace. "
            "You have tools to write files, read files, run commands, and list files.\n\n"
            "Your job: generate implementation code that passes all derived tests.\n\n"
            "Workflow:\n"
            "1. List files in the workspace to see existing test files from the derive stage\n"
            "2. Read the test files to understand what's expected\n"
            "3. Write implementation code using write_file\n"
            "4. Install dependencies with run_command (pip install -r requirements.txt)\n"
            "5. Run the tests with run_command (python -m pytest -x -v)\n"
            "6. Read error output, fix issues, iterate until all tests pass\n"
            "7. If building a web app, ensure it starts with a simple command (python app.py)\n"
            "8. Create requirements.txt listing all dependencies\n"
            "9. Respond with a summary of what you built\n\n"
            "The test files from the derive stage are already in the workspace. "
            "Your code must pass those tests.\n\n"
            "When tests don't exist or are trivial, focus on building a working application "
            "that matches the scope document. Write clean, functional code.\n\n"
            "Your code will be deployed in a Docker container and served over HTTP. "
            "Make sure any web server binds to 0.0.0.0, not localhost/127.0.0.1.\n\n"
            "Available tools: write_file, read_file, run_command, list_files"
        ),
        deps_type=WorkspaceContext,
    )
    _register_workspace_tools(agent)
    return agent
