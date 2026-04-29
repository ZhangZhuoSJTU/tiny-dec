"""Stage-13 variable recovery from stage-12 aggregate-type facts.

This file owns the transformation from stage-12 aggregate recovery into
stage-13 variable facts.

Implementation notes:
- The stage is read-only with respect to upstream CFG, SSA, call, stack,
  memory, scalar-type, and aggregate-layout artifacts.
- It preserves upstream `pending_entries` and `invalidated_entries` unchanged.
- Recovery is intentionally conservative and prefers omission over guessed
  merging when an anchor is ambiguous.
- Aggregate-backed variables are emitted before scalar stack variables so field
  partitions do not later reappear as raw dereference variables.
- Saved-register stack slots remain absent from the recovered source-level
  variable set.

Recovery strategy — variables are recovered from four sources in
priority order:
1. Aggregate layouts (pointer root + field partitions → struct variable)
2. Stack-slot partitions not already claimed by an aggregate
3. Absolute-address and value-root partitions (globals, indirects)
4. Register-only parameters (live-in ABI registers with scalar type
   evidence but no corresponding stack slot or aggregate)
This ordering ensures that a struct variable subsumes its constituent
field partitions rather than each field appearing as a separate local.
"""

from __future__ import annotations

from tiny_dec.analysis._helpers import partition_sort_key
from tiny_dec.analysis.highvars.models import (
    FunctionVariableFacts,
    ProgramVariableFacts,
    RecoveredVariable,
    VariableBinding,
    VariableBindingKind,
    VariableKind,
    _variable_sort_key,
)
from tiny_dec.analysis.memory.models import MemoryPartition, MemoryPartitionKind
from tiny_dec.analysis.ssa.models import SSAName, SSANameKind, SSAValue
from tiny_dec.analysis.stack.models import StackSlot, StackSlotRole
from tiny_dec.analysis.types import (
    AggregateLayout,
    FunctionAggregateTypeFacts,
    ProgramAggregateTypeFacts,
    ScalarType,
    build_program_aggregate_type_facts,
)
from tiny_dec.loader import ProgramView


