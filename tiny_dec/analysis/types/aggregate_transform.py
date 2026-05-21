"""Stage-12 aggregate layout recovery from stage-11 scalar type facts.

This file owns the transformation from stage-11 scalar recovery into stage-12
aggregate layout facts.

Implementation notes:
- The stage is read-only with respect to upstream CFG, SSA, call, stack,
  memory, and scalar-type artifacts.
- It preserves upstream `pending_entries` and `invalidated_entries` unchanged.
- The algorithm rebuilds conservative pointer-identity groups across pointer
  values via copies, phis, and pointer-typed memory partitions so root values
  stay deterministic.
- It tracks integer stride hints through a small arithmetic subset and then
  tracks pointer expressions of the form
  `canonical_root + unknown_multiple_of(stride) + constant`.
- Only scalar-typed `MemoryPartitionKind.VALUE` partitions become aggregate
  field candidates in the first implementation.
- Unsupported pointer arithmetic, conflicting field widths, and ambiguous
  memory-to-pointer identity propagation bail out conservatively instead of
  inventing a stronger layout.

Simplifying assumptions:
- Aggregate field merging assumes fields at the same base+offset with
  compatible types are the same struct/array field.  Unions (overlapping
  fields at the same offset with incompatible types) cause the merge to
  bail out, leaving the fields as separate partitions.
- Stride-based array detection only recognizes power-of-2 element sizes
  derived from INT_LEFT shifts.  Non-power-of-2 struct arrays (e.g.
  12-byte elements) produce per-access partitions instead.
- Pointer identity groups are built from SSA dataflow only; pointer
  arithmetic that crosses function boundaries is not tracked.
"""

from __future__ import annotations

from dataclasses import dataclass

from tiny_dec.analysis._helpers import (
    is_const_ssa,
    opcode_text,
    partition_sort_key,
    signed_const,
    value_size,
    value_sort_key,
)
from tiny_dec.analysis.memory.models import MemoryPartition, MemoryPartitionKind
from tiny_dec.analysis.ssa import SSAOp
from tiny_dec.analysis.ssa.models import SSAValue
from tiny_dec.analysis.types.aggregate_models import (
    AggregateField,
    AggregateLayout,
    AggregateRoot,
    AggregateRootKind,
    FunctionAggregateTypeFacts,
    ProgramAggregateTypeFacts,
)
from tiny_dec.analysis.types.models import (
    FunctionScalarTypeFacts,
    ProgramScalarTypeFacts,
    ScalarType,
    ScalarTypeKind,
)
from tiny_dec.analysis.types.transform import build_program_scalar_type_facts
from tiny_dec.ir.pcode import PcodeSpace, Varnode
from tiny_dec.loader import ProgramView


type _PointerValueMap = dict[SSAValue, ScalarType]

type _PartitionTypeMap = dict[MemoryPartition, ScalarType]


@dataclass(frozen=True, slots=True)
class _PointerExpr:
    root: SSAValue
    constant_offset: int = 0
    stride: int | None = None


@dataclass(slots=True)
class _MergedField:
    scalar_type: ScalarType
    partitions: list[MemoryPartition]


class _UnionFind:
    def __init__(self) -> None:
        self._parent: dict[SSAValue, SSAValue] = {}

    def add(self, value: SSAValue) -> None:
        self._parent.setdefault(value, value)

    def find(self, value: SSAValue) -> SSAValue:
        parent = self._parent.get(value)
        if parent is None:
            self._parent[value] = value
            return value
        if parent == value:
            return value
        root = self.find(parent)
        self._parent[value] = root
        return root

    def union(self, left: SSAValue, right: SSAValue) -> None:
        if _value_size(left) != _value_size(right):
            raise ValueError("aggregate pointer-identity edges must preserve value widths")

        self.add(left)
        self.add(right)
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return

        if _value_sort_key(right_root) < _value_sort_key(left_root):
            left_root, right_root = right_root, left_root
        self._parent[right_root] = left_root

    def grouped_values(self) -> dict[SSAValue, tuple[SSAValue, ...]]:
        grouped: dict[SSAValue, list[SSAValue]] = {}
        for value in self._parent:
            grouped.setdefault(self.find(value), []).append(value)
        return {
            root: tuple(sorted(values, key=_value_sort_key))
            for root, values in grouped.items()
        }


