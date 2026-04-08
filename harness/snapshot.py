"""
harness/snapshot.py — Workspace snapshot store for pause/resume.

Local filesystem backend for Phase 3. Interface is swappable to S3/MinIO
in Phase 6 without changing calling code. D-04.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class SnapshotStore:
    """Filesystem-backed workspace snapshot storage. Thread-safe (reads/writes are atomic via Path)."""

    def __init__(self, base_dir: str = "/tmp/eclusa/snapshots") -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, session_id: str) -> Path:
        return self._base / f"{session_id}.json"

    def save_snapshot(self, session_id: str, data: list[dict]) -> str:
        """Serialize message history to disk. Returns the path written."""
        path = self._path(session_id)
        path.write_text(json.dumps(data), encoding="utf-8")
        logger.debug("Snapshot saved: %s", path)
        return str(path)

    def load_snapshot(self, session_id: str) -> list[dict]:
        """Load message history from disk. Raises FileNotFoundError if absent."""
        path = self._path(session_id)
        return json.loads(path.read_text(encoding="utf-8"))

    def snapshot_exists(self, session_id: str) -> bool:
        return self._path(session_id).exists()
