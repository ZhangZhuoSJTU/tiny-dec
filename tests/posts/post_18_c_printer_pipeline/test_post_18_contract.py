from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.c_emit import build_program_c_rendered, format_program_c_rendered
from tiny_dec.loader import ProgramView


def test_build_program_c_rendered_is_stable_for_loop_fixture(
    fixture_binary: Callable[[str], Path],
) -> None:
    view = ProgramView(fixture_binary("fixture_loop_O0_nopie"))
    entry = view.find_main().address
    sum_to_n = view.get_symbol_address("sum_to_n")
    assert entry is not None
    assert sum_to_n is not None

    first = format_program_c_rendered(build_program_c_rendered(view, entry))
    second = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert first == second
    assert "typedef struct ret_x10_x11 {" not in first
    assert "static int32_t main(void);" in first
    assert "static int32_t sum_to_n(int32_t arg_x10_4);" in first
    assert "while (local_20_4 <s arg_x10_4) {" in first
    assert "int32_t call_0x110e8_ret;" in first
    assert "call_0x110e8_ret = sum_to_n(10);" in first
    assert "return call_0x110e8_ret;" in first
    assert "ret_0x110e8_x10_4 = raw<x10_2:4>;" not in first
    assert "ret_0x110e8_x11_4 = raw<x11_1:4>;" not in first
    assert "return local_16_4;" in first


def test_build_program_c_rendered_is_stable_for_struct_fixture(
    fixture_binary: Callable[[str], Path],
) -> None:
    view = ProgramView(fixture_binary("fixture_struct_O0_nopie"))
    entry = view.find_main().address
    parse_record = view.get_symbol_address("parse_record")
    assert entry is not None
    assert parse_record is not None

    first = format_program_c_rendered(build_program_c_rendered(view, entry))
    second = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert first == second
    assert "typedef struct agg_8 {" in first
    assert "static uint32_t parse_record(agg_8* arg_x10_4, int32_t arg_x11_4);" in first
    assert "call_0x11118_ret = parse_record(&local_24_4, 2);" in first
    assert "arg_x10_4[local_24_4].field_4" in first
    assert "return local_20_4;" in first


