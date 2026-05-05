from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.cli import main as cli_main


def test_cli_decompile_stage_interproc_outputs_program_snapshot(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_loop_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "interproc", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "stage: interproc" in output
    assert "interproc:" in output
    assert "functions:" in output
    assert "function 0x110fc name=sum_to_n" in output
    assert "param x10:4 type=int:4 name=arg_x10_4" in output
    assert "param x11:4 type=int:4 name=arg_x11_4" not in output
    assert "return x11:4 type=int:4" not in output


def test_cli_decompile_stage_interproc_prunes_spurious_external_x11_return(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_calls_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "interproc", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "return x10:4" in output
    assert "return x11:4" not in output


def test_cli_decompile_stage_interproc_exposes_stack_parameters(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_stack_args_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "interproc", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "name=sum10" in output
    assert "param x17:4" in output
    assert "stack+0:4" in output
    assert "name=local_0_4" in output
    assert "stack+4:4" in output
    assert "name=local_4_4" in output


def test_cli_decompile_stage_interproc_prunes_observed_only_mixed_adjust_step_x12_parameter(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_mixed_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "interproc", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "function 0x11224 name=adjust_step" in output
    assert "function 0x11158 name=run_steps" in output
    assert "param x12:4 type=int:4 name=arg_x12_4" in output

    adjust_step_section = output.split("function 0x11224 name=adjust_step", maxsplit=1)[1]

    assert "param x10:4 type=pointer:4 name=arg_x10_4" in adjust_step_section
    assert "param x11:4 type=int:4 name=arg_x11_4" in adjust_step_section
    assert "param x12:4 type=int:4 name=arg_x12_4" not in adjust_step_section


def test_cli_decompile_stage_interproc_strict_func_rejects_unresolved_selector(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")

    exit_code = cli_main(
        [
            "decompile",
            str(binary),
            "--stage",
            "interproc",
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
    binary = fixture_binary("fixture_basic_O2_nopie")

    exit_code = cli_main(["decompile", str(binary), "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "/* root:" in output
    assert "static" in output
