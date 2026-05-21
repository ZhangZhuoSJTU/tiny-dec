"""Deterministic pretty-printers for stage-17 C-like IR and stage-18 C text."""

from __future__ import annotations

from tiny_dec.ir.pretty_containers import format_call_graph_edge
from tiny_dec.c_emit.models import (
    CAssignStmt,
    CBreakStmt,
    CCallExpr,
    CCallTarget,
    CConstExpr,
    CContinueStmt,
    CExpr,
    CExprStmt,
    CFieldExpr,
    CGlobalExpr,
    CIfStmt,
    CLoweredReturn,
    CLoweredType,
    CLoweredVariable,
    CNameExpr,
    CRawExpr,
    CReturnBinding,
    CReturnStmt,
    CStmt,
    CStmtSequence,
    CSwitchStmt,
    CUnaryExpr,
    CWhileStmt,
    CBinaryExpr,
    CGotoStmt,
    FunctionCLowered,
    FunctionCRendered,
    ProgramCLowered,
    ProgramCRendered,
)


def format_c_lowered_type(ctype: CLoweredType) -> str:
    return ctype.to_pretty()


def format_c_lowered_variable(variable: CLoweredVariable) -> str:
    return variable.to_pretty()


def format_c_lowered_return(carrier: CLoweredReturn) -> str:
    return carrier.to_pretty()


def format_c_call_target(target: CCallTarget) -> str:
    return target.to_pretty()


def format_c_expr(expr: CExpr) -> str:
    if isinstance(expr, CNameExpr):
        return expr.to_pretty()
    if isinstance(expr, CFieldExpr):
        return expr.to_pretty()
    if isinstance(expr, CGlobalExpr):
        return expr.to_pretty()
    if isinstance(expr, CRawExpr):
        return expr.to_pretty()
    if isinstance(expr, CConstExpr):
        return expr.to_pretty()
    if isinstance(expr, CUnaryExpr):
        return expr.to_pretty()
    if isinstance(expr, CBinaryExpr):
        return expr.to_pretty()
    if isinstance(expr, CCallExpr):
        return expr.to_pretty()
    raise TypeError(f"unsupported c-lowered expression: {type(expr)!r}")


def format_c_return_binding(binding: CReturnBinding) -> str:
    return binding.to_pretty()


def format_c_stmt(stmt: CStmt) -> str:
    return stmt.to_pretty()


def format_c_stmt_sequence(sequence: CStmtSequence, indent: str = "") -> str:
    if not sequence.items:
        return f"{indent}<none>"
    lines: list[str] = []
    for item in sequence.items:
        lines.extend(_format_stmt(item, indent))
    return "\n".join(lines)


def _format_stmt(item: CStmt, indent: str) -> list[str]:
    if isinstance(item, (CAssignStmt, CExprStmt, CReturnStmt, CGotoStmt, CBreakStmt, CContinueStmt)):
        return [f"{indent}{format_c_stmt(item)}"]
    if isinstance(item, CWhileStmt):
        lines = [f"{indent}{format_c_stmt(item)}", f"{indent}body:"]
        lines.extend(format_c_stmt_sequence(item.body, indent + "  ").splitlines())
        return lines
    if isinstance(item, CSwitchStmt):
        lines = [f"{indent}{format_c_stmt(item)}"]
        for case in item.cases:
            lines.append(f"{indent}{case.to_pretty()}")
            lines.extend(format_c_stmt_sequence(case.body, indent + "  ").splitlines())
        lines.append(f"{indent}default:")
        lines.extend(format_c_stmt_sequence(item.default_body, indent + "  ").splitlines())
        return lines
    assert isinstance(item, CIfStmt)
    lines = [f"{indent}{format_c_stmt(item)}", f"{indent}then:"]
    lines.extend(format_c_stmt_sequence(item.then_body, indent + "  ").splitlines())
    lines.append(f"{indent}else:")
    lines.extend(format_c_stmt_sequence(item.else_body, indent + "  ").splitlines())
    return lines


