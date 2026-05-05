from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.cli import main as cli_main


def test_cli_decompile_stage_pcode_outputs_lifted_window(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "pcode", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "stage: pcode" in output
    assert "pcode:" in output
    assert "INT_ADD register[0x2:4]" in output


def test_cli_decompile_stage_pcode_strict_func_rejects_unresolved_selector(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")

    exit_code = cli_main(
        [
            "decompile",
            str(binary),
            "--stage",
            "pcode",
            "--func",
            "no_such_symbol",
            "--strict-func",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "decompile_error: unresolved function selector" in captured.err
