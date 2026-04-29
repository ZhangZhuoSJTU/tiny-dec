from __future__ import annotations

import pytest

pytest.importorskip("pwn")

from tiny_dec.analysis.interproc import (
    PrototypeRegister,
    build_program_interproc_facts,
    format_function_interproc_facts,
    format_program_interproc_facts,
)
from tiny_dec.analysis.types import ScalarType, ScalarTypeKind
from tiny_dec.loader import ProgramView


def _parameter_registers(
    facts,
) -> tuple[int, ...]:
    return tuple(
        carrier.register
        for carrier in facts.prototype.parameters
        if isinstance(carrier, PrototypeRegister)
    )


def test_build_program_interproc_facts_recovers_parse_record_parameter_surface(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_struct_O0_nopie"))
    entry = view.find_main().address
    parse_record = view.get_symbol_address("parse_record")
    assert entry is not None
    assert parse_record is not None

    program = build_program_interproc_facts(view, entry)
    rendered = format_program_interproc_facts(program)
    facts = program.functions[parse_record]

    assert _parameter_registers(facts) == (10, 11)
    assert tuple(carrier.register for carrier in facts.prototype.returns) == (10,)
    assert facts.prototype.parameters[0].scalar_type == ScalarType(ScalarTypeKind.POINTER, 4)
    assert facts.prototype.parameters[1].scalar_type == ScalarType(ScalarTypeKind.INT, 4)
    assert facts.prototype.no_return is False
    assert "function 0x1112c name=parse_record" in rendered
    assert "param x10:4 type=pointer:4 name=arg_x10_4" in rendered
    assert "param x11:4 type=int:4 name=arg_x11_4" in rendered
    assert "return x11:4 type=int:4" not in rendered


def test_build_program_interproc_facts_drops_switch_compare_scratch_x11_return(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_switch_O0_nopie"))
    entry = view.find_main().address
    dispatch = view.get_symbol_address("dispatch")
    assert entry is not None
    assert dispatch is not None

    program = build_program_interproc_facts(view, entry)
    rendered = format_program_interproc_facts(program)
    dispatch_facts = program.functions[dispatch]
    main_facts = program.functions[entry]

    assert tuple(carrier.register for carrier in dispatch_facts.prototype.returns) == (10,)
    assert tuple(carrier.register for carrier in main_facts.prototype.returns) == (10,)
    assert "function 0x11100 name=dispatch" in rendered
    assert "return x10:4 type=int:4" in rendered
    assert "return x11:4 type=int:4" not in rendered


def test_build_program_interproc_facts_prunes_loop_root_only_x11_parameter(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_loop_O0_nopie"))
    entry = view.find_main().address
    sum_to_n = view.get_symbol_address("sum_to_n")
    assert entry is not None
    assert sum_to_n is not None

    program = build_program_interproc_facts(view, entry)
    rendered = format_program_interproc_facts(program)
    facts = program.functions[sum_to_n]

    assert _parameter_registers(facts) == (10,)
    assert tuple(carrier.register for carrier in facts.prototype.returns) == (10,)
    assert "function 0x110fc name=sum_to_n" in rendered
    assert "param x10:4 type=int:4 name=arg_x10_4" in rendered
    assert "param x11:4 type=int:4 name=arg_x11_4" not in rendered
    assert "return x11:4 type=int:4" not in rendered


def test_build_program_interproc_facts_prunes_unconsumed_basic_x11_return(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_basic_O0_nopie"))
    entry = view.find_main().address
    helper = view.get_symbol_address("helper")
    assert entry is not None
    assert helper is not None

    program = build_program_interproc_facts(view, entry)
    rendered = format_program_interproc_facts(program)
    helper_facts = program.functions[helper]
    main_facts = program.functions[entry]

    assert tuple(carrier.register for carrier in helper_facts.prototype.returns) == (10,)
    assert tuple(carrier.register for carrier in main_facts.prototype.returns) == (10,)
    assert "function 0x11110 name=helper" in rendered
    assert "return x11:4 type=int:4" not in rendered


def test_build_program_interproc_facts_prunes_observed_only_mixed_adjust_step_x12_parameter(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_mixed_O0_nopie"))
    entry = view.find_main().address
    run_steps = view.get_symbol_address("run_steps")
    adjust_step = view.get_symbol_address("adjust_step")
    assert entry is not None
    assert run_steps is not None
    assert adjust_step is not None

    program = build_program_interproc_facts(view, entry)
    run_steps_facts = program.functions[run_steps]
    adjust_step_facts = program.functions[adjust_step]
    adjust_step_rendered = format_function_interproc_facts(adjust_step_facts)

    assert _parameter_registers(run_steps_facts) == (10, 11, 12)
    assert _parameter_registers(adjust_step_facts) == (10, 11)
    assert "function 0x11224 name=adjust_step" in adjust_step_rendered
    assert "param x10:4 type=pointer:4 name=arg_x10_4" in adjust_step_rendered
    assert "param x11:4 type=int:4 name=arg_x11_4" in adjust_step_rendered
    assert "param x12:4" not in adjust_step_rendered
