from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.cli import main as cli_main


def test_cli_decompile_stage_c_outputs_parse_record_rendering(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_struct_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c", "--func", "parse_record"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "#include <stdint.h>" in output
    assert "typedef struct agg_8 {" in output
    assert "static ret_x10_x11 parse_record(agg_8* arg_x10_4, int32_t arg_x11_4) {" in output
    assert "arg_x10_4[local_24_4].field_0" in output


def test_cli_decompile_stage_c_outputs_rendered_program(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_loop_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "/* root:" in output
    assert "/* scheduled_roots: " in output
    assert "static int32_t main(void);" in output
    assert "static int32_t sum_to_n(int32_t arg_x10_4);" in output
    assert "while (local_20_4 <s arg_x10_4) {" in output
    assert "int32_t call_0x110e8_ret;" in output
    assert "call_0x110e8_ret = sum_to_n(10);" in output
    assert "return call_0x110e8_ret;" in output
    assert "ret_0x110e8_x10_4 = raw<x10_2:4>;" not in output


def test_cli_decompile_stage_c_suppresses_switch_x11_scratch_return(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_switch_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "static int32_t main(void);" in output
    assert "static int32_t dispatch(uint32_t arg_x10_4, uint32_t arg_x11_4);" in output
    assert "int32_t call_0x110ec_ret;" in output
    assert "switch (arg_x10_4) {" in output
    assert output.count("case ") == 4
    assert "default:" in output
    assert "else if (" not in output
    assert "return call_0x110ec_ret;" in output
    assert "raw<x11_1:4>" not in output


def test_cli_decompile_stage_c_strict_func_rejects_unresolved_selector(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")

    exit_code = cli_main(
        [
            "decompile",
            str(binary),
            "--stage",
            "c",
            "--func",
            "no_such_symbol",
            "--strict-func",
        ]
    )
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "decompile_error: unresolved function selector" in captured.err


def test_cli_decompile_stage_c_outputs_rendered_program_banner(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_struct_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "/* root:" in output
    assert "/* scheduled_roots: " in output
    assert "typedef struct ret_x10_x11 {" not in output
    assert "static uint32_t parse_record(agg_8* arg_x10_4, int32_t arg_x11_4);" in output
    assert "call_0x11118_ret = parse_record(&local_24_4, 2);" in output
    assert "c_lowering:" not in output


def test_cli_decompile_stage_c_exposes_named_secondary_call_returns(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_calls_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "static int32_t main(void);" in output
    assert "call_0x110fc_ret" not in output
    assert "call_0x1112c_ret" not in output
    assert "call_0x11140_ret" not in output
    assert "phi_0x11150_x11_4" not in output
    assert "local_16_4 = malloc(32);" in output
    assert "memset(local_16_4, 0, 32);" in output
    assert "puts(0x100d4);" in output
    assert "free(local_16_4);" in output
    assert "return local_12_4;" in output
    assert "ret_0x110fc_x11_4 = raw<x11_1:4>;" not in output


def test_cli_decompile_stage_c_exposes_stack_argument_fixture(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_stack_args_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "static int32_t sum10(" in output
    assert "local_0_4" in output
    assert "local_4_4" in output
    assert "call_0x11118_ret = sum10(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);" in output
    assert "return call_0x11118_ret;" in output


def test_cli_decompile_stage_c_collapses_basic_program_to_single_return(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "static int32_t main(void);" in output
    assert "static int32_t helper(int32_t arg_x10_4);" in output
    assert "int32_t local_16_4;" in output
    assert "local_16_4 = helper(local_12_4);" in output
    assert "return local_16_4 - 2;" in output
    assert "ret_0x110f0_x11_4 = raw<x11_1:4>;" not in output


def test_cli_decompile_stage_c_exposes_mixed_fixture_loop_switch_and_call(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_mixed_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "typedef struct agg_8 {" in output
    assert "static uint32_t run_steps(" in output
    assert "static uint32_t adjust_step(agg_8* arg_x10_4, int32_t arg_x11_4);" in output
    assert "call_0x11144_ret = run_steps(&local_40_4, 4, 6);" in output
    assert "while (local_28_4 <s arg_x11_4) {" in output
    assert "switch (arg_x10_4->field_0) {" in output
    assert "call_0x11144_ret = run_steps(" in output
    assert "raw<x12_1:4>" not in output


def test_cli_decompile_stage_c_uses_address_of_local_for_indirect_select(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_indirect_select_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "local_16_4 = choose_op(&local_12_4);" in output
    assert "choose_op(raw<x2_0:4>" not in output


def test_cli_decompile_stage_c_exposes_chain_fixture_call_chain(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_chain_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "static int32_t fold(int32_t arg_x10_4, uint32_t arg_x11_4);" in output
    assert "static int32_t mix(int32_t arg_x10_4, int32_t arg_x11_4);" in output
    assert "call_0x110ec_ret = fold(5, 2);" in output
    assert "while (local_24_4 <s arg_x10_4) {" in output
    assert "if (arg_x10_4 >=s arg_x11_4) {" in output


def test_cli_decompile_stage_c_exposes_switch_loop_fixture_switch(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_switch_loop_O0_nopie")

    exit_code = cli_main(["decompile", str(binary), "--stage", "c", "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "static int32_t execute(int32_t arg_x10_4);" in output
    assert "static int32_t decode(uint32_t arg_x10_4, uint32_t arg_x11_4);" in output
    assert "call_0x110e8_ret = execute(6);" in output
    assert "while (local_20_4 <s arg_x10_4) {" in output
    assert "switch (arg_x10_4) {" in output


def test_cli_decompile_defaults_to_c(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
) -> None:
    binary = fixture_binary("fixture_basic_O2_nopie")

    exit_code = cli_main(["decompile", str(binary), "--func", "main"])
    output = capsys.readouterr().out

    assert exit_code == 0
    assert "/* root:" in output
    assert "/* scheduled_roots: " in output
    assert "static" in output
    assert "stage:" not in output
