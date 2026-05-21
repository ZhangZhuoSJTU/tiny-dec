from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.cli import main as cli_main

def test_cli_decompile_stage_ssa_outputs_program_snapshot(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_switch_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "ssa", "--func", "dispatch"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "stage: ssa" in output
    assert "ssa:" in output
    assert "functions:" in output


def test_cli_decompile_defaults_to_c(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_loop_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--func", "sum_to_n"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "/* root:" in output
    assert "static" in output
