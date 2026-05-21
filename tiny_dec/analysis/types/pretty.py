"""Deterministic pretty-printers for stage-11 scalar type recovery snapshots."""

from __future__ import annotations

from tiny_dec.analysis.types.models import (
    FunctionScalarTypeFacts,
    PartitionScalarTypeFact,
    ProgramScalarTypeFacts,
    ScalarType,
    ValueScalarTypeFact,
)
from tiny_dec.ir.pretty_containers import format_call_graph_edge


def format_scalar_type(scalar_type: ScalarType) -> str:
    return scalar_type.to_pretty()


def format_partition_scalar_type_fact(fact: PartitionScalarTypeFact) -> str:
    return fact.to_pretty()


def format_value_scalar_type_fact(fact: ValueScalarTypeFact) -> str:
    return fact.to_pretty()


def format_function_scalar_type_facts(function: FunctionScalarTypeFacts) -> str:
    pending = ", ".join(f"0x{entry:x}" for entry in function.pending_entries)
    frame_size = str(function.frame_size) if function.frame_size is not None else "?"
    lines = [
        (
            f"function 0x{function.entry:x} name={function.name or '?'} "
            f"frame_size={frame_size} "
            f"dynamic_sp={'yes' if function.dynamic_stack_pointer else 'no'} "
            f"typed_partitions={len(function.partition_facts)} "
            f"typed_values={len(function.value_facts)} pending=[{pending}]"
        ),
        "partitions:",
    ]
    if function.partition_facts:
        lines.extend(f"  {format_partition_scalar_type_fact(fact)}" for fact in function.partition_facts)
    else:
        lines.append("  <none>")

    lines.append("values:")
    if function.value_facts:
        lines.extend(f"  {format_value_scalar_type_fact(fact)}" for fact in function.value_facts)
    else:
        lines.append("  <none>")
    return "\n".join(lines)


def format_program_scalar_type_facts(program: ProgramScalarTypeFacts) -> str:
    upstream = program.memory.stack.calls.ssa.dataflow.program
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
    if program.memory.stack.calls.call_graph:
        lines.extend(
            f"  {format_call_graph_edge(edge)}"
            for edge in program.memory.stack.calls.call_graph
        )
    else:
        lines.append("  <none>")

    lines.append("functions:")
    for function in program.ordered_functions():
        lines.extend(
            f"  {line}" for line in format_function_scalar_type_facts(function).splitlines()
        )
    return "\n".join(lines)
