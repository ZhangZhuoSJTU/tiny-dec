from __future__ import annotations

import pytest

pytest.importorskip("pwn")

from tiny_dec.analysis.memory import build_program_memory_facts, format_program_memory_facts
from tiny_dec.analysis.memory.models import MemoryPartitionKind
from tiny_dec.loader import ProgramView


def test_build_program_memory_facts_recovers_struct_fixture_memory_surface(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_struct_O0_nopie"))
    entry = view.find_main().address
    parse_record = view.get_symbol_address("parse_record")
    assert entry is not None
    assert parse_record is not None

    program = build_program_memory_facts(view, entry)
    rendered = format_program_memory_facts(program)
    facts = program.functions[parse_record]

    assert len(facts.partitions) == 8
    assert sum(
        1 for partition in facts.partitions if partition.kind == MemoryPartitionKind.STACK_SLOT
    ) == 6
    assert sum(
        1 for partition in facts.partitions if partition.kind == MemoryPartitionKind.VALUE
    ) == 2
    value_partitions = [
        partition.identity_pretty()
        for partition in facts.partitions
        if partition.kind == MemoryPartitionKind.VALUE
    ]
    assert value_partitions == [
        "value x10_0:4 offset=+0 size=4",
        "value x10_0:4 offset=+4 size=4",
    ]
    assert sorted(
        access.instruction_address
        for partition in facts.partitions
        if partition.kind == MemoryPartitionKind.VALUE
        for access in partition.accesses
    ) == [0x11174, 0x11194]
    assert "load 0x11174 block=0x11164 size=4 value=x11_5:4 [m7]" in rendered
    assert "store 0x11180 block=0x11164 size=4 value=x10_8:4 [m7 -> m8]" in rendered
    assert "partitions=8" in rendered
    assert "stack_slot -12 size=4 role=argument_home(x10) accesses=3" in rendered
    assert "value" in rendered


def test_build_program_memory_facts_handles_stackless_optimized_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_basic_O2_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_memory_facts(build_program_memory_facts(view, entry))
    second = format_program_memory_facts(build_program_memory_facts(view, entry))
    program = build_program_memory_facts(view, entry)
    facts = program.functions[entry]

    assert facts.frame_size is None
    assert facts.dynamic_stack_pointer is False
    assert facts.partitions == ()
    assert first == second
    assert "partitions=0" in first


def test_build_program_memory_facts_recovers_lookup_fixture_stack_array_surface(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_lookup_O0_nopie"))
    entry = view.find_main().address
    fetch = view.get_symbol_address("fetch")
    assert entry is not None
    assert fetch is not None

    program = build_program_memory_facts(view, entry)
    rendered = format_program_memory_facts(program)
    facts = program.functions[fetch]

    assert len(facts.partitions) == 8
    assert sum(
        1 for partition in facts.partitions if partition.kind == MemoryPartitionKind.STACK_SLOT
    ) == 7
    assert sum(
        1 for partition in facts.partitions if partition.kind == MemoryPartitionKind.VALUE
    ) == 1
    assert "function 0x111ac name=fetch" in rendered
    assert "value u0_9:4 offset=+0 size=4 accesses=1" in rendered