def analyze_function_variables(function: FunctionAggregateTypeFacts) -> FunctionVariableFacts:
    """Analyze one function and emit stage-13 variable facts."""

    scalar_types = function.scalar_types
    memory = scalar_types.memory
    ssa = memory.stack.calls.ssa
    abi = memory.stack.calls.abi

    partition_types = {
        fact.partition: fact.scalar_type
        for fact in scalar_types.partition_facts
    }
    value_types = {
        fact.value: fact.scalar_type
        for fact in scalar_types.value_facts
    }
    stack_partition_by_slot = {
        partition.stack_slot: partition
        for partition in memory.partitions
        if partition.kind == MemoryPartitionKind.STACK_SLOT and partition.stack_slot is not None
    }
    live_in_by_register = {
        live_in.base: live_in
        for live_in in ssa.live_ins
        if live_in.kind == SSANameKind.REGISTER
    }

    used_partitions: set[MemoryPartition] = set()
    bound_stack_slots: set[StackSlot] = set()
    bound_roots: set[SSAValue] = set()
    variables: list[RecoveredVariable] = []

    for layout in function.layouts:
        variable = _recover_aggregate_variable(
            layout,
            abi_argument_registers=set(abi.argument_registers),
            stack_partition_by_slot=stack_partition_by_slot,
            partition_types=partition_types,
            live_in_by_register=live_in_by_register,
        )
        if variable is None:
            continue
        variables.append(variable)
        used_partitions.update(variable.partitions)
        if variable.binding.kind == VariableBindingKind.STACK_SLOT:
            assert variable.binding.stack_slot is not None
            bound_stack_slots.add(variable.binding.stack_slot)
        if variable.root_value is not None:
            bound_roots.add(variable.root_value)

    for partition in memory.partitions:
        if partition.kind != MemoryPartitionKind.STACK_SLOT or partition.stack_slot is None:
            continue
        slot = partition.stack_slot
        if partition in used_partitions or slot in bound_stack_slots:
            continue
        if slot.role == StackSlotRole.SAVED_REGISTER:
            continue

        variable_kind = (
            VariableKind.PARAMETER
            if slot.role == StackSlotRole.ARGUMENT_HOME
            else VariableKind.LOCAL
        )
        root_value = None
        if slot.argument_register is not None:
            root_value = live_in_by_register.get(slot.argument_register)

        variables.append(
            RecoveredVariable(
                name=_name_for_stack_slot(slot),
                kind=variable_kind,
                size=slot.size,
                binding=VariableBinding(
                    kind=VariableBindingKind.STACK_SLOT,
                    stack_slot=slot,
                ),
                scalar_type=partition_types.get(partition),
                root_value=root_value,
                partitions=(partition,),
            )
        )
        used_partitions.add(partition)
        bound_stack_slots.add(slot)
        if root_value is not None:
            bound_roots.add(root_value)

    for partition in memory.partitions:
        if partition in used_partitions or partition.kind == MemoryPartitionKind.STACK_SLOT:
            continue
        if partition.kind == MemoryPartitionKind.ABSOLUTE:
            assert partition.absolute_address is not None
            variables.append(
                RecoveredVariable(
                    name=f"global_0x{partition.absolute_address:x}_{partition.size}",
                    kind=VariableKind.GLOBAL,
                    size=partition.size,
                    binding=VariableBinding(
                        kind=VariableBindingKind.ABSOLUTE,
                        absolute_address=partition.absolute_address,
                    ),
                    scalar_type=partition_types.get(partition),
                    partitions=(partition,),
                )
            )
            used_partitions.add(partition)
            continue

        variables.append(
            RecoveredVariable(
                name=_name_for_value_partition(partition),
                kind=VariableKind.INDIRECT,
                size=partition.size,
                binding=VariableBinding(
                    kind=VariableBindingKind.PARTITION,
                    partition=partition,
                ),
                scalar_type=partition_types.get(partition),
                partitions=(partition,),
            )
        )
        used_partitions.add(partition)

    for register in abi.argument_registers:
        live_in = live_in_by_register.get(register)
        if live_in is None or live_in in bound_roots:
            continue
        scalar_type = value_types.get(live_in)
        if scalar_type is None:
            continue
        variables.append(
            RecoveredVariable(
                name=f"arg_x{register}_{live_in.size}",
                kind=VariableKind.PARAMETER,
                size=live_in.size,
                binding=VariableBinding(
                    kind=VariableBindingKind.ROOT_VALUE,
                    root_value=live_in,
                ),
                scalar_type=scalar_type,
                root_value=live_in,
                partitions=(),
            )
        )
        bound_roots.add(live_in)

    _deduplicate_variable_names(variables)

    return FunctionVariableFacts(
        aggregate_types=function,
        variables=tuple(sorted(variables, key=_variable_sort_key)),
    )


def analyze_program_variables(program: ProgramAggregateTypeFacts) -> ProgramVariableFacts:
    """Analyze a whole program and emit stage-13 variable facts."""

    functions = {
        function.entry: analyze_function_variables(function)
        for function in program.ordered_functions()
    }
    return ProgramVariableFacts(
        aggregate_types=program,
        functions=functions,
        pending_entries=program.pending_entries,
        invalidated_entries=program.invalidated_entries,
    )


def build_function_variable_facts(
    view: ProgramView,
    entry: int,
) -> FunctionVariableFacts:
    """Build stage-12 aggregate facts first, then derive stage-13 variables."""

    program = build_program_variable_facts(view, entry)
    return program.functions[entry]


def build_program_variable_facts(
    view: ProgramView,
    root_entry: int,
) -> ProgramVariableFacts:
    """Build stage-12 aggregate facts first, then derive stage-13 variables."""

    program = build_program_aggregate_type_facts(view, root_entry)
    return analyze_program_variables(program)


