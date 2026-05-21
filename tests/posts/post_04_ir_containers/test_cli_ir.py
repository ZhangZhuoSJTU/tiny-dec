from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.cli import main as cli_main

def test_cli_decompile_stage_ir_outputs_program_snapshot(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "ir", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "stage: ir" in output
    assert "ir:" in output
    assert "call_graph:" in output
