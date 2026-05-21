"""Stage-11 scalar type recovery data structures built on top of stage-10 memory facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from tiny_dec.analysis._helpers import partition_sort_key, value_size, value_sort_key
from tiny_dec.analysis.memory.models import (
    FunctionMemoryFacts,
    MemoryPartition,
    ProgramMemoryFacts,
)
from tiny_dec.analysis.ssa.models import SSAValue


class ScalarTypeKind(str, Enum):
    BOOL = "bool"
    INT = "int"
    POINTER = "pointer"
    WORD = "word"


@dataclass(frozen=True, slots=True)
class ScalarType:
    kind: ScalarTypeKind
    size: int

    def __post_init__(self) -> None:
        if self.size <= 0:
            raise ValueError("scalar type size must be positive")

    def to_pretty(self) -> str:
        return f"{self.kind.value}:{self.size}"


@dataclass(frozen=True, slots=True)
class PartitionScalarTypeFact:
    partition: MemoryPartition
    scalar_type: ScalarType

    def __post_init__(self) -> None:
        if self.partition.size != self.scalar_type.size:
            raise ValueError("partition scalar type width must match partition size")

    def to_pretty(self) -> str:
        return f"{self.partition.identity_pretty()} type={self.scalar_type.to_pretty()}"


@dataclass(frozen=True, slots=True)
class ValueScalarTypeFact:
    value: SSAValue
    scalar_type: ScalarType

    def __post_init__(self) -> None:
        if _value_size(self.value) != self.scalar_type.size:
            raise ValueError("value scalar type width must match value size")

    def to_pretty(self) -> str:
        return f"{self.value.to_pretty()} type={self.scalar_type.to_pretty()}"


_partition_sort_key = partition_sort_key

_value_sort_key = value_sort_key

_value_size = value_size


@dataclass(slots=True)
class FunctionScalarTypeFacts:
    memory: FunctionMemoryFacts
    partition_facts: tuple[PartitionScalarTypeFact, ...] = ()
    value_facts: tuple[ValueScalarTypeFact, ...] = ()

    def __post_init__(self) -> None:
        expected_partitions = tuple(
            sorted(
                self.partition_facts,
                key=lambda fact: _partition_sort_key(fact.partition),
            )
        )
        if self.partition_facts != expected_partitions:
            raise ValueError(
                "function scalar-type partition facts must be ordered deterministically"
            )
        if len({fact.partition for fact in self.partition_facts}) != len(self.partition_facts):
            raise ValueError("function scalar-type partition facts must be unique")
        memory_partitions = set(self.memory.partitions)
        for fact in self.partition_facts:
            if fact.partition not in memory_partitions:
                raise ValueError(
                    "function scalar-type partition facts must reference memory partitions"
                )

        expected_values = tuple(
            sorted(self.value_facts, key=lambda fact: _value_sort_key(fact.value))
        )
        if self.value_facts != expected_values:
            raise ValueError(
                "function scalar-type value facts must be ordered deterministically"
            )
        if len({fact.value for fact in self.value_facts}) != len(self.value_facts):
            raise ValueError("function scalar-type value facts must be unique")

    @property
    def entry(self) -> int:
        return self.memory.entry

    @property
    def name(self) -> str | None:
        return self.memory.name

    @property
    def pending_entries(self) -> tuple[int, ...]:
        return self.memory.pending_entries

    @property
    def frame_size(self) -> int | None:
        return self.memory.frame_size

    @property
    def dynamic_stack_pointer(self) -> bool:
        return self.memory.dynamic_stack_pointer


@dataclass(slots=True)
class ProgramScalarTypeFacts:
    memory: ProgramMemoryFacts
    functions: dict[int, FunctionScalarTypeFacts] = field(default_factory=dict)
    pending_entries: tuple[int, ...] = ()
    invalidated_entries: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if set(self.functions) != set(self.memory.functions):
            raise ValueError(
                "program scalar-type facts must cover memory-fact functions exactly"
            )
        if self.pending_entries != self.memory.pending_entries:
            raise ValueError(
                "program scalar-type facts pending entries must match memory facts"
            )
        if self.invalidated_entries != self.memory.invalidated_entries:
            raise ValueError(
                "program scalar-type facts invalidated entries must match memory facts"
            )

    def ordered_function_entries(self) -> tuple[int, ...]:
        return self.memory.ordered_function_entries()

    def ordered_functions(self) -> tuple[FunctionScalarTypeFacts, ...]:
        return tuple(self.functions[entry] for entry in self.ordered_function_entries())
