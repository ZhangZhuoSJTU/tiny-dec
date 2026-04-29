"""Deterministic pretty-printers for stage-4 IR containers."""

from __future__ import annotations

from tiny_dec.disasm.pretty import format_disasm
from tiny_dec.ir.function_ir import CallSite, FunctionIR
from tiny_dec.ir.program_ir import CallGraphEdge, ProgramIR


def format_callsite(callsite: CallSite) -> str:
    return callsite.to_pretty()


def format_call_graph_edge(edge: CallGraphEdge) -> str:
    return edge.to_pretty()


def format_function_ir(function: FunctionIR) -> str:
    return_blocks = ", ".join(f"0x{entry:x}" for entry in function.return_blocks)
    direct_callees = ", ".join(f"0x{entry:x}" for entry in function.direct_callees)
    instruction_addresses = ", ".join(
        f"0x{address:x}" for address in function.instruction_index
    )
    lines = [
        (
            f"function 0x{function.entry:x} name={function.name or '?'} "
            f"blocks={len(function.disasm.blocks)} "
            f"instructions={len(function.instruction_index)} "
            f"returns=[{return_blocks}] "
            f"callees=[{direct_callees}]"
        ),
        "callsites:",
    ]

    if function.callsites:
        lines.extend(f"  {format_callsite(callsite)}" for callsite in function.callsites)
    else:
        lines.append("  <none>")

    lines.append(f"instructions: {instruction_addresses}" if instruction_addresses else "instructions:")
    lines.append("disasm:")
    lines.extend(f"  {line}" for line in format_disasm(function.disasm).splitlines())
    return "\n".join(lines)


def format_program_ir(program: ProgramIR) -> str:
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
        lines.extend(f"  {line}" for line in format_function_ir(function).splitlines())
    return "\n".join(lines)
