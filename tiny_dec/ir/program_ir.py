"""Stage-4 program-level IR containers built from discovered functions."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from tiny_dec.ir.function_ir import FunctionIR
from tiny_dec.loader import ExternalFunction


class CallGraphEdgeKind(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class CallGraphEdge:
    caller: int
    callsite_address: int
    kind: CallGraphEdgeKind
    callee_address: int | None = None
    callee_name: str | None = None

    def __post_init__(self) -> None:
        if self.caller < 0:
            raise ValueError("call graph edge caller must be non-negative")
        if self.callsite_address < 0:
            raise ValueError("call graph edge callsite must be non-negative")
        if self.kind == CallGraphEdgeKind.INTERNAL and self.callee_address is None:
            raise ValueError("internal call graph edge must carry a callee address")
        if self.kind == CallGraphEdgeKind.EXTERNAL and self.callee_name is None:
            raise ValueError("external call graph edge must carry a callee name")
        if self.kind == CallGraphEdgeKind.UNRESOLVED and self.callee_address is None:
            raise ValueError("unresolved call graph edge must carry a target address")

    def to_pretty(self) -> str:
        prefix = f"0x{self.caller:x}@0x{self.callsite_address:x} -> {self.kind.value}"
        if self.callee_address is not None:
            prefix += f" 0x{self.callee_address:x}"
        if self.callee_name is not None:
            prefix += f" name={self.callee_name}"
        return prefix


@dataclass(slots=True)
class ProgramIR:
    root_entry: int
    functions: dict[int, FunctionIR] = field(default_factory=dict)
    discovery_order: tuple[int, ...] = ()
    externals: tuple[ExternalFunction, ...] = ()
    call_graph: tuple[CallGraphEdge, ...] = ()
    pending_entries: tuple[int, ...] = ()
    invalidated_entries: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.root_entry < 0:
            raise ValueError("program ir root entry must be non-negative")
        if self.functions and self.root_entry not in self.functions:
            raise ValueError("program ir root entry must be present in functions")
        if self.discovery_order:
            missing = [entry for entry in self.discovery_order if entry not in self.functions]
            if missing:
                raise ValueError("program ir discovery order must reference known functions")
            if len(set(self.discovery_order)) != len(self.discovery_order):
                raise ValueError("program ir discovery order must be unique")
        if len(set(self.pending_entries)) != len(self.pending_entries):
            raise ValueError("program ir pending entries must be unique")
        if len(set(self.invalidated_entries)) != len(self.invalidated_entries):
            raise ValueError("program ir invalidated entries must be unique")

    def ordered_function_entries(self) -> tuple[int, ...]:
        if self.discovery_order:
            return self.discovery_order
        return tuple(sorted(self.functions))

    def ordered_functions(self) -> tuple[FunctionIR, ...]:
        return tuple(self.functions[entry] for entry in self.ordered_function_entries())
