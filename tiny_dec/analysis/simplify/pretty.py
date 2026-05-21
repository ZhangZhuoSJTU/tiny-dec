"""Deterministic pretty-printers for stage-5 canonical IR snapshots."""

from __future__ import annotations

from tiny_dec.analysis.simplify.models import (
    CanonicalBlock,
    CanonicalFunctionIR,
    CanonicalInstruction,
    CanonicalProgramIR,
)
from tiny_dec.ir.pretty_containers import format_call_graph_edge, format_callsite


def format_canonical_instruction(instruction: CanonicalInstruction) -> list[str]:
    lines = [instruction.instruction.to_pretty_line()]
    if instruction.ops:
        lines.extend(f"  {op.to_pretty()}" for op in instruction.ops)
    else:
        lines.append("  <none>")
    return lines


def format_canonical_block(block: CanonicalBlock) -> list[str]:
    lines = [block.header_pretty()]
    for instruction in block.instructions:
        rendered = format_canonical_instruction(instruction)
        lines.append(f"  {rendered[0]}")
        lines.extend(f"  {line}" for line in rendered[1:])
    return lines


def format_canonical_function_ir(function: CanonicalFunctionIR) -> str:
    return_blocks = ", ".join(f"0x{entry:x}" for entry in function.return_blocks)
    direct_callees = ", ".join(f"0x{entry:x}" for entry in function.direct_callees)
    lines = [
        (
            f"function 0x{function.entry:x} name={function.name or '?'} "
            f"blocks={len(function.blocks)} "
            f"instructions={function.instruction_count} "
            f"ops={function.op_count} "
            f"returns=[{return_blocks}] "
            f"callees=[{direct_callees}]"
        ),
        "callsites:",
    ]

    if function.callsites:
        lines.extend(f"  {format_callsite(callsite)}" for callsite in function.callsites)
    else:
        lines.append("  <none>")

    lines.append("blocks:")
    for block in function.ordered_blocks():
        lines.extend(f"  {line}" for line in format_canonical_block(block))
    return "\n".join(lines)


def format_canonical_program_ir(program: CanonicalProgramIR) -> str:
    order_text = ", ".join(f"0x{entry:x}" for entry in program.ordered_function_entries())
    pending_text = ", ".join(f"0x{entry:x}" for entry in program.pending_entries)
    invalidated_text = ", ".join(
        f"0x{entry:x}" for entry in program.invalidated_entries
    )
    lines = [
        f"root: 0x{program.root_entry:x}",
        f"order: {order_text}" if order_text else "order:",
        f"pending: {pending_text}" if pending_text else "pending:",
        f"invalidated: {invalidated_text}" if invalidated_text else "invalidated:",
        "externals:",
    ]

    if program.externals:
        lines.extend(f"  {external.to_pretty_line()}" for external in program.externals)
    else:
        lines.append("  <none>")

    lines.append("call_graph:")
    if program.call_graph:
        lines.extend(f"  {format_call_graph_edge(edge)}" for edge in program.call_graph)
    else:
        lines.append("  <none>")

    lines.append("functions:")
    for function in program.ordered_functions():
        lines.extend(f"  {line}" for line in format_canonical_function_ir(function).splitlines())
    return "\n".join(lines)
