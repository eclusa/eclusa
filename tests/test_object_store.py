"""
tests/test_object_store.py — Unit tests for ObjectStore ABC and LocalObjectStore.

TDD RED: These tests are written before the implementation exists.
Uses tmp_path pytest fixture — no DB fixture needed, pure filesystem.
"""

import pytest


class TestObjectStoreABC:
    def test_object_store_is_abstract(self):
        """ObjectStore is an ABC with abstract methods — cannot be instantiated."""
        from storage.object_store import ObjectStore

        with pytest.raises(TypeError):
            ObjectStore()  # type: ignore[abstract]

    def test_object_store_has_abstract_put(self):
        """ObjectStore has abstract put(data: bytes) -> str."""
        from storage.object_store import ObjectStore

        assert hasattr(ObjectStore, "put")

    def test_object_store_has_abstract_get(self):
        """ObjectStore has abstract get(key: str) -> bytes."""
        from storage.object_store import ObjectStore

        assert hasattr(ObjectStore, "get")

    def test_object_store_has_abstract_exists(self):
        """ObjectStore has abstract exists(key: str) -> bool."""
        from storage.object_store import ObjectStore

        assert hasattr(ObjectStore, "exists")


class TestLocalObjectStorePut:
    def test_put_returns_64_char_hex_string(self, tmp_path):
        """LocalObjectStore().put(b'hello world') returns a 64-char hex string (blake3 hash)."""
        from storage.object_store import LocalObjectStore

        store = LocalObjectStore(base_dir=str(tmp_path))
        key = store.put(b"hello world")
        assert isinstance(key, str)
        assert len(key) == 64
        assert all(c in "0123456789abcdef" for c in key)

    def test_put_writes_file_keyed_by_blake3(self, tmp_path):
        """put() writes a file using blake3 hash as the key."""
        import blake3
        from storage.object_store import LocalObjectStore

        store = LocalObjectStore(base_dir=str(tmp_path))
        data = b"test data for blake3 keying"
        key = store.put(data)

        expected_key = blake3.blake3(data).hexdigest()
        assert key == expected_key

    def test_put_stores_correct_bytes(self, tmp_path):
        """put() stores the exact bytes passed."""
        from storage.object_store import LocalObjectStore

        store = LocalObjectStore(base_dir=str(tmp_path))
        data = b"binary data \x00\x01\x02\xff"
        key = store.put(data)
        result = store.get(key)
        assert result == data

    def test_put_same_data_returns_same_key(self, tmp_path):
        """Two identical payloads produce the same key (natural deduplication, D-24)."""
        from storage.object_store import LocalObjectStore

        store = LocalObjectStore(base_dir=str(tmp_path))
        data = b"same content"
        key1 = store.put(data)
        key2 = store.put(data)
        assert key1 == key2

    def test_put_different_data_returns_different_keys(self, tmp_path):
        """Different payloads produce different keys."""
        from storage.object_store import LocalObjectStore

        store = LocalObjectStore(base_dir=str(tmp_path))
        key1 = store.put(b"content A")
        key2 = store.put(b"content B")
        assert key1 != key2


class TestLocalObjectStoreGet:
    def test_get_returns_exact_bytes(self, tmp_path):
        """get(hash) returns the exact bytes put()."""
        from storage.object_store import LocalObjectStore

        store = LocalObjectStore(base_dir=str(tmp_path))
        data = b"retrieve me"
        key = store.put(data)
        result = store.get(key)
        assert result == data

    def test_get_unknown_key_raises_file_not_found(self, tmp_path):
        """LocalObjectStore raises FileNotFoundError on get() for unknown key."""
        from storage.object_store import LocalObjectStore

        store = LocalObjectStore(base_dir=str(tmp_path))
        fake_key = "a" * 64
        with pytest.raises(FileNotFoundError):
            store.get(fake_key)

    def test_get_large_binary_data(self, tmp_path):
        """get() handles large binary payloads correctly."""
        from storage.object_store import LocalObjectStore

        store = LocalObjectStore(base_dir=str(tmp_path))
        data = bytes(range(256)) * 1000  # 256KB
        key = store.put(data)
        result = store.get(key)
        assert result == data


class TestLocalObjectStoreExists:
    def test_exists_true_after_put(self, tmp_path):
        """exists(key) returns True after put()."""
        from storage.object_store import LocalObjectStore

        store = LocalObjectStore(base_dir=str(tmp_path))
        key = store.put(b"exists check")
        assert store.exists(key) is True

    def test_exists_false_before_put(self, tmp_path):
        """exists(key) returns False for unknown key."""
        from storage.object_store import LocalObjectStore

        store = LocalObjectStore(base_dir=str(tmp_path))
        fake_key = "b" * 64
        assert store.exists(fake_key) is False


class TestLocalObjectStoreDefaultDir:
    def test_default_base_dir(self):
        """Default base_dir is './storage/objects'."""
        from storage.object_store import LocalObjectStore

        store = LocalObjectStore()
        from pathlib import Path

        assert store._base == Path("./storage/objects")

    def test_custom_base_dir(self, tmp_path):
        """Custom base_dir is used when provided."""
        from storage.object_store import LocalObjectStore

        store = LocalObjectStore(base_dir=str(tmp_path))
        assert store._base == tmp_path


class TestLocalObjectStoreSharding:
    def test_files_sharded_by_first_two_chars(self, tmp_path):
        """Files are stored under base_dir/key[:2]/key for inode efficiency."""
        from storage.object_store import LocalObjectStore

        store = LocalObjectStore(base_dir=str(tmp_path))
        data = b"sharding test"
        key = store.put(data)

        expected_path = tmp_path / key[:2] / key
        assert expected_path.exists()
        assert expected_path.read_bytes() == data


class TestLocalObjectStoreIsObjectStore:
    def test_local_object_store_implements_abc(self, tmp_path):
        """LocalObjectStore is a concrete implementation of ObjectStore ABC."""
        from storage.object_store import LocalObjectStore, ObjectStore

        store = LocalObjectStore(base_dir=str(tmp_path))
        assert isinstance(store, ObjectStore)
