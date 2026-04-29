from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.cli import main as cli_main

def test_cli_decompile_stage_range_outputs_program_snapshot(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_switch_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "range", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "stage: range" in output
    assert "range:" in output
    assert "functions:" in output


def test_cli_decompile_stage_range_exposes_mixed_fixture_branch_refinements(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_mixed_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "range", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "function 0x11158 name=run_steps" in output
    assert "function 0x11224 name=adjust_step" in output
    assert "source=INT_SLESS" in output
    assert "source=INT_EQUAL" in output


def test_cli_decompile_stage_range_exposes_chain_fixture_branch_refinements(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_chain_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "range", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "function 0x11100 name=fold" in output
    assert "source=INT_SLESS" in output


def test_cli_decompile_stage_range_exposes_switch_loop_fixture_branch_refinements(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_switch_loop_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "range", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "function 0x110fc name=execute" in output
    assert "function 0x111b4 name=decode" in output
    assert "source=INT_SLESS" in output
    assert "source=INT_EQUAL" in output


def test_cli_decompile_defaults_to_c(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_basic_O2_nopie")

    exit_code = cli_main(["decompile", str(binary), "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "/* root:" in output
    assert "static" in output
