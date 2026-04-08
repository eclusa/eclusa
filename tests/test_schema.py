"""Test schema correctness — table existence, column presence, extension availability, indexes."""

import pytest

EXPECTED_TABLES = [
    # 9 domain entities
    "intent",
    "actor",
    "cascade",
    "stage",
    "work_session",
    "judgment_pass",
    "fan_out",
    "artifact",
    "ledger_entry",
    # tool (10th domain entity)
    "tool",
    # 4 knowledge graph tables
    "episode",
    "entity",
    "fact",
    "community",
]

EXPECTED_ENUMS = [
    "intent_source",
    "actor_type",
    "cascade_state",
    "stage_type",
    "stage_state",
    "work_session_state",
    "artifact_type",
    "fan_out_verdict",
    "ledger_type",
]

VECTOR_COLUMNS = [
    ("intent", "embedding"),
    ("cascade", "embedding"),
    ("entity", "embedding"),
    ("fact", "embedding"),
]


@pytest.mark.asyncio
async def test_all_tables_exist(conn):
    """After migration runs, all 13 tables must exist in public schema."""
    result = await conn.fetch(
        """
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
        ORDER BY table_name
        """
    )
    table_names = {row["table_name"] for row in result}
    missing = set(EXPECTED_TABLES) - table_names
    assert not missing, f"Missing tables: {missing}"
    assert len(table_names) >= 13, (
        f"Expected ≥13 tables, got {len(table_names)}: {table_names}"
    )


# Alias for backwards compatibility
test_all_13_tables_exist = test_all_tables_exist


@pytest.mark.asyncio
async def test_all_enum_types_exist(conn):
    """All 9 enum types must be created."""
    result = await conn.fetch(
        "SELECT typname FROM pg_type WHERE typtype = 'e' ORDER BY typname"
    )
    enum_names = {row["typname"] for row in result}
    missing = set(EXPECTED_ENUMS) - enum_names
    assert not missing, f"Missing enum types: {missing}"


@pytest.mark.asyncio
async def test_ledger_type_enum_has_gate_values(conn):
    """ledger_type enum must include all values required for self-calibration metrics."""
    result = await conn.fetch(
        """
        SELECT enumlabel FROM pg_enum
        JOIN pg_type ON pg_type.oid = pg_enum.enumtypid
        WHERE pg_type.typname = 'ledger_type'
        """
    )
    values = {row["enumlabel"] for row in result}
    # PITFALL 6: these values are required for the 8 self-calibration metrics
    required_metric_values = {
        "gate_surfaced",
        "gate_resolved",
        "gate_auto_resolved",
        "cascade_reopened",
        "orchestrator_absorbed",
    }
    missing = required_metric_values - values
    assert not missing, f"ledger_type enum missing metric values: {missing}"


# Alias for backwards compatibility
test_ledger_type_enum_includes_metric_values = test_ledger_type_enum_has_gate_values


@pytest.mark.asyncio
async def test_pgvector_extension(conn):
    """pgvector extension must be installed."""
    result = await conn.fetchval(
        "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector'"
    )
    assert result == 1, "pgvector (vector) extension not installed"


@pytest.mark.asyncio
async def test_hnsw_indexes_on_vector_columns(conn):
    """HNSW indexes must exist on all 4 vector(1024) columns."""
    for table, column in VECTOR_COLUMNS:
        result = await conn.fetch(
            "SELECT indexname FROM pg_indexes WHERE indexdef LIKE '%hnsw%' AND tablename = $1",
            table,
        )
        assert len(result) >= 1, f"Missing HNSW index for {table}.{column}"


# Alias for backwards compatibility
test_hnsw_indexes_exist = test_hnsw_indexes_on_vector_columns


@pytest.mark.asyncio
async def test_pg_search_extension(conn):
    """pg_search extension must be installed."""
    result = await conn.fetchval(
        "SELECT COUNT(*) FROM pg_extension WHERE extname = 'pg_search'"
    )
    assert result == 1, "pg_search extension not installed"


@pytest.mark.asyncio
async def test_extensions_installed(conn):
    """Both pgvector and pg_search extensions must be installed (combined check)."""
    result = await conn.fetch(
        "SELECT extname FROM pg_extension WHERE extname IN ('vector', 'pg_search')"
    )
    installed = {row["extname"] for row in result}
    assert "vector" in installed, "pgvector extension not installed"
    assert "pg_search" in installed, "pg_search extension not installed"


@pytest.mark.asyncio
async def test_single_db_all_tables(conn):
    """INFRA-02: Single DB instance — all tables are present in the same connection.

    Queries all expected table counts in a single query to assert single-DB containment.
    """
    result = await conn.fetch(
        """
        SELECT table_name, (SELECT COUNT(*) FROM information_schema.columns c2
            WHERE c2.table_name = t.table_name AND c2.table_schema = 'public') AS col_count
        FROM information_schema.tables t
        WHERE table_schema = 'public'
          AND table_type = 'BASE TABLE'
          AND table_name = ANY($1)
        ORDER BY table_name
        """,
        EXPECTED_TABLES,
    )
    found = {row["table_name"] for row in result}
    missing = set(EXPECTED_TABLES) - found
    assert not missing, f"Single-connection check failed — missing tables: {missing}"
    assert len(found) == len(EXPECTED_TABLES), (
        f"Expected {len(EXPECTED_TABLES)} tables, found {len(found)}: {found}"
    )


@pytest.mark.asyncio
async def test_ledger_entry_schema_version_column(conn):
    """ledger_entry.schema_version must exist with NOT NULL constraint."""
    result = await conn.fetchrow(
        """
        SELECT column_name, is_nullable, column_default
        FROM information_schema.columns
        WHERE table_name = 'ledger_entry'
          AND column_name = 'schema_version'
        """
    )
    assert result is not None, "ledger_entry.schema_version column does not exist"
    assert result["is_nullable"] == "NO", "ledger_entry.schema_version must be NOT NULL"
    assert result["column_default"] is not None, (
        "ledger_entry.schema_version must have a DEFAULT"
    )


@pytest.mark.asyncio
async def test_bm25_index_exists(conn):
    """BM25 index must exist on entity.name + entity.summary columns."""
    result = await conn.fetch(
        """
        SELECT indexname, indexdef FROM pg_indexes
        WHERE tablename = 'entity'
          AND indexdef ILIKE '%bm25%'
        """
    )
    assert len(result) >= 1, "Expected BM25 index on entity table, got none"


@pytest.mark.asyncio
async def test_fact_table_bitemporal_columns(conn):
    """fact table must have all 4 bi-temporal timestamp columns per D-10."""
    result = await conn.fetch(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_name = 'fact'
          AND column_name IN ('t_valid', 't_invalid', 't_created', 't_expired')
        """
    )
    cols = {row["column_name"] for row in result}
    assert "t_valid" in cols, "fact.t_valid column missing"
    assert "t_invalid" in cols, "fact.t_invalid column missing"
    assert "t_created" in cols, "fact.t_created column missing"
    assert "t_expired" in cols, "fact.t_expired column missing"
