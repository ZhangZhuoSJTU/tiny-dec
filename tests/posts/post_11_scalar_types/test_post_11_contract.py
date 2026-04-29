from __future__ import annotations

import pytest

pytest.importorskip("pwn")

from tiny_dec.analysis.types import build_program_scalar_type_facts, format_program_scalar_type_facts
from tiny_dec.loader import ProgramView


def test_build_program_scalar_type_facts_recovers_struct_fixture_scalar_surface(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_struct_O0_nopie"))
    entry = view.find_main().address
    parse_record = view.get_symbol_address("parse_record")
    assert entry is not None
    assert parse_record is not None

    program = build_program_scalar_type_facts(view, entry)
    rendered = format_program_scalar_type_facts(program)
    facts = program.functions[parse_record]

    partition_types = {
        fact.partition.identity_pretty(): fact.scalar_type.to_pretty()
        for fact in facts.partition_facts
    }
    value_types = {
        fact.value.to_pretty(): fact.scalar_type.to_pretty()
        for fact in facts.value_facts
    }

    assert partition_types["stack_slot -12 size=4 role=argument_home(x10)"] == "pointer:4"
    assert partition_types["stack_slot -24 size=4 role=local"] == "int:4"
    assert partition_types["value x10_0:4 offset=+0 size=4"] == "int:4"
    assert partition_types["value x10_0:4 offset=+4 size=4"] == "int:4"
    assert value_types["x10_5:4"] == "pointer:4"
    assert value_types["x11_5:4"] == "int:4"
    first_value_access = next(
        access
        for partition in facts.memory.partitions
        if partition.identity_pretty() == "value x10_0:4 offset=+0 size=4"
        for access in partition.accesses
    )
    assert first_value_access.memory_before is not None
    assert first_value_access.memory_before.to_pretty() == "m7"
    assert first_value_access.memory_after is None
    assert any(fact.scalar_type.to_pretty() == "bool:1" for fact in facts.value_facts)
    assert "type=pointer:4" in rendered
    assert "type=int:4" in rendered


def test_build_program_scalar_type_facts_handles_stackless_optimized_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_basic_O2_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_scalar_type_facts(build_program_scalar_type_facts(view, entry))
    second = format_program_scalar_type_facts(build_program_scalar_type_facts(view, entry))
    program = build_program_scalar_type_facts(view, entry)
    facts = program.functions[entry]

    assert facts.partition_facts == ()
    assert first == second
    assert "typed_partitions=0" in first


def test_build_program_scalar_type_facts_recovers_basic_fixture_helper_result_as_int(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_basic_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    program = build_program_scalar_type_facts(view, entry)
    rendered = format_program_scalar_type_facts(program)
    facts = program.functions[entry]

    partition_types = {
        fact.partition.identity_pretty(): fact.scalar_type.to_pretty()
        for fact in facts.partition_facts
    }
    value_types = {
        fact.value.to_pretty(): fact.scalar_type.to_pretty()
        for fact in facts.value_facts
    }

    assert partition_types["stack_slot -12 size=4 role=local"] == "int:4"
    assert partition_types["stack_slot -16 size=4 role=local"] == "int:4"
    assert value_types["x10_3:4"] == "int:4"
    assert value_types["x10_4:4"] == "int:4"
    assert value_types["x10_5:4"] == "int:4"
    assert "stack_slot -16 size=4 role=local type=int:4" in rendered
