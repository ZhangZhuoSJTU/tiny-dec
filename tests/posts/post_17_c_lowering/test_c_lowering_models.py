from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any, cast

import pytest

from tiny_dec.c_emit import (
    CAssignStmt,
    CBinaryExpr,
    CBreakStmt,
    CCallExpr,
    CCallTarget,
    CCallTargetKind,
    CConstExpr,
    CContinueStmt,
    CExprStmt,
    CFieldExpr,
    CGotoStmt,
    CIfStmt,
    CLoweredReturn,
    CLoweredType,
    CLoweredVariable,
    CLoweredVariableKind,
    CNameExpr,
    CRawExpr,
    CReturnBinding,
    CReturnStmt,
    CStmtSequence,
    CSwitchCase,
    CSwitchStmt,
    CUnaryExpr,
    CWhileStmt,
    format_c_stmt,
    FunctionCLowered,
    ProgramCLowered,
    format_c_expr,
    format_c_lowered_return,
    format_c_lowered_type,
    format_c_lowered_variable,
    format_c_stmt_sequence,
    format_function_c_lowered,
    format_program_c_lowered,
)


def _load_helpers() -> Any:
    spec = importlib.util.spec_from_file_location(
        "post_17_c_lowering_helpers_for_models",
        Path(__file__).with_name("_helpers.py"),
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


def test_c_lowering_model_pretty_output_is_stable() -> None:
    structured_program = build_structured_program(
        root_entry=0x1000,
        function_specs=(
            FunctionSpec(
                dataflow=function(
                    0x1000,
                    (block(0x1000, instruction(0x1000)),),
                    name="main",
                )
            ),
        ),
        pending_entries=(0x2000,),
        invalidated_entries=(0x1000,),
    )
    structured_function = structured_program.functions[0x1000]

    int32 = CLoweredType("int32_t", 4)
    parameter = CLoweredVariable(
        name="arg_x10_4",
        kind=CLoweredVariableKind.PARAMETER,
        ctype=int32,
        register=10,
    )
    stack_parameter = CLoweredVariable(
        name="local_0_4",
        kind=CLoweredVariableKind.PARAMETER,
        ctype=int32,
        stack_offset=0,
    )
    local = CLoweredVariable(
        name="local_16_4",
        kind=CLoweredVariableKind.LOCAL,
        ctype=int32,
    )
    returned = CLoweredReturn(register=10, ctype=int32)
    call = CCallExpr(
        target=CCallTarget(
            kind=CCallTargetKind.UNRESOLVED,
            address=0x1300,
        ),
        arguments=(CConstExpr(32, 4), CNameExpr("arg_x10_4")),
    )
    loop = CWhileStmt(
        condition=CBinaryExpr("<", CNameExpr("local_16_4"), CConstExpr(3, 4)),
        body=CStmtSequence(
            (
                CAssignStmt(
                    CNameExpr("local_16_4"),
                    CBinaryExpr("+", CNameExpr("local_16_4"), CConstExpr(1, 4)),
                ),
                CContinueStmt(0x1010),
            )
        ),
    )
    conditional = CIfStmt(
        condition=CBinaryExpr("!=", CNameExpr("local_16_4"), CConstExpr(0, 4)),
        then_body=CStmtSequence((CExprStmt(call),)),
        else_body=CStmtSequence((CBreakStmt(0x1040),)),
    )
    function_facts = FunctionCLowered(
        structured=structured_function,
        parameters=(parameter, stack_parameter),
        returns=(returned,),
        locals=(local,),
        body=CStmtSequence(
            (
                CAssignStmt(CNameExpr("local_16_4"), CConstExpr(0, 4)),
                conditional,
                loop,
                CGotoStmt(0x1400),
                CReturnStmt((CReturnBinding(10, CNameExpr("local_16_4")),)),
            )
        ),
    )
    program = ProgramCLowered(
        structured=structured_program,
        functions={0x1000: function_facts},
        pending_entries=structured_program.pending_entries,
        invalidated_entries=structured_program.invalidated_entries,
        scheduler_invalidations=structured_program.scheduler_invalidations,
    )

    assert format_c_lowered_type(int32) == "int32_t"
    assert format_c_lowered_variable(parameter) == "param x10 int32_t arg_x10_4"
    assert format_c_lowered_variable(stack_parameter) == "param stack+0 int32_t local_0_4"
    assert format_c_lowered_variable(local) == "local int32_t local_16_4"
    assert format_c_lowered_return(returned) == "return x10 int32_t"
    assert format_c_expr(CFieldExpr("items", 4, "field_4", CNameExpr("i"))) == "items[i].field_4"
    assert format_c_expr(CRawExpr("x10_6:4")) == "raw<x10_6:4>"
    assert format_c_stmt_sequence(
        CStmtSequence(
            (
                CAssignStmt(CNameExpr("local_16_4"), CConstExpr(0, 4)),
                CGotoStmt(0x1400),
            )
        ),
        indent="  ",
    ) == "  local_16_4 = 0;\n  goto label_0x1400;"

    function_rendered = format_function_c_lowered(function_facts)
    assert (
        "function 0x1000 name=main frame_size=? dynamic_sp=no params=2 locals=1 returns=1 stmts=9 pending=[]"
        in function_rendered
    )
    assert "signature:" in function_rendered
    assert "param x10 int32_t arg_x10_4" in function_rendered
    assert "param stack+0 int32_t local_0_4" in function_rendered
    assert "returns:" in function_rendered
    assert "return x10 int32_t" in function_rendered
    assert "call_0x1300(32, arg_x10_4);" in function_rendered
    assert "while (local_16_4 < 3)" in function_rendered
    assert "continue /* 0x1010 */;" in function_rendered
    assert "return [x10=local_16_4];" in function_rendered

    program_rendered = format_program_c_lowered(program)
    assert "pending: 0x2000" in program_rendered
    assert "invalidated: 0x1000" in program_rendered
    assert "functions:" in program_rendered
    assert "goto label_0x1400;" in program_rendered


def test_c_lowering_switch_stmt_pretty_output_is_stable() -> None:
    switch = CSwitchStmt(
        selector=CNameExpr("arg_x10_4"),
        cases=(
            CSwitchCase(
                value=0,
                body=CStmtSequence(
                    (
                        CAssignStmt(CNameExpr("local_12_4"), CConstExpr(1, 4)),
                        CBreakStmt(0x1300),
                    )
                ),
            ),
            CSwitchCase(
                value=1,
                body=CStmtSequence(
                    (
                        CAssignStmt(CNameExpr("local_12_4"), CConstExpr(2, 4)),
                        CBreakStmt(0x1300),
                    )
                ),
            ),
        ),
        default_body=CStmtSequence(
            (
                CAssignStmt(CNameExpr("local_12_4"), CConstExpr(-1, 4)),
                CBreakStmt(0x1300),
            )
        ),
    )

    assert format_c_stmt(switch) == "switch (arg_x10_4)"
    assert format_c_stmt_sequence(CStmtSequence((switch,)), indent="  ") == (
        "  switch (arg_x10_4)\n"
        "  case 0:\n"
        "    local_12_4 = 1;\n"
        "    break /* 0x1300 */;\n"
        "  case 1:\n"
        "    local_12_4 = 2;\n"
        "    break /* 0x1300 */;\n"
        "  default:\n"
        "    local_12_4 = -1;\n"
        "    break /* 0x1300 */;"
    )


def test_c_lowering_expr_formatting_normalizes_safe_surface_syntax() -> None:
    negative_add = CBinaryExpr("+", CNameExpr("local_16_4"), CConstExpr(-2, 4))
    inverted_less = CUnaryExpr(
        "!",
        CBinaryExpr("<", CNameExpr("arg_x10_4"), CNameExpr("arg_x11_4")),
    )
    shifted_sum = CBinaryExpr(
        "+",
        CBinaryExpr(
            "+",
            CBinaryExpr("<<", CNameExpr("arg_x10_4"), CConstExpr(1, 4)),
            CNameExpr("arg_x10_4"),
        ),
        CConstExpr(1, 4),
    )

    assert format_c_expr(negative_add) == "local_16_4 - 2"
    assert format_c_expr(inverted_less) == "arg_x10_4 >= arg_x11_4"
    assert format_c_expr(shifted_sum) == "(arg_x10_4 << 1) + arg_x10_4 + 1"
    assert format_c_stmt(CIfStmt(condition=inverted_less)) == "if (arg_x10_4 >= arg_x11_4)"


def test_c_lowering_model_rejects_parameter_without_location() -> None:
    with pytest.raises(ValueError, match="must carry exactly one non-negative register or stack offset"):
        CLoweredVariable(
            name="arg_x10_4",
            kind=CLoweredVariableKind.PARAMETER,
            ctype=CLoweredType("int32_t", 4),
        )


def test_c_lowering_model_rejects_parameter_with_both_register_and_stack_offset() -> None:
    with pytest.raises(ValueError, match="must carry exactly one non-negative register or stack offset"):
        CLoweredVariable(
            name="arg_x10_4",
            kind=CLoweredVariableKind.PARAMETER,
            ctype=CLoweredType("int32_t", 4),
            register=10,
            stack_offset=0,
        )


def test_program_c_lowered_rejects_scheduler_state_drift() -> None:
    structured_program = build_structured_program(
        root_entry=0x1000,
        function_specs=(
            FunctionSpec(
                dataflow=function(
                    0x1000,
                    (block(0x1000, instruction(0x1000)),),
                    name="main",
                )
            ),
        ),
        pending_entries=(0x2000,),
    )
    function_facts = FunctionCLowered(structured=structured_program.functions[0x1000])

    with pytest.raises(ValueError, match="pending entries must match structured facts"):
        ProgramCLowered(
            structured=structured_program,
            functions={0x1000: function_facts},
            pending_entries=(),
            invalidated_entries=structured_program.invalidated_entries,
            scheduler_invalidations=structured_program.scheduler_invalidations,
        )
