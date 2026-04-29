"""Deterministic pretty-printers for stage-12 aggregate layout snapshots."""

from __future__ import annotations

from tiny_dec.analysis.types.aggregate_models import (
    AggregateField,
    AggregateLayout,
    AggregateRoot,
    FunctionAggregateTypeFacts,
    ProgramAggregateTypeFacts,
)
from tiny_dec.ir.pretty_containers import format_call_graph_edge


def format_aggregate_root(root: AggregateRoot) -> str:
    return root.to_pretty()


def format_aggregate_field(field: AggregateField) -> str:
    return field.to_pretty()


def format_aggregate_layout(layout: AggregateLayout) -> str:
    lines = [layout.header_pretty()]
    lines.extend(f"  {format_aggregate_field(field)}" for field in layout.fields)
    return "\n".join(lines)


def format_function_aggregate_type_facts(function: FunctionAggregateTypeFacts) -> str:
    pending = ", ".join(f"0x{entry:x}" for entry in function.pending_entries)
    frame_size = str(function.frame_size) if function.frame_size is not None else "?"
    lines = [
        (
            f"function 0x{function.entry:x} name={function.name or '?'} "
            f"frame_size={frame_size} "
            f"dynamic_sp={'yes' if function.dynamic_stack_pointer else 'no'} "
            f"aggregates={len(function.layouts)} pending=[{pending}]"
        ),
        "aggregates:",
    ]
    if function.layouts:
        for layout in function.layouts:
            lines.extend(f"  {line}" for line in format_aggregate_layout(layout).splitlines())
    else:
        lines.append("  <none>")
    return "\n".join(lines)


def format_program_aggregate_type_facts(program: ProgramAggregateTypeFacts) -> str:
    upstream = program.scalar_types.memory.stack.calls.ssa.dataflow.program
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
    if program.scalar_types.memory.stack.calls.call_graph:
        lines.extend(
            f"  {format_call_graph_edge(edge)}"
            for edge in program.scalar_types.memory.stack.calls.call_graph
        )
    else:
        lines.append("  <none>")

    lines.append("functions:")
    for function in program.ordered_functions():
        lines.extend(
            f"  {line}" for line in format_function_aggregate_type_facts(function).splitlines()
        )
    return "\n".join(lines)
