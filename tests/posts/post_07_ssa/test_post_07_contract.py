from __future__ import annotations

import pytest

pytest.importorskip("pwn")

from tiny_dec.analysis.ssa import build_ssa_program_ir, format_ssa_program_ir
from tiny_dec.loader import ProgramView


def test_build_ssa_program_ir_uses_dataflow_output_for_switch_dispatch_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_switch_O0_nopie"))
    entry = view.get_symbol_address("dispatch")
    assert entry is not None

    program = build_ssa_program_ir(view, entry)
    rendered = format_ssa_program_ir(program)

    assert program.dataflow.program.root_entry == entry
    assert program.functions[entry].name == "dispatch"
    assert f"function 0x{entry:x} name=dispatch" in rendered
    assert "live_ins:" in rendered
    assert "x10_0:4" in rendered
    assert "blocks:" in rendered
    assert "idom=<entry>" in rendered


def test_ssa_program_pretty_output_is_deterministic_for_loop_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_loop_O0_nopie"))
    entry = view.get_symbol_address("sum_to_n")
    assert entry is not None

    first = format_ssa_program_ir(build_ssa_program_ir(view, entry))
    second = format_ssa_program_ir(build_ssa_program_ir(view, entry))

    assert first == second
    assert "functions:" in first
    assert "live_ins:" in first


def test_build_ssa_program_ir_exposes_call_return_defs_for_calls_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_calls_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    rendered = format_ssa_program_ir(build_ssa_program_ir(view, entry))

    assert "CALL const[" in rendered
    assert "CALL_RETURN x10_" in rendered
    assert "CALL_RETURN x11_" in rendered
    assert "memory_live_in:" in rendered
    assert "[m" in rendered
