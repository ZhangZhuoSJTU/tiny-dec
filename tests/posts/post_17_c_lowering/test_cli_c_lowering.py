from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.cli import main as cli_main


def test_cli_decompile_stage_c_lowering_outputs_parse_record_snapshot(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_struct_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c_lowering", "--func", "parse_record"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "stage: c_lowering" in output
    assert "target_function: parse_record" in output
    assert "c_lowering:" in output
    assert "arg_x10_4[local_24_4].field_0" in output


def test_cli_decompile_stage_c_lowering_outputs_program_snapshot(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_loop_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c_lowering", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "stage: c_lowering" in output
    assert "c_lowering:" in output
    assert "param x11 int32_t arg_x11_4" not in output
    assert "return x11 int32_t" not in output
    assert "while (local_20_4 <s arg_x10_4)" in output


def test_cli_decompile_stage_c_lowering_suppresses_switch_x11_scratch_return(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_switch_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c_lowering", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "function 0x11100 name=dispatch" in output
    assert "switch (arg_x10_4)" in output
    assert output.count("case ") == 4
    assert "default:" in output
    assert "if (arg_x10_4 == 0)" not in output
    assert "return x11 int32_t" not in output
    assert "return [x10=local_12_4];" in output
    assert "raw<x11_1:4>" not in output


def test_cli_decompile_stage_c_lowering_exposes_folded_call_result_assignment(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_calls_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c_lowering", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "local_16_4 = malloc(32);" in output
    assert "local_16_4 = raw<x10_2:4>;" not in output
    assert "ret_0x110fc_x11_4 = raw<x11_1:4>;" not in output
    assert "ret_0x1112c_x11_4 = raw<x11_3:4>;" not in output
    assert "memset(local_16_4, 0, 32);" in output
    assert "puts(0x100d4);" in output
    assert "free(local_16_4);" in output
    assert "return [x10=local_12_4];" in output


def test_cli_decompile_stage_c_lowering_exposes_stack_argument_fixture(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_stack_args_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c_lowering", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "name=sum10" in output
    assert "param stack+0" in output
    assert "param stack+4" in output
    assert "sum10(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);" in output


def test_cli_decompile_stage_c_lowering_collapses_basic_program_to_single_return(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c_lowering", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "local_16_4 = helper(local_12_4);" in output
    assert "local word32_t ret_0x110f0_x11_4" not in output
    assert "ret_0x110f0_x11_4 = raw<x11_1:4>;" not in output
    assert "return [x10=local_16_4 - 2];" in output


def test_cli_decompile_stage_c_lowering_exposes_mixed_fixture_loop_switch_and_call(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_mixed_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c_lowering", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "function 0x11158 name=run_steps" in output
    assert "function 0x11224 name=adjust_step" in output
    assert "run_steps(&local_40_4, 4, 6);" in output
    assert "while (local_28_4 <s arg_x11_4)" in output
    assert "switch (arg_x10_4->field_0)" in output
    assert "adjust_step(" in output
    assert "raw<x12_1:4>" not in output


def test_cli_decompile_stage_c_lowering_exposes_chain_fixture_call_chain(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_chain_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c_lowering", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "function 0x11100 name=fold" in output
    assert "function 0x111b4 name=mix" in output
    assert "while (local_24_4 <s arg_x10_4)" in output
    assert "if (arg_x10_4 >=s arg_x11_4)" in output
    assert "bump(" in output


def test_cli_decompile_stage_c_lowering_exposes_switch_loop_fixture_switch(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_switch_loop_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c_lowering", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "function 0x110fc name=execute" in output
    assert "function 0x111b4 name=decode" in output
    assert "while (local_20_4 <s arg_x10_4)" in output
    assert "switch (arg_x10_4)" in output


def test_cli_decompile_stage_c_lowering_strict_func_rejects_unresolved_selector(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")

    exit_code = cli_main(
        [
            "decompile",
            str(binary),
            "--stage",
            "c_lowering",
            "--func",
            "no_such_symbol",
            "--strict-func",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "decompile_error: unresolved function selector" in captured.err


def test_cli_decompile_stage_c_lowering_outputs_program_banner(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_struct_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c_lowering", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "stage: c_lowering" in output
    assert "c_lowering:" in output
    assert "functions:" in output
    assert "parse_record(&local_24_4, 2);" in output


def test_cli_decompile_stage_c_lowering_uses_address_of_local_for_indirect_select(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_indirect_select_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c_lowering", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "local_16_4 = choose_op(&local_12_4);" in output
    assert "choose_op(raw<x2_0:4>" not in output


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
