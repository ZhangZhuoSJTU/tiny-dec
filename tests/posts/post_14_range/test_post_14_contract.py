from __future__ import annotations

import pytest

pytest.importorskip("pwn")

from tiny_dec.analysis.range import build_program_range_facts, format_program_range_facts
from tiny_dec.loader import ProgramView


def test_build_program_range_facts_recovers_loop_fixture_ranges(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_loop_O0_nopie"))
    entry = view.find_main().address
    sum_to_n = view.get_symbol_address("sum_to_n")
    assert entry is not None
    assert sum_to_n is not None

    program = build_program_range_facts(view, entry)
    rendered = format_program_range_facts(program)
    facts = program.functions[sum_to_n]
    value_ranges = {
        fact.value.to_pretty(): (fact.value_range.lower, fact.value_range.upper)
        for fact in facts.value_ranges
    }
    variable_ranges = {
        fact.variable.name: (fact.value_range.lower, fact.value_range.upper)
        for fact in facts.variable_ranges
    }

    assert value_ranges["x10_1:4"] == (0, 0)
    assert variable_ranges["local_20_4"] == (0, None)
    assert variable_ranges["local_16_4"] == (0, None)
    assert facts.branch_refinements == ()
    assert "variable local_20_4 range=[0, +inf]" in rendered


def test_build_program_range_facts_recovers_switch_fixture_branch_surface(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_switch_O0_nopie"))
    entry = view.find_main().address
    dispatch = view.get_symbol_address("dispatch")
    assert entry is not None
    assert dispatch is not None

    first = format_program_range_facts(build_program_range_facts(view, entry))
    second = format_program_range_facts(build_program_range_facts(view, entry))
    program = build_program_range_facts(view, entry)
    facts = program.functions[dispatch]

    assert first == second
    assert any(
        fact.block_start == dispatch
        and fact.source_opcode == "INT_EQUAL"
        and fact.value.to_pretty() == "x10_1:4"
        and fact.value_range.lower == 0
        and fact.value_range.upper == 0
        for fact in facts.branch_refinements
    )
    assert "branch 0x11100 -> 0x11158 sense=true source=INT_EQUAL value=x10_1:4 range=[0, 0]" in first


def test_build_program_range_facts_recovers_mixed_fixture_branch_surface(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_mixed_O0_nopie"))
    entry = view.find_main().address
    run_steps = view.get_symbol_address("run_steps")
    adjust_step = view.get_symbol_address("adjust_step")
    assert entry is not None
    assert run_steps is not None
    assert adjust_step is not None

    first = format_program_range_facts(build_program_range_facts(view, entry))
    second = format_program_range_facts(build_program_range_facts(view, entry))
    program = build_program_range_facts(view, entry)
    run_steps_facts = program.functions[run_steps]
    adjust_step_facts = program.functions[adjust_step]

    assert first == second
    assert len(run_steps_facts.branch_refinements) == 2
    assert len(adjust_step_facts.branch_refinements) == 4
    assert any(
        fact.source_opcode == "INT_SLESS"
        and fact.value_range.lower == 20
        and fact.value_range.upper is None
        for fact in run_steps_facts.branch_refinements
    )
    assert all(
        fact.source_opcode == "INT_EQUAL"
        for fact in adjust_step_facts.branch_refinements
    )
    assert "function 0x11158 name=run_steps" in first
    assert "function 0x11224 name=adjust_step" in first


def test_build_program_range_facts_recovers_chain_fixture_branch_surface(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_chain_O0_nopie"))
    entry = view.find_main().address
    fold = view.get_symbol_address("fold")
    assert entry is not None
    assert fold is not None

    program = build_program_range_facts(view, entry)
    facts = program.functions[fold]
    rendered = format_program_range_facts(program)

    assert len(facts.branch_refinements) == 2
    assert any(
        fact.source_opcode == "INT_SLESS"
        and fact.value_range.lower == 15
        and fact.value_range.upper is None
        for fact in facts.branch_refinements
    )
    assert "function 0x11100 name=fold" in rendered


def test_build_program_range_facts_recovers_switch_loop_fixture_branch_surface(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_switch_loop_O0_nopie"))
    entry = view.find_main().address
    execute = view.get_symbol_address("execute")
    decode = view.get_symbol_address("decode")
    assert entry is not None
    assert execute is not None
    assert decode is not None

    program = build_program_range_facts(view, entry)
    execute_facts = program.functions[execute]
    decode_facts = program.functions[decode]
    rendered = format_program_range_facts(program)

    assert len(execute_facts.branch_refinements) == 2
    assert len(decode_facts.branch_refinements) == 4
    assert any(
        fact.source_opcode == "INT_SLESS"
        and fact.value_range.lower == 12
        and fact.value_range.upper is None
        for fact in execute_facts.branch_refinements
    )
    assert all(
        fact.source_opcode == "INT_EQUAL"
        for fact in decode_facts.branch_refinements
    )
    assert "function 0x110fc name=execute" in rendered
    assert "function 0x111b4 name=decode" in rendered


def test_build_program_range_facts_recovers_nested_fixture_branch_surface(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_nested_O0_nopie"))
    entry = view.find_main().address
    sweep = view.get_symbol_address("sweep")
    assert entry is not None
    assert sweep is not None

    program = build_program_range_facts(view, entry)
    facts = program.functions[sweep]
    rendered = format_program_range_facts(program)

    assert len(facts.branch_refinements) == 2
    assert any(
        fact.source_opcode == "INT_SLESS"
        and fact.value_range.lower == 25
        and fact.value_range.upper is None
        for fact in facts.branch_refinements
    )
    assert "function 0x11100 name=sweep" in rendered
