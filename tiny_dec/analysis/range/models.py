"""Stage-14 range-refinement data structures built on top of stage-13 facts."""

from __future__ import annotations

from dataclasses import dataclass, field

from tiny_dec.analysis.highvars.models import (
    FunctionVariableFacts,
    ProgramVariableFacts,
    RecoveredVariable,
)
from tiny_dec.analysis._helpers import value_sort_key
from tiny_dec.analysis.ssa.models import SSAValue


@dataclass(frozen=True, slots=True)
class IntegerRange:
    lower: int | None = None
    upper: int | None = None

    def __post_init__(self) -> None:
        if self.lower is None and self.upper is None:
            raise ValueError("integer ranges must carry at least one bound")
        if (
            self.lower is not None
            and self.upper is not None
            and self.lower > self.upper
        ):
            raise ValueError("integer range lower bound must not exceed upper bound")

    def to_pretty(self) -> str:
        lower = str(self.lower) if self.lower is not None else "-inf"
        upper = str(self.upper) if self.upper is not None else "+inf"
        return f"[{lower}, {upper}]"


@dataclass(frozen=True, slots=True)
class ValueRangeFact:
    value: SSAValue
    value_range: IntegerRange

    def to_pretty(self) -> str:
        return f"value {self.value.to_pretty()} range={self.value_range.to_pretty()}"


@dataclass(frozen=True, slots=True)
class VariableRangeFact:
    variable: RecoveredVariable
    value_range: IntegerRange

    def to_pretty(self) -> str:
        return f"variable {self.variable.name} range={self.value_range.to_pretty()}"


@dataclass(frozen=True, slots=True)
class BranchRangeRefinement:
    block_start: int
    successor: int
    sense: bool
    source_opcode: str
    value: SSAValue
    value_range: IntegerRange

    def __post_init__(self) -> None:
        if self.block_start < 0:
            raise ValueError("branch range refinement block start must be non-negative")
        if self.successor < 0:
            raise ValueError("branch range refinement successor must be non-negative")
        if not self.source_opcode:
            raise ValueError("branch range refinement source opcode must not be empty")

    def to_pretty(self) -> str:
        sense = "true" if self.sense else "false"
        return (
            f"branch 0x{self.block_start:x} -> 0x{self.successor:x} "
            f"sense={sense} source={self.source_opcode} "
            f"value={self.value.to_pretty()} range={self.value_range.to_pretty()}"
        )


@dataclass(slots=True)
class FunctionRangeFacts:
    variables: FunctionVariableFacts
    value_ranges: tuple[ValueRangeFact, ...] = ()
    variable_ranges: tuple[VariableRangeFact, ...] = ()
    branch_refinements: tuple[BranchRangeRefinement, ...] = ()

    def __post_init__(self) -> None:
        expected_value_ranges = tuple(
            sorted(self.value_ranges, key=lambda fact: _value_sort_key(fact.value))
        )
        if self.value_ranges != expected_value_ranges:
            raise ValueError("function value-range facts must be ordered deterministically")
        if len({fact.value for fact in self.value_ranges}) != len(self.value_ranges):
            raise ValueError("function value-range facts must be unique by value")

        expected_variable_ranges = tuple(
            sorted(self.variable_ranges, key=lambda fact: fact.variable.name)
        )
        if self.variable_ranges != expected_variable_ranges:
            raise ValueError(
                "function variable-range facts must be ordered deterministically"
            )
        if len({fact.variable.name for fact in self.variable_ranges}) != len(
            self.variable_ranges
        ):
            raise ValueError("function variable-range facts must be unique by variable")

        expected_branch_refinements = tuple(
            sorted(
                self.branch_refinements,
                key=lambda fact: (
                    fact.block_start,
                    fact.successor,
                    0 if fact.sense else 1,
                    _value_sort_key(fact.value),
                    fact.source_opcode,
                ),
            )
        )
        if self.branch_refinements != expected_branch_refinements:
            raise ValueError(
                "function branch range refinements must be ordered deterministically"
            )
        keys = {
            (fact.block_start, fact.successor, fact.sense, fact.value)
            for fact in self.branch_refinements
        }
        if len(keys) != len(self.branch_refinements):
            raise ValueError(
                "function branch range refinements must be unique by edge, sense, and value"
            )

    @property
    def entry(self) -> int:
        return self.variables.entry

    @property
    def name(self) -> str | None:
        return self.variables.name

    @property
    def pending_entries(self) -> tuple[int, ...]:
        return self.variables.pending_entries

    @property
    def frame_size(self) -> int | None:
        return self.variables.frame_size

    @property
    def dynamic_stack_pointer(self) -> bool:
        return self.variables.dynamic_stack_pointer


@dataclass(slots=True)
class ProgramRangeFacts:
    variables: ProgramVariableFacts
    functions: dict[int, FunctionRangeFacts] = field(default_factory=dict)
    pending_entries: tuple[int, ...] = ()
    invalidated_entries: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if set(self.functions) != set(self.variables.functions):
            raise ValueError("program range facts must cover variable functions exactly")
        if self.pending_entries != self.variables.pending_entries:
            raise ValueError("program range facts pending entries must match variable facts")
        if self.invalidated_entries != self.variables.invalidated_entries:
            raise ValueError(
                "program range facts invalidated entries must match variable facts"
            )

    def ordered_function_entries(self) -> tuple[int, ...]:
        return self.variables.ordered_function_entries()

    def ordered_functions(self) -> tuple[FunctionRangeFacts, ...]:
        return tuple(self.functions[entry] for entry in self.ordered_function_entries())


_value_sort_key = value_sort_key
