from __future__ import annotations

import pytest

pytest.importorskip("pwn")

from tiny_dec.analysis.stack import build_program_stack_facts, format_program_stack_facts
from tiny_dec.loader import ProgramView


def test_build_program_stack_facts_recovers_struct_fixture_frame_layout(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_struct_O0_nopie"))
    entry = view.find_main().address
    parse_record = view.get_symbol_address("parse_record")
    assert entry is not None
    assert parse_record is not None

    program = build_program_stack_facts(view, entry)
    rendered = format_program_stack_facts(program)
    facts = program.functions[parse_record]

    assert facts.frame_size == 32
    assert facts.frame_pointer is not None
    assert facts.frame_pointer.register == 8
    assert facts.frame_pointer.frame_top_delta == 0
    assert [(slot.frame_offset, slot.role.value) for slot in facts.slots] == [
        (-24, "local"),
        (-20, "local"),
        (-16, "argument_home"),
        (-12, "argument_home"),
        (-8, "saved_register"),
        (-4, "saved_register"),
    ]
    assert "frame_size=32" in rendered
    assert "role=argument_home(x10)" in rendered
    assert "role=saved_register(x1)" in rendered


def test_build_program_stack_facts_handles_stackless_optimized_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_basic_O2_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_stack_facts(build_program_stack_facts(view, entry))
    second = format_program_stack_facts(build_program_stack_facts(view, entry))
    program = build_program_stack_facts(view, entry)
    facts = program.functions[entry]

    assert facts.frame_size is None
    assert facts.frame_pointer is None
    assert facts.dynamic_stack_pointer is False
    assert facts.slots == ()
    assert first == second
    assert "slots=0" in first
