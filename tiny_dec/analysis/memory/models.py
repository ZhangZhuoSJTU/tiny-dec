"""Stage-10 memory modeling data structures built on top of stage-9 stack facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from tiny_dec.analysis.stack.models import FunctionStackFacts, ProgramStackFacts, StackSlot
from tiny_dec.analysis.ssa.models import MemoryVersion, SSAValue


class MemoryPartitionKind(str, Enum):
    STACK_SLOT = "stack_slot"
    ABSOLUTE = "absolute"
    VALUE = "value"


class MemoryAccessKind(str, Enum):
    LOAD = "load"
    STORE = "store"


@dataclass(frozen=True, slots=True)
class MemoryAccess:
    instruction_address: int
    block_start: int
    kind: MemoryAccessKind
    size: int
    value: SSAValue | None = None
    memory_before: MemoryVersion | None = None
    memory_after: MemoryVersion | None = None

    def __post_init__(self) -> None:
        if self.instruction_address < 0:
            raise ValueError("memory access instruction address must be non-negative")
        if self.block_start < 0:
            raise ValueError("memory access block start must be non-negative")
        if self.size <= 0:
            raise ValueError("memory access size must be positive")
        if self.memory_after is not None and self.memory_before is None:
            raise ValueError("memory access memory_after requires memory_before")

    def to_pretty(self) -> str:
        text = (
            f"{self.kind.value} 0x{self.instruction_address:x} "
            f"block=0x{self.block_start:x} size={self.size}"
        )
        if self.value is not None:
            text += f" value={self.value.to_pretty()}"
        if self.memory_before is None:
            return text
        if self.memory_after is None or self.memory_after == self.memory_before:
            return f"{text} [{self.memory_before.to_pretty()}]"
        return (
            f"{text} "
            f"[{self.memory_before.to_pretty()} -> {self.memory_after.to_pretty()}]"
        )


@dataclass(frozen=True, slots=True)
class MemoryPartition:
    kind: MemoryPartitionKind
    size: int
    stack_slot: StackSlot | None = None
    absolute_address: int | None = None
    base_value: SSAValue | None = None
    offset: int = 0
    accesses: tuple[MemoryAccess, ...] = ()

    def __post_init__(self) -> None:
        if self.size <= 0:
            raise ValueError("memory partition size must be positive")

        if self.kind == MemoryPartitionKind.STACK_SLOT:
            if self.stack_slot is None:
                raise ValueError("stack-slot memory partitions must reference a stack slot")
            if self.stack_slot.size != self.size:
                raise ValueError("stack-slot memory partition size must match its stack slot")
            if self.absolute_address is not None or self.base_value is not None or self.offset != 0:
                raise ValueError(
                    "stack-slot memory partitions must only carry stack-slot detail"
                )
        elif self.kind == MemoryPartitionKind.ABSOLUTE:
            if self.absolute_address is None or self.absolute_address < 0:
                raise ValueError("absolute memory partitions must carry a non-negative address")
            if self.stack_slot is not None or self.base_value is not None or self.offset != 0:
                raise ValueError("absolute memory partitions must only carry address detail")
        elif self.kind == MemoryPartitionKind.VALUE:
            if self.base_value is None:
                raise ValueError("value memory partitions must carry a base value")
            if self.stack_slot is not None or self.absolute_address is not None:
                raise ValueError("value memory partitions must only carry value detail")

        expected = tuple(
            sorted(
                self.accesses,
                key=lambda access: (
                    access.instruction_address,
                    access.kind.value,
                    access.block_start,
                ),
            )
        )
        if self.accesses != expected:
            raise ValueError("memory partition accesses must be ordered deterministically")
        for access in self.accesses:
            if access.size != self.size:
                raise ValueError("memory partition accesses must match the partition size")

    def identity_pretty(self) -> str:
        if self.kind == MemoryPartitionKind.STACK_SLOT:
            assert self.stack_slot is not None
            return (
                f"stack_slot {self.stack_slot.frame_offset:+d} size={self.size} "
                f"role={self.stack_slot.role_pretty()}"
            )
        if self.kind == MemoryPartitionKind.ABSOLUTE:
            assert self.absolute_address is not None
            return f"absolute 0x{self.absolute_address:x} size={self.size}"
        assert self.base_value is not None
        return (
            f"value {self.base_value.to_pretty()} offset={self.offset:+d} "
            f"size={self.size}"
        )

    def to_pretty(self) -> str:
        return f"{self.identity_pretty()} accesses={len(self.accesses)}"


def _partition_sort_key(partition: MemoryPartition) -> tuple[int, int, int, str]:
    if partition.kind == MemoryPartitionKind.STACK_SLOT:
        assert partition.stack_slot is not None
        return (0, partition.stack_slot.frame_offset, partition.size, "")
    if partition.kind == MemoryPartitionKind.ABSOLUTE:
        assert partition.absolute_address is not None
        return (1, partition.absolute_address, partition.size, "")
    assert partition.base_value is not None
    return (2, partition.offset, partition.size, partition.base_value.to_pretty())


@dataclass(slots=True)
class FunctionMemoryFacts:
    stack: FunctionStackFacts
    partitions: tuple[MemoryPartition, ...] = ()

    def __post_init__(self) -> None:
        expected = tuple(sorted(self.partitions, key=_partition_sort_key))
        if self.partitions != expected:
            raise ValueError("function memory partitions must be ordered deterministically")

    @property
    def entry(self) -> int:
        return self.stack.entry

    @property
    def name(self) -> str | None:
        return self.stack.name

    @property
    def pending_entries(self) -> tuple[int, ...]:
        return self.stack.pending_entries

    @property
    def frame_size(self) -> int | None:
        return self.stack.frame_size

    @property
    def dynamic_stack_pointer(self) -> bool:
        return self.stack.dynamic_stack_pointer

    @property
    def access_count(self) -> int:
        return sum(len(partition.accesses) for partition in self.partitions)


@dataclass(slots=True)
class ProgramMemoryFacts:
    stack: ProgramStackFacts
    functions: dict[int, FunctionMemoryFacts] = field(default_factory=dict)
    pending_entries: tuple[int, ...] = ()
    invalidated_entries: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if set(self.functions) != set(self.stack.functions):
            raise ValueError(
                "program memory facts must cover stack-fact functions exactly"
            )
        if self.pending_entries != self.stack.pending_entries:
            raise ValueError("program memory facts pending entries must match stack facts")
        if self.invalidated_entries != self.stack.invalidated_entries:
            raise ValueError(
                "program memory facts invalidated entries must match stack facts"
            )

    def ordered_function_entries(self) -> tuple[int, ...]:
        return self.stack.ordered_function_entries()

    def ordered_functions(self) -> tuple[FunctionMemoryFacts, ...]:
        return tuple(self.functions[entry] for entry in self.ordered_function_entries())
