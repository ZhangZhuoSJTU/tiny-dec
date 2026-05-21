from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.cli import main as cli_main


def test_cli_decompile_stage_calls_outputs_program_snapshot(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_calls_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "calls", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "stage: calls" in output
    assert "calls:" in output
    assert "functions:" in output
    assert "call_graph:" in output
    assert "mem=[" in output
    assert "returns=[" in output


def test_cli_decompile_stage_calls_omits_saved_register_slots_from_stack_args_fixture(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_stack_args_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "calls", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "stack_args=[stack+0=" in output
    assert "stack+4=" in output
    assert "stack+8=" not in output
    assert "stack+12=" not in output


def test_cli_decompile_stage_calls_strict_func_rejects_unresolved_selector(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")

    exit_code = cli_main(
        [
            "decompile",
            str(binary),
            "--stage",
            "calls",
            "--func",
            "no_such_symbol",
            "--strict-func",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "decompile_error: unresolved function selector" in captured.err


def test_cli_decompile_defaults_to_c(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "/* root:" in output
    assert "static" in output
