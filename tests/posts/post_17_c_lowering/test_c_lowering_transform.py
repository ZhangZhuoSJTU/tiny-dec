from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, cast

import pytest

pytest.importorskip("pwn")

from tiny_dec.c_emit import (
    analyze_program_c_lowering,
    build_program_c_lowered,
    format_function_c_lowered,
    format_program_c_lowered,
)
from tiny_dec.disasm.models import BlockTerminator
from tiny_dec.ir.function_ir import CallSite
from tiny_dec.ir.pcode import PcodeOp, PcodeOpcode, const_varnode, register_varnode
from tiny_dec.loader import ProgramView


def _load_helpers() -> Any:
    spec = importlib.util.spec_from_file_location(
        "post_17_c_lowering_helpers",
        Path(__file__).with_name("_helpers.py"),
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return cast(Any, module)


_HELPERS = _load_helpers()
FunctionSpec = _HELPERS.FunctionSpec
block = _HELPERS.block
build_structured_program = _HELPERS.build_structured_program
function = _HELPERS.function
instruction = _HELPERS.instruction


def _build_forwarded_internal_argument_program():
    return build_structured_program(
        root_entry=0x1000,
        function_specs=(
            FunctionSpec(
                dataflow=function(
                    0x1000,
                    (
                        block(
                            0x1000,
                            instruction(
                                0x1000,
                                PcodeOp(
                                    opcode=PcodeOpcode.COPY,
                                    inputs=(register_varnode(10),),
                                    output=register_varnode(12),
                                ),
                            ),
                            instruction(
                                0x1004,
                                PcodeOp(
                                    opcode=PcodeOpcode.CALL,
                                    inputs=(const_varnode(0x1100),),
                                ),
                            ),
                            terminator=BlockTerminator.RETURN,
                            call_targets=(0x1100,),
                        ),
                    ),
                    name="main",
                    callsites=(
                        CallSite(
                            instruction_address=0x1004,
                            block_start=0x1000,
                            target=0x1100,
                            target_name="helper",
                        ),
                    ),
                    direct_callees=(0x1100,),
                )
            ),
            FunctionSpec(
                dataflow=function(
                    0x1100,
                    (
                        block(
                            0x1100,
                            instruction(
                                0x1100,
                                PcodeOp(
                                    opcode=PcodeOpcode.INT_ADD,
                                    inputs=(register_varnode(10), const_varnode(1)),
                                    output=register_varnode(10),
                                ),
                            ),
                            terminator=BlockTerminator.RETURN,
                        ),
                    ),
                    name="helper",
                )
            ),
        ),
    )


def test_build_program_c_lowered_uses_internal_prototype_to_trim_forwarded_call_args() -> None:
    program = analyze_program_c_lowering(_build_forwarded_internal_argument_program())
    rendered = format_program_c_lowered(program)
    helper = program.functions[0x1100]

    assert tuple(parameter.register for parameter in helper.parameters) == (10,)
    assert "param x12" not in rendered
    assert "helper(raw<x10_0:4>);" in rendered
    assert "helper(raw<x10_0:4>, raw<x10_0:4>);" not in rendered


def test_build_program_c_lowered_recovers_loop_fixture_statements(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_loop_O0_nopie"))
    entry = view.find_main().address
    sum_to_n = view.get_symbol_address("sum_to_n")
    assert entry is not None
    assert sum_to_n is not None

    program = build_program_c_lowered(view, entry)
    facts = program.functions[sum_to_n]
    rendered = format_function_c_lowered(facts)

    assert tuple(parameter.name for parameter in facts.parameters) == ("arg_x10_4",)
    assert tuple(parameter.register for parameter in facts.parameters) == (10,)
    assert tuple(returned.register for returned in facts.returns) == (10,)
    assert tuple(local.name for local in facts.locals) == ("local_20_4", "local_16_4")
    assert "local_16_4 = 0;" in rendered
    assert "local_20_4 = 0;" in rendered
    assert "while (local_20_4 <s arg_x10_4)" in rendered
    assert "local_16_4 = local_16_4 + local_20_4;" in rendered
    assert "local_20_4 = local_20_4 + 1;" in rendered
    assert "param x11 int32_t arg_x11_4" not in rendered
    assert "return [x10=local_16_4];" in rendered


def test_build_program_c_lowered_recovers_switch_fixture_switch(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_switch_O0_nopie"))
    entry = view.find_main().address
    dispatch = view.get_symbol_address("dispatch")
    assert entry is not None
    assert dispatch is not None

    program = build_program_c_lowered(view, entry)
    facts = program.functions[dispatch]
    rendered = format_function_c_lowered(facts)

    assert tuple(parameter.name for parameter in facts.parameters) == (
        "arg_x10_4",
        "arg_x11_4",
    )
    assert tuple(returned.register for returned in facts.returns) == (10,)
    assert tuple(local.name for local in facts.locals) == (
        "local_24_4",
        "local_12_4",
    )
    assert "switch (arg_x10_4)" in rendered
    assert "case 0:" in rendered
    assert "case 1:" in rendered
    assert "case 2:" in rendered
    assert "case 3:" in rendered
    assert "default:" in rendered
    assert "if (arg_x10_4 == 0)" not in rendered
    assert "if (local_24_4 == 1)" not in rendered
    assert "local_12_4 = -1;" in rendered
    assert "return [x10=local_12_4];" in rendered
    assert "raw<x11_1:4>" not in rendered


def test_build_program_c_lowered_recovers_struct_fixture_field_accesses(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_struct_O0_nopie"))
    entry = view.find_main().address
    parse_record = view.get_symbol_address("parse_record")
    assert entry is not None
    assert parse_record is not None

    program = build_program_c_lowered(view, entry)
    facts = program.functions[parse_record]
    main_rendered = format_function_c_lowered(program.functions[entry])
    rendered = format_function_c_lowered(facts)

    assert tuple(parameter.name for parameter in facts.parameters) == (
        "arg_x10_4",
        "arg_x11_4",
    )
    assert tuple(returned.register for returned in facts.returns) == (10,)
    assert "param x10 agg_8* arg_x10_4" in rendered
    assert "parse_record(&local_24_4, 2);" in main_rendered
    assert "while (local_24_4 <s arg_x11_4)" in rendered
    assert "arg_x10_4[local_24_4].field_0" in rendered
    assert "arg_x10_4[local_24_4].field_4" in rendered
    assert "return [x10=local_20_4];" in rendered


def test_build_program_c_lowered_recovers_call_statements_for_main(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_calls_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    program = build_program_c_lowered(view, entry)
    facts = program.functions[entry]
    rendered = format_function_c_lowered(facts)

    assert tuple(parameter.name for parameter in facts.parameters) == ()
    assert tuple(returned.register for returned in facts.returns) == (10,)
    assert tuple(local.name for local in facts.locals) == (
        "local_20_4",
        "local_16_4",
        "local_12_4",
    )
    assert "local_16_4 = malloc(32);" in rendered
    assert "\n  malloc(32);" not in rendered
    assert "local_16_4 = raw<x10_2:4>;" not in rendered
    assert "ret_0x110fc_x11_4 = raw<x11_1:4>;" not in rendered
    assert "ret_0x1112c_x11_4 = raw<x11_3:4>;" not in rendered
    assert "ret_0x11138_x11_4 = raw<x11_4:4>;" not in rendered
    assert "ret_0x11140_x11_4 = raw<x11_5:4>;" not in rendered
    assert "memset(local_16_4, 0, 32);" in rendered
    assert "puts(0x100d4);" in rendered
    assert "free(local_16_4);" in rendered
    assert "call_0x110fc" not in rendered
    assert "call_0x1112c" not in rendered
    assert "call_0x11138" not in rendered
    assert "call_0x11140" not in rendered
    assert "if (local_16_4 != 0)" in rendered
    assert "return [x10=local_12_4];" in rendered
    assert "return [x10=local_12_4, x11=" not in rendered


def test_build_program_c_lowered_recovers_stack_argument_fixture_signature_and_call(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_stack_args_O0_nopie"))
    entry = view.find_main().address
    sum10 = view.get_symbol_address("sum10")
    assert entry is not None
    assert sum10 is not None

    program = build_program_c_lowered(view, entry)
    sum10_facts = program.functions[sum10]
    main_facts = program.functions[entry]
    sum10_rendered = format_function_c_lowered(sum10_facts)
    main_rendered = format_function_c_lowered(main_facts)

    assert tuple(
        (parameter.register, parameter.stack_offset, parameter.name)
        for parameter in sum10_facts.parameters
    ) == (
        (10, None, "arg_x10_4"),
        (11, None, "arg_x11_4"),
        (12, None, "arg_x12_4"),
        (13, None, "arg_x13_4"),
        (14, None, "arg_x14_4"),
        (15, None, "arg_x15_4"),
        (16, None, "arg_x16_4"),
        (17, None, "arg_x17_4"),
        (None, 0, "local_0_4"),
        (None, 4, "local_4_4"),
    )
    assert "param stack+0" in sum10_rendered
    assert "param stack+4" in sum10_rendered
    assert "locals:\n  <none>\nbody:" in sum10_rendered
    assert "sum10(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);" in main_rendered


def test_build_program_c_lowered_collapses_basic_program_to_single_return(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_basic_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    program = build_program_c_lowered(view, entry)
    facts = program.functions[entry]
    rendered = format_function_c_lowered(facts)

    assert tuple(returned.register for returned in facts.returns) == (10,)
    assert tuple(local.name for local in facts.locals) == (
        "local_16_4",
        "local_12_4",
    )
    assert "local_16_4 = helper(local_12_4);" in rendered
    assert "local word32_t ret_0x110f0_x11_4" not in rendered
    assert "ret_0x110f0_x11_4 = raw<x11_1:4>;" not in rendered
    assert "return [x10=local_16_4 - 2];" in rendered


def test_build_program_c_lowered_recovers_mixed_fixture_loop_switch_and_internal_calls(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_mixed_O0_nopie"))
    entry = view.find_main().address
    run_steps = view.get_symbol_address("run_steps")
    adjust_step = view.get_symbol_address("adjust_step")
    assert entry is not None
    assert run_steps is not None
    assert adjust_step is not None

    program = build_program_c_lowered(view, entry)
    main_rendered = format_function_c_lowered(program.functions[entry])
    run_steps_facts = program.functions[run_steps]
    adjust_step_facts = program.functions[adjust_step]
    run_steps_rendered = format_function_c_lowered(run_steps_facts)
    adjust_step_rendered = format_function_c_lowered(adjust_step_facts)

    assert tuple(parameter.name for parameter in run_steps_facts.parameters) == (
        "arg_x10_4",
        "arg_x11_4",
        "arg_x12_4",
    )
    assert tuple(parameter.name for parameter in adjust_step_facts.parameters) == (
        "arg_x10_4",
        "arg_x11_4",
    )
    assert tuple(local.name for local in run_steps_facts.locals) == (
        "local_32_4",
        "local_28_4",
        "local_24_4",
    )
    assert "run_steps(&local_40_4, 4, 6);" in main_rendered
    assert "while (local_28_4 <s arg_x11_4)" in run_steps_rendered
    assert "adjust_step(" in run_steps_rendered
    assert "if (19 <s local_32_4)" in run_steps_rendered
    assert "local_24_4 = local_24_4 + local_32_4;" in run_steps_rendered
    assert "raw<x12_1:4>" not in run_steps_rendered
    assert "switch (arg_x10_4->field_0)" in adjust_step_rendered
    assert "case 0:" in adjust_step_rendered
    assert "case 1:" in adjust_step_rendered
    assert "case 2:" in adjust_step_rendered
    assert "case 3:" in adjust_step_rendered
    assert "default:" in adjust_step_rendered
    assert "arg_x10_4->field_4" in adjust_step_rendered


def test_build_program_c_lowered_recovers_chain_fixture_loop_and_call_chain(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_chain_O0_nopie"))
    entry = view.find_main().address
    fold = view.get_symbol_address("fold")
    mix = view.get_symbol_address("mix")
    assert entry is not None
    assert fold is not None
    assert mix is not None

    program = build_program_c_lowered(view, entry)
    fold_facts = program.functions[fold]
    mix_facts = program.functions[mix]
    fold_rendered = format_function_c_lowered(fold_facts)
    mix_rendered = format_function_c_lowered(mix_facts)

    assert tuple(parameter.name for parameter in fold_facts.parameters) == (
        "arg_x10_4",
        "arg_x11_4",
    )
    assert tuple(parameter.name for parameter in mix_facts.parameters) == (
        "arg_x10_4",
        "arg_x11_4",
    )
    assert tuple(returned.register for returned in fold_facts.returns) == (10,)
    assert "while (local_24_4 <s arg_x10_4)" in fold_rendered
    assert "mix(local_20_4, local_24_4 + arg_x11_4);" in fold_rendered
    assert "if (14 <s local_28_4)" in fold_rendered
    assert "bump(" in mix_rendered
    assert "if (arg_x10_4 >=s arg_x11_4)" in mix_rendered


def test_build_program_c_lowered_recovers_switch_loop_fixture_loop_and_switch(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_switch_loop_O0_nopie"))
    entry = view.find_main().address
    execute = view.get_symbol_address("execute")
    decode = view.get_symbol_address("decode")
    assert entry is not None
    assert execute is not None
    assert decode is not None

    program = build_program_c_lowered(view, entry)
    execute_facts = program.functions[execute]
    decode_facts = program.functions[decode]
    execute_rendered = format_function_c_lowered(execute_facts)
    decode_rendered = format_function_c_lowered(decode_facts)

    assert tuple(parameter.name for parameter in execute_facts.parameters) == ("arg_x10_4",)
    assert tuple(parameter.name for parameter in decode_facts.parameters) == (
        "arg_x10_4",
        "arg_x11_4",
    )
    assert tuple(returned.register for returned in execute_facts.returns) == (10,)
    assert "while (local_20_4 <s arg_x10_4)" in execute_rendered
    assert "local_24_4 = local_20_4 & 3;" in execute_rendered
    assert "decode(local_24_4, local_16_4 + local_20_4);" in execute_rendered
    assert "switch (arg_x10_4)" in decode_rendered
    assert "case 0:" in decode_rendered
    assert "case 1:" in decode_rendered
    assert "case 2:" in decode_rendered
    assert "case 3:" in decode_rendered
    assert "default:" in decode_rendered


def test_build_program_c_lowered_spells_exact_stack_slot_addresses_as_address_of_locals(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_indirect_select_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    rendered = format_function_c_lowered(build_program_c_lowered(view, entry).functions[entry])

    assert "local_16_4 = choose_op(&local_12_4);" in rendered
    assert "choose_op(raw<x2_0:4>" not in rendered
