from __future__ import annotations

import pytest

pytest.importorskip("pwn")

from tiny_dec.analysis.dataflow import build_program_dataflow, format_program_dataflow
from tiny_dec.loader import ProgramView


def test_build_program_dataflow_uses_stage5_output_for_basic_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_basic_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    program = build_program_dataflow(view, entry)
    rendered = format_program_dataflow(program)

    assert program.program.root_entry == entry
    assert program.program.discovery_order == (entry, 0x11110)
    assert program.functions[0x11110].function.name == "helper"
    assert f"function 0x{entry:x} name=main" in rendered
    assert "pending:" in rendered
    assert "invalidated:" in rendered
    assert "recovered_targets:" in rendered
    assert "in=[<empty>]" in rendered


def test_dataflow_program_pretty_output_is_deterministic_for_calls_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_calls_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_dataflow(build_program_dataflow(view, entry))
    second = format_program_dataflow(build_program_dataflow(view, entry))

    assert first == second
    assert "call_graph:" in first
    assert "functions:" in first


def test_build_program_dataflow_keeps_indirect_select_fixture_honest_about_unrecovered_call_target(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_indirect_select_O0_nopie"))
    entry = view.find_main().address
    choose_op = view.get_symbol_address("choose_op")
    assert entry is not None
    assert choose_op is not None

    program = build_program_dataflow(view, entry)
    rendered = format_program_dataflow(program)

    assert program.program.discovery_order == (entry, choose_op)
    assert program.functions[entry].function.name == "main"
    assert program.functions[choose_op].function.name == "choose_op"
    assert program.functions[entry].recovered_targets == ()
    assert f"internal 0x{choose_op:x} name=choose_op" in rendered
    assert "indirect_call=yes" in rendered
    assert "recovered_targets:" in rendered
