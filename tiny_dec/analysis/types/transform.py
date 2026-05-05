"""Stage-11 scalar type recovery from stage-10 memory facts.

This file owns the transformation from stage-10 memory modeling into stage-11
scalar type facts.

Implementation notes:
- The stage is read-only with respect to upstream CFG, SSA, call, stack, and
  memory artifacts.
- It preserves upstream `pending_entries` and `invalidated_entries` unchanged.
- The algorithm builds deterministic scalar-identity groups across SSA copies,
  phi nodes, and stage-10 memory traffic.
- It seeds conservative scalar evidence from stage-10 value partitions,
  comparisons, boolean operators, arithmetic, and address-style argument-home
  reloads.
- Conflicting precise evidence degrades to `word` rather than inventing a
  stronger type.
- Unsupported or absent evidence leaves a value or partition untyped.

Educational note — the type lattice is intentionally flat: each SSA
value or memory partition receives at most one scalar type from the set
{bool, signed, unsigned, pointer, word}.  There is no subtyping,
parametric polymorphism, or integer-width–sensitive typing.  Two values
connected by COPY or PHI edges are placed in the same union-find group
and must agree on a single type; conflicting evidence (e.g. one use
as signed, another as unsigned) degrades to `word`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from tiny_dec.analysis._helpers import (
    is_const_ssa,
    opcode_text,
    value_size,
    value_sort_key,
)
from tiny_dec.analysis.memory import (
    FunctionMemoryFacts,
    MemoryPartition,
    MemoryPartitionKind,
    ProgramMemoryFacts,
    build_program_memory_facts,
)
from tiny_dec.analysis.ssa import SSAName, SSAOp
from tiny_dec.analysis.ssa.models import SSAValue
from tiny_dec.analysis.stack import StackSlotRole
from tiny_dec.analysis.types.models import (
    FunctionScalarTypeFacts,
    PartitionScalarTypeFact,
    ProgramScalarTypeFacts,
    ScalarType,
    ScalarTypeKind,
    ValueScalarTypeFact,
)
from tiny_dec.loader import ProgramView


type _Entity = MemoryPartition | SSAValue

_BOOL_COMPARE_OPS = frozenset({"INT_EQUAL", "INT_NOTEQUAL", "INT_SLESS", "INT_LESS"})  # all comparison opcodes in PcodeOpcode
_WORD_OPS = frozenset({"INT_AND", "INT_OR", "INT_XOR"})
_SHIFT_OR_EXTEND_OPS = frozenset(
    {"INT_LEFT", "INT_RIGHT", "INT_SRIGHT", "INT_SEXT", "INT_ZEXT"}
)


@dataclass(frozen=True, slots=True)
class _GroupInfo:
    contains_argument_home_partition: bool = False
    contains_local_stack_partition: bool = False
    contains_call_return_value: bool = False


class _UnionFind:
    """Disjoint-set (union-find) for grouping SSA values and memory
    partitions that must share the same scalar type.  Copies, phi nodes,
    and load/store edges between SSA values and partitions create union
    constraints; the final type for each group is the meet of all
    evidence seeds contributed by its members.
    """
    def __init__(self) -> None:
        self._parent: dict[_Entity, _Entity] = {}

    def add(self, entity: _Entity) -> None:
        self._parent.setdefault(entity, entity)

    def find(self, entity: _Entity) -> _Entity:
        parent = self._parent.get(entity)
        if parent is None:
            self._parent[entity] = entity
            return entity
        if parent == entity:
            return entity
        root = self.find(parent)
        self._parent[entity] = root
        return root

    def union(self, left: _Entity, right: _Entity) -> None:
        if _entity_size(left) != _entity_size(right):
            raise ValueError("scalar-type identity edges must preserve value widths")

        self.add(left)
        self.add(right)
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return

        if _entity_sort_key(right_root) < _entity_sort_key(left_root):
            left_root, right_root = right_root, left_root
        self._parent[right_root] = left_root

    def grouped_entities(self) -> dict[_Entity, tuple[_Entity, ...]]:
        grouped: dict[_Entity, list[_Entity]] = {}
        for entity in self._parent:
            grouped.setdefault(self.find(entity), []).append(entity)
        return {
            root: tuple(sorted(members, key=_entity_sort_key))
            for root, members in grouped.items()
        }


def analyze_function_scalar_types(function: FunctionMemoryFacts) -> FunctionScalarTypeFacts:
    """Analyze one function and emit stage-11 scalar type facts."""

    union_find = _build_scalar_identity(function)
    groups = union_find.grouped_entities()
    group_of = {
        entity: root
        for root, members in groups.items()
        for entity in members
    }
    group_info = _build_group_info(function, groups)
    direct_evidence = _build_direct_evidence(function, group_of)
    group_kinds = _resolve_group_kinds(function, group_of, group_info, direct_evidence)

    partition_facts = tuple(
        PartitionScalarTypeFact(
            partition=partition,
            scalar_type=ScalarType(kind, partition.size),
        )
        for partition in function.partitions
        if (kind := group_kinds[group_of[partition]]) is not None
    )

    values = sorted(
        (
            entity
            for root, members in groups.items()
            if group_kinds[root] is not None
            for entity in members
            if not isinstance(entity, MemoryPartition)
        ),
        key=_value_sort_key,
    )
    value_facts = tuple(
        ValueScalarTypeFact(
            value=value,
            scalar_type=ScalarType(kind, _value_size(value)),
        )
        for value in values
        if (kind := group_kinds[group_of[value]]) is not None
    )

    return FunctionScalarTypeFacts(
        memory=function,
        partition_facts=partition_facts,
        value_facts=value_facts,
    )


def analyze_program_scalar_types(program: ProgramMemoryFacts) -> ProgramScalarTypeFacts:
    """Analyze a whole program and emit stage-11 scalar type facts."""

    functions = {
        function.entry: analyze_function_scalar_types(function)
        for function in program.ordered_functions()
    }
    return ProgramScalarTypeFacts(
        memory=program,
        functions=functions,
        pending_entries=program.pending_entries,
        invalidated_entries=program.invalidated_entries,
    )


def build_function_scalar_type_facts(
    view: ProgramView,
    entry: int,
) -> FunctionScalarTypeFacts:
    """Build stage-10 memory facts first, then derive stage-11 scalar facts."""

    program = build_program_scalar_type_facts(view, entry)
    return program.functions[entry]


def build_program_scalar_type_facts(
    view: ProgramView,
    root_entry: int,
) -> ProgramScalarTypeFacts:
    """Build stage-10 memory facts first, then derive stage-11 scalar facts."""

    program = build_program_memory_facts(view, root_entry)
    return analyze_program_scalar_types(program)


def _build_scalar_identity(function: FunctionMemoryFacts) -> _UnionFind:
    union_find = _UnionFind()
    ssa = function.stack.calls.ssa

    for live_in in ssa.live_ins:
        union_find.add(live_in)

    for partition in function.partitions:
        union_find.add(partition)
        if partition.kind == MemoryPartitionKind.VALUE and partition.base_value is not None:
            if _is_tracked_value(partition.base_value):
                union_find.add(partition.base_value)
        for access in partition.accesses:
            if access.value is None or not _is_tracked_value(access.value):
                continue
            union_find.add(access.value)
            union_find.union(partition, access.value)

    for block in ssa.ordered_blocks():
        for phi in block.phis:
            union_find.add(phi.output)
            for phi_input in phi.inputs:
                if not _is_tracked_value(phi_input.value):
                    continue
                union_find.add(phi_input.value)
                union_find.union(phi.output, phi_input.value)

        for instruction in block.instructions:
            for op in instruction.ops:
                if op.output is not None:
                    union_find.add(op.output)
                for value in op.inputs:
                    if _is_tracked_value(value):
                        union_find.add(value)

                if op.output is None or _opcode_text(op) != "COPY" or not op.inputs:
                    continue
                copied = op.inputs[0]
                if not _is_tracked_value(copied):
                    continue
                union_find.union(op.output, copied)

    return union_find


def _build_group_info(
    function: FunctionMemoryFacts,
    groups: dict[_Entity, tuple[_Entity, ...]],
) -> dict[_Entity, _GroupInfo]:
    call_return_values = {
        op.output
        for block in function.stack.calls.ssa.ordered_blocks()
        for instruction in block.instructions
        for op in instruction.ops
        if op.output is not None and _opcode_text(op) == "CALL_RETURN"
    }
    info: dict[_Entity, _GroupInfo] = {}
    for root, members in groups.items():
        info[root] = _GroupInfo(
            contains_argument_home_partition=any(
                isinstance(entity, MemoryPartition)
                and entity.kind == MemoryPartitionKind.STACK_SLOT
                and entity.stack_slot is not None
                and entity.stack_slot.role == StackSlotRole.ARGUMENT_HOME
                for entity in members
            ),
            contains_local_stack_partition=any(
                isinstance(entity, MemoryPartition)
                and entity.kind == MemoryPartitionKind.STACK_SLOT
                and entity.stack_slot is not None
                and entity.stack_slot.role == StackSlotRole.LOCAL
                for entity in members
            ),
            contains_call_return_value=any(entity in call_return_values for entity in members),
        )
    return info


def _build_direct_evidence(
    function: FunctionMemoryFacts,
    group_of: dict[_Entity, _Entity],
) -> dict[_Entity, tuple[ScalarTypeKind, ...]]:
    evidence: dict[_Entity, list[ScalarTypeKind]] = {}

    def record(entity: _Entity | None, kind: ScalarTypeKind) -> None:
        if entity is None:
            return
        root = group_of.get(entity)
        if root is None:
            return
        evidence.setdefault(root, []).append(kind)

    for partition in function.partitions:
        if partition.kind == MemoryPartitionKind.ABSOLUTE:
            record(partition, ScalarTypeKind.WORD)
        if partition.kind == MemoryPartitionKind.VALUE and partition.base_value is not None:
            if _is_tracked_value(partition.base_value):
                record(partition.base_value, ScalarTypeKind.POINTER)

    ssa = function.stack.calls.ssa
    for block in ssa.ordered_blocks():
        for instruction in block.instructions:
            for op in instruction.ops:
                opcode = _opcode_text(op)
                output = op.output

                if opcode == "COPY" and output is not None and op.inputs and _is_const(op.inputs[0]):
                    record(output, ScalarTypeKind.INT)
                if opcode in _BOOL_COMPARE_OPS and output is not None:
                    record(output, ScalarTypeKind.BOOL)
                if opcode == "BOOL_NEGATE":
                    if output is not None:
                        record(output, ScalarTypeKind.BOOL)
                    if op.inputs:
                        record(_tracked_entity(op.inputs[0]), ScalarTypeKind.BOOL)
                if opcode == "CBRANCH":
                    condition = _branch_condition_entity(op)
                    record(condition, ScalarTypeKind.BOOL)

                if opcode in {"INT_SLESS", "INT_LESS"}:
                    for value in op.inputs:
                        record(_tracked_entity(value), ScalarTypeKind.INT)
                if opcode in {"INT_EQUAL", "INT_NOTEQUAL"}:
                    for value in op.inputs:
                        record(_tracked_entity(value), ScalarTypeKind.WORD)
                if opcode in _WORD_OPS:
                    if output is not None:
                        record(output, ScalarTypeKind.WORD)
                    for value in op.inputs:
                        record(_tracked_entity(value), ScalarTypeKind.WORD)
                if opcode in _SHIFT_OR_EXTEND_OPS and output is not None:
                    record(output, ScalarTypeKind.INT)

    return {
        root: tuple(kinds)
        for root, kinds in evidence.items()
    }


def _resolve_group_kinds(
    function: FunctionMemoryFacts,
    group_of: dict[_Entity, _Entity],
    group_info: dict[_Entity, _GroupInfo],
    direct_evidence: dict[_Entity, tuple[ScalarTypeKind, ...]],
) -> dict[_Entity, ScalarTypeKind | None]:
    roots = tuple(sorted(group_info, key=_entity_sort_key))
    current = {
        root: _merge_kinds(direct_evidence.get(root, ()))
        for root in roots
    }

    while True:
        evidence = {
            root: list(direct_evidence.get(root, ()))
            for root in roots
        }
        _add_relational_evidence(function, group_of, group_info, current, evidence)
        updated = {
            root: _merge_kinds(evidence[root])
            for root in roots
        }
        if updated == current:
            return updated
        current = updated


def _add_relational_evidence(
    function: FunctionMemoryFacts,
    group_of: dict[_Entity, _Entity],
    group_info: dict[_Entity, _GroupInfo],
    current: dict[_Entity, ScalarTypeKind | None],
    evidence: dict[_Entity, list[ScalarTypeKind]],
) -> None:
    def record(root: _Entity | None, kind: ScalarTypeKind) -> None:
        if root is None:
            return
        evidence[root].append(kind)

    ssa = function.stack.calls.ssa
    for block in ssa.ordered_blocks():
        for instruction in block.instructions:
            for op in instruction.ops:
                opcode = _opcode_text(op)
                if opcode == "INT_ADD":
                    _add_additive_evidence(op, group_of, group_info, current, record)
                elif opcode == "INT_SUB":
                    _add_subtractive_evidence(op, group_of, group_info, current, record)


def _add_additive_evidence(
    op: SSAOp,
    group_of: dict[_Entity, _Entity],
    group_info: dict[_Entity, _GroupInfo],
    current: dict[_Entity, ScalarTypeKind | None],
    record: Callable[[_Entity | None, ScalarTypeKind], None],
) -> None:
    output = op.output
    if output is None or len(op.inputs) != 2:
        return

    left = op.inputs[0]
    right = op.inputs[1]
    output_root = group_of.get(output)
    left_root = _group_root(left, group_of)
    right_root = _group_root(right, group_of)
    left_kind = current.get(left_root) if left_root is not None else None
    right_kind = current.get(right_root) if right_root is not None else None
    output_kind = current.get(output_root) if output_root is not None else None
    left_const = _is_const(left)
    right_const = _is_const(right)

    if (
        left_root is not None
        and right_const
        and group_info[left_root].contains_argument_home_partition
    ):
        record(left_root, ScalarTypeKind.POINTER)
        record(output_root, ScalarTypeKind.POINTER)
    if (
        right_root is not None
        and left_const
        and group_info[right_root].contains_argument_home_partition
    ):
        record(right_root, ScalarTypeKind.POINTER)
        record(output_root, ScalarTypeKind.POINTER)

    if (
        left_root is not None
        and right_const
        and output_kind != ScalarTypeKind.POINTER
        and _can_seed_local_call_result_int(group_info[left_root], left_kind)
    ):
        record(left_root, ScalarTypeKind.INT)
        record(output_root, ScalarTypeKind.INT)
    if (
        right_root is not None
        and left_const
        and output_kind != ScalarTypeKind.POINTER
        and _can_seed_local_call_result_int(group_info[right_root], right_kind)
    ):
        record(right_root, ScalarTypeKind.INT)
        record(output_root, ScalarTypeKind.INT)

    if output_kind == ScalarTypeKind.POINTER:
        if left_root is not None and (right_const or _is_non_pointer_scalar_kind(right_kind)):
            record(left_root, ScalarTypeKind.POINTER)
        if right_root is not None and (left_const or _is_non_pointer_scalar_kind(left_kind)):
            record(right_root, ScalarTypeKind.POINTER)
    elif output_kind == ScalarTypeKind.INT:
        if left_root is not None and (right_const or _is_non_pointer_scalar_kind(right_kind)):
            record(left_root, ScalarTypeKind.INT)
        if right_root is not None and (left_const or _is_non_pointer_scalar_kind(left_kind)):
            record(right_root, ScalarTypeKind.INT)

    if left_kind == ScalarTypeKind.POINTER or right_kind == ScalarTypeKind.POINTER:
        record(output_root, ScalarTypeKind.POINTER)
        return

    if output_kind == ScalarTypeKind.POINTER:
        return

    if _is_non_pointer_scalar_kind(left_kind) or _is_non_pointer_scalar_kind(right_kind):
        record(output_root, ScalarTypeKind.INT)


def _add_subtractive_evidence(
    op: SSAOp,
    group_of: dict[_Entity, _Entity],
    group_info: dict[_Entity, _GroupInfo],
    current: dict[_Entity, ScalarTypeKind | None],
    record: Callable[[_Entity | None, ScalarTypeKind], None],
) -> None:
    output = op.output
    if output is None or len(op.inputs) != 2:
        return

    left = op.inputs[0]
    right = op.inputs[1]
    output_root = group_of.get(output)
    left_root = _group_root(left, group_of)
    right_root = _group_root(right, group_of)
    left_kind = current.get(left_root) if left_root is not None else None
    right_kind = current.get(right_root) if right_root is not None else None
    output_kind = current.get(output_root) if output_root is not None else None
    right_const = _is_const(right)

    if (
        left_root is not None
        and right_const
        and group_info[left_root].contains_argument_home_partition
    ):
        record(left_root, ScalarTypeKind.POINTER)
        record(output_root, ScalarTypeKind.POINTER)

    if (
        left_root is not None
        and right_const
        and output_kind != ScalarTypeKind.POINTER
        and _can_seed_local_call_result_int(group_info[left_root], left_kind)
    ):
        record(left_root, ScalarTypeKind.INT)
        record(output_root, ScalarTypeKind.INT)

    if output_kind == ScalarTypeKind.POINTER:
        if left_root is not None and (right_const or _is_non_pointer_scalar_kind(right_kind)):
            record(left_root, ScalarTypeKind.POINTER)
    elif output_kind == ScalarTypeKind.INT:
        if left_root is not None and (right_const or _is_non_pointer_scalar_kind(right_kind)):
            record(left_root, ScalarTypeKind.INT)
        if right_root is not None and _is_non_pointer_scalar_kind(left_kind):
            record(right_root, ScalarTypeKind.INT)

    if left_kind == ScalarTypeKind.POINTER:
        record(output_root, ScalarTypeKind.POINTER)
        return

    if output_kind == ScalarTypeKind.POINTER:
        return

    if _is_non_pointer_scalar_kind(left_kind) or _is_non_pointer_scalar_kind(right_kind):
        record(output_root, ScalarTypeKind.INT)


def _merge_kinds(kinds: tuple[ScalarTypeKind, ...] | list[ScalarTypeKind]) -> ScalarTypeKind | None:
    merged: ScalarTypeKind | None = None
    conflicted = False
    for kind in kinds:
        if merged is None:
            merged = kind
            continue
        if merged == kind:
            continue
        if merged == ScalarTypeKind.WORD:
            merged = kind
            continue
        if kind == ScalarTypeKind.WORD:
            continue
        conflicted = True
    if conflicted:
        return ScalarTypeKind.WORD
    return merged


def _group_root(
    value: SSAValue,
    group_of: dict[_Entity, _Entity],
) -> _Entity | None:
    entity = _tracked_entity(value)
    if entity is None:
        return None
    return group_of.get(entity)


def _tracked_entity(value: SSAValue) -> SSAValue | None:
    if _is_tracked_value(value):
        return value
    return None


def _is_tracked_value(value: SSAValue) -> bool:
    if isinstance(value, SSAName):
        return True
    return not _is_const(value)


def _branch_condition_entity(op: SSAOp) -> SSAValue | None:
    if len(op.inputs) >= 2:
        return _tracked_entity(op.inputs[1])
    if len(op.inputs) == 1:
        return _tracked_entity(op.inputs[0])
    return None


def _entity_sort_key(entity: _Entity) -> tuple[int, str]:
    if isinstance(entity, MemoryPartition):
        return (0, entity.identity_pretty())
    return (1, entity.to_pretty())


def _entity_size(entity: _Entity) -> int:
    if isinstance(entity, MemoryPartition):
        return entity.size
    return _value_size(entity)


_value_sort_key = value_sort_key

_value_size = value_size

_is_const = is_const_ssa


def _is_non_pointer_scalar_kind(kind: ScalarTypeKind | None) -> bool:
    return kind in {ScalarTypeKind.BOOL, ScalarTypeKind.INT, ScalarTypeKind.WORD}


def _can_seed_local_call_result_int(
    info: _GroupInfo,
    kind: ScalarTypeKind | None,
) -> bool:
    return (
        info.contains_local_stack_partition
        and info.contains_call_return_value
        and kind not in {ScalarTypeKind.BOOL, ScalarTypeKind.POINTER}
    )


_opcode_text = opcode_text
