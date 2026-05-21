from __future__ import annotations

import pytest

pytest.importorskip("pwn")

from tiny_dec.c_emit import build_program_c_lowered, format_program_c_lowered
from tiny_dec.loader import ProgramView


def test_build_program_c_lowered_is_stable_for_loop_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_loop_O0_nopie"))
    entry = view.find_main().address
    sum_to_n = view.get_symbol_address("sum_to_n")
    assert entry is not None
    assert sum_to_n is not None

    first = format_program_c_lowered(build_program_c_lowered(view, entry))
    second = format_program_c_lowered(build_program_c_lowered(view, entry))
    program = build_program_c_lowered(view, entry)
    facts = program.functions[sum_to_n]

    assert first == second
    assert facts.statement_count >= 6
    assert "param x10 int32_t arg_x10_4" in first
    assert "param x11 int32_t arg_x11_4" not in first
    assert "local int32_t local_16_4" in first
    assert "while (local_20_4 <s arg_x10_4)" in first
    assert "return x10 int32_t" in first
    assert "return x11 int32_t" not in first
    assert "return [x10=local_16_4];" in first


def test_build_program_c_lowered_is_stable_for_struct_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_struct_O0_nopie"))
    entry = view.find_main().address
    parse_record = view.get_symbol_address("parse_record")
    assert entry is not None
    assert parse_record is not None

    first = format_program_c_lowered(build_program_c_lowered(view, entry))
    second = format_program_c_lowered(build_program_c_lowered(view, entry))
    program = build_program_c_lowered(view, entry)
    facts = program.functions[parse_record]

    assert first == second
    assert facts.statement_count >= 5
    assert "param x10 agg_8* arg_x10_4" in first
    assert "parse_record(&local_24_4, 2);" in first
    assert "arg_x10_4[local_24_4].field_0" in first
    assert "arg_x10_4[local_24_4].field_4" in first
    assert "return x10 word32_t" in first
    assert "return x11 int32_t" not in first
    assert "return [x10=local_20_4];" in first


def test_build_program_c_lowered_is_stable_for_switch_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_switch_O0_nopie"))
    entry = view.find_main().address
    dispatch = view.get_symbol_address("dispatch")
    assert entry is not None
    assert dispatch is not None

    first = format_program_c_lowered(build_program_c_lowered(view, entry))
    second = format_program_c_lowered(build_program_c_lowered(view, entry))
    program = build_program_c_lowered(view, entry)
    facts = program.functions[dispatch]

    assert first == second
    assert facts.statement_count >= 8
    assert tuple(returned.register for returned in facts.returns) == (10,)
    assert "function 0x11100 name=dispatch" in first
    assert "switch (arg_x10_4)" in first
    assert first.count("case ") == 4
    assert "default:" in first
    assert "if (arg_x10_4 == 0)" not in first
    assert "return x10 int32_t" in first
    assert "return x11 int32_t" not in first
    assert "return [x10=local_12_4];" in first
    assert "raw<x11_1:4>" not in first


def test_build_program_c_lowered_is_stable_for_calls_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_calls_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_c_lowered(build_program_c_lowered(view, entry))
    second = format_program_c_lowered(build_program_c_lowered(view, entry))
    program = build_program_c_lowered(view, entry)
    facts = program.functions[entry]

    assert first == second
    assert facts.statement_count >= 8
    assert "param x12 int32_t arg_x12_4" not in first
    assert "local_16_4 = malloc(32);" in first
    assert "local_16_4 = raw<x10_2:4>;" not in first
    assert "local word32_t ret_0x110fc_x11_4" not in first
    assert "local word32_t ret_0x1112c_x11_4" not in first
    assert "local word32_t ret_0x11138_x11_4" not in first
    assert "local word32_t ret_0x11140_x11_4" not in first
    assert "local word32_t phi_0x11150_x11_4" not in first
    assert "memset(local_16_4, 0, 32);" in first
    assert "puts(0x100d4);" in first
    assert "free(local_16_4);" in first
    assert "return [x10=local_12_4];" in first


def test_build_program_c_lowered_is_stable_for_basic_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_basic_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_c_lowered(build_program_c_lowered(view, entry))
    second = format_program_c_lowered(build_program_c_lowered(view, entry))

    assert first == second
    assert "return x10 int32_t" in first
    assert "return x11 int32_t" not in first
    assert "local int32_t local_16_4" in first
    assert "local word32_t ret_0x110f0_x11_4" not in first
    assert "ret_0x110f0_x11_4 = raw<x11_1:4>;" not in first
    assert "return [x10=local_16_4 - 2];" in first
    assert "return [x10=(arg_x10_4 << 1) + arg_x10_4 + 1];" in first


