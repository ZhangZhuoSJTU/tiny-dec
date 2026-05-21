"""Deterministic pretty-printers for stage-13 variable-recovery snapshots."""

from __future__ import annotations

from tiny_dec.analysis.highvars.models import (
    FunctionVariableFacts,
    ProgramVariableFacts,
    RecoveredVariable,
    VariableBinding,
)
from tiny_dec.analysis.types.aggregate_pretty import format_aggregate_layout
from tiny_dec.ir.pretty_containers import format_call_graph_edge


def format_variable_binding(binding: VariableBinding) -> str:
    return binding.to_pretty()


def format_recovered_variable(variable: RecoveredVariable) -> str:
    lines = [variable.header_pretty()]
    if variable.aggregate_layout is not None:
        lines.extend(
            f"  {line}" for line in format_aggregate_layout(variable.aggregate_layout).splitlines()
        )
    return "\n".join(lines)


def format_function_variable_facts(function: FunctionVariableFacts) -> str:
    pending = ", ".join(f"0x{entry:x}" for entry in function.pending_entries)
    frame_size = str(function.frame_size) if function.frame_size is not None else "?"
    lines = [
        (
            f"function 0x{function.entry:x} name={function.name or '?'} "
            f"frame_size={frame_size} "
            f"dynamic_sp={'yes' if function.dynamic_stack_pointer else 'no'} "
            f"variables={len(function.variables)} pending=[{pending}]"
        ),
        "variables:",
    ]
    if function.variables:
        for variable in function.variables:
            lines.extend(f"  {line}" for line in format_recovered_variable(variable).splitlines())
    else:
        lines.append("  <none>")
    return "\n".join(lines)


def format_program_variable_facts(program: ProgramVariableFacts) -> str:
    upstream = program.aggregate_types.scalar_types.memory.stack.calls.ssa.dataflow.program
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
    if program.aggregate_types.scalar_types.memory.stack.calls.call_graph:
        lines.extend(
            f"  {format_call_graph_edge(edge)}"
            for edge in program.aggregate_types.scalar_types.memory.stack.calls.call_graph
        )
    else:
        lines.append("  <none>")

    lines.append("functions:")
    for function in program.ordered_functions():
        lines.extend(f"  {line}" for line in format_function_variable_facts(function).splitlines())
    return "\n".join(lines)
