"""Deterministic pretty-printers for stage-7 SSA snapshots."""

from __future__ import annotations

from tiny_dec.analysis.ssa.models import (
    MemoryVersion,
    SSABlock,
    SSAFunctionIR,
    SSAInstruction,
    SSAMemoryPhiNode,
    SSAName,
    SSAOp,
    SSAProgramIR,
    SSAPhiNode,
    SSAValue,
)
from tiny_dec.ir.pretty_containers import format_call_graph_edge


def format_ssa_name(name: SSAName) -> str:
    return name.to_pretty()


def format_memory_version(version: MemoryVersion) -> str:
    return version.to_pretty()


def format_ssa_value(value: SSAValue) -> str:
    if isinstance(value, SSAName):
        return value.to_pretty()
    return value.to_pretty()


def format_ssa_op(op: SSAOp) -> str:
    return op.to_pretty()


def format_ssa_phi(phi: SSAPhiNode) -> str:
    return phi.to_pretty()


def format_ssa_memory_phi(phi: SSAMemoryPhiNode) -> str:
    return phi.to_pretty()


def format_ssa_instruction(instruction: SSAInstruction) -> list[str]:
    lines = [instruction.instruction.to_pretty_line()]
    if instruction.ops:
        lines.extend(f"  {format_ssa_op(op)}" for op in instruction.ops)
    else:
        lines.append("  <none>")
    return lines


def format_ssa_block(
    block: SSABlock,
    *,
    immediate_dominator: int | None,
    dominance_frontier: tuple[int, ...],
) -> list[str]:
    frontier_text = ", ".join(f"0x{target:x}" for target in dominance_frontier)
    header = (
        f"{block.header_pretty()} "
        f"idom={'<entry>' if immediate_dominator is None else f'0x{immediate_dominator:x}'} "
        f"df=[{frontier_text}]"
    )
    lines = [header]
    if block.memory_phi is not None:
        lines.append(f"  {format_ssa_memory_phi(block.memory_phi)}")
    lines.extend(f"  {format_ssa_phi(phi)}" for phi in block.phis)
    for instruction in block.instructions:
        rendered = format_ssa_instruction(instruction)
        lines.append(f"  {rendered[0]}")
        lines.extend(f"  {line}" for line in rendered[1:])
    return lines


def format_ssa_function_ir(function: SSAFunctionIR) -> str:
    lines = [
        (
            f"function 0x{function.entry:x} name={function.name or '?'} "
            f"reachable={len(function.blocks)} "
            f"unreachable={len(function.unreachable_blocks)} "
            f"phis={function.phi_count}"
        ),
        "live_ins:",
    ]
    if function.live_ins:
        lines.extend(f"  {format_ssa_name(name)}" for name in function.live_ins)
    else:
        lines.append("  <none>")

    lines.append("memory_live_in:")
    if function.memory_live_in is not None:
        lines.append(f"  {format_memory_version(function.memory_live_in)}")
    else:
        lines.append("  <none>")

    lines.append("unreachable_blocks:")
    if function.unreachable_blocks:
        lines.append("  " + ", ".join(f"0x{start:x}" for start in function.unreachable_blocks))
    else:
        lines.append("  <none>")

    lines.append("blocks:")
    for start in function.ordered_block_starts():
        lines.extend(
            f"  {line}"
            for line in format_ssa_block(
                function.blocks[start],
                immediate_dominator=function.immediate_dominators[start],
                dominance_frontier=function.dominance_frontiers[start],
            )
        )
    return "\n".join(lines)


def format_ssa_program_ir(program: SSAProgramIR) -> str:
    dataflow = program.dataflow
    program_ir = dataflow.program
    order_text = ", ".join(f"0x{entry:x}" for entry in program.ordered_function_entries())
    pending_text = ", ".join(f"0x{entry:x}" for entry in dataflow.pending_entries)
    invalidated_text = ", ".join(f"0x{entry:x}" for entry in dataflow.invalidated_entries)
    lines = [
        f"root: 0x{program_ir.root_entry:x}",
        f"order: {order_text}" if order_text else "order:",
        f"pending: {pending_text}" if pending_text else "pending:",
        f"invalidated: {invalidated_text}" if invalidated_text else "invalidated:",
        "externals:",
    ]

    if program_ir.externals:
        lines.extend(f"  {external.to_pretty_line()}" for external in program_ir.externals)
    else:
        lines.append("  <none>")

    lines.append("call_graph:")
    if program_ir.call_graph:
        lines.extend(f"  {format_call_graph_edge(edge)}" for edge in program_ir.call_graph)
    else:
        lines.append("  <none>")

    lines.append("functions:")
    for function in program.ordered_functions():
        lines.extend(f"  {line}" for line in format_ssa_function_ir(function).splitlines())
    return "\n".join(lines)