def test_build_program_c_lowered_is_stable_for_mixed_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_mixed_O0_nopie"))
    entry = view.find_main().address
    run_steps = view.get_symbol_address("run_steps")
    adjust_step = view.get_symbol_address("adjust_step")
    assert entry is not None
    assert run_steps is not None
    assert adjust_step is not None

    first = format_program_c_lowered(build_program_c_lowered(view, entry))
    second = format_program_c_lowered(build_program_c_lowered(view, entry))
    program = build_program_c_lowered(view, entry)

    assert first == second
    assert program.functions[run_steps].statement_count >= 8
    assert program.functions[adjust_step].statement_count >= 10
    assert "function 0x11158 name=run_steps" in first
    assert "function 0x11224 name=adjust_step" in first
    assert "run_steps(&local_40_4, 4, 6);" in first
    assert "while (local_28_4 <s arg_x11_4)" in first
    assert "switch (arg_x10_4->field_0)" in first
    assert "adjust_step(" in first
    assert "raw<x12_1:4>" not in first


def test_build_program_c_lowered_is_stable_for_chain_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_chain_O0_nopie"))
    entry = view.find_main().address
    fold = view.get_symbol_address("fold")
    mix = view.get_symbol_address("mix")
    assert entry is not None
    assert fold is not None
    assert mix is not None

    first = format_program_c_lowered(build_program_c_lowered(view, entry))
    second = format_program_c_lowered(build_program_c_lowered(view, entry))
    program = build_program_c_lowered(view, entry)

    assert first == second
    assert program.functions[fold].statement_count >= 7
    assert program.functions[mix].statement_count >= 3
    assert "function 0x11100 name=fold" in first
    assert "function 0x111b4 name=mix" in first
    assert "while (local_24_4 <s arg_x10_4)" in first
    assert "if (14 <s local_28_4)" in first
    assert "bump(" in first


def test_build_program_c_lowered_is_stable_for_switch_loop_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_switch_loop_O0_nopie"))
    entry = view.find_main().address
    execute = view.get_symbol_address("execute")
    decode = view.get_symbol_address("decode")
    assert entry is not None
    assert execute is not None
    assert decode is not None

    first = format_program_c_lowered(build_program_c_lowered(view, entry))
    second = format_program_c_lowered(build_program_c_lowered(view, entry))
    program = build_program_c_lowered(view, entry)

    assert first == second
    assert program.functions[execute].statement_count >= 7
    assert program.functions[decode].statement_count >= 8
    assert "function 0x110fc name=execute" in first
    assert "function 0x111b4 name=decode" in first
    assert "while (local_20_4 <s arg_x10_4)" in first
    assert "switch (arg_x10_4)" in first
    assert "decode(local_24_4" in first


def test_build_program_c_lowered_is_stable_for_nested_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_nested_O0_nopie"))
    entry = view.find_main().address
    sweep = view.get_symbol_address("sweep")
    tweak = view.get_symbol_address("tweak")
    assert entry is not None
    assert sweep is not None
    assert tweak is not None

    first = format_program_c_lowered(build_program_c_lowered(view, entry))
    second = format_program_c_lowered(build_program_c_lowered(view, entry))
    program = build_program_c_lowered(view, entry)

    assert first == second
    assert program.functions[sweep].statement_count >= 10
    assert program.functions[tweak].statement_count >= 4
    assert "function 0x11100 name=sweep" in first
    assert "function 0x111dc name=tweak" in first
    assert first.count("while (") >= 2
    assert "tweak(local_20_4, local_24_4, local_28_4);" in first


def test_build_program_c_lowered_is_stable_for_indirect_const_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_indirect_const_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_c_lowered(build_program_c_lowered(view, entry))
    second = format_program_c_lowered(build_program_c_lowered(view, entry))
    program = build_program_c_lowered(view, entry)
    facts = program.functions[entry]

    assert first == second
    assert facts.statement_count >= 5
    assert tuple(returned.register for returned in facts.returns) == (10, 11)
    assert "local_12_4 = 0x1110c;" in first
    assert "call_indirect(local_12_4, 7);" in first
    assert "call_indirect(7, local_12_4);" not in first
    assert "return [x10=ret_0x110f8_x10_4, x11=ret_0x110f8_x11_4];" in first


def test_build_program_c_lowered_is_stable_for_indirect_select_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_indirect_select_O0_nopie"))
    entry = view.find_main().address
    choose_op = view.get_symbol_address("choose_op")
    assert entry is not None
    assert choose_op is not None

    first = format_program_c_lowered(build_program_c_lowered(view, entry))
    second = format_program_c_lowered(build_program_c_lowered(view, entry))

    assert first == second
    assert f"function 0x{choose_op:x} name=choose_op" in first
    assert "local_16_4 = choose_op(&local_12_4);" in first
    assert "choose_op(raw<x2_0:4>" not in first
    assert "call_indirect(local_16_4, local_12_4 + 2, 9" in first
    assert "call_indirect(local_12_4 + 2, 9, local_16_4" not in first
