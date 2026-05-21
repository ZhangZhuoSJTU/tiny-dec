from __future__ import annotations

import pytest

pytest.importorskip("pwn")

from tiny_dec.disasm import disassemble_function, format_disasm
from tiny_dec.loader import ProgramView


def test_disasm_uses_loader_output_for_basic_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_basic_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    function = disassemble_function(view, entry)
    rendered = format_disasm(function)

    assert function.entry == entry
    assert entry in function.blocks
    assert f"entry: 0x{entry:x}" in rendered
    assert f"block 0x{entry:x}" in rendered


def test_disasm_keeps_basic_fixture_call_target_out_of_main_blocks(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_basic_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    function = disassemble_function(view, entry)
    entry_block = function.blocks[entry]

    assert entry_block.call_targets == (0x11110,)
    assert 0x11110 not in function.blocks


def test_disasm_pretty_output_is_deterministic_for_calls_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_calls_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_disasm(disassemble_function(view, entry))
    second = format_disasm(disassemble_function(view, entry))

    assert first == second
    assert "term=branch" in first
    assert "term=jump" in first


def test_disasm_marks_unresolved_indirect_call_for_indirect_const_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_indirect_const_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    function = disassemble_function(view, entry)
    entry_block = function.blocks[entry]
    rendered = format_disasm(function)

    assert entry_block.call_targets == ()
    assert entry_block.has_indirect_call is True
    assert "indirect_call=yes" in rendered
    assert "calls=[" not in rendered


def test_disasm_preserves_direct_and_indirect_calls_for_indirect_select_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_indirect_select_O0_nopie"))
    entry = view.find_main().address
    choose_op = view.get_symbol_address("choose_op")
    assert entry is not None
    assert choose_op is not None

    function = disassemble_function(view, entry)
    entry_block = function.blocks[entry]
    rendered = format_disasm(function)

    assert entry_block.call_targets == (choose_op,)
    assert entry_block.has_indirect_call is True
    assert f"calls=[0x{choose_op:x}] indirect_call=yes" in rendered
