from __future__ import annotations

from tiny_dec.analysis.calls import build_program_call_facts, format_program_call_facts
from tiny_dec.analysis.dataflow import build_program_dataflow, format_program_dataflow
from tiny_dec.analysis.highvars import (
    build_program_variable_facts,
    format_program_variable_facts,
)
from tiny_dec.analysis.interproc import (
    build_program_interproc_facts,
    format_program_interproc_facts,
)
from tiny_dec.analysis.memory import build_program_memory_facts, format_program_memory_facts
from tiny_dec.analysis.range import build_program_range_facts, format_program_range_facts
from tiny_dec.analysis.simplify import build_canonical_program_ir, format_canonical_program_ir
from tiny_dec.analysis.ssa import build_ssa_program_ir, format_ssa_program_ir
from tiny_dec.analysis.stack import build_program_stack_facts, format_program_stack_facts
from tiny_dec.analysis.types import (
    build_program_aggregate_type_facts,
    build_program_scalar_type_facts,
    format_program_aggregate_type_facts,
    format_program_scalar_type_facts,
)
from tiny_dec.decode import decode_window_lines
from tiny_dec.disasm import disassemble_function, format_disasm
from tiny_dec.ir import lift_window_lines
from tiny_dec.ir.containers import build_program_ir
from tiny_dec.ir.pretty_containers import format_program_ir
from tiny_dec.loader import ProgramView
from tiny_dec.c_emit import (
    build_program_c_lowered,
    format_program_c_lowered,
)
from tiny_dec.pipeline.passes import render_scheduled_c_program
from tiny_dec.structuring import (
    build_program_structured_facts,
    format_program_structured_facts,
)


_DEFAULT_STAGE_LIMIT = 8


def resolve_function_address(view: ProgramView, selector: str) -> int | None:
    if selector.startswith("0x"):
        return int(selector, 16)
    if selector.isdigit():
        return int(selector, 10)
    if selector == "main":
        return view.find_main().address
    return view.get_symbol_address(selector)