def analyze_function_aggregate_types(
    function: FunctionScalarTypeFacts,
) -> FunctionAggregateTypeFacts:
    """Analyze one function and emit stage-12 aggregate layout facts."""

    partition_types = {
        fact.partition: fact.scalar_type
        for fact in function.partition_facts
    }
    pointer_value_types = {
        fact.value: fact.scalar_type
        for fact in function.value_facts
        if fact.scalar_type.kind == ScalarTypeKind.POINTER
    }
    scalar_value_types = {
        fact.value: fact.scalar_type
        for fact in function.value_facts
    }

    canonical_root_of = _build_canonical_pointer_roots(function, partition_types, pointer_value_types)
    stride_hints = _build_stride_hints(function, scalar_value_types)
    expressions = _build_pointer_expressions(
        function,
        partition_types,
        pointer_value_types,
        canonical_root_of,
        stride_hints,
    )
    layouts = _build_layouts(function, partition_types, expressions)

    return FunctionAggregateTypeFacts(
        scalar_types=function,
        layouts=layouts,
    )


def analyze_program_aggregate_types(program: ProgramScalarTypeFacts) -> ProgramAggregateTypeFacts:
    """Analyze a whole program and emit stage-12 aggregate layout facts."""

    functions = {
        function.entry: analyze_function_aggregate_types(function)
        for function in program.ordered_functions()
    }
    return ProgramAggregateTypeFacts(
        scalar_types=program,
        functions=functions,
        pending_entries=program.pending_entries,
        invalidated_entries=program.invalidated_entries,
    )


def build_function_aggregate_type_facts(
    view: ProgramView,
    entry: int,
) -> FunctionAggregateTypeFacts:
    """Build stage-11 scalar facts first, then derive stage-12 aggregate facts."""

    program = build_program_aggregate_type_facts(view, entry)
    return program.functions[entry]


def build_program_aggregate_type_facts(
    view: ProgramView,
    root_entry: int,
) -> ProgramAggregateTypeFacts:
    """Build stage-11 scalar facts first, then derive stage-12 aggregate facts."""

    program = build_program_scalar_type_facts(view, root_entry)
    return analyze_program_aggregate_types(program)


def _build_canonical_pointer_roots(
    function: FunctionScalarTypeFacts,
    partition_types: _PartitionTypeMap,
    pointer_value_types: _PointerValueMap,
) -> dict[SSAValue, SSAValue]:
    union_find = _UnionFind()
    ssa = function.memory.stack.calls.ssa

    for value in pointer_value_types:
        union_find.add(value)

    for partition, scalar_type in partition_types.items():
        if scalar_type.kind != ScalarTypeKind.POINTER:
            continue
        access_values = tuple(_pointer_access_values(partition, pointer_value_types))
        if not access_values:
            continue
        anchor = access_values[0]
        for value in access_values[1:]:
            union_find.union(anchor, value)

    for block in ssa.ordered_blocks():
        for phi in block.phis:
            if phi.output not in pointer_value_types:
                continue
            union_find.add(phi.output)
            for phi_input in phi.inputs:
                if phi_input.value not in pointer_value_types:
                    continue
                union_find.union(phi.output, phi_input.value)

        for instruction in block.instructions:
            for op in instruction.ops:
                if op.output is None or op.output not in pointer_value_types:
                    continue
                if _opcode_text(op) != "COPY" or not op.inputs:
                    continue
                copied = op.inputs[0]
                if copied not in pointer_value_types:
                    continue
                union_find.union(op.output, copied)

    groups = union_find.grouped_values()
    return {
        value: root
        for root, values in groups.items()
        for value in values
    }


