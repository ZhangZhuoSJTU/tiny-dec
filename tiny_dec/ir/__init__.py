from __future__ import annotations

from typing import Any

from tiny_dec.ir.lift_rv32i import lift_instruction
from tiny_dec.ir.pretty import format_lifted_word, lift_window_lines
from tiny_dec.ir.pcode import (
    PcodeOp,
    PcodeOpcode,
    PcodeSpace,
    Varnode,
    const_varnode,
    format_pcode_ops,
    ram_varnode,
    register_varnode,
    unique_varnode,
)

__all__ = [
    "build_function_ir",
    "build_program_ir",
    "CallGraphEdge",
    "CallGraphEdgeKind",
    "CallSite",
    "FunctionIR",
    "PcodeOp",
    "PcodeOpcode",
    "PcodeSpace",
    "ProgramIR",
    "Varnode",
    "const_varnode",
    "format_call_graph_edge",
    "format_callsite",
    "format_function_ir",
    "format_pcode_ops",
    "format_lifted_word",
    "format_program_ir",
    "lift_instruction",
    "lift_window_lines",
    "ram_varnode",
    "register_varnode",
    "unique_varnode",
]


def __getattr__(name: str) -> Any:
    if name in {"build_function_ir", "build_program_ir"}:
        from tiny_dec.ir.containers import build_function_ir, build_program_ir

        return {
            "build_function_ir": build_function_ir,
            "build_program_ir": build_program_ir,
        }[name]

    if name in {"CallSite", "FunctionIR"}:
        from tiny_dec.ir.function_ir import CallSite, FunctionIR

        return {
            "CallSite": CallSite,
            "FunctionIR": FunctionIR,
        }[name]

    if name in {"CallGraphEdge", "CallGraphEdgeKind", "ProgramIR"}:
        from tiny_dec.ir.program_ir import CallGraphEdge, CallGraphEdgeKind, ProgramIR

        return {
            "CallGraphEdge": CallGraphEdge,
            "CallGraphEdgeKind": CallGraphEdgeKind,
            "ProgramIR": ProgramIR,
        }[name]

    if name in {
        "format_call_graph_edge",
        "format_callsite",
        "format_function_ir",
        "format_program_ir",
    }:
        from tiny_dec.ir.pretty_containers import (
            format_call_graph_edge,
            format_callsite,
            format_function_ir,
            format_program_ir,
        )

        return {
            "format_call_graph_edge": format_call_graph_edge,
            "format_callsite": format_callsite,
            "format_function_ir": format_function_ir,
            "format_program_ir": format_program_ir,
        }[name]

    raise AttributeError(f"module 'tiny_dec.ir' has no attribute {name!r}")
