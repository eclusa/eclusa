"""SCC-E2E-02: GHC sidecar container verifies Haskell constraints correctly.

Proves:
  - Well-typed Haskell passes GHC verification (returncode 0)
  - Ill-typed Haskell returns actionable GHC type error messages
  - Syntax errors are detected and reported
  - Prelude-only constraints (the SCC pattern) pass without external deps

Approach: Uses `docker cp` + `docker exec` directly against the live ghc-sidecar
container to prove the sidecar itself works. The verify_with_ghc Python function
is unit-tested elsewhere (tests/test_formalize.py); this E2E test exercises the
actual GHC 9.10.1 container end-to-end.
"""

import asyncio
import os
import subprocess
import tempfile
from pathlib import Path

import pytest

pytestmark = pytest.mark.asyncio

GHC_CONTAINER = "ghc-sidecar"
GHC_TIMEOUT = 10


def _ghc_sidecar_available() -> bool:
    """Check whether the ghc-sidecar container is running."""
    result = subprocess.run(
        ["docker", "inspect", "--format", "{{.State.Running}}", GHC_CONTAINER],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and "true" in result.stdout


if not _ghc_sidecar_available():
    pytestmark = [pytestmark, pytest.mark.skip("ghc-sidecar container not running")]


async def run_ghc_check(haskell_source: str, tag: str = "check") -> tuple[bool, str]:
    """Write Haskell source to a temp file, copy into ghc-sidecar, type-check.

    Args:
        haskell_source: The Haskell source code to verify.
        tag: A unique tag for the temp filename to avoid collisions.

    Returns:
        (success, output) where success is True if GHC returncode == 0.
    """
    filename = f"check_{tag}_{os.getpid()}.hs"
    container_path = f"/workspace/{filename}"

    # Write source to a local temp file
    fd, local_path = tempfile.mkstemp(suffix=".hs", prefix=f"ghc_{tag}_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(haskell_source)

        # Copy into the container
        cp_proc = await asyncio.create_subprocess_exec(
            "docker", "cp", local_path, f"{GHC_CONTAINER}:{container_path}",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await cp_proc.communicate()
        assert cp_proc.returncode == 0, "docker cp failed"

        # Run GHC type-check inside the container
        ghc_proc = await asyncio.create_subprocess_exec(
            "docker", "exec", GHC_CONTAINER,
            "ghc", "-fno-code", container_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            stdout, stderr = await asyncio.wait_for(
                ghc_proc.communicate(), timeout=GHC_TIMEOUT
            )
        except asyncio.TimeoutError:
            try:
                ghc_proc.kill()
            except Exception:
                pass
            return False, "GHC compilation timed out"

        output = (stdout + stderr).decode("utf-8", errors="replace")

        # Cleanup inside the container
        rm_proc = await asyncio.create_subprocess_exec(
            "docker", "exec", GHC_CONTAINER, "rm", "-f", container_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await rm_proc.communicate()

        return ghc_proc.returncode == 0, output
    finally:
        Path(local_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# Test 1: Well-typed Haskell passes verification
# ---------------------------------------------------------------------------


WELLTYPED_SOURCE = """\
module WellTyped where

data UserRole = Admin | Editor | Viewer

canEdit :: UserRole -> Bool
canEdit Admin = True
canEdit Editor = True
canEdit Viewer = False

type NonEmptyString = String
"""


async def test_ghc_welltyped_constraint_passes():
    """A well-typed Haskell module should pass GHC -fno-code with no errors."""
    success, output = await run_ghc_check(WELLTYPED_SOURCE, tag="welltyped")

    assert success is True, f"Expected well-typed source to pass, got output:\n{output}"
    assert "error" not in output.lower(), (
        f"Well-typed source should produce no errors, got:\n{output}"
    )


# ---------------------------------------------------------------------------
# Test 2: Ill-typed Haskell returns actionable GHC type errors
# ---------------------------------------------------------------------------


ILLTYPED_SOURCE = """\
module IllTyped where

data Color = Red | Blue

-- Type error: applying arithmetic to a Color
badFunction :: Color -> Int
badFunction x = x + 1
"""


async def test_ghc_illtyped_constraint_returns_errors():
    """An ill-typed Haskell module should fail with actionable GHC type errors."""
    success, output = await run_ghc_check(ILLTYPED_SOURCE, tag="illtyped")

    assert success is False, "Expected ill-typed source to fail GHC verification"
    assert "error" in output.lower(), (
        f"Expected 'error' in GHC output, got:\n{output}"
    )
    # GHC should report a line number (proves actionable location info)
    assert any(char.isdigit() for char in output), (
        f"Expected line number reference in GHC output, got:\n{output}"
    )
    # Output should be substantive, not just a generic one-liner
    assert len(output.strip()) > 10, (
        f"Expected substantive error output (>10 chars), got:\n{output}"
    )


# ---------------------------------------------------------------------------
# Test 3: Syntax error returns parse error
# ---------------------------------------------------------------------------


SYNTAX_ERROR_SOURCE = """\
module BadSyntax where

data Foo =
  -- Missing constructor
"""


async def test_ghc_syntax_error_returns_parse_error():
    """A Haskell module with syntax errors should fail with parse error."""
    success, output = await run_ghc_check(SYNTAX_ERROR_SOURCE, tag="syntax")

    assert success is False, "Expected syntax-error source to fail GHC verification"
    output_lower = output.lower()
    assert "error" in output_lower or "parse error" in output_lower, (
        f"Expected 'error' or 'parse error' in GHC output, got:\n{output}"
    )


# ---------------------------------------------------------------------------
# Test 4: Prelude-only constraints pass (the SCC pattern)
# ---------------------------------------------------------------------------


PRELUDE_ONLY_SOURCE = """\
module Constraints where

-- Business constraint: order total must be positive
type OrderTotal = Int

validateTotal :: OrderTotal -> Either String OrderTotal
validateTotal n
  | n > 0     = Right n
  | otherwise = Left "Order total must be positive"

-- Type-level constraint: API endpoint must return a list
type APIResponse a = [a]

data Endpoint = Endpoint
  { path :: String
  , method :: String
  }
"""


async def test_ghc_prelude_only_no_external_deps():
    """Prelude-only Haskell constraints (the SCC pattern) should pass GHC."""
    success, output = await run_ghc_check(PRELUDE_ONLY_SOURCE, tag="prelude")

    assert success is True, (
        f"Expected Prelude-only source to pass, got output:\n{output}"
    )
    assert "Could not find module" not in output, (
        f"Expected no missing module errors, got:\n{output}"
    )
