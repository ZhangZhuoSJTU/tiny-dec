from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.cli import main as cli_main

def test_cli_decompile_stage_stack_outputs_program_snapshot(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_struct_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "stack", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "stage: stack" in output
    assert "stack:" in output
    assert "functions:" in output


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
