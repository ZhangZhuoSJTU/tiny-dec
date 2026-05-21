from __future__ import annotations

import pytest

pytest.importorskip("pwn")

from tiny_dec.analysis.highvars import (
    VariableBindingKind,
    VariableKind,
    build_program_variable_facts,
    format_program_variable_facts,
)
from tiny_dec.loader import ProgramView


def test_build_program_variable_facts_recovers_struct_fixture_variables(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_struct_O0_nopie"))
    entry = view.find_main().address
    parse_record = view.get_symbol_address("parse_record")
    assert entry is not None
    assert parse_record is not None

    program = build_program_variable_facts(view, entry)
    rendered = format_program_variable_facts(program)
    facts = program.functions[parse_record]

    assert any(
        variable.kind == VariableKind.PARAMETER
        and variable.binding.kind == VariableBindingKind.STACK_SLOT
        for variable in facts.variables
    )
    assert any(
        variable.kind == VariableKind.LOCAL
        and variable.binding.kind == VariableBindingKind.STACK_SLOT
        for variable in facts.variables
    )
    assert any(
        variable.aggregate_layout is not None
        and len(variable.aggregate_layout.fields) == 2
        for variable in facts.variables
    )
    assert f"function 0x{parse_record:x} name=parse_record" in rendered
    assert "variables:" in rendered
    assert "variable " in rendered


def test_build_program_variable_facts_handles_stackless_optimized_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_basic_O2_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_variable_facts(build_program_variable_facts(view, entry))
    second = format_program_variable_facts(build_program_variable_facts(view, entry))

    assert first == second
    assert "variables=0" in first or "variables:" in first


def test_build_program_variable_facts_recovers_basic_fixture_locals(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_basic_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    program = build_program_variable_facts(view, entry)
    rendered = format_program_variable_facts(program)
    facts = program.functions[entry]

    assert any(variable.kind == VariableKind.LOCAL for variable in facts.variables)
    assert all(variable.size > 0 for variable in facts.variables)
    assert all(variable.name for variable in facts.variables)
    assert f"function 0x{entry:x} name=main" in rendered
    assert "variables:" in rendered
