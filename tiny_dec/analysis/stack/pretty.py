"""Deterministic pretty-printers for stage-9 stack recovery snapshots."""

from __future__ import annotations

from tiny_dec.analysis.stack.models import (
    FunctionStackFacts,
    ProgramStackFacts,
    StackAccess,
    StackFrameBase,
    StackSlot,
)
from tiny_dec.ir.pretty_containers import format_call_graph_edge


def format_stack_frame_base(base: StackFrameBase) -> str:
    return base.to_pretty()


def format_stack_access(access: StackAccess) -> str:
    return access.to_pretty()


def format_stack_slot(slot: StackSlot) -> str:
    return slot.to_pretty()


def format_function_stack_facts(function: FunctionStackFacts) -> str:
    pending = ", ".join(f"0x{entry:x}" for entry in function.pending_entries)
    frame_size = str(function.frame_size) if function.frame_size is not None else "?"
    frame_pointer = (
        format_stack_frame_base(function.frame_pointer)
        if function.frame_pointer is not None
        else "none"
    )
    lines = [
        (
            f"function 0x{function.entry:x} name={function.name or '?'} "
            f"frame_size={frame_size} fp={frame_pointer} "
            f"dynamic_sp={'yes' if function.dynamic_stack_pointer else 'no'} "
            f"slots={len(function.slots)} pending=[{pending}]"
        ),
        "slots:",
    ]
    if function.slots:
        for slot in function.slots:
            lines.append(f"  {format_stack_slot(slot)}")
            for access in slot.accesses:
                lines.append(f"    {format_stack_access(access)}")
    else:
        lines.append("  <none>")
    return "\n".join(lines)


def format_program_stack_facts(program: ProgramStackFacts) -> str:
    upstream = program.calls.ssa.dataflow.program
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
    if program.calls.call_graph:
        lines.extend(f"  {format_call_graph_edge(edge)}" for edge in program.calls.call_graph)
    else:
        lines.append("  <none>")

    lines.append("functions:")
    for function in program.ordered_functions():
        lines.extend(
            f"  {line}" for line in format_function_stack_facts(function).splitlines()
        )
    return "\n".join(lines)
