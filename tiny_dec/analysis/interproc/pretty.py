"""Deterministic pretty-printers for stage-15 interprocedural summaries."""

from __future__ import annotations

from tiny_dec.analysis.interproc.models import (
    FunctionEffectSummary,
    FunctionInterprocFacts,
    InferredPrototype,
    InterprocInvalidation,
    ProgramInterprocFacts,
    PrototypeRegister,
    PrototypeStackParameter,
)
from tiny_dec.ir.pretty_containers import format_call_graph_edge


def format_prototype_parameter(
    carrier: PrototypeRegister | PrototypeStackParameter,
) -> str:
    return carrier.to_pretty()


def format_prototype_register(carrier: PrototypeRegister) -> str:
    return carrier.to_pretty()


def format_prototype_stack_parameter(carrier: PrototypeStackParameter) -> str:
    return carrier.to_pretty()


def format_inferred_prototype(prototype: InferredPrototype) -> str:
    return prototype.to_pretty()


def format_function_effect_summary(summary: FunctionEffectSummary) -> str:
    return summary.to_pretty()


def format_interproc_invalidation(invalidation: InterprocInvalidation) -> str:
    return invalidation.to_pretty()


def format_function_interproc_facts(function: FunctionInterprocFacts) -> str:
    pending = ", ".join(f"0x{entry:x}" for entry in function.pending_entries)
    frame_size = str(function.frame_size) if function.frame_size is not None else "?"
    lines = [
        (
            f"function 0x{function.entry:x} name={function.name or '?'} "
            f"frame_size={frame_size} "
            f"dynamic_sp={'yes' if function.dynamic_stack_pointer else 'no'} "
            f"params={len(function.prototype.parameters)} "
            f"returns={len(function.prototype.returns)} "
            f"no_return={'yes' if function.prototype.no_return else 'no'} "
            f"globals_read={len(function.effects.global_reads)} "
            f"globals_written={len(function.effects.global_writes)} "
            f"pending=[{pending}]"
        ),
        "prototype:",
    ]
    if function.prototype.parameters:
        lines.extend(
            f"  param {format_prototype_parameter(carrier)}"
            for carrier in function.prototype.parameters
        )
    else:
        lines.append("  param <none>")

    if function.prototype.returns:
        lines.extend(
            f"  return {format_prototype_register(carrier)}"
            for carrier in function.prototype.returns
        )
    else:
        lines.append("  return <none>")

    lines.extend(
        [
            "effects:",
            f"  {format_function_effect_summary(function.effects)}",
        ]
    )
    return "\n".join(lines)


def format_program_interproc_facts(program: ProgramInterprocFacts) -> str:
    upstream = (
        program.ranges.variables.aggregate_types.scalar_types.memory.stack.calls.ssa.dataflow.program
    )
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
    if program.ranges.variables.aggregate_types.scalar_types.memory.stack.calls.call_graph:
        lines.extend(
            f"  {format_call_graph_edge(edge)}"
            for edge in program.ranges.variables.aggregate_types.scalar_types.memory.stack.calls.call_graph
        )
    else:
        lines.append("  <none>")

    lines.append("scheduler_invalidations:")
    if program.scheduler_invalidations:
        lines.extend(
            f"  {format_interproc_invalidation(item)}"
            for item in program.scheduler_invalidations
        )
    else:
        lines.append("  <none>")

    lines.append("functions:")
    for function in program.ordered_functions():
        lines.extend(f"  {line}" for line in format_function_interproc_facts(function).splitlines())
    return "\n".join(lines)
