from __future__ import annotations

import pytest

pytest.importorskip("pwn")

from tiny_dec.analysis.simplify import build_canonical_program_ir, format_canonical_program_ir
from tiny_dec.loader import ProgramView


def test_build_canonical_program_ir_uses_stage4_output_for_basic_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_basic_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    program = build_canonical_program_ir(view, entry)
    rendered = format_canonical_program_ir(program)

    assert program.root_entry == entry
    assert program.discovery_order == (entry, 0x11110)
    assert program.functions[0x11110].name == "helper"
    assert f"function 0x{entry:x} name=main" in rendered
    assert "COPY register[0xa:4] <- const[0x7:4]" in rendered
    assert "LOAD register[0xa:4] <- unique[0x0:4]" in rendered


def test_canonical_program_pretty_output_is_deterministic_for_calls_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_calls_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_canonical_program_ir(build_canonical_program_ir(view, entry))
    second = format_canonical_program_ir(build_canonical_program_ir(view, entry))

    assert first == second
    assert "call_graph:" in first
    assert "functions:" in first
