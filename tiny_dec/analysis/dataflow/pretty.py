"""Deterministic pretty-printers for stage-6 dataflow and target facts."""

from __future__ import annotations

from tiny_dec.analysis.dataflow.models import (
    BlockDataflowFacts,
    FunctionDataflowFacts,
    ProgramDataflowFacts,
    RegisterState,
    RecoveredTarget,
)
from tiny_dec.analysis.simplify.models import CanonicalBlock
from tiny_dec.ir.pretty_containers import format_call_graph_edge


def format_register_state(state: RegisterState) -> str:
    return state.to_pretty()


def format_recovered_target(target: RecoveredTarget) -> str:
    return target.to_pretty()


def format_block_dataflow(block: CanonicalBlock, facts: BlockDataflowFacts) -> list[str]:
    header = (
        f"{block.header_pretty()} "
        f"in=[{format_register_state(facts.in_state)}] "
        f"out=[{format_register_state(facts.out_state)}]"
    )
    lines = [header]
    if facts.recovered_targets:
        lines.extend(f"  {format_recovered_target(target)}" for target in facts.recovered_targets)
    return lines


def format_function_dataflow(facts: FunctionDataflowFacts) -> str:
    function = facts.function
    lines = [
        (
            f"function 0x{function.entry:x} name={function.name or '?'} "
            f"blocks={len(function.blocks)} recovered={len(facts.recovered_targets)}"
        ),
        "recovered_targets:",
    ]

    if facts.recovered_targets:
        lines.extend(
            f"  {format_recovered_target(target)}" for target in facts.recovered_targets
        )
    else:
        lines.append("  <none>")

    lines.append("blocks:")
    for block, block_facts in facts.ordered_blocks():
        lines.extend(f"  {line}" for line in format_block_dataflow(block, block_facts))
    return "\n".join(lines)


def format_program_dataflow(facts: ProgramDataflowFacts) -> str:
    program = facts.program
    order_text = ", ".join(f"0x{entry:x}" for entry in facts.ordered_function_entries())
    pending_text = ", ".join(f"0x{entry:x}" for entry in facts.pending_entries)
    invalidated_text = ", ".join(f"0x{entry:x}" for entry in facts.invalidated_entries)
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
    for function in facts.ordered_functions():
        lines.extend(f"  {line}" for line in format_function_dataflow(function).splitlines())
    return "\n".join(lines)