def test_build_program_c_rendered_is_stable_for_switch_fixture(
    fixture_binary: Callable[[str], Path],
) -> None:
    view = ProgramView(fixture_binary("fixture_switch_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_c_rendered(build_program_c_rendered(view, entry))
    second = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert first == second
    assert "static int32_t main(void);" in first
    assert "static int32_t dispatch(uint32_t arg_x10_4, uint32_t arg_x11_4);" in first
    assert "int32_t call_0x110ec_ret;" in first
    assert "call_0x110ec_ret = dispatch(2, 9);" in first
    assert "switch (arg_x10_4) {" in first
    assert first.count("case ") == 4
    assert "default:" in first
    assert "else if (" not in first
    assert "return call_0x110ec_ret;" in first
    assert "raw<x11_1:4>" not in first


def test_build_program_c_rendered_is_stable_for_calls_fixture(
    fixture_binary: Callable[[str], Path],
) -> None:
    view = ProgramView(fixture_binary("fixture_calls_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_c_rendered(build_program_c_rendered(view, entry))
    second = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert first == second
    assert "static int32_t main(void);" in first
    assert "call_0x110fc_ret" not in first
    assert "call_0x1112c_ret" not in first
    assert "call_0x11138_ret" not in first
    assert "call_0x11140_ret" not in first
    assert "phi_0x11150_x11_4" not in first
    assert "local_16_4 = malloc(32);" in first
    assert "memset(local_16_4, 0, 32);" in first
    assert "puts(0x100d4);" in first
    assert "free(local_16_4);" in first
    assert "ret_0x110fc_x11_4 = raw<x11_1:4>;" not in first
    assert "return local_12_4;" in first


def test_build_program_c_rendered_is_stable_for_basic_fixture(
    fixture_binary: Callable[[str], Path],
) -> None:
    view = ProgramView(fixture_binary("fixture_basic_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_c_rendered(build_program_c_rendered(view, entry))
    second = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert first == second
    assert "static int32_t main(void);" in first
    assert "static int32_t helper(int32_t arg_x10_4);" in first
    assert "int32_t local_16_4;" in first
    assert "local_16_4 = helper(local_12_4);" in first
    assert "return local_16_4 - 2;" in first
    assert "return (arg_x10_4 << 1) + arg_x10_4 + 1;" in first
    assert "ret_0x110f0_x11_4 = raw<x11_1:4>;" not in first


def test_build_program_c_rendered_is_stable_for_mixed_fixture(
    fixture_binary: Callable[[str], Path],
) -> None:
    view = ProgramView(fixture_binary("fixture_mixed_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_c_rendered(build_program_c_rendered(view, entry))
    second = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert first == second
    assert "typedef struct agg_8 {" in first
    assert "static uint32_t run_steps(" in first
    assert "static uint32_t adjust_step(agg_8* arg_x10_4, int32_t arg_x11_4);" in first
    assert "call_0x11144_ret = run_steps(&local_40_4, 4, 6);" in first
    assert "while (local_28_4 <s arg_x11_4) {" in first
    assert "switch (arg_x10_4->field_0) {" in first
    assert "call_0x11144_ret = run_steps(" in first
    assert "raw<x12_1:4>" not in first


def test_build_program_c_rendered_is_stable_for_chain_fixture(
    fixture_binary: Callable[[str], Path],
) -> None:
    view = ProgramView(fixture_binary("fixture_chain_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_c_rendered(build_program_c_rendered(view, entry))
    second = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert first == second
    assert "static int32_t fold(int32_t arg_x10_4, uint32_t arg_x11_4);" in first
    assert "static int32_t mix(int32_t arg_x10_4, int32_t arg_x11_4);" in first
    assert "while (local_24_4 <s arg_x10_4) {" in first
    assert "call_0x110ec_ret = fold(5, 2);" in first


def test_build_program_c_rendered_is_stable_for_switch_loop_fixture(
    fixture_binary: Callable[[str], Path],
) -> None:
    view = ProgramView(fixture_binary("fixture_switch_loop_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_c_rendered(build_program_c_rendered(view, entry))
    second = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert first == second
    assert "static int32_t execute(int32_t arg_x10_4);" in first
    assert "static int32_t decode(uint32_t arg_x10_4, uint32_t arg_x11_4);" in first
    assert "while (local_20_4 <s arg_x10_4) {" in first
    assert "switch (arg_x10_4) {" in first
    assert "call_0x110e8_ret = execute(6);" in first


def test_build_program_c_rendered_is_stable_for_nested_fixture(
    fixture_binary: Callable[[str], Path],
) -> None:
    view = ProgramView(fixture_binary("fixture_nested_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_c_rendered(build_program_c_rendered(view, entry))
    second = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert first == second
    assert "static int32_t sweep(uint32_t arg_x10_4, int32_t arg_x11_4);" in first
    assert "static int32_t tweak(int32_t arg_x10_4, int32_t arg_x11_4, uint32_t arg_x12_4);" in first
    assert "call_0x110ec_ret = sweep(3, 4);" in first
    assert first.count("while (") >= 2


def test_build_program_c_rendered_is_stable_for_indirect_const_fixture(
    fixture_binary: Callable[[str], Path],
) -> None:
    view = ProgramView(fixture_binary("fixture_indirect_const_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_c_rendered(build_program_c_rendered(view, entry))
    second = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert first == second
    assert "typedef struct ret_x10_x11 {" in first
    assert "static ret_x10_x11 main(void);" in first
    assert "local_12_4 = 0x1110c;" in first
    assert "call_0x110f8_ret = call_indirect(local_12_4, 7);" in first
    assert "call_0x110f8_ret = call_indirect(7, local_12_4);" not in first


def test_build_program_c_rendered_is_stable_for_indirect_select_fixture(
    fixture_binary: Callable[[str], Path],
) -> None:
    view = ProgramView(fixture_binary("fixture_indirect_select_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_c_rendered(build_program_c_rendered(view, entry))
    second = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert first == second
    assert "static uint32_t choose_op(agg_4* arg_x10_4);" in first
    assert "local_16_4 = choose_op(&local_12_4);" in first
    assert "choose_op(raw<x2_0:4>" not in first
    assert "call_0x11108_ret = call_indirect(local_16_4, local_12_4 + 2, 9" in first
    assert "call_0x11108_ret = call_indirect(local_12_4 + 2, 9, local_16_4" not in first
