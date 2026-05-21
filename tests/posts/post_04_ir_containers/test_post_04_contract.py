from __future__ import annotations

import pytest

pytest.importorskip("pwn")

from tiny_dec.ir.containers import build_function_ir, build_program_ir
from tiny_dec.ir.pretty_containers import format_function_ir, format_program_ir
from tiny_dec.ir.program_ir import CallGraphEdgeKind
from tiny_dec.loader import ProgramView


def test_build_function_ir_uses_stage3_output_for_basic_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_basic_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    function = build_function_ir(view, entry)
    rendered = format_function_ir(function)

    assert function.entry == entry
    assert function.name == "main"
    assert function.direct_callees == (0x11110,)
    assert function.return_blocks == (entry,)
    assert f"function 0x{entry:x} name=main" in rendered
    assert "callsites:" in rendered


def test_build_program_ir_discovers_helper_for_basic_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_basic_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    program = build_program_ir(view, entry)

    assert program.discovery_order == (entry, 0x11110)
    assert program.functions[0x11110].name == "helper"
    assert len(program.call_graph) == 1
    assert program.call_graph[0].kind == CallGraphEdgeKind.INTERNAL
    assert program.call_graph[0].callee_address == 0x11110


def test_program_ir_pretty_output_is_deterministic_for_calls_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_calls_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_program_ir(build_program_ir(view, entry))
    second = format_program_ir(build_program_ir(view, entry))

    assert first == second
    assert "call_graph:" in first
    assert "functions:" in first
    assert "external" in first
    assert "name=malloc" in first


def test_build_function_ir_keeps_indirect_const_fixture_unresolved(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_indirect_const_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    function = build_function_ir(view, entry)
    rendered = format_function_ir(function)

    assert function.direct_callees == ()
    assert len(function.callsites) == 1
    assert function.callsites[0].is_indirect is True
    assert function.callsites[0].target is None
    assert "-> <indirect>" in rendered


def test_build_program_ir_models_mixed_direct_and_indirect_calls_for_indirect_select_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_indirect_select_O0_nopie"))
    entry = view.find_main().address
    choose_op = view.get_symbol_address("choose_op")
    assert entry is not None
    assert choose_op is not None

    program = build_program_ir(view, entry)
    main_function = program.functions[entry]

    assert program.discovery_order == (entry, choose_op)
    assert main_function.direct_callees == (choose_op,)
    assert len(main_function.callsites) == 2
    assert main_function.callsites[0].target == choose_op
    assert main_function.callsites[1].is_indirect is True
    assert len(program.call_graph) == 1
    assert program.call_graph[0].kind == CallGraphEdgeKind.INTERNAL
    assert program.call_graph[0].callee_address == choose_op