def decompile_function(
    view: ProgramView, *, func: str = "main", stage: str = "c"
) -> str:
    """Pipeline entrypoint with real outputs through post_18_c_printer_pipeline."""
    address = resolve_function_address(view, func)

    if stage == "c":
        if address is None:
            return f"/* unresolved function selector: {func} */"
        return render_scheduled_c_program(view, address)

    lines = [
        "tiny_dec decompile",
        f"binary: {view.path}",
        f"arch: {view.arch} ({view.bits}-bit, {view.endian}-endian)",
        f"entrypoint: {view.entrypoint:#x}",
        f"target_function: {func}",
        f"target_address: {address:#x}"
        if address is not None
        else "target_address: <unresolved>",
        f"stage: {stage}",
    ]

    if stage == "loader":
        lines.append("loader:")
        lines.extend(f"  {line}" for line in view.format_snapshot().splitlines())
        return "\n".join(lines)

    if stage == "decode":
        if address is None:
            lines.append("decode: <unresolved>")
            return "\n".join(lines)

        lines.append("decode:")
        lines.extend(
            f"  {line}"
            for line in decode_window_lines(view, address, limit=_DEFAULT_STAGE_LIMIT)
        )
        return "\n".join(lines)

    if stage == "pcode":
        if address is None:
            lines.append("pcode: <unresolved>")
            return "\n".join(lines)

        lines.append("pcode:")
        lines.extend(
            f"  {line}"
            for line in lift_window_lines(view, address, limit=_DEFAULT_STAGE_LIMIT)
        )
        return "\n".join(lines)

    if stage == "disasm":
        if address is None:
            lines.append("disasm: <unresolved>")
            return "\n".join(lines)

        lines.append("disasm:")
        lines.extend(
            f"  {line}"
            for line in format_disasm(disassemble_function(view, address)).splitlines()
        )
        return "\n".join(lines)

    if stage == "ir":
        if address is None:
            lines.append("ir: <unresolved>")
            return "\n".join(lines)

        lines.append("ir:")
        lines.extend(
            f"  {line}"
            for line in format_program_ir(build_program_ir(view, address)).splitlines()
        )
        return "\n".join(lines)

    if stage == "simplify":
        if address is None:
            lines.append("simplify: <unresolved>")
            return "\n".join(lines)

        lines.append("simplify:")
        lines.extend(
            f"  {line}"
            for line in format_canonical_program_ir(
                build_canonical_program_ir(view, address)
            ).splitlines()
        )
        return "\n".join(lines)

    if stage == "dataflow":
        if address is None:
            lines.append("dataflow: <unresolved>")
            return "\n".join(lines)

        lines.append("dataflow:")
        lines.extend(
            f"  {line}"
            for line in format_program_dataflow(
                build_program_dataflow(view, address)
            ).splitlines()
        )
        return "\n".join(lines)

    if stage == "ssa":
        if address is None:
            lines.append("ssa: <unresolved>")
            return "\n".join(lines)

        lines.append("ssa:")
        lines.extend(
            f"  {line}"
            for line in format_ssa_program_ir(
                build_ssa_program_ir(view, address)
            ).splitlines()
        )
        return "\n".join(lines)

    if stage == "calls":
        if address is None:
            lines.append("calls: <unresolved>")
            return "\n".join(lines)

        lines.append("calls:")
        lines.extend(
            f"  {line}"
            for line in format_program_call_facts(
                build_program_call_facts(view, address)
            ).splitlines()
        )
        return "\n".join(lines)

    if stage == "stack":
        if address is None:
            lines.append("stack: <unresolved>")
            return "\n".join(lines)

        lines.append("stack:")
        lines.extend(
            f"  {line}"
            for line in format_program_stack_facts(
                build_program_stack_facts(view, address)
            ).splitlines()
        )
        return "\n".join(lines)

    if stage == "memory":
        if address is None:
            lines.append("memory: <unresolved>")
            return "\n".join(lines)

        lines.append("memory:")
        lines.extend(
            f"  {line}"
            for line in format_program_memory_facts(
                build_program_memory_facts(view, address)
            ).splitlines()
        )
        return "\n".join(lines)

    if stage == "scalar_types":
        if address is None:
            lines.append("scalar_types: <unresolved>")
            return "\n".join(lines)

        lines.append("scalar_types:")
        lines.extend(
            f"  {line}"
            for line in format_program_scalar_type_facts(
                build_program_scalar_type_facts(view, address)
            ).splitlines()
        )
        return "\n".join(lines)

    if stage == "aggregate_types":
        if address is None:
            lines.append("aggregate_types: <unresolved>")
            return "\n".join(lines)

        lines.append("aggregate_types:")
        lines.extend(
            f"  {line}"
            for line in format_program_aggregate_type_facts(
                build_program_aggregate_type_facts(view, address)
            ).splitlines()
        )
        return "\n".join(lines)

    if stage == "variables":
        if address is None:
            lines.append("variables: <unresolved>")
            return "\n".join(lines)

        lines.append("variables:")
        lines.extend(
            f"  {line}"
            for line in format_program_variable_facts(
                build_program_variable_facts(view, address)
            ).splitlines()
        )
        return "\n".join(lines)

    if stage == "range":
        if address is None:
            lines.append("range: <unresolved>")
            return "\n".join(lines)

        lines.append("range:")
        lines.extend(
            f"  {line}"
            for line in format_program_range_facts(
                build_program_range_facts(view, address)
            ).splitlines()
        )
        return "\n".join(lines)

    if stage == "interproc":
        if address is None:
            lines.append("interproc: <unresolved>")
            return "\n".join(lines)

        lines.append("interproc:")
        lines.extend(
            f"  {line}"
            for line in format_program_interproc_facts(
                build_program_interproc_facts(view, address)
            ).splitlines()
        )
        return "\n".join(lines)

    if stage == "structuring":
        if address is None:
            lines.append("structuring: <unresolved>")
            return "\n".join(lines)

        lines.append("structuring:")
        lines.extend(
            f"  {line}"
            for line in format_program_structured_facts(
                build_program_structured_facts(view, address)
            ).splitlines()
        )
        return "\n".join(lines)

    if stage == "c_lowering":
        if address is None:
            lines.append("c_lowering: <unresolved>")
            return "\n".join(lines)

        lines.append("c_lowering:")
        lines.extend(
            f"  {line}"
            for line in format_program_c_lowered(
                build_program_c_lowered(view, address)
            ).splitlines()
        )
        return "\n".join(lines)

    raise ValueError(f"unsupported decompile stage: {stage}")
