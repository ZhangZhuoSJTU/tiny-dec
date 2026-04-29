"""Deterministic pretty-printers for stage-16 structured-control snapshots."""

from __future__ import annotations

from tiny_dec.ir.pretty_containers import format_call_graph_edge
from tiny_dec.structuring.models import (
    FunctionStructuredFacts,
    ProgramStructuredFacts,
    StructuredBlock,
    StructuredBreak,
    StructuredContinue,
    StructuredGoto,
    StructuredIf,
    StructuredSequence,
    StructuredStmt,
    StructuredSwitch,
    StructuredSwitchCase,
    StructuredWhile,
)


def format_structured_block(block: StructuredBlock) -> str:
    return block.to_pretty()


def format_structured_goto(node: StructuredGoto) -> str:
    return node.to_pretty()


def format_structured_break(node: StructuredBreak) -> str:
    return node.to_pretty()


def format_structured_continue(node: StructuredContinue) -> str:
    return node.to_pretty()


def format_structured_if(node: StructuredIf) -> str:
    return node.to_pretty()


def format_structured_switch_case(case: StructuredSwitchCase) -> str:
    return case.to_pretty()


def format_structured_switch(node: StructuredSwitch) -> str:
    return node.to_pretty()


def format_structured_while(node: StructuredWhile) -> str:
    return node.to_pretty()


def format_structured_sequence(sequence: StructuredSequence, indent: str = "") -> str:
    if not sequence.items:
        return f"{indent}<none>"
    lines: list[str] = []
    for item in sequence.items:
        lines.extend(_format_structured_stmt(item, indent))
    return "\n".join(lines)


def _format_structured_stmt(item: StructuredStmt, indent: str) -> list[str]:
    if isinstance(item, StructuredBlock):
        return [f"{indent}{format_structured_block(item)}"]
    if isinstance(item, StructuredGoto):
        return [f"{indent}{format_structured_goto(item)}"]
    if isinstance(item, StructuredBreak):
        return [f"{indent}{format_structured_break(item)}"]
    if isinstance(item, StructuredContinue):
        return [f"{indent}{format_structured_continue(item)}"]
    if isinstance(item, StructuredWhile):
        lines = [f"{indent}{format_structured_while(item)}", f"{indent}body:"]
        lines.extend(format_structured_sequence(item.body, indent + "  ").splitlines())
        return lines
    if isinstance(item, StructuredSwitch):
        lines = [f"{indent}{format_structured_switch(item)}", f"{indent}cases:"]
        for case in item.cases:
            lines.append(f"{indent}  {format_structured_switch_case(case)}")
            lines.extend(format_structured_sequence(case.body, indent + "    ").splitlines())
        lines.append(f"{indent}default:")
        lines.extend(format_structured_sequence(item.default_body, indent + "    ").splitlines())
        return lines
    lines = [f"{indent}{format_structured_if(item)}", f"{indent}then:"]
    lines.extend(format_structured_sequence(item.then_body, indent + "  ").splitlines())
    lines.append(f"{indent}else:")
    lines.extend(format_structured_sequence(item.else_body, indent + "  ").splitlines())
    return lines


def format_function_structured_facts(function: FunctionStructuredFacts) -> str:
    pending = ", ".join(f"0x{entry:x}" for entry in function.pending_entries)
    frame_size = str(function.frame_size) if function.frame_size is not None else "?"
    lines = [
        (
            f"function 0x{function.entry:x} name={function.name or '?'} "
            f"frame_size={frame_size} "
            f"dynamic_sp={'yes' if function.dynamic_stack_pointer else 'no'} "
            f"stmts={function.statement_count} "
            f"loops={function.loop_count} "
            f"ifs={function.if_count} "
            f"switches={function.switch_count} "
            f"gotos={function.goto_count} "
            f"pending=[{pending}]"
        ),
        "body:",
    ]
    if function.body.items:
        lines.extend(format_structured_sequence(function.body, "  ").splitlines())
    else:
        lines.append("  <none>")
    return "\n".join(lines)


def format_program_structured_facts(program: ProgramStructuredFacts) -> str:
    upstream = (
        program.interproc.ranges.variables.aggregate_types.scalar_types.memory.stack.calls.ssa.dataflow.program
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
    if program.interproc.ranges.variables.aggregate_types.scalar_types.memory.stack.calls.call_graph:
        lines.extend(
            f"  {format_call_graph_edge(edge)}"
            for edge in program.interproc.ranges.variables.aggregate_types.scalar_types.memory.stack.calls.call_graph
        )
    else:
        lines.append("  <none>")

    lines.append("scheduler_invalidations:")
    if program.scheduler_invalidations:
        lines.extend(f"  {item.to_pretty()}" for item in program.scheduler_invalidations)
    else:
        lines.append("  <none>")

    lines.append("functions:")
    for function in program.ordered_functions():
        lines.extend(
            f"  {line}" for line in format_function_structured_facts(function).splitlines()
        )
    return "\n".join(lines)
