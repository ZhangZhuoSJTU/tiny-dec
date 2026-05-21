from __future__ import annotations

from collections.abc import Callable
import importlib.util
from pathlib import Path
import sys
from typing import Any, cast

import pytest

pytest.importorskip("pwn")
from tiny_dec.c_emit import (
    analyze_program_c_lowering,
    analyze_program_c_rendered,
    build_function_c_rendered,
    build_program_c_rendered,
    format_function_c_rendered,
    format_program_c_rendered,
)
from tiny_dec.disasm.models import BlockTerminator
from tiny_dec.ir.function_ir import CallSite
from tiny_dec.ir.pcode import PcodeOp, PcodeOpcode, const_varnode, register_varnode
from tiny_dec.loader import ProgramView


def _load_helpers() -> Any:
    spec = importlib.util.spec_from_file_location(
        "post_17_c_lowering_helpers_for_rendered",
        Path(__file__).resolve().parents[1] / "post_17_c_lowering" / "_helpers.py",
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return cast(Any, module)


_HELPERS = _load_helpers()
FunctionSpec = _HELPERS.FunctionSpec
block = _HELPERS.block
build_structured_program = _HELPERS.build_structured_program
function = _HELPERS.function
instruction = _HELPERS.instruction


def _build_forwarded_internal_argument_program():
    return build_structured_program(
        root_entry=0x1000,
        function_specs=(
            FunctionSpec(
                dataflow=function(
                    0x1000,
                    (
                        block(
                            0x1000,
                            instruction(
                                0x1000,
                                PcodeOp(
                                    opcode=PcodeOpcode.COPY,
                                    inputs=(register_varnode(10),),
                                    output=register_varnode(12),
                                ),
                            ),
                            instruction(
                                0x1004,
                                PcodeOp(
                                    opcode=PcodeOpcode.CALL,
                                    inputs=(const_varnode(0x1100),),
                                ),
                            ),
                            terminator=BlockTerminator.RETURN,
                            call_targets=(0x1100,),
                        ),
                    ),
                    name="main",
                    callsites=(
                        CallSite(
                            instruction_address=0x1004,
                            block_start=0x1000,
                            target=0x1100,
                            target_name="helper",
                        ),
                    ),
                    direct_callees=(0x1100,),
                )
            ),
            FunctionSpec(
                dataflow=function(
                    0x1100,
                    (
                        block(
                            0x1100,
                            instruction(
                                0x1100,
                                PcodeOp(
                                    opcode=PcodeOpcode.INT_ADD,
                                    inputs=(register_varnode(10), const_varnode(1)),
                                    output=register_varnode(10),
                                ),
                            ),
                            terminator=BlockTerminator.RETURN,
                        ),
                    ),
                    name="helper",
                )
            ),
        ),
    )


def test_build_program_c_rendered_uses_internal_prototype_to_trim_forwarded_call_args() -> None:
    lowered = analyze_program_c_lowering(_build_forwarded_internal_argument_program())
    rendered = format_program_c_rendered(analyze_program_c_rendered(lowered))

    assert "static uint32_t helper(uint32_t arg_x10_4);" in rendered
    assert "uint32_t arg_x12_4" not in rendered
    assert "helper(raw<x10_0:4>);" in rendered
    assert "helper(raw<x10_0:4>, raw<x10_0:4>);" not in rendered


def test_build_program_c_rendered_struct_fixture_recovers_helper_types(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_struct_O0_nopie")
    view = ProgramView(binary)
    entry = view.find_main().address
    assert entry is not None

    rendered = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert "#include <stdint.h>" in rendered
    assert "typedef struct agg_8 {" in rendered
    assert "typedef struct ret_x10_x11 {" not in rendered
    assert "static uint32_t main(void);" in rendered
    assert "static uint32_t parse_record(agg_8* arg_x10_4, int32_t arg_x11_4);" in rendered
    assert "while (local_24_4 <s arg_x11_4) {" in rendered
    assert "uint32_t call_0x11118_ret;" in rendered
    assert "call_0x11118_ret = parse_record(&local_24_4, 2);" in rendered
    assert "return call_0x11118_ret;" in rendered
    assert "return local_20_4;" in rendered
    assert "return [x10=" not in rendered
    assert "c_lowering:" not in rendered


def test_build_program_c_rendered_switch_fixture_drops_spurious_x11_return(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_switch_O0_nopie")
    view = ProgramView(binary)
    entry = view.find_main().address
    assert entry is not None

    rendered = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert "static int32_t main(void);" in rendered
    assert "static int32_t dispatch(uint32_t arg_x10_4, uint32_t arg_x11_4);" in rendered
    assert "int32_t call_0x110ec_ret;" in rendered
    assert "call_0x110ec_ret = dispatch(2, 9);" in rendered
    assert "switch (arg_x10_4) {" in rendered
    assert "case 0:" in rendered
    assert "case 1:" in rendered
    assert "case 2:" in rendered
    assert "case 3:" in rendered
    assert "default:" in rendered
    assert "else if (" not in rendered
    assert "return call_0x110ec_ret;" in rendered
    assert "return (ret_x10_x11_2){.x10 = local_12_4, .x11 = raw<x11_1:4>};" not in rendered
    assert "raw<x11_1:4>" not in rendered


def test_build_program_c_rendered_basic_fixture_preserves_single_return_functions(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")
    view = ProgramView(binary)
    entry = view.find_main().address
    assert entry is not None

    rendered = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert "static int32_t main(void);" in rendered
    assert "static int32_t helper(int32_t arg_x10_4);" in rendered
    assert "int32_t local_16_4;" in rendered
    assert "local_16_4 = helper(local_12_4);" in rendered
    assert "return local_16_4 - 2;" in rendered
    assert "uint32_t ret_0x110f0_x11_4;" not in rendered
    assert "ret_0x110f0_x11_4 = raw<x11_1:4>;" not in rendered
    assert "return (arg_x10_4 << 1) + arg_x10_4 + 1;" in rendered


def test_build_program_c_rendered_mixed_fixture_exposes_loop_switch_and_internal_calls(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_mixed_O0_nopie")
    view = ProgramView(binary)
    entry = view.find_main().address
    assert entry is not None

    rendered = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert "typedef struct agg_8 {" in rendered
    assert "typedef struct ret_x10_x11 {" not in rendered
    assert "static uint32_t main(void);" in rendered
    assert "static uint32_t run_steps(" in rendered
    assert "static uint32_t adjust_step(agg_8* arg_x10_4, int32_t arg_x11_4);" in rendered
    assert "while (local_28_4 <s arg_x11_4) {" in rendered
    assert "switch (arg_x10_4->field_0) {" in rendered
    assert "if (19 <s local_32_4) {" in rendered
    assert "call_0x11144_ret = run_steps(&local_40_4, 4, 6);" in rendered
    assert "raw<x12_1:4>" not in rendered


def test_build_program_c_rendered_chain_fixture_exposes_call_chain_and_loop(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_chain_O0_nopie")
    view = ProgramView(binary)
    entry = view.find_main().address
    assert entry is not None

    rendered = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert "static int32_t main(void);" in rendered
    assert "static int32_t fold(int32_t arg_x10_4, uint32_t arg_x11_4);" in rendered
    assert "static int32_t mix(int32_t arg_x10_4, int32_t arg_x11_4);" in rendered
    assert "call_0x110ec_ret = fold(5, 2);" in rendered
    assert "while (local_24_4 <s arg_x10_4) {" in rendered
    assert "if (14 <s local_28_4) {" in rendered
    assert "if (arg_x10_4 >=s arg_x11_4) {" in rendered


def test_build_program_c_rendered_indirect_select_fixture_uses_address_of_local_stack_slot(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_indirect_select_O0_nopie")
    view = ProgramView(binary)
    entry = view.find_main().address
    assert entry is not None

    rendered = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert "static uint32_t choose_op(agg_4* arg_x10_4);" in rendered
    assert "local_16_4 = choose_op(&local_12_4);" in rendered
    assert "choose_op(raw<x2_0:4>" not in rendered


def test_build_program_c_rendered_switch_loop_fixture_exposes_switch_inside_loop(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_switch_loop_O0_nopie")
    view = ProgramView(binary)
    entry = view.find_main().address
    assert entry is not None

    rendered = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert "static int32_t main(void);" in rendered
    assert "static int32_t execute(int32_t arg_x10_4);" in rendered
    assert "static int32_t decode(uint32_t arg_x10_4, uint32_t arg_x11_4);" in rendered
    assert "call_0x110e8_ret = execute(6);" in rendered
    assert "while (local_20_4 <s arg_x10_4) {" in rendered
    assert "switch (arg_x10_4) {" in rendered


def test_build_program_c_rendered_loop_fixture_collapses_direct_wrapper_call_returns(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_loop_O0_nopie")
    view = ProgramView(binary)
    entry = view.find_main().address
    assert entry is not None

    rendered = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert "static int32_t main(void);" in rendered
    assert "static int32_t sum_to_n(int32_t arg_x10_4);" in rendered
    assert "int32_t call_0x110e8_ret;" in rendered
    assert "call_0x110e8_ret = sum_to_n(10);" in rendered
    assert "return call_0x110e8_ret;" in rendered
    assert "uint32_t ret_0x110e8_x10_4;" not in rendered
    assert "uint32_t ret_0x110e8_x11_4;" not in rendered
    assert "ret_0x110e8_x10_4 = raw<x10_2:4>;" not in rendered
    assert "ret_0x110e8_x11_4 = raw<x11_1:4>;" not in rendered
    assert "return local_16_4;" in rendered


def test_build_function_c_rendered_includes_required_helper_declarations(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_struct_O0_nopie")
    view = ProgramView(binary)
    function_entry = view.get_symbol_address("parse_record")
    assert function_entry is not None

    rendered = format_function_c_rendered(build_function_c_rendered(view, function_entry))

    assert "#include <stdint.h>" in rendered
    assert "typedef struct agg_8 {" in rendered
    assert "typedef struct ret_x10_x11 {" in rendered
    assert "static ret_x10_x11 parse_record(agg_8* arg_x10_4, int32_t arg_x11_4) {" in rendered
    assert "arg_x10_4[local_24_4].field_0" in rendered


def test_build_program_c_rendered_calls_fixture_folds_primary_call_result_assignment(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_calls_O0_nopie")
    view = ProgramView(binary)
    entry = view.find_main().address
    assert entry is not None

    rendered = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert "static int32_t main(void);" in rendered
    assert "call_0x110fc_ret" not in rendered
    assert "call_0x1112c_ret" not in rendered
    assert "call_0x11138_ret" not in rendered
    assert "call_0x11140_ret" not in rendered
    assert "phi_0x11150_x11_4" not in rendered
    assert "local_16_4 = malloc(32);" in rendered
    assert "if (local_16_4 != 0) {" in rendered
    assert "memset(local_16_4, 0, 32);" in rendered
    assert "puts(0x100d4);" in rendered
    assert "free(local_16_4);" in rendered
    assert "call_0x110fc(" not in rendered
    assert "call_0x1112c(" not in rendered
    assert "call_0x11138(" not in rendered
    assert "call_0x11140(" not in rendered
    assert "return local_12_4;" in rendered


def test_build_program_c_rendered_stack_argument_fixture_exposes_full_signature_and_call(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_stack_args_O0_nopie")
    view = ProgramView(binary)
    entry = view.find_main().address
    assert entry is not None

    rendered = format_program_c_rendered(build_program_c_rendered(view, entry))

    assert "static int32_t sum10(" in rendered
    assert "local_0_4" in rendered
    assert "local_4_4" in rendered
    assert "\n  uint32_t local_0_4;" not in rendered
    assert "\n  uint32_t local_4_4;" not in rendered
    assert "int32_t local_0_4;" not in rendered
    assert "int32_t local_4_4;" not in rendered
    assert "call_0x11118_ret = sum10(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);" in rendered
    assert "return call_0x11118_ret;" in rendered
