from __future__ import annotations

import pytest

pytest.importorskip("pwn")

from tiny_dec.analysis.calls import build_program_call_facts, format_program_call_facts
from tiny_dec.loader import ProgramView


def test_build_program_call_facts_models_internal_calls_for_basic_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_basic_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    program = build_program_call_facts(view, entry)
    rendered = format_program_call_facts(program)

    assert program.ssa.dataflow.program.root_entry == entry
    assert program.functions[entry].name == "main"
    assert f"function 0x{entry:x} name=main" in rendered
    assert "abi: rv32i_ilp32" in rendered
    assert "call_graph:" in rendered
    assert "mem=[" in rendered


def test_call_program_pretty_output_is_deterministic_for_calls_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_calls_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_call_facts(build_program_call_facts(view, entry))
    second = format_program_call_facts(build_program_call_facts(view, entry))

    assert first == second
    assert "functions:" in first
    assert "callsites:" in first
    assert "via=direct" in first
    assert "mem=[" in first


def test_build_program_call_facts_omits_saved_register_slots_from_stack_args_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_stack_args_O0_nopie"))
    entry = view.find_main().address
    sum10 = view.get_symbol_address("sum10")
    assert entry is not None
    assert sum10 is not None

    program = build_program_call_facts(view, entry)
    rendered = format_program_call_facts(program)
    main_callsite = program.functions[entry].callsites[0]

    assert main_callsite.target_address == sum10
    assert tuple(value.stack_offset for value in main_callsite.stack_argument_values) == (0, 4)
    assert "stack+8=" not in rendered
    assert "stack+12=" not in rendered


def test_build_program_call_facts_models_nested_fixture_internal_call_chain(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_nested_O0_nopie"))
    entry = view.find_main().address
    sweep = view.get_symbol_address("sweep")
    tweak = view.get_symbol_address("tweak")
    assert entry is not None
    assert sweep is not None
    assert tweak is not None

    program = build_program_call_facts(view, entry)
    rendered = format_program_call_facts(program)
    main_callsite = program.functions[entry].callsites[0]
    sweep_callsite = program.functions[sweep].callsites[0]

    assert main_callsite.target_address == sweep
    assert sweep_callsite.target_address == tweak
    assert "function 0x11100 name=sweep" in rendered
    assert "function 0x111dc name=tweak" in rendered
    assert "call 0x110ec block=0x110d4 via=direct -> internal 0x11100 name=sweep" in rendered
    assert "call 0x11160 block=0x11154 via=direct -> internal 0x111dc name=tweak" in rendered


def test_build_program_call_facts_preserves_unresolved_indirect_call_for_indirect_const_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_indirect_const_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    program = build_program_call_facts(view, entry)
    rendered = format_program_call_facts(program)
    main_callsite = program.functions[entry].callsites[0]

    assert main_callsite.is_indirect is True
    assert main_callsite.indirect_target_value is not None
    assert main_callsite.indirect_target_value.to_pretty() == "x11_1:4"
    assert main_callsite.target_address is None
    assert main_callsite.callee_name is None
    assert tuple(value.register for value in main_callsite.argument_values) == (10,)
    assert "via=indirect -> unresolved target_value=x11_1:4" in rendered
    assert "x11=x11_1:4" not in rendered


def test_build_program_call_facts_models_mixed_direct_and_indirect_calls_for_indirect_select_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_indirect_select_O0_nopie"))
    entry = view.find_main().address
    choose_op = view.get_symbol_address("choose_op")
    assert entry is not None
    assert choose_op is not None

    program = build_program_call_facts(view, entry)
    rendered = format_program_call_facts(program)
    direct_callsite, indirect_callsite = program.functions[entry].callsites

    assert program.ssa.dataflow.program.discovery_order == (entry, choose_op)
    assert program.functions[choose_op].name == "choose_op"
    assert direct_callsite.target_address == choose_op
    assert direct_callsite.is_indirect is False
    assert indirect_callsite.is_indirect is True
    assert indirect_callsite.indirect_target_value is not None
    assert indirect_callsite.indirect_target_value.to_pretty() == "x12_2:4"
    assert indirect_callsite.target_address is None
    assert tuple(value.register for value in indirect_callsite.argument_values) == (10, 11, 13, 14, 15, 16, 17)
    assert tuple(value.stack_offset for value in indirect_callsite.stack_argument_values) == (0, 4)
    assert f"function 0x{choose_op:x} name=choose_op" in rendered
    assert "via=indirect -> unresolved target_value=x12_2:4" in rendered
    assert "x12=x12_2:4" not in rendered
