"""
storage/object_store.py — Content-addressed object storage for Eclusa.

Decisions:
- D-23: Local filesystem storage under ./storage/ with abstract interface
- D-24: Files keyed by content hash (blake3) for natural deduplication
- D-25: Extends the pattern from harness/snapshot.py (SnapshotStore) to general object storage

Note: SnapshotStore (harness/snapshot.py) is keyed by session_id (UUID).
      ObjectStore is keyed by content hash (blake3). Different problems — do not merge.
"""

from abc import ABC, abstractmethod
from pathlib import Path

import blake3


class ObjectStore(ABC):
    """Abstract base class for content-addressed object storage."""

    @abstractmethod
    def put(self, data: bytes) -> str:
        """Store data and return its content-hash key (blake3 hexdigest)."""
        ...

    @abstractmethod
    def get(self, key: str) -> bytes:
        """Retrieve data by its content-hash key. Raises FileNotFoundError if absent."""
        ...

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if a blob with the given key exists, False otherwise."""
        ...


class LocalObjectStore(ObjectStore):
    """
    Filesystem-backed object storage keyed by blake3 content hash.

    Files are stored at base_dir/key[:2]/key — sharding by first 2 hex chars
    keeps individual directory sizes manageable (256 shards max).
    """

    def __init__(self, base_dir: str = "./storage/objects") -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        """Return the shard path for a given key."""
        return self._base / key[:2] / key

    def put(self, data: bytes) -> str:
        """
        Store data bytes. Returns the blake3 hexdigest (64-char hex string).

        Idempotent: re-storing the same content is a no-op (same path written again).
        Natural deduplication: same bytes always produce the same key (D-24).
        """
        key = blake3.blake3(data).hexdigest()
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        """
        Retrieve bytes by content-hash key.

        Raises:
            FileNotFoundError: if no object with this key exists.
        """
        path = self._path(key)
        if not path.exists():
            raise FileNotFoundError(f"Object not found: {key}")
        return path.read_bytes()

    def exists(self, key: str) -> bool:
        """Return True if a blob with the given key exists."""
        return self._path(key).exists()
