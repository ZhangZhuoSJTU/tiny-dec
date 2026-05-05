from __future__ import annotations

import pytest

pytest.importorskip("pwn")

from tiny_dec.loader import ProgramView
from tiny_dec.structuring import build_program_structured_facts, format_program_structured_facts


def test_build_program_structured_facts_recovers_loop_fixture_while(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_loop_O0_nopie"))
    entry = view.find_main().address
    sum_to_n = view.get_symbol_address("sum_to_n")
    assert entry is not None
    assert sum_to_n is not None

    program = build_program_structured_facts(view, entry)
    rendered = format_program_structured_facts(program)
    facts = program.functions[sum_to_n]

    assert facts.loop_count == 1
    assert facts.if_count == 0
    assert facts.goto_count == 0
    assert "while header=0x11120 body=0x1112c exit=0x11154" in rendered
    assert "block 0x110fc" in rendered
    assert "block 0x11154" in rendered


def test_build_program_structured_facts_recovers_switch_fixture_switch(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_switch_O0_nopie"))
    entry = view.find_main().address
    dispatch = view.get_symbol_address("dispatch")
    assert entry is not None
    assert dispatch is not None

    first = format_program_structured_facts(build_program_structured_facts(view, entry))
    second = format_program_structured_facts(build_program_structured_facts(view, entry))
    program = build_program_structured_facts(view, entry)
    facts = program.functions[dispatch]

    assert first == second
    assert facts.statement_count == 7
    assert facts.loop_count == 0
    assert facts.if_count == 0
    assert facts.switch_count == 1
    assert (
        "function 0x11100 name=dispatch frame_size=32 dynamic_sp=no stmts=7 loops=0 ifs=0 switches=1 gotos=0 pending=[]"
        in first
    )
    assert "switch header=0x11100 cases=4 default=0x11198 merge=0x111a4" in first
    assert "case 0 -> 0x11158" in first
    assert "case 1 -> 0x11168" in first
    assert "case 2 -> 0x11178" in first
    assert "case 3 -> 0x11188" in first
    assert "default:" in first
    assert "block 0x11124" not in first
    assert "block 0x11134" not in first
    assert "block 0x11144" not in first
    assert "block 0x11154" not in first
    assert "if header=" not in first
    assert "block 0x11198" in first
    assert "block 0x111a4" in first


def test_build_program_structured_facts_recovers_nested_fixture_nested_loops(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_nested_O0_nopie"))
    entry = view.find_main().address
    sweep = view.get_symbol_address("sweep")
    tweak = view.get_symbol_address("tweak")
    assert entry is not None
    assert sweep is not None
    assert tweak is not None

    program = build_program_structured_facts(view, entry)
    rendered = format_program_structured_facts(program)
    sweep_facts = program.functions[sweep]
    tweak_facts = program.functions[tweak]

    assert sweep_facts.loop_count == 2
    assert sweep_facts.if_count == 1
    assert tweak_facts.loop_count == 0
    assert tweak_facts.if_count == 1
    assert "function 0x11100 name=sweep" in rendered
    assert "while header=0x11128 body=0x11134 exit=0x111c8" in rendered
    assert "while header=0x11144 body=0x11150 exit=0x111b4" in rendered
