"""Stage-10 memory modeling from stage-9 stack facts.

This file owns the transformation from stage-9 stack recovery into stage-10
memory facts.

Implementation notes:
- The stage is read-only with respect to upstream CFG, SSA, call, and stack
  artifacts.
- It preserves upstream `pending_entries` and `invalidated_entries` unchanged.
- The algorithm walks SSA blocks in dominator-tree order while tracking
  symbolic address expressions of three forms:
  - stack slot addresses rooted at the entry frame top
  - absolute addresses
  - value-root addresses of the form `base_value + constant`
- Value-root addresses may additionally carry one scaled dynamic index of the
  form `base_value + (index_value * stride) + constant`. The dynamic index is
  preserved in the tracked address but intentionally dropped from the exposed
  partition identity so repeated field loads still group by pointer root and
  field offset.
- `COPY`, `INT_ADD`, `INT_SUB`, and `INT_LEFT` are the only arithmetic forms
  that may keep an address expression or one scaled index tracked.
- Loads from stage-9 `argument_home` slots may re-seed a pointer root from the
  corresponding live-in register so later constant-offset dereferences remain
  attributable to that argument.
- Unsupported or non-constant address arithmetic falls back to a deterministic
  value-based partition keyed by the raw SSA address value at the access site
  rather than guessing a stronger alias class.

Simplifying assumptions:
- No alias analysis: two value-root partitions with different SSA base
  values are assumed disjoint even when they may point to the same object
  at runtime.  This is safe (overly conservative) but means the
  decompiler may show redundant loads that a real alias analysis would
  eliminate.
- The only tracked address arithmetic is linear (add/sub/shift by
  constant).  Multiplications, divisions, or multi-level indirections
  produce an opaque partition per access site.
- Power-of-2 strides are recognized via INT_LEFT; arbitrary element
  sizes (e.g. struct arrays with non-power-of-2 stride) require an
  INT_ADD with a constant that happens to equal the product.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from tiny_dec.analysis._helpers import (
    build_dominator_children,
    opcode_text,
    partition_sort_key,
    signed_const,
)
from tiny_dec.analysis.memory.models import (
    FunctionMemoryFacts,
    MemoryAccess,
    MemoryAccessKind,
    MemoryPartition,
    MemoryPartitionKind,
    ProgramMemoryFacts,
)
from tiny_dec.analysis.ssa import MemoryVersion, SSAFunctionIR, SSAName, SSANameKind, SSAOp
from tiny_dec.analysis.ssa.models import SSAValue
from tiny_dec.analysis.stack import (
    FunctionStackFacts,
    ProgramStackFacts,
    StackAccess,
    StackAccessKind,
    StackSlot,
    StackSlotRole,
    build_program_stack_facts,
)
from tiny_dec.ir.pcode import PcodeSpace, Varnode
from tiny_dec.loader import ProgramView


@dataclass(frozen=True, slots=True)
class _TrackedAddress:
    stack_frame_offset: int | None = None
    absolute_address: int | None = None
    base_value: SSAValue | None = None
    value_offset: int = 0
    index_value: SSAValue | None = None
    index_stride: int | None = None

    def __post_init__(self) -> None:
        kinds = sum(
            (
                self.stack_frame_offset is not None,
                self.absolute_address is not None,
                self.base_value is not None,
            )
        )
        if kinds != 1:
            raise ValueError("tracked addresses must carry exactly one address form")
        if (self.index_value is None) != (self.index_stride is None):
            raise ValueError("tracked addresses must carry both dynamic-index fields")
        if self.index_value is not None and self.base_value is None:
            raise ValueError("only value-root tracked addresses may carry dynamic indexes")
        if self.index_stride is not None and self.index_stride <= 0:
            raise ValueError("tracked address dynamic-index stride must be positive")

    @classmethod
    def stack(cls, frame_offset: int) -> _TrackedAddress:
        return cls(stack_frame_offset=frame_offset)

    @classmethod
    def absolute(cls, address: int) -> _TrackedAddress:
        return cls(absolute_address=address)

    @classmethod
    def value(
        cls,
        base_value: SSAValue,
        offset: int = 0,
        index_value: SSAValue | None = None,
        index_stride: int | None = None,
    ) -> _TrackedAddress:
        return cls(
            base_value=base_value,
            value_offset=offset,
            index_value=index_value,
            index_stride=index_stride,
        )

    def add_const(self, delta: int) -> _TrackedAddress:
        if self.stack_frame_offset is not None:
            return _TrackedAddress.stack(self.stack_frame_offset + delta)
        if self.absolute_address is not None:
            return _TrackedAddress.absolute(self.absolute_address + delta)
        assert self.base_value is not None
        return _TrackedAddress.value(
            self.base_value,
            self.value_offset + delta,
            index_value=self.index_value,
            index_stride=self.index_stride,
        )

    def add_scaled(self, scaled: _ScaledValue) -> _TrackedAddress | None:
        if self.base_value is None or self.index_value is not None:
            return None
        return _TrackedAddress.value(
            self.base_value,
            self.value_offset,
            index_value=scaled.base_value,
            index_stride=scaled.scale,
        )


@dataclass(frozen=True, slots=True)
class _ScaledValue:
    base_value: SSAValue
    scale: int

    def __post_init__(self) -> None:
        if self.scale <= 0:
            raise ValueError("scaled value scale must be positive")


type _PartitionKey = tuple[str, object, int, int]
type _AccessKey = tuple[int, int, MemoryAccessKind, int, SSAValue | None]
type _AccessVersions = tuple[MemoryVersion | None, MemoryVersion | None]


def analyze_function_memory(function: FunctionStackFacts) -> FunctionMemoryFacts:
    """Analyze one function and emit stage-10 memory facts."""

    access_versions = _collect_access_versions(function.calls.ssa)
    stack_slot_partitions = [
        _build_stack_partition(slot, access_versions)
        for slot in function.slots
    ]
    stack_slots = {(slot.frame_offset, slot.size): slot for slot in function.slots}
    grouped_accesses: dict[_PartitionKey, list[MemoryAccess]] = {}

    ssa = function.calls.ssa
    tracked_values = _recover_tracked_values(function, stack_slots)

    for block in ssa.ordered_blocks():
        for instruction in block.instructions:
            for op in instruction.ops:
                recovered = _recover_partitioned_access(
                    op,
                    instruction_address=instruction.address,
                    block_start=block.start,
                    current=tracked_values,
                    stack_slots=stack_slots,
                )
                if recovered is not None:
                    key, access = recovered
                    grouped_accesses.setdefault(key, []).append(access)

    non_stack_partitions = [
        _build_non_stack_partition(key, accesses)
        for key, accesses in grouped_accesses.items()
    ]
    partitions = tuple(
        sorted(
            [*stack_slot_partitions, *non_stack_partitions],
            key=_partition_sort_key,
        )
    )
    return FunctionMemoryFacts(
        stack=function,
        partitions=partitions,
    )


def analyze_program_memory(program: ProgramStackFacts) -> ProgramMemoryFacts:
    """Analyze a whole program and emit stage-10 memory facts."""

    functions = {
        function.entry: analyze_function_memory(function)
        for function in program.ordered_functions()
    }
    return ProgramMemoryFacts(
        stack=program,
        functions=functions,
        pending_entries=program.pending_entries,
        invalidated_entries=program.invalidated_entries,
    )


def build_function_memory_facts(view: ProgramView, entry: int) -> FunctionMemoryFacts:
    """Build stage-9 stack facts first, then derive stage-10 memory facts."""

    program = build_program_memory_facts(view, entry)
    return program.functions[entry]


def build_program_memory_facts(view: ProgramView, root_entry: int) -> ProgramMemoryFacts:
    """Build stage-9 stack facts first, then derive stage-10 memory facts."""

    program = build_program_stack_facts(view, root_entry)
    return analyze_program_memory(program)


def _build_stack_partition(
    slot: StackSlot,
    access_versions: dict[_AccessKey, _AccessVersions],
) -> MemoryPartition:
    return MemoryPartition(
        kind=MemoryPartitionKind.STACK_SLOT,
        size=slot.size,
        stack_slot=slot,
        accesses=tuple(
            _stack_access_to_memory_access(access, access_versions)
            for access in slot.accesses
        ),
    )


def _stack_access_to_memory_access(
    access: StackAccess,
    access_versions: dict[_AccessKey, _AccessVersions],
) -> MemoryAccess:
    kind = (
        MemoryAccessKind.LOAD
        if access.kind == StackAccessKind.LOAD
        else MemoryAccessKind.STORE
    )
    memory_before, memory_after = access_versions.get(
        _access_key(
            instruction_address=access.instruction_address,
            block_start=access.block_start,
            kind=kind,
            size=access.size,
            value=access.value,
        ),
        (None, None),
    )
    return MemoryAccess(
        instruction_address=access.instruction_address,
        block_start=access.block_start,
        kind=kind,
        size=access.size,
        value=access.value,
        memory_before=memory_before,
        memory_after=memory_after,
    )


_build_dominator_children = build_dominator_children


def _recover_tracked_values(
    function: FunctionStackFacts,
    stack_slots: dict[tuple[int, int], StackSlot],
) -> dict[SSAName | Varnode, _TrackedAddress]:
    ssa = function.calls.ssa
    live_in_roots = {
        live_in.base: live_in
        for live_in in ssa.live_ins
        if live_in.kind == SSANameKind.REGISTER and live_in.base != 2
    }
    tracked: dict[SSAName | Varnode, _TrackedAddress] = {}
    scaled: dict[SSAName | Varnode, _ScaledValue] = {}

    for live_in in ssa.live_ins:
        if live_in.kind != SSANameKind.REGISTER:
            continue
        if live_in.base == 2:
            tracked[live_in] = _TrackedAddress.stack(0)
            continue
        tracked[live_in] = _TrackedAddress.value(live_in)

    changed = True
    while changed:
        changed = False

        for block in ssa.ordered_blocks():
            for phi in block.phis:
                candidate = _recover_phi_tracked_output(phi.inputs, tracked)
                if candidate is None or tracked.get(phi.output) == candidate:
                    pass
                else:
                    tracked[phi.output] = candidate
                    changed = True
                scaled_candidate = _recover_phi_scaled_output(phi.inputs, scaled)
                if scaled_candidate is None or scaled.get(phi.output) == scaled_candidate:
                    continue
                scaled[phi.output] = scaled_candidate
                changed = True

            for instruction in block.instructions:
                for op in instruction.ops:
                    tracked_output = _recover_tracked_output(
                        op,
                        current=tracked,
                        scaled_values=scaled,
                        stack_slots=stack_slots,
                        live_in_roots=live_in_roots,
                    )
                    scaled_output = _recover_scaled_output(op, current=scaled)
                    if op.output is None or tracked_output is None:
                        pass
                    elif tracked.get(op.output) != tracked_output:
                        tracked[op.output] = tracked_output
                        changed = True
                    if op.output is None or scaled_output is None:
                        continue
                    if scaled.get(op.output) == scaled_output:
                        continue
                    scaled[op.output] = scaled_output
                    changed = True

    return tracked


def _recover_partitioned_access(
    op: SSAOp,
    *,
    instruction_address: int,
    block_start: int,
    current: dict[SSAName | Varnode, _TrackedAddress],
    stack_slots: dict[tuple[int, int], StackSlot],
) -> tuple[_PartitionKey, MemoryAccess] | None:
    opcode = _opcode_text(op)
    if opcode == "LOAD":
        output = op.output
        if output is None or not op.inputs:
            return None
        address_value = op.inputs[0]
        tracked = _tracked_input(address_value, current)
        key = _recover_partition_key(
            address_value=address_value,
            tracked=tracked,
            size=output.size,
            stack_slots=stack_slots,
        )
        if key is None:
            return None
        return (
            key,
            MemoryAccess(
                instruction_address=instruction_address,
                block_start=block_start,
                kind=MemoryAccessKind.LOAD,
                size=output.size,
                value=output,
                memory_before=op.memory_before,
                memory_after=op.memory_after,
            ),
        )

    if opcode == "STORE" and len(op.inputs) >= 2:
        address_value = op.inputs[0]
        value = op.inputs[1]
        tracked = _tracked_input(address_value, current)
        key = _recover_partition_key(
            address_value=address_value,
            tracked=tracked,
            size=value.size,
            stack_slots=stack_slots,
        )
        if key is None:
            return None
        return (
            key,
            MemoryAccess(
                instruction_address=instruction_address,
                block_start=block_start,
                kind=MemoryAccessKind.STORE,
                size=value.size,
                value=value,
                memory_before=op.memory_before,
                memory_after=op.memory_after,
            ),
        )

    return None


def _collect_access_versions(
    function: SSAFunctionIR,
) -> dict[_AccessKey, _AccessVersions]:
    versions: dict[_AccessKey, _AccessVersions] = {}
    for block in function.ordered_blocks():
        for instruction in block.instructions:
            for op in instruction.ops:
                opcode = _opcode_text(op)
                if opcode == "LOAD":
                    output = op.output
                    if output is None:
                        continue
                    key = _access_key(
                        instruction_address=instruction.address,
                        block_start=block.start,
                        kind=MemoryAccessKind.LOAD,
                        size=output.size,
                        value=output,
                    )
                    versions[key] = (op.memory_before, op.memory_after)
                elif opcode == "STORE" and len(op.inputs) >= 2:
                    value = op.inputs[1]
                    key = _access_key(
                        instruction_address=instruction.address,
                        block_start=block.start,
                        kind=MemoryAccessKind.STORE,
                        size=value.size,
                        value=value,
                    )
                    versions[key] = (op.memory_before, op.memory_after)
    return versions


def _access_key(
    *,
    instruction_address: int,
    block_start: int,
    kind: MemoryAccessKind,
    size: int,
    value: SSAValue | None,
) -> _AccessKey:
    return (instruction_address, block_start, kind, size, value)


def _recover_partition_key(
    *,
    address_value: SSAValue,
    tracked: _TrackedAddress | None,
    size: int,
    stack_slots: dict[tuple[int, int], StackSlot],
) -> _PartitionKey | None:
    if tracked is None:
        return ("value", address_value, 0, size)

    if tracked.stack_frame_offset is not None:
        if (tracked.stack_frame_offset, size) in stack_slots:
            return None
        return ("value", address_value, 0, size)

    if tracked.absolute_address is not None:
        return ("absolute", tracked.absolute_address, 0, size)

    assert tracked.base_value is not None
    return ("value", tracked.base_value, tracked.value_offset, size)


def _recover_tracked_output(
    op: SSAOp,
    *,
    current: dict[SSAName | Varnode, _TrackedAddress],
    scaled_values: dict[SSAName | Varnode, _ScaledValue],
    stack_slots: dict[tuple[int, int], StackSlot],
    live_in_roots: dict[int, SSAName],
) -> _TrackedAddress | None:
    output = op.output
    if output is None:
        return None

    opcode = _opcode_text(op)
    if opcode == "COPY" and op.inputs:
        return _tracked_input(op.inputs[0], current)

    if opcode == "INT_ADD":
        return _recover_additive_output(op.inputs, current, scaled_values)

    if opcode == "INT_SUB":
        return _recover_subtractive_output(op.inputs, current)

    if opcode == "LOAD" and op.inputs:
        tracked_address = _tracked_input(op.inputs[0], current)
        if tracked_address is None or tracked_address.stack_frame_offset is None:
            return None
        slot = stack_slots.get((tracked_address.stack_frame_offset, output.size))
        if slot is None or slot.role != StackSlotRole.ARGUMENT_HOME:
            return None
        if slot.argument_register is None:
            return None
        live_in = live_in_roots.get(slot.argument_register)
        if live_in is None:
            return None
        return _TrackedAddress.value(live_in)

    return None


def _recover_phi_tracked_output(
    inputs: tuple,
    current: dict[SSAName | Varnode, _TrackedAddress],
) -> _TrackedAddress | None:
    tracked_inputs = [
        _tracked_input(phi_input.value, current)
        for phi_input in inputs
    ]
    if any(tracked is None for tracked in tracked_inputs) or not tracked_inputs:
        return None
    first = tracked_inputs[0]
    assert first is not None
    if any(tracked != first for tracked in tracked_inputs[1:]):
        return None
    return first


def _recover_phi_scaled_output(
    inputs: tuple,
    current: dict[SSAName | Varnode, _ScaledValue],
) -> _ScaledValue | None:
    scaled_inputs = [_scaled_input(phi_input.value, current) for phi_input in inputs]
    if any(value is None for value in scaled_inputs) or not scaled_inputs:
        return None
    first = scaled_inputs[0]
    assert first is not None
    if any(value != first for value in scaled_inputs[1:]):
        return None
    return first


def _recover_additive_output(
    inputs: tuple[SSAName | Varnode, ...],
    current: dict[SSAName | Varnode, _TrackedAddress],
    scaled_values: dict[SSAName | Varnode, _ScaledValue],
) -> _TrackedAddress | None:
    if len(inputs) != 2:
        return None

    left = _tracked_input(inputs[0], current)
    right = _tracked_input(inputs[1], current)
    left_scaled = _scaled_input(inputs[0], scaled_values)
    right_scaled = _scaled_input(inputs[1], scaled_values)
    left_const = _signed_const(inputs[0])
    right_const = _signed_const(inputs[1])

    if left is not None and right_const is not None:
        return left.add_const(right_const)

    if right is not None and left_const is not None:
        return right.add_const(left_const)

    if left is not None and right_scaled is not None:
        return left.add_scaled(right_scaled)

    if right is not None and left_scaled is not None:
        return right.add_scaled(left_scaled)

    return None


def _recover_subtractive_output(
    inputs: tuple[SSAName | Varnode, ...],
    current: dict[SSAName | Varnode, _TrackedAddress],
) -> _TrackedAddress | None:
    if len(inputs) != 2:
        return None

    left = _tracked_input(inputs[0], current)
    right_const = _signed_const(inputs[1])
    if left is None or right_const is None:
        return None
    return left.add_const(-right_const)


def _tracked_input(
    value: SSAName | Varnode,
    current: dict[SSAName | Varnode, _TrackedAddress],
) -> _TrackedAddress | None:
    tracked = current.get(value)
    if tracked is not None:
        return tracked
    absolute_address = _absolute_const(value)
    if absolute_address is not None:
        return _TrackedAddress.absolute(absolute_address)
    return None


def _recover_scaled_output(
    op: SSAOp,
    *,
    current: dict[SSAName | Varnode, _ScaledValue],
) -> _ScaledValue | None:
    if op.output is None:
        return None

    opcode = _opcode_text(op)
    if opcode == "COPY" and op.inputs:
        return _scaled_input(op.inputs[0], current)

    if opcode != "INT_LEFT" or len(op.inputs) != 2:  # INT_MUL not needed for RV32I base ISA
        return None

    shift = _signed_const(op.inputs[1])
    if shift is None or shift < 0:
        return None

    input_scaled = _scaled_input(op.inputs[0], current)
    if input_scaled is not None:
        return _ScaledValue(
            base_value=input_scaled.base_value,
            scale=input_scaled.scale << shift,
        )
    return _ScaledValue(base_value=op.inputs[0], scale=1 << shift)


def _scaled_input(
    value: SSAName | Varnode,
    current: dict[SSAName | Varnode, _ScaledValue],
) -> _ScaledValue | None:
    return current.get(value)


def _build_non_stack_partition(
    key: _PartitionKey,
    accesses: list[MemoryAccess],
) -> MemoryPartition:
    kind_text, detail, offset, size = key
    ordered_accesses = tuple(
        sorted(
            accesses,
            key=lambda access: (
                access.instruction_address,
                access.kind.value,
                access.block_start,
            ),
        )
    )
    if kind_text == MemoryPartitionKind.ABSOLUTE.value:
        assert isinstance(detail, int)
        return MemoryPartition(
            kind=MemoryPartitionKind.ABSOLUTE,
            size=size,
            absolute_address=detail,
            accesses=ordered_accesses,
        )
    return MemoryPartition(
        kind=MemoryPartitionKind.VALUE,
        size=size,
        base_value=cast(SSAValue, detail),
        offset=offset,
        accesses=ordered_accesses,
    )


_partition_sort_key = partition_sort_key


def _absolute_const(value: SSAName | Varnode) -> int | None:
    if not isinstance(value, Varnode):
        return None
    space = value.space.value if isinstance(value.space, PcodeSpace) else value.space
    if space != PcodeSpace.CONST.value:
        return None
    return value.offset


_signed_const = signed_const

_opcode_text = opcode_text