def _recover_aggregate_variable(
    layout: AggregateLayout,
    *,
    abi_argument_registers: set[int],
    stack_partition_by_slot: dict[StackSlot, MemoryPartition],
    partition_types: dict[MemoryPartition, ScalarType],
    live_in_by_register: dict[int, SSAName],
) -> RecoveredVariable | None:
    root = layout.root.pointer_value
    if root is None:
        return None

    aggregate_partitions = {
        partition
        for field in layout.fields
        for partition in field.partitions
    }
    stack_slot = _choose_aggregate_stack_slot_anchor(
        root,
        stack_partition_by_slot,
        abi_argument_registers=abi_argument_registers,
    )
    if stack_slot is not None:
        partition = stack_partition_by_slot[stack_slot]
        partitions = tuple(sorted({partition, *aggregate_partitions}, key=_partition_sort_key))
        variable_kind = (
            VariableKind.PARAMETER
            if stack_slot.role == StackSlotRole.ARGUMENT_HOME
            else VariableKind.LOCAL
        )
        scalar_type = partition_types.get(partition)
        return RecoveredVariable(
            name=_name_for_stack_slot(stack_slot),
            kind=variable_kind,
            size=root.size,
            binding=VariableBinding(
                kind=VariableBindingKind.STACK_SLOT,
                stack_slot=stack_slot,
            ),
            scalar_type=scalar_type,
            root_value=root,
            aggregate_layout=layout,
            partitions=partitions,
        )

    if (
        isinstance(root, SSAName)
        and root.kind == SSANameKind.REGISTER
        and root.version == 0
        and root.base in abi_argument_registers
        and live_in_by_register.get(root.base) == root
    ):
        return RecoveredVariable(
            name=f"arg_x{root.base}_{root.size}",
            kind=VariableKind.PARAMETER,
            size=root.size,
            binding=VariableBinding(
                kind=VariableBindingKind.ROOT_VALUE,
                root_value=root,
            ),
            scalar_type=None,
            root_value=root,
            aggregate_layout=layout,
            partitions=tuple(sorted(aggregate_partitions, key=_partition_sort_key)),
        )

    return RecoveredVariable(
        name=f"root_{_sanitize_value(root)}_{root.size}",
        kind=VariableKind.INDIRECT,
        size=root.size,
        binding=VariableBinding(
            kind=VariableBindingKind.ROOT_VALUE,
            root_value=root,
        ),
        scalar_type=None,
        root_value=root,
        aggregate_layout=layout,
        partitions=tuple(sorted(aggregate_partitions, key=_partition_sort_key)),
    )


def _choose_aggregate_stack_slot_anchor(
    root: SSAValue,
    stack_partition_by_slot: dict[StackSlot, MemoryPartition],
    *,
    abi_argument_registers: set[int],
) -> StackSlot | None:
    if isinstance(root, SSAName) and root.kind == SSANameKind.REGISTER and root.base in abi_argument_registers:
        for slot in sorted(stack_partition_by_slot, key=lambda item: (item.frame_offset, item.size)):
            if (
                slot.role == StackSlotRole.ARGUMENT_HOME
                and slot.argument_register == root.base
                and slot.size == root.size
            ):
                return slot

    for slot in sorted(stack_partition_by_slot, key=lambda item: (item.frame_offset, item.size)):
        if slot.role == StackSlotRole.SAVED_REGISTER:
            continue
        if any(access.value == root for access in slot.accesses):
            return slot
    return None


def _deduplicate_variable_names(variables: list[RecoveredVariable]) -> None:
    """Append numeric suffixes to resolve any duplicate variable names.

    Multiple recovery paths (aggregate layout, stack-slot, register-only
    parameter) can independently produce the same name when their naming
    inputs coincide.  This pass ensures uniqueness by appending ``_2``,
    ``_3``, etc. to later duplicates.  The list is mutated in place.
    """
    from dataclasses import replace

    seen: dict[str, int] = {}
    for i, variable in enumerate(variables):
        count = seen.get(variable.name, 0) + 1
        seen[variable.name] = count
        if count > 1:
            variables[i] = replace(variable, name=f"{variable.name}_{count}")


def _name_for_stack_slot(slot: StackSlot) -> str:
    if slot.role == StackSlotRole.ARGUMENT_HOME and slot.argument_register is not None:
        return f"arg_x{slot.argument_register}_{slot.size}"
    if slot.role == StackSlotRole.LOCAL:
        return f"local_{abs(slot.frame_offset)}_{slot.size}"
    return f"slot_{abs(slot.frame_offset)}_{slot.size}"


def _name_for_value_partition(partition: MemoryPartition) -> str:
    assert partition.kind == MemoryPartitionKind.VALUE
    assert partition.base_value is not None
    return (
        f"deref_{_sanitize_value(partition.base_value)}_"
        f"{_offset_tag(partition.offset)}_{partition.size}"
    )


def _sanitize_value(value: SSAValue) -> str:
    if isinstance(value, SSAName):
        prefix = "x" if value.kind == SSANameKind.REGISTER else "u"
        return f"{prefix}{value.base}_{value.version}"
    text = value.to_pretty()
    return (
        text.replace(":", "_")
        .replace("+", "p")
        .replace("-", "m")
        .replace(" ", "_")
    )


def _offset_tag(offset: int) -> str:
    if offset >= 0:
        return f"p{offset}"
    return f"m{abs(offset)}"


_partition_sort_key = partition_sort_key
