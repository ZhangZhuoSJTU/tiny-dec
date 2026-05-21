"""Deterministic pretty-printers for stage-14 range-refinement snapshots."""

from __future__ import annotations

from tiny_dec.analysis.range.models import (
    BranchRangeRefinement,
    FunctionRangeFacts,
    IntegerRange,
    ProgramRangeFacts,
    ValueRangeFact,
    VariableRangeFact,
)
from tiny_dec.ir.pretty_containers import format_call_graph_edge


def format_integer_range(value_range: IntegerRange) -> str:
    return value_range.to_pretty()


def format_value_range_fact(fact: ValueRangeFact) -> str:
    return fact.to_pretty()


def format_variable_range_fact(fact: VariableRangeFact) -> str:
    return fact.to_pretty()


def format_branch_range_refinement(refinement: BranchRangeRefinement) -> str:
    return refinement.to_pretty()


def format_function_range_facts(function: FunctionRangeFacts) -> str:
    pending = ", ".join(f"0x{entry:x}" for entry in function.pending_entries)
    frame_size = str(function.frame_size) if function.frame_size is not None else "?"
    lines = [
        (
            f"function 0x{function.entry:x} name={function.name or '?'} "
            f"frame_size={frame_size} "
            f"dynamic_sp={'yes' if function.dynamic_stack_pointer else 'no'} "
            f"value_ranges={len(function.value_ranges)} "
            f"variable_ranges={len(function.variable_ranges)} "
            f"branch_refinements={len(function.branch_refinements)} "
            f"pending=[{pending}]"
        ),
        "variables:",
    ]
    if function.variable_ranges:
        lines.extend(f"  {format_variable_range_fact(fact)}" for fact in function.variable_ranges)
    else:
        lines.append("  <none>")

    lines.append("values:")
    if function.value_ranges:
        lines.extend(f"  {format_value_range_fact(fact)}" for fact in function.value_ranges)
    else:
        lines.append("  <none>")

    lines.append("branches:")
    if function.branch_refinements:
        lines.extend(
            f"  {format_branch_range_refinement(fact)}"
            for fact in function.branch_refinements
        )
    else:
        lines.append("  <none>")
    return "\n".join(lines)


def format_program_range_facts(program: ProgramRangeFacts) -> str:
    upstream = program.variables.aggregate_types.scalar_types.memory.stack.calls.ssa.dataflow.program
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
    if program.variables.aggregate_types.scalar_types.memory.stack.calls.call_graph:
        lines.extend(
            f"  {format_call_graph_edge(edge)}"
            for edge in program.variables.aggregate_types.scalar_types.memory.stack.calls.call_graph
        )
    else:
        lines.append("  <none>")

    lines.append("functions:")
    for function in program.ordered_functions():
        lines.extend(f"  {line}" for line in format_function_range_facts(function).splitlines())
    return "\n".join(lines)
