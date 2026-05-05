"""Stage-6 intraprocedural dataflow facts built on top of canonical IR."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from tiny_dec.analysis.simplify.models import CanonicalBlock, CanonicalFunctionIR, CanonicalProgramIR


@dataclass(slots=True)
class RegisterState:
    reachable: bool = True
    known_registers: dict[int, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.reachable and self.known_registers:
            raise ValueError("unreachable register state must not carry known registers")

        normalized: dict[int, int] = {}
        for register, value in self.known_registers.items():
            if register < 0:
                raise ValueError("register-state register index must be non-negative")
            if register == 0:
                raise ValueError("register-state must not materialize implicit x0")
            normalized[register] = value & 0xFFFFFFFF
        self.known_registers = normalized

    @classmethod
    def unreachable(cls) -> RegisterState:
        return cls(reachable=False, known_registers={})

    def to_pretty(self) -> str:
        if not self.reachable:
            return "<unreachable>"
        if not self.known_registers:
            return "<empty>"
        parts = [f"x{register}=0x{value:x}" for register, value in sorted(self.known_registers.items())]
        return ", ".join(parts)


class RecoveredTargetKind(str, Enum):
    BRANCH = "branch"
    CALL = "call"


@dataclass(frozen=True, slots=True)
class RecoveredTarget:
    instruction_address: int
    block_start: int
    kind: RecoveredTargetKind
    target: int

    def __post_init__(self) -> None:
        if self.instruction_address < 0:
            raise ValueError("recovered-target instruction address must be non-negative")
        if self.block_start < 0:
            raise ValueError("recovered-target block start must be non-negative")
        if self.target < 0:
            raise ValueError("recovered-target target must be non-negative")

    def to_pretty(self) -> str:
        return (
            f"recover {self.kind.value} 0x{self.instruction_address:x} -> 0x{self.target:x}"
        )


@dataclass(slots=True)
class BlockDataflowFacts:
    start: int
    in_state: RegisterState
    out_state: RegisterState
    recovered_targets: tuple[RecoveredTarget, ...] = ()

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("block dataflow start must be non-negative")
        keys = {
            (target.instruction_address, target.kind, target.target)
            for target in self.recovered_targets
        }
        if len(keys) != len(self.recovered_targets):
            raise ValueError("block recovered targets must be unique")
        for target in self.recovered_targets:
            if target.block_start != self.start:
                raise ValueError("recovered target block start must match owning block")


@dataclass(slots=True)
class FunctionDataflowFacts:
    function: CanonicalFunctionIR
    blocks: dict[int, BlockDataflowFacts] = field(default_factory=dict)
    recovered_targets: tuple[RecoveredTarget, ...] = ()

    def __post_init__(self) -> None:
        if set(self.blocks) != set(self.function.blocks):
            raise ValueError("function dataflow facts must cover canonical blocks exactly")
        ordered_targets: list[RecoveredTarget] = []
        for start in self.function.ordered_block_starts():
            if start not in self.blocks:
                raise ValueError("function dataflow facts must cover canonical blocks exactly")
            ordered_targets.extend(self.blocks[start].recovered_targets)
        if self.recovered_targets != tuple(ordered_targets):
            raise ValueError("function recovered target order must match block order")

    def ordered_block_starts(self) -> tuple[int, ...]:
        return self.function.ordered_block_starts()

    def ordered_blocks(self) -> tuple[tuple[CanonicalBlock, BlockDataflowFacts], ...]:
        return tuple(
            (self.function.blocks[start], self.blocks[start])
            for start in self.ordered_block_starts()
        )


@dataclass(slots=True)
class ProgramDataflowFacts:
    program: CanonicalProgramIR
    functions: dict[int, FunctionDataflowFacts] = field(default_factory=dict)
    pending_entries: tuple[int, ...] = ()
    invalidated_entries: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if set(self.functions) != set(self.program.functions):
            raise ValueError(
                "program dataflow facts must cover canonical program functions exactly"
            )
        if len(set(self.pending_entries)) != len(self.pending_entries):
            raise ValueError("program dataflow pending entries must be unique")
        if len(set(self.invalidated_entries)) != len(self.invalidated_entries):
            raise ValueError("program dataflow invalidated entries must be unique")
        for entry in self.invalidated_entries:
            if entry not in self.program.functions:
                raise ValueError(
                    "program dataflow invalidated entries must reference known functions"
                )

    def ordered_function_entries(self) -> tuple[int, ...]:
        return self.program.ordered_function_entries()

    def ordered_functions(self) -> tuple[FunctionDataflowFacts, ...]:
        return tuple(self.functions[entry] for entry in self.ordered_function_entries())
