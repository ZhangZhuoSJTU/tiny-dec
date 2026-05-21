"""Stage-12 aggregate layout data structures built on top of stage-11 scalar facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from tiny_dec.analysis._helpers import partition_sort_key, value_sort_key
from tiny_dec.analysis.memory.models import MemoryPartition
from tiny_dec.analysis.ssa.models import SSAValue
from tiny_dec.analysis.types.models import (
    FunctionScalarTypeFacts,
    ProgramScalarTypeFacts,
    ScalarType,
)


class AggregateRootKind(str, Enum):
    POINTER = "pointer"


@dataclass(frozen=True, slots=True)
class AggregateRoot:
    kind: AggregateRootKind
    pointer_value: SSAValue | None = None
    stride: int | None = None

    def __post_init__(self) -> None:
        if self.kind == AggregateRootKind.POINTER and self.pointer_value is None:
            raise ValueError("pointer aggregate roots must reference a pointer value")
        if self.stride is not None and self.stride <= 0:
            raise ValueError("aggregate root stride must be positive when present")

    def to_pretty(self) -> str:
        if self.kind == AggregateRootKind.POINTER:
            assert self.pointer_value is not None
            stride = str(self.stride) if self.stride is not None else "?"
            return f"pointer {self.pointer_value.to_pretty()} stride={stride}"
        raise ValueError(f"unsupported aggregate root kind: {self.kind}")


@dataclass(frozen=True, slots=True)
class AggregateField:
    offset: int
    scalar_type: ScalarType
    partitions: tuple[MemoryPartition, ...] = ()

    def __post_init__(self) -> None:
        if self.offset < 0:  # no container_of-style negative offsets
            raise ValueError("aggregate field offset must be non-negative")
        if not self.partitions:
            raise ValueError("aggregate fields must reference at least one partition")

        expected = tuple(sorted(self.partitions, key=_partition_sort_key))
        if self.partitions != expected:
            raise ValueError("aggregate field partitions must be ordered deterministically")
        if len(set(self.partitions)) != len(self.partitions):
            raise ValueError("aggregate field partitions must be unique")
        for partition in self.partitions:
            if partition.size != self.scalar_type.size:
                raise ValueError("aggregate field width must match referenced partitions")

    @property
    def size(self) -> int:
        return self.scalar_type.size

    def to_pretty(self) -> str:
        partition_text = ", ".join(
            partition.identity_pretty() for partition in self.partitions
        )
        return (
            f"field {self.offset:+d} size={self.size} "
            f"type={self.scalar_type.to_pretty()} partitions=[{partition_text}]"
        )


@dataclass(frozen=True, slots=True)
class AggregateLayout:
    root: AggregateRoot
    fields: tuple[AggregateField, ...] = ()

    def __post_init__(self) -> None:
        if not self.fields:
            raise ValueError("aggregate layouts must contain at least one field")

        expected = tuple(sorted(self.fields, key=lambda field: (field.offset, field.size)))
        if self.fields != expected:
            raise ValueError("aggregate layout fields must be ordered deterministically")
        if len({field.offset for field in self.fields}) != len(self.fields):
            raise ValueError("aggregate layout fields must be unique by offset")

    def header_pretty(self) -> str:
        return f"aggregate {self.root.to_pretty()} fields={len(self.fields)}"


@dataclass(slots=True)
class FunctionAggregateTypeFacts:
    scalar_types: FunctionScalarTypeFacts
    layouts: tuple[AggregateLayout, ...] = ()

    def __post_init__(self) -> None:
        expected = tuple(sorted(self.layouts, key=_layout_sort_key))
        if self.layouts != expected:
            raise ValueError("function aggregate layouts must be ordered deterministically")
        if len({layout.root for layout in self.layouts}) != len(self.layouts):
            raise ValueError("function aggregate layouts must be unique by root")

    @property
    def entry(self) -> int:
        return self.scalar_types.entry

    @property
    def name(self) -> str | None:
        return self.scalar_types.name

    @property
    def pending_entries(self) -> tuple[int, ...]:
        return self.scalar_types.pending_entries

    @property
    def frame_size(self) -> int | None:
        return self.scalar_types.frame_size

    @property
    def dynamic_stack_pointer(self) -> bool:
        return self.scalar_types.dynamic_stack_pointer


@dataclass(slots=True)
class ProgramAggregateTypeFacts:
    scalar_types: ProgramScalarTypeFacts
    functions: dict[int, FunctionAggregateTypeFacts] = field(default_factory=dict)
    pending_entries: tuple[int, ...] = ()
    invalidated_entries: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if set(self.functions) != set(self.scalar_types.functions):
            raise ValueError(
                "program aggregate-type facts must cover scalar-type functions exactly"
            )
        if self.pending_entries != self.scalar_types.pending_entries:
            raise ValueError(
                "program aggregate-type facts pending entries must match scalar-type facts"
            )
        if self.invalidated_entries != self.scalar_types.invalidated_entries:
            raise ValueError(
                "program aggregate-type facts invalidated entries must match scalar-type facts"
            )

    def ordered_function_entries(self) -> tuple[int, ...]:
        return self.scalar_types.ordered_function_entries()

    def ordered_functions(self) -> tuple[FunctionAggregateTypeFacts, ...]:
        return tuple(self.functions[entry] for entry in self.ordered_function_entries())


_partition_sort_key = partition_sort_key

_value_sort_key = value_sort_key


def _root_sort_key(root: AggregateRoot) -> tuple[int, tuple[int, int, int, int, str], int]:
    assert root.kind == AggregateRootKind.POINTER
    assert root.pointer_value is not None
    stride = root.stride if root.stride is not None else -1
    return (0, _value_sort_key(root.pointer_value), stride)


def _layout_sort_key(layout: AggregateLayout) -> tuple[int, tuple[int, int, int, int, str], int]:
    return _root_sort_key(layout.root)