def _build_stride_hints(
    function: FunctionScalarTypeFacts,
    scalar_value_types: dict[SSAValue, ScalarType],
) -> dict[SSAValue, int]:
    ssa = function.memory.stack.calls.ssa
    hints: dict[SSAValue, int] = {}

    changed = True
    while changed:
        changed = False

        for block in ssa.ordered_blocks():
            for phi in block.phis:
                output = phi.output
                if not _is_integer_value(output, scalar_value_types):
                    continue
                phi_hints = [
                    hints[value]
                    for value in (phi_input.value for phi_input in phi.inputs)
                    if value in hints
                ]
                if len(phi_hints) != len(phi.inputs) or not phi_hints:
                    continue
                if len(set(phi_hints)) != 1:
                    continue
                if _set_hint(hints, output, phi_hints[0]):
                    changed = True

            for instruction in block.instructions:
                for op in instruction.ops:
                    candidate = _recover_stride_hint(op, scalar_value_types, hints)
                    if candidate is None or op.output is None:
                        continue
                    if _set_hint(hints, op.output, candidate):
                        changed = True

    return hints


def _build_pointer_expressions(
    function: FunctionScalarTypeFacts,
    partition_types: _PartitionTypeMap,
    pointer_value_types: _PointerValueMap,
    canonical_root_of: dict[SSAValue, SSAValue],
    stride_hints: dict[SSAValue, int],
) -> dict[SSAValue, _PointerExpr]:
    ssa = function.memory.stack.calls.ssa
    expressions: dict[SSAValue, _PointerExpr] = {}

    for live_in in ssa.live_ins:
        if live_in not in pointer_value_types:
            continue
        expressions[live_in] = _PointerExpr(root=canonical_root_of.get(live_in, live_in))

    changed = True
    while changed:
        changed = False

        if _propagate_pointer_partition_identities(
            partition_types,
            pointer_value_types,
            canonical_root_of,
            expressions,
        ):
            changed = True

        for block in ssa.ordered_blocks():
            for phi in block.phis:
                if phi.output not in pointer_value_types:
                    continue
                candidate = _recover_phi_pointer_expr(phi.inputs, expressions)
                if candidate is None:
                    continue
                if expressions.get(phi.output) != candidate:
                    expressions[phi.output] = candidate
                    changed = True

            for instruction in block.instructions:
                for op in instruction.ops:
                    if op.output is None or op.output not in pointer_value_types:
                        continue
                    candidate = _recover_pointer_expr(op, expressions, stride_hints)
                    if candidate is None:
                        continue
                    if expressions.get(op.output) != candidate:
                        expressions[op.output] = candidate
                        changed = True

    return expressions


def _build_layouts(
    function: FunctionScalarTypeFacts,
    partition_types: _PartitionTypeMap,
    expressions: dict[SSAValue, _PointerExpr],
) -> tuple[AggregateLayout, ...]:
    merged_fields: dict[SSAValue, dict[int, _MergedField]] = {}
    root_strides: dict[SSAValue, set[int]] = {}

    for partition, scalar_type in partition_types.items():
        if partition.kind != MemoryPartitionKind.VALUE or partition.base_value is None:
            continue
        expression = expressions.get(partition.base_value)
        if expression is None:
            continue

        field_offset = expression.constant_offset + partition.offset
        if field_offset < 0:
            continue

        if expression.stride is not None:
            root_strides.setdefault(expression.root, set()).add(expression.stride)

        by_offset = merged_fields.setdefault(expression.root, {})
        current = by_offset.get(field_offset)
        if current is None:
            by_offset[field_offset] = _MergedField(
                scalar_type=scalar_type,
                partitions=[partition],
            )
            continue

        current.scalar_type = _merge_scalar_types(current.scalar_type, scalar_type)
        if partition not in current.partitions:
            current.partitions.append(partition)

    layouts: list[AggregateLayout] = []
    for root in sorted(merged_fields, key=_value_sort_key):
        stride_values = root_strides.get(root, set())
        stride = next(iter(stride_values)) if len(stride_values) == 1 else None
        fields = tuple(
            AggregateField(
                offset=offset,
                scalar_type=merged_fields[root][offset].scalar_type,
                partitions=tuple(
                    sorted(
                        merged_fields[root][offset].partitions,
                        key=_partition_sort_key,
                    )
                ),
            )
            for offset in sorted(merged_fields[root])
        )
        if not fields:
            continue
        layouts.append(
            AggregateLayout(
                root=AggregateRoot(
                    kind=AggregateRootKind.POINTER,
                    pointer_value=root,
                    stride=stride,
                ),
                fields=fields,
            )
        )

    return tuple(layouts)


