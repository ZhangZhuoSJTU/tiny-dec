"""Deterministic pretty-printers for stage-8 call modeling snapshots."""

from __future__ import annotations

from tiny_dec.analysis.calls.models import (
    CallABI,
    CallRegisterValue,
    CallStackValue,
    FunctionCallFacts,
    KnownExternalSignature,
    ModeledCallSite,
    ProgramCallFacts,
)
from tiny_dec.ir.pretty_containers import format_call_graph_edge


def format_call_abi(abi: CallABI) -> str:
    return abi.to_pretty()


def format_call_register_value(value: CallRegisterValue) -> str:
    return value.to_pretty()


def format_call_stack_value(value: CallStackValue) -> str:
    return value.to_pretty()


def format_known_external_signature(signature: KnownExternalSignature) -> str:
    return signature.to_pretty()


def format_modeled_callsite(callsite: ModeledCallSite) -> str:
    return callsite.to_pretty()


def format_function_call_facts(function: FunctionCallFacts) -> str:
    pending = ", ".join(f"0x{entry:x}" for entry in function.pending_entries)
    lines = [
        (
            f"function 0x{function.entry:x} name={function.name or '?'} "
            f"callsites={len(function.callsites)} "
            f"pending=[{pending}]"
        ),
        f"abi: {format_call_abi(function.abi)}",
        "callsites:",
    ]
    if function.callsites:
        lines.extend(f"  {format_modeled_callsite(callsite)}" for callsite in function.callsites)
    else:
        lines.append("  <none>")
    return "\n".join(lines)


def format_program_call_facts(program: ProgramCallFacts) -> str:
    ssa_program = program.ssa
    upstream = ssa_program.dataflow.program
    order_text = ", ".join(f"0x{entry:x}" for entry in program.ordered_function_entries())
    pending_text = ", ".join(f"0x{entry:x}" for entry in program.pending_entries)
    invalidated_text = ", ".join(f"0x{entry:x}" for entry in program.invalidated_entries)
    lines = [
        f"root: 0x{upstream.root_entry:x}",
        f"order: {order_text}" if order_text else "order:",
        f"pending: {pending_text}" if pending_text else "pending:",
        f"invalidated: {invalidated_text}" if invalidated_text else "invalidated:",
        f"abi: {format_call_abi(program.abi)}",
        "externals:",
    ]

    if upstream.externals:
        lines.extend(f"  {external.to_pretty_line()}" for external in upstream.externals)
    else:
        lines.append("  <none>")

    lines.append("call_graph:")
    if program.call_graph:
        lines.extend(f"  {format_call_graph_edge(edge)}" for edge in program.call_graph)
    else:
        lines.append("  <none>")

    lines.append("functions:")
    for function in program.ordered_functions():
        lines.extend(f"  {line}" for line in format_function_call_facts(function).splitlines())
    return "\n".join(lines)
