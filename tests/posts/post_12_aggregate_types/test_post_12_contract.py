from __future__ import annotations

import pytest

pytest.importorskip("pwn")

from tiny_dec.analysis.types import (
    build_program_aggregate_type_facts,
    format_program_aggregate_type_facts,
)
from tiny_dec.loader import ProgramView



def test_build_program_aggregate_type_facts_recovers_struct_fixture_layout(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_struct_O0_nopie"))
    entry = view.find_main().address
    parse_record = view.get_symbol_address("parse_record")
    assert entry is not None
    assert parse_record is not None

    program = build_program_aggregate_type_facts(view, entry)
    rendered = format_program_aggregate_type_facts(program)
    facts = program.functions[parse_record]

    assert len(facts.layouts) == 1
    layout = facts.layouts[0]
    assert layout.root.pointer_value is not None
    assert layout.root.pointer_value.to_pretty() == "x10_0:4"
    assert layout.root.stride is None
    assert [
        (field.offset, field.scalar_type.to_pretty())
        for field in layout.fields
    ] == [(0, "int:4"), (4, "int:4")]
    assert "aggregate pointer x10_0:4 stride=? fields=2" in rendered



def test_build_program_aggregate_type_facts_handles_stackless_optimized_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_basic_O2_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_aggregate_type_facts(build_program_aggregate_type_facts(view, entry))
    second = format_program_aggregate_type_facts(build_program_aggregate_type_facts(view, entry))
    program = build_program_aggregate_type_facts(view, entry)
    facts = program.functions[entry]

    assert facts.layouts == ()
    assert first == second
    assert "aggregates=0" in first