def _pointer_access_values(
    partition: MemoryPartition,
    pointer_value_types: _PointerValueMap,
) -> tuple[SSAValue, ...]:
    return tuple(
        access.value
        for access in partition.accesses
        if access.value is not None and access.value in pointer_value_types
    )


def _propagate_pointer_partition_identities(
    partition_types: _PartitionTypeMap,
    pointer_value_types: _PointerValueMap,
    canonical_root_of: dict[SSAValue, SSAValue],
    expressions: dict[SSAValue, _PointerExpr],
) -> bool:
    changed = False

    for partition, scalar_type in partition_types.items():
        if scalar_type.kind != ScalarTypeKind.POINTER:
            continue

        access_values = _pointer_access_values(partition, pointer_value_types)
        if not access_values:
            continue

        known = [expressions[value] for value in access_values if value in expressions]
        if known:
            if len(set(known)) != 1:
                continue
            target = known[0]
        else:
            representative = canonical_root_of.get(access_values[0], access_values[0])
            target = _PointerExpr(root=representative)

        for value in access_values:
            if expressions.get(value) == target:
                continue
            expressions[value] = target
            changed = True

    return changed


def _recover_phi_pointer_expr(
    inputs,
    expressions: dict[SSAValue, _PointerExpr],
) -> _PointerExpr | None:
    phi_exprs = [expressions[phi_input.value] for phi_input in inputs if phi_input.value in expressions]
    if len(phi_exprs) != len(inputs) or not phi_exprs:
        return None
    if len(set(phi_exprs)) != 1:
        return None
    return phi_exprs[0]


def _recover_pointer_expr(
    op: SSAOp,
    expressions: dict[SSAValue, _PointerExpr],
    stride_hints: dict[SSAValue, int],
) -> _PointerExpr | None:
    output = op.output
    if output is None:
        return None

    opcode = _opcode_text(op)
    if opcode == "COPY" and op.inputs:
        return expressions.get(op.inputs[0])

    if opcode == "INT_ADD":
        return _recover_additive_pointer_expr(op.inputs, expressions, stride_hints)

    if opcode == "INT_SUB":
        return _recover_subtractive_pointer_expr(op.inputs, expressions)

    return None


def _recover_additive_pointer_expr(
    inputs: tuple[SSAValue, ...],
    expressions: dict[SSAValue, _PointerExpr],
    stride_hints: dict[SSAValue, int],
) -> _PointerExpr | None:
    if len(inputs) != 2:
        return None

    left = inputs[0]
    right = inputs[1]
    left_expr = expressions.get(left)
    right_expr = expressions.get(right)
    left_const = _signed_const(left)
    right_const = _signed_const(right)
    left_stride = stride_hints.get(left)
    right_stride = stride_hints.get(right)

    if left_expr is not None and right_const is not None:
        return _PointerExpr(
            root=left_expr.root,
            constant_offset=left_expr.constant_offset + right_const,
            stride=left_expr.stride,
        )
    if right_expr is not None and left_const is not None:
        return _PointerExpr(
            root=right_expr.root,
            constant_offset=right_expr.constant_offset + left_const,
            stride=right_expr.stride,
        )

    if left_expr is not None and right_stride is not None:
        stride = _merge_stride(left_expr.stride, right_stride)
        if stride is None:
            return None
        return _PointerExpr(
            root=left_expr.root,
            constant_offset=left_expr.constant_offset,
            stride=stride,
        )
    if right_expr is not None and left_stride is not None:
        stride = _merge_stride(right_expr.stride, left_stride)
        if stride is None:
            return None
        return _PointerExpr(
            root=right_expr.root,
            constant_offset=right_expr.constant_offset,
            stride=stride,
        )

    return None


