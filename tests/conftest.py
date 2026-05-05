from __future__ import annotations

import importlib
import warnings
from collections.abc import Callable
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).resolve().parent
FIXTURE_SRC_DIR = TESTS_DIR / "fixtures" / "src"
FIXTURE_BIN_DIR = TESTS_DIR / "fixtures" / "bin"

# ---------------------------------------------------------------------------
# pwntools availability check
# ---------------------------------------------------------------------------
_PWN_AVAILABLE = importlib.util.find_spec("pwn") is not None


def pytest_configure(config: pytest.Config) -> None:
    """Register the ``requires_pwn`` marker and warn early if pwn is missing."""
    config.addinivalue_line(
        "markers",
        "requires_pwn: mark test as requiring pwntools (pwn)",
    )
    if not _PWN_AVAILABLE:
        warnings.warn(
            "pwntools (pwn) is NOT installed. "
            "All tests guarded by `pytest.importorskip('pwn')` will be silently skipped. "
            "Install pwntools to run the full test suite.",
            stacklevel=1,
        )


def pytest_terminal_summary(
    terminalreporter: "pytest.TerminalReporter",
    exitstatus: int,
    config: pytest.Config,
) -> None:
    """Emit a loud warning when a large fraction of tests were skipped due to
    missing *pwn* (pwntools).  This prevents CI from appearing green while the
    important end-to-end / contract tests never actually ran.
    """
    skipped_stats = terminalreporter.stats.get("skipped", [])
    pwn_skipped = 0
    for report in skipped_stats:
        # report.longrepr is a tuple (file, lineno, reason) for skips
        if hasattr(report, "longrepr") and isinstance(report.longrepr, tuple):
            reason = report.longrepr[2] if len(report.longrepr) > 2 else ""
            if "pwn" in reason.lower():
                pwn_skipped += 1

    total = terminalreporter._numcollected  # type: ignore[attr-defined]
    if total and pwn_skipped > 0:
        pct = pwn_skipped / total * 100
        msg = (
            f"\n*** WARNING: {pwn_skipped}/{total} tests ({pct:.0f}%) were "
            f"skipped because pwntools (pwn) is not installed. ***"
        )
        terminalreporter.write_line(msg, yellow=True)
        if pct > 50:
            terminalreporter.write_line(
                "*** More than 50% of the test suite was skipped! "
                "CI results are NOT trustworthy without pwntools. ***",
                red=True,
            )
            if config.getoption("--strict-markers", default=False):
                raise pytest.UsageError(
                    "Aborting: >50% of tests skipped due to missing pwntools."
                )


@pytest.fixture(scope="session")
def fixture_src_dir() -> Path:
    return FIXTURE_SRC_DIR


@pytest.fixture(scope="session")
def fixture_bin_dir() -> Path:
    return FIXTURE_BIN_DIR


@pytest.fixture(scope="session")
def fixture_binary() -> Callable[[str], Path]:
    def _resolve(name: str) -> Path:
        candidates = (FIXTURE_BIN_DIR / name, FIXTURE_BIN_DIR / f"{name}.elf")
        for candidate in candidates:
            if candidate.exists():
                return candidate

        pytest.skip(
            "Missing compiled fixture binary. Build fixtures on Linux with "
            "scripts/build_fixtures.sh"
        )

    return _resolve