def format_function_c_lowered(function: FunctionCLowered) -> str:
    pending = ", ".join(f"0x{entry:x}" for entry in function.pending_entries)
    frame_size = str(function.frame_size) if function.frame_size is not None else "?"
    lines = [
        (
            f"function 0x{function.entry:x} name={function.name or '?'} "
            f"frame_size={frame_size} "
            f"dynamic_sp={'yes' if function.dynamic_stack_pointer else 'no'} "
            f"params={len(function.parameters)} "
            f"locals={len(function.locals)} "
            f"returns={len(function.returns)} "
            f"stmts={function.statement_count} "
            f"pending=[{pending}]"
        ),
        "signature:",
    ]
    if function.parameters:
        lines.extend(f"  {format_c_lowered_variable(parameter)}" for parameter in function.parameters)
    else:
        lines.append("  <none>")

    lines.append("returns:")
    if function.returns:
        lines.extend(f"  {format_c_lowered_return(carrier)}" for carrier in function.returns)
    else:
        lines.append("  <none>")

    lines.append("locals:")
    if function.locals:
        lines.extend(f"  {format_c_lowered_variable(local)}" for local in function.locals)
    else:
        lines.append("  <none>")

    lines.append("body:")
    if function.body.items:
        lines.extend(format_c_stmt_sequence(function.body, "  ").splitlines())
    else:
        lines.append("  <none>")
    return "\n".join(lines)


def format_program_c_lowered(program: ProgramCLowered) -> str:
    upstream = (
        program.structured.interproc.ranges.variables.aggregate_types.scalar_types.memory.stack.calls.ssa.dataflow.program
    )
    order_text = ", ".join(f"0x{entry:x}" for entry in program.ordered_function_entries())
    pending_text = ", ".join(f"0x{entry:x}" for entry in program.pending_entries)
    invalidated_text = ", ".join(f"0x{entry:x}" for entry in program.invalidated_entries)
    lines = [
        f"root: 0x{upstream.root_entry:x}",
        f"order: {order_text}" if order_text else "order:",
        f"pending: {pending_text}" if pending_text else "pending:",
        f"invalidated: {invalidated_text}" if invalidated_text else "invalidated:",
        "externals:",
    ]

    if upstream.externals:
        lines.extend(f"  {external.to_pretty_line()}" for external in upstream.externals)
    else:
        lines.append("  <none>")

    lines.append("call_graph:")
    if program.structured.interproc.ranges.variables.aggregate_types.scalar_types.memory.stack.calls.call_graph:
        lines.extend(
            f"  {format_call_graph_edge(edge)}"
            for edge in program.structured.interproc.ranges.variables.aggregate_types.scalar_types.memory.stack.calls.call_graph
        )
    else:
        lines.append("  <none>")

    lines.append("scheduler_invalidations:")
    if program.scheduler_invalidations:
        lines.extend(f"  {item.to_pretty()}" for item in program.scheduler_invalidations)
    else:
        lines.append("  <none>")

    lines.append("functions:")
    for function in program.ordered_functions():
        lines.extend(f"  {line}" for line in format_function_c_lowered(function).splitlines())
    return "\n".join(lines)


def format_function_c_rendered(function: FunctionCRendered) -> str:
    lines: list[str] = []

    if function.includes:
        lines.extend(function.includes)
        lines.append("")

    if function.type_declarations:
        for declaration in function.type_declarations:
            lines.extend(declaration.splitlines())
            lines.append("")

    lines.append(f"{function.prototype} {{")
    if function.local_declarations:
        lines.extend(f"  {line}" for line in function.local_declarations)
        if function.statement_lines:
            lines.append("")
    if function.statement_lines:
        lines.extend(f"  {line}" for line in function.statement_lines)
    lines.append("}")
    return "\n".join(lines)


def format_program_c_rendered(program: ProgramCRendered) -> str:
    pending = ", ".join(f"0x{entry:x}" for entry in program.pending_entries) or "none"
    invalidated = (
        ", ".join(f"0x{entry:x}" for entry in program.invalidated_entries) or "none"
    )
    scheduler = (
        ", ".join(item.to_pretty() for item in program.scheduler_invalidations) or "none"
    )

    lines = [
        f"/* root: 0x{program.root_entry:x} */",
        f"/* pending: {pending} */",
        f"/* invalidated: {invalidated} */",
        f"/* scheduler_invalidations: {scheduler} */",
    ]

    if program.includes:
        lines.append("")
        lines.extend(program.includes)

    if program.type_declarations:
        lines.append("")
        for index, declaration in enumerate(program.type_declarations):
            if index:
                lines.append("")
            lines.extend(declaration.splitlines())

    if program.prototypes:
        lines.append("")
        lines.extend(program.prototypes)

    for function in program.ordered_functions():
        lines.append("")
        lines.extend(format_function_c_rendered(function).splitlines())

    return "\n".join(lines).rstrip()
