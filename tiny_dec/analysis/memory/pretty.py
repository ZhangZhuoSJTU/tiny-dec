"""Deterministic pretty-printers for stage-10 memory modeling snapshots."""

from __future__ import annotations

from tiny_dec.analysis.memory.models import (
    FunctionMemoryFacts,
    MemoryAccess,
    MemoryPartition,
    ProgramMemoryFacts,
)
from tiny_dec.ir.pretty_containers import format_call_graph_edge


def format_memory_access(access: MemoryAccess) -> str:
    return access.to_pretty()


def format_memory_partition(partition: MemoryPartition) -> str:
    return partition.to_pretty()


def format_function_memory_facts(function: FunctionMemoryFacts) -> str:
    pending = ", ".join(f"0x{entry:x}" for entry in function.pending_entries)
    frame_size = str(function.frame_size) if function.frame_size is not None else "?"
    lines = [
        (
            f"function 0x{function.entry:x} name={function.name or '?'} "
            f"frame_size={frame_size} "
            f"dynamic_sp={'yes' if function.dynamic_stack_pointer else 'no'} "
            f"partitions={len(function.partitions)} accesses={function.access_count} "
            f"pending=[{pending}]"
        ),
        "partitions:",
    ]
    if function.partitions:
        for partition in function.partitions:
            lines.append(f"  {format_memory_partition(partition)}")
            for access in partition.accesses:
                lines.append(f"    {format_memory_access(access)}")
    else:
        lines.append("  <none>")
    return "\n".join(lines)


def format_program_memory_facts(program: ProgramMemoryFacts) -> str:
    upstream = program.stack.calls.ssa.dataflow.program
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
    if program.stack.calls.call_graph:
        lines.extend(
            f"  {format_call_graph_edge(edge)}"
            for edge in program.stack.calls.call_graph
        )
    else:
        lines.append("  <none>")

    lines.append("functions:")
    for function in program.ordered_functions():
        lines.extend(
            f"  {line}" for line in format_function_memory_facts(function).splitlines()
        )
    return "\n".join(lines)
