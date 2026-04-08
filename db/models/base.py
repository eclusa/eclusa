import uuid
from ulid import ULID
from sqlalchemy.orm import DeclarativeBase


def new_id() -> uuid.UUID:
    """Generate a ULID as UUID — sortable by creation time, stored as native UUID type.
    Per D-01 (ULID) and D-02 (UUID type for index efficiency)."""
    return ULID().to_uuid()


class Base(DeclarativeBase):
    pass
