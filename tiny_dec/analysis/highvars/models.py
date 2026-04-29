"""Stage-13 variable-recovery data structures built on top of stage-12 facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from tiny_dec.analysis._helpers import partition_sort_key, value_size, value_sort_key
from tiny_dec.analysis.memory.models import MemoryPartition
from tiny_dec.analysis.ssa.models import SSAValue
from tiny_dec.analysis.stack.models import StackSlot
from tiny_dec.analysis.types.aggregate_models import (
    AggregateLayout,
    FunctionAggregateTypeFacts,
    ProgramAggregateTypeFacts,
)
from tiny_dec.analysis.types.models import ScalarType


class VariableKind(str, Enum):
    PARAMETER = "parameter"
    LOCAL = "local"
    GLOBAL = "global"
    INDIRECT = "indirect"


class VariableBindingKind(str, Enum):
    STACK_SLOT = "stack_slot"
    ROOT_VALUE = "root_value"
    ABSOLUTE = "absolute"
    PARTITION = "partition"


@dataclass(frozen=True, slots=True)
class VariableBinding:
    kind: VariableBindingKind
    stack_slot: StackSlot | None = None
    root_value: SSAValue | None = None
    absolute_address: int | None = None
    partition: MemoryPartition | None = None

    def __post_init__(self) -> None:
        if self.kind == VariableBindingKind.STACK_SLOT:
            if self.stack_slot is None:
                raise ValueError("stack-slot variable bindings must reference a stack slot")
            if (
                self.root_value is not None
                or self.absolute_address is not None
                or self.partition is not None
            ):
                raise ValueError("stack-slot variable bindings must only carry stack-slot detail")
            return

        if self.kind == VariableBindingKind.ROOT_VALUE:
            if self.root_value is None:
                raise ValueError("root-value variable bindings must reference a root value")
            if self.absolute_address is not None or self.partition is not None or self.stack_slot is not None:
                raise ValueError("root-value variable bindings must only carry root-value detail")
            return

        if self.kind == VariableBindingKind.ABSOLUTE:
            if self.absolute_address is None or self.absolute_address < 0:
                raise ValueError(
                    "absolute variable bindings must carry a non-negative address"
                )
            if self.root_value is not None or self.partition is not None or self.stack_slot is not None:
                raise ValueError("absolute variable bindings must only carry address detail")
            return

        if self.partition is None:
            raise ValueError("partition variable bindings must reference a memory partition")
        if self.root_value is not None or self.absolute_address is not None or self.stack_slot is not None:
            raise ValueError("partition variable bindings must only carry partition detail")

    def to_pretty(self) -> str:
        if self.kind == VariableBindingKind.STACK_SLOT:
            assert self.stack_slot is not None
            return (
                f"stack_slot {self.stack_slot.frame_offset:+d} size={self.stack_slot.size} "
                f"role={self.stack_slot.role_pretty()}"
            )
        if self.kind == VariableBindingKind.ROOT_VALUE:
            assert self.root_value is not None
            return f"root_value {self.root_value.to_pretty()}"
        if self.kind == VariableBindingKind.ABSOLUTE:
            assert self.absolute_address is not None
            return f"absolute 0x{self.absolute_address:x}"
        assert self.partition is not None
        return f"partition {self.partition.identity_pretty()}"


@dataclass(frozen=True, slots=True)
class RecoveredVariable:
    name: str
    kind: VariableKind
    size: int
    binding: VariableBinding
    scalar_type: ScalarType | None = None
    root_value: SSAValue | None = None
    aggregate_layout: AggregateLayout | None = None
    partitions: tuple[MemoryPartition, ...] = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("recovered variable names must not be empty")
        if self.size <= 0:
            raise ValueError("recovered variable size must be positive")
        if self.scalar_type is not None and self.scalar_type.size != self.size:
            raise ValueError("recovered variable scalar type size must match variable size")
        if self.root_value is not None and _value_size(self.root_value) != self.size:
            raise ValueError("recovered variable root value size must match variable size")

        expected = tuple(sorted(self.partitions, key=_partition_sort_key))
        if self.partitions != expected:
            raise ValueError("recovered variable partitions must be ordered deterministically")
        if len(set(self.partitions)) != len(self.partitions):
            raise ValueError("recovered variable partitions must be unique")

        if self.binding.kind == VariableBindingKind.STACK_SLOT:
            assert self.binding.stack_slot is not None
            if self.binding.stack_slot.size != self.size:
                raise ValueError("stack-slot variable bindings must match variable size")
        elif self.binding.kind == VariableBindingKind.ROOT_VALUE:
            assert self.binding.root_value is not None
            if _value_size(self.binding.root_value) != self.size:
                raise ValueError("root-value variable bindings must match variable size")
        elif self.binding.kind == VariableBindingKind.PARTITION:
            assert self.binding.partition is not None
            if self.binding.partition.size != self.size:
                raise ValueError("partition variable bindings must match variable size")
            if self.binding.partition not in self.partitions:
                raise ValueError(
                    "partition-bound variables must include the binding partition"
                )

        if self.aggregate_layout is not None:
            if self.root_value is None:
                raise ValueError("aggregate-backed variables must carry their root value")
            if self.aggregate_layout.root.pointer_value != self.root_value:
                raise ValueError(
                    "aggregate-backed variable root value must match the aggregate root"
                )
            aggregate_partitions = {
                partition
                for field in self.aggregate_layout.fields
                for partition in field.partitions
            }
            if not aggregate_partitions.issubset(self.partitions):
                raise ValueError(
                    "aggregate-backed variables must include all aggregate field partitions"
                )

    def header_pretty(self) -> str:
        text = (
            f"variable {self.name} kind={self.kind.value} size={self.size} "
            f"binding={self.binding.to_pretty()}"
        )
        if self.scalar_type is not None:
            text += f" type={self.scalar_type.to_pretty()}"
        if self.root_value is not None:
            text += f" root={self.root_value.to_pretty()}"
        if self.aggregate_layout is not None:
            text += f" aggregate_fields={len(self.aggregate_layout.fields)}"
        text += f" partitions={len(self.partitions)}"
        return text


@dataclass(slots=True)
class FunctionVariableFacts:
    aggregate_types: FunctionAggregateTypeFacts
    variables: tuple[RecoveredVariable, ...] = ()

    def __post_init__(self) -> None:
        expected = tuple(sorted(self.variables, key=_variable_sort_key))
        if self.variables != expected:
            raise ValueError("function variable facts must be ordered deterministically")
        if len({variable.name for variable in self.variables}) != len(self.variables):
            raise ValueError("function variable facts must use unique variable names")

    @property
    def entry(self) -> int:
        return self.aggregate_types.entry

    @property
    def name(self) -> str | None:
        return self.aggregate_types.name

    @property
    def pending_entries(self) -> tuple[int, ...]:
        return self.aggregate_types.pending_entries

    @property
    def frame_size(self) -> int | None:
        return self.aggregate_types.frame_size

    @property
    def dynamic_stack_pointer(self) -> bool:
        return self.aggregate_types.dynamic_stack_pointer


@dataclass(slots=True)
class ProgramVariableFacts:
    aggregate_types: ProgramAggregateTypeFacts
    functions: dict[int, FunctionVariableFacts] = field(default_factory=dict)
    pending_entries: tuple[int, ...] = ()
    invalidated_entries: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if set(self.functions) != set(self.aggregate_types.functions):
            raise ValueError(
                "program variable facts must cover aggregate-type functions exactly"
            )
        if self.pending_entries != self.aggregate_types.pending_entries:
            raise ValueError(
                "program variable facts pending entries must match aggregate-type facts"
            )
        if self.invalidated_entries != self.aggregate_types.invalidated_entries:
            raise ValueError(
                "program variable facts invalidated entries must match aggregate-type facts"
            )

    def ordered_function_entries(self) -> tuple[int, ...]:
        return self.aggregate_types.ordered_function_entries()

    def ordered_functions(self) -> tuple[FunctionVariableFacts, ...]:
        return tuple(self.functions[entry] for entry in self.ordered_function_entries())


_partition_sort_key = partition_sort_key

_value_sort_key = value_sort_key

_value_size = value_size


def _binding_sort_key(
    binding: VariableBinding,
) -> tuple[int, tuple[int, int, int, int, str] | tuple[int, int, int, str] | tuple[int] | tuple[int, int]]:
    if binding.kind == VariableBindingKind.STACK_SLOT:
        assert binding.stack_slot is not None
        return (
            0,
            (
                binding.stack_slot.frame_offset,
                binding.stack_slot.size,
                0,
                0,
                binding.stack_slot.role.value,
            ),
        )
    if binding.kind == VariableBindingKind.ROOT_VALUE:
        assert binding.root_value is not None
        return (1, _value_sort_key(binding.root_value))
    if binding.kind == VariableBindingKind.ABSOLUTE:
        assert binding.absolute_address is not None
        return (2, (binding.absolute_address, 0))
    assert binding.partition is not None
    partition = binding.partition
    return (3, _partition_sort_key(partition))


def _variable_sort_key(
    variable: RecoveredVariable,
) -> tuple[
    int,
    tuple[int, tuple[int, int, int, int, str] | tuple[int, int, int, str] | tuple[int] | tuple[int, int]],
    str,
]:
    kind_order = {
        VariableKind.PARAMETER: 0,
        VariableKind.LOCAL: 1,
        VariableKind.GLOBAL: 2,
        VariableKind.INDIRECT: 3,
    }
    return (kind_order[variable.kind], _binding_sort_key(variable.binding), variable.name)