def _recover_subtractive_pointer_expr(
    inputs: tuple[SSAValue, ...],
    expressions: dict[SSAValue, _PointerExpr],
) -> _PointerExpr | None:
    if len(inputs) != 2:
        return None

    left_expr = expressions.get(inputs[0])
    right_const = _signed_const(inputs[1])
    if left_expr is None or right_const is None:
        return None

    return _PointerExpr(
        root=left_expr.root,
        constant_offset=left_expr.constant_offset - right_const,
        stride=left_expr.stride,
    )


def _recover_stride_hint(
    op: SSAOp,
    scalar_value_types: dict[SSAValue, ScalarType],
    hints: dict[SSAValue, int],
) -> int | None:
    output = op.output
    if output is None or not _is_integer_value(output, scalar_value_types):
        return None

    opcode = _opcode_text(op)
    if opcode == "COPY" and op.inputs:
        return hints.get(op.inputs[0])

    if opcode == "INT_LEFT" and len(op.inputs) == 2:
        shift_amount = _unsigned_const(op.inputs[1])
        if shift_amount is None or shift_amount < 0 or shift_amount > 31:
            return None
        if _is_const(op.inputs[0]):
            return None
        base_hint = hints.get(op.inputs[0], 1)
        return base_hint << shift_amount

    if opcode in {"INT_ADD", "INT_SUB"} and len(op.inputs) == 2:
        left_const = _signed_const(op.inputs[0])
        right_const = _signed_const(op.inputs[1])
        if left_const is not None and _is_integer_value(op.inputs[1], scalar_value_types):
            return hints.get(op.inputs[1])
        if right_const is not None and _is_integer_value(op.inputs[0], scalar_value_types):
            return hints.get(op.inputs[0])

    return None


def _merge_stride(current: int | None, candidate: int) -> int | None:
    if current is None:
        return candidate
    if current == candidate:
        return current
    return None


def _set_hint(hints: dict[SSAValue, int], value: SSAValue, hint: int) -> bool:
    if hint <= 0:
        return False
    current = hints.get(value)
    if current == hint:
        return False
    if current is not None and current != hint:
        return False
    hints[value] = hint
    return True


def _merge_scalar_types(left: ScalarType, right: ScalarType) -> ScalarType:
    if left.size != right.size:
        raise ValueError("aggregate field merges must preserve scalar widths")

    merged_kind = _merge_scalar_kinds(left.kind, right.kind)
    return ScalarType(merged_kind, left.size)


def _merge_scalar_kinds(left: ScalarTypeKind, right: ScalarTypeKind) -> ScalarTypeKind:
    if left == right:
        return left
    if left == ScalarTypeKind.WORD:
        return right
    if right == ScalarTypeKind.WORD:
        return left
    return ScalarTypeKind.WORD


_partition_sort_key = partition_sort_key

_value_sort_key = value_sort_key

_value_size = value_size


def _is_integer_value(value: SSAValue, scalar_value_types: dict[SSAValue, ScalarType]) -> bool:
    scalar_type = scalar_value_types.get(value)
    if scalar_type is None:
        return False
    return scalar_type.kind in {ScalarTypeKind.INT, ScalarTypeKind.WORD}


_is_const = is_const_ssa


def _unsigned_const(value: SSAValue) -> int | None:
    if not isinstance(value, Varnode):
        return None
    space = value.space.value if isinstance(value.space, PcodeSpace) else value.space
    if space != PcodeSpace.CONST.value:
        return None
    return value.offset


_signed_const = signed_const

_opcode_text = opcode_text
