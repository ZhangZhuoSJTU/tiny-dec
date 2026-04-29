"""Stage-14 range refinement from stage-13 variable facts.

This file owns the transformation from stage-13 variable recovery into
stage-14 range and predicate-refinement facts.

Implementation notes:
- The stage is read-only with respect to upstream CFG, SSA, call, stack,
  memory, scalar-type, aggregate-layout, and variable artifacts.
- It preserves upstream `pending_entries` and `invalidated_entries` unchanged.
- The analysis uses one small signed-interval domain over SSA values and only
  supports the arithmetic subset documented in the stage contract.
- Unsupported arithmetic, ambiguous predicate shapes, and non-interval facts
  bail out conservatively instead of inventing stronger evidence.
- Branch refinements are keyed by CFG edge and the underlying compare sense so
  later stages can inspect edge-local facts without rewriting the CFG.

Educational note — the propagation loop uses a widening threshold:
after 3 monotone interval expansions on the same SSA value, the bound
is widened to the full signed range for that value's size.  This
guarantees fixed-point convergence at the cost of precision for deeply
nested loop induction variables.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from tiny_dec.analysis._helpers import (
    is_const_ssa,
    opcode_text,
    signed_const,
    value_sort_key,
)
from tiny_dec.analysis.highvars import (
    FunctionVariableFacts,
    ProgramVariableFacts,
    build_program_variable_facts,
)
from tiny_dec.analysis.memory import MemoryAccessKind, MemoryPartition
from tiny_dec.analysis.range.models import (
    BranchRangeRefinement,
    FunctionRangeFacts,
    IntegerRange,
    ProgramRangeFacts,
    ValueRangeFact,
    VariableRangeFact,
)
from tiny_dec.analysis.ssa import SSAFunctionIR, SSAOp
from tiny_dec.analysis.ssa.models import SSAValue
from tiny_dec.analysis.types import ScalarTypeKind
from tiny_dec.loader import ProgramView


@dataclass(frozen=True, slots=True)
class _PredicateInfo:
    source_opcode: str
    left: SSAValue
    right: SSAValue
    condition_true_means_source_true: bool = True


def analyze_function_ranges(function: FunctionVariableFacts) -> FunctionRangeFacts:
    """Analyze one function and emit stage-14 range facts."""

    scalar_types = function.aggregate_types.scalar_types
    ssa = scalar_types.memory.stack.calls.ssa
    scalar_type_by_value = {
        fact.value: fact.scalar_type
        for fact in scalar_types.value_facts
    }
    value_ranges: dict[SSAValue, IntegerRange] = {}
    range_update_counts: dict[SSAValue, int] = {}
    predicate_defs: dict[SSAValue, _PredicateInfo] = {}

    _seed_bool_and_predicate_ranges(
        ssa,
        scalar_type_by_value,
        value_ranges,
        range_update_counts,
        predicate_defs,
    )
    _propagate_value_ranges(
        ssa,
        scalar_type_by_value,
        scalar_types.memory.partitions,
        value_ranges,
        range_update_counts,
        predicate_defs,
    )

    variable_ranges = _build_variable_ranges(function, scalar_type_by_value, value_ranges)
    branch_refinements = _build_branch_refinements(
        ssa,
        scalar_type_by_value,
        value_ranges,
        predicate_defs,
    )

    return FunctionRangeFacts(
        variables=function,
        value_ranges=tuple(
            ValueRangeFact(value=value, value_range=value_range)
            for value, value_range in sorted(
                value_ranges.items(),
                key=lambda item: _value_sort_key(item[0]),
            )
            if not _is_const(value)
        ),
        variable_ranges=tuple(
            sorted(variable_ranges, key=lambda fact: fact.variable.name)
        ),
        branch_refinements=tuple(
            sorted(
                branch_refinements,
                key=lambda fact: (
                    fact.block_start,
                    fact.successor,
                    0 if fact.sense else 1,
                    _value_sort_key(fact.value),
                    fact.source_opcode,
                ),
            )
        ),
    )


def analyze_program_ranges(program: ProgramVariableFacts) -> ProgramRangeFacts:
    """Analyze a whole program and emit stage-14 range facts."""

    functions = {
        function.entry: analyze_function_ranges(function)
        for function in program.ordered_functions()
    }
    return ProgramRangeFacts(
        variables=program,
        functions=functions,
        pending_entries=program.pending_entries,
        invalidated_entries=program.invalidated_entries,
    )


def build_function_range_facts(
    view: ProgramView,
    entry: int,
) -> FunctionRangeFacts:
    """Build stage-13 variable facts first, then derive stage-14 ranges."""

    program = build_program_range_facts(view, entry)
    return program.functions[entry]


def build_program_range_facts(
    view: ProgramView,
    root_entry: int,
) -> ProgramRangeFacts:
    """Build stage-13 variable facts first, then derive stage-14 ranges."""

    program = build_program_variable_facts(view, root_entry)
    return analyze_program_ranges(program)


def _seed_bool_and_predicate_ranges(
    ssa: SSAFunctionIR,
    scalar_type_by_value: Mapping[SSAValue, object],
    value_ranges: dict[SSAValue, IntegerRange],
    range_update_counts: dict[SSAValue, int],
    predicate_defs: dict[SSAValue, _PredicateInfo],
) -> None:
    for value, scalar_type in scalar_type_by_value.items():
        if getattr(scalar_type, "kind", None) == ScalarTypeKind.BOOL:
            _record_range(value_ranges, range_update_counts, value, IntegerRange(0, 1))

    for block in ssa.ordered_blocks():
        for instruction in block.instructions:
            for op in instruction.ops:
                output = op.output
                if output is None:
                    continue

                opcode = _opcode_text(op)
                if opcode in {"INT_EQUAL", "INT_NOTEQUAL", "INT_SLESS", "INT_LESS"} and len(op.inputs) == 2:
                    predicate_defs[output] = _PredicateInfo(
                        source_opcode=opcode,
                        left=op.inputs[0],
                        right=op.inputs[1],
                    )
                    _record_range(
                        value_ranges,
                        range_update_counts,
                        output,
                        IntegerRange(0, 1),
                    )
                    continue

                if opcode == "BOOL_NEGATE" and len(op.inputs) == 1:
                    inner = predicate_defs.get(op.inputs[0])
                    if inner is not None:
                        predicate_defs[output] = _PredicateInfo(
                            source_opcode=inner.source_opcode,
                            left=inner.left,
                            right=inner.right,
                            condition_true_means_source_true=not inner.condition_true_means_source_true,
                        )
                    _record_range(
                        value_ranges,
                        range_update_counts,
                        output,
                        IntegerRange(0, 1),
                    )


def _propagate_value_ranges(
    ssa: SSAFunctionIR,
    scalar_type_by_value: Mapping[SSAValue, object],
    partitions: tuple[MemoryPartition, ...],
    value_ranges: dict[SSAValue, IntegerRange],
    range_update_counts: dict[SSAValue, int],
    predicate_defs: dict[SSAValue, _PredicateInfo],
) -> None:
    max_iterations = 10 * len(ssa.blocks) + 10
    changed = True
    while changed:
        max_iterations -= 1
        if max_iterations < 0:
            break
        changed = False

        for block in ssa.ordered_blocks():
            for phi in block.phis:
                inputs = [
                    _range_of(phi_input.value, value_ranges)
                    for phi_input in phi.inputs
                ]
                known_inputs = tuple(
                    value_range for value_range in inputs if value_range is not None
                )
                if not known_inputs:
                    continue
                candidate = _union_many(known_inputs)
                if candidate is not None and _record_range(
                    value_ranges,
                    range_update_counts,
                    phi.output,
                    candidate,
                ):
                    changed = True

            for instruction in block.instructions:
                for op in instruction.ops:
                    output = op.output
                    if output is None:
                        continue

                    candidate = _range_from_op(
                        op,
                        scalar_type_by_value=scalar_type_by_value,
                        value_ranges=value_ranges,
                        predicate_defs=predicate_defs,
                    )
                    if candidate is not None and _record_range(
                        value_ranges,
                        range_update_counts,
                        output,
                        candidate,
                    ):
                        changed = True

        if _propagate_partition_load_ranges(
            partitions,
            value_ranges,
            range_update_counts,
        ):
            changed = True


def _range_from_op(
    op: SSAOp,
    *,
    scalar_type_by_value: Mapping[SSAValue, object],
    value_ranges: dict[SSAValue, IntegerRange],
    predicate_defs: dict[SSAValue, _PredicateInfo],
) -> IntegerRange | None:
    opcode = _opcode_text(op)

    if opcode == "COPY" and len(op.inputs) == 1:
        copied = _range_of(op.inputs[0], value_ranges)
        if copied is not None:
            return copied
        copied_predicate = predicate_defs.get(op.inputs[0])
        if copied_predicate is not None and op.output is not None:
            predicate_defs[op.output] = copied_predicate
            return IntegerRange(0, 1)
        return None

    if opcode == "BOOL_NEGATE" and len(op.inputs) == 1:
        source = _range_of(op.inputs[0], value_ranges)
        if source is None:
            return IntegerRange(0, 1) if op.output in predicate_defs else None
        if source.lower == 0 and source.upper == 0:
            return IntegerRange(1, 1)
        if source.lower == 1 and source.upper == 1:
            return IntegerRange(0, 0)
        return IntegerRange(0, 1)

    if opcode == "INT_ADD" and len(op.inputs) == 2:
        left = _range_of(op.inputs[0], value_ranges)
        right = _range_of(op.inputs[1], value_ranges)
        left_const = _exact_constant(op.inputs[0], value_ranges)
        right_const = _exact_constant(op.inputs[1], value_ranges)
        if left is not None and right is not None:
            combined = _add_ranges(left, right)
            if combined is not None:
                return combined
        if left is not None and right_const is not None:
            return _shift_range(left, right_const)
        if right is not None and left_const is not None:
            return _shift_range(right, left_const)
        return None

    if opcode == "INT_SUB" and len(op.inputs) == 2:
        left = _range_of(op.inputs[0], value_ranges)
        right_const = _exact_constant(op.inputs[1], value_ranges)
        if left is None or right_const is None:
            return None
        return _shift_range(left, -right_const)

    if opcode == "INT_AND" and len(op.inputs) == 2:
        left = _range_of(op.inputs[0], value_ranges)
        right = _range_of(op.inputs[1], value_ranges)
        left_mask = _non_negative_exact_constant(op.inputs[0], value_ranges)
        right_mask = _non_negative_exact_constant(op.inputs[1], value_ranges)
        if left is not None and right_mask is not None:
            return IntegerRange(0, right_mask)
        if right is not None and left_mask is not None:
            return IntegerRange(0, left_mask)
        return None

    if opcode in {"INT_EQUAL", "INT_NOTEQUAL", "INT_SLESS", "INT_LESS"} and op.output is not None:
        return IntegerRange(0, 1)

    if (
        op.output is not None
        and getattr(scalar_type_by_value.get(op.output), "kind", None) == ScalarTypeKind.BOOL
    ):
        return IntegerRange(0, 1)

    return None


def _propagate_partition_load_ranges(
    partitions: tuple[MemoryPartition, ...],
    value_ranges: dict[SSAValue, IntegerRange],
    range_update_counts: dict[SSAValue, int],
) -> bool:
    changed = False

    for partition in partitions:
        accesses = partition.accesses
        known_ranges = tuple(
            access_range
            for access_range in (
                _range_of(access.value, value_ranges)
                for access in accesses
                if access.value is not None
            )
            if access_range is not None
        )
        if not known_ranges:
            continue

        partition_range = _union_many(known_ranges)
        if partition_range is None:
            continue

        for access in accesses:
            if access.kind != MemoryAccessKind.LOAD:
                continue
            value = access.value
            if value is None or _is_const(value):
                continue
            if _record_range(
                value_ranges,
                range_update_counts,
                value,
                partition_range,
            ):
                changed = True

    return changed


def _build_variable_ranges(
    function: FunctionVariableFacts,
    scalar_type_by_value: Mapping[SSAValue, object],
    value_ranges: dict[SSAValue, IntegerRange],
) -> list[VariableRangeFact]:
    facts: list[VariableRangeFact] = []

    for variable in function.variables:
        candidates: list[IntegerRange] = []
        if variable.root_value is not None:
            root_range = _range_of(variable.root_value, value_ranges)
            if root_range is not None:
                candidates.append(root_range)

        for partition in variable.partitions:
            for access in partition.accesses:
                if access.value is None:
                    continue
                access_range = _range_of(access.value, value_ranges)
                if access_range is not None:
                    candidates.append(access_range)

        if variable.scalar_type is not None and variable.scalar_type.kind == ScalarTypeKind.BOOL:
            candidates.append(IntegerRange(0, 1))

        if variable.root_value is not None and getattr(
            scalar_type_by_value.get(variable.root_value),
            "kind",
            None,
        ) == ScalarTypeKind.BOOL:
            candidates.append(IntegerRange(0, 1))

        merged = _union_many(tuple(candidates))
        if merged is None:
            continue
        facts.append(VariableRangeFact(variable=variable, value_range=merged))

    return facts


def _build_branch_refinements(
    ssa: SSAFunctionIR,
    scalar_type_by_value: Mapping[SSAValue, object],
    value_ranges: dict[SSAValue, IntegerRange],
    predicate_defs: dict[SSAValue, _PredicateInfo],
) -> list[BranchRangeRefinement]:
    refinements: list[BranchRangeRefinement] = []

    for block in ssa.ordered_blocks():
        branch_taken = None
        fallthrough = None
        for edge in block.successors:
            if edge.kind.value == "branch_taken":
                branch_taken = edge.target
            elif edge.kind.value == "fallthrough":
                fallthrough = edge.target

        if branch_taken is None or fallthrough is None:
            continue

        for instruction in block.instructions:
            for op in instruction.ops:
                if _opcode_text(op) != "CBRANCH" or len(op.inputs) < 2:
                    continue
                predicate = predicate_defs.get(op.inputs[1])
                if predicate is None:
                    continue

                taken_range = _refinement_for_truth(
                    predicate,
                    predicate.condition_true_means_source_true,
                    scalar_type_by_value=scalar_type_by_value,
                    value_ranges=value_ranges,
                )
                if taken_range is not None:
                    tracked_value, interval = taken_range
                    refinements.append(
                        BranchRangeRefinement(
                            block_start=block.start,
                            successor=branch_taken,
                            sense=predicate.condition_true_means_source_true,
                            source_opcode=predicate.source_opcode,
                            value=tracked_value,
                            value_range=interval,
                        )
                    )

                fallthrough_range = _refinement_for_truth(
                    predicate,
                    not predicate.condition_true_means_source_true,
                    scalar_type_by_value=scalar_type_by_value,
                    value_ranges=value_ranges,
                )
                if fallthrough_range is not None:
                    tracked_value, interval = fallthrough_range
                    refinements.append(
                        BranchRangeRefinement(
                            block_start=block.start,
                            successor=fallthrough,
                            sense=not predicate.condition_true_means_source_true,
                            source_opcode=predicate.source_opcode,
                            value=tracked_value,
                            value_range=interval,
                        )
                    )

    return refinements


def _refinement_for_truth(
    predicate: _PredicateInfo,
    source_truth: bool,
    *,
    scalar_type_by_value: Mapping[SSAValue, object],
    value_ranges: dict[SSAValue, IntegerRange],
) -> tuple[SSAValue, IntegerRange] | None:
    left_const = _exact_constant(predicate.left, value_ranges)
    right_const = _exact_constant(predicate.right, value_ranges)

    if left_const is None and right_const is None:
        return None

    if right_const is not None and not _is_const(predicate.left):
        return _refinement_for_compare(
            opcode=predicate.source_opcode,
            tracked_value=predicate.left,
            constant=right_const,
            tracked_on_left=True,
            source_truth=source_truth,
            scalar_type_by_value=scalar_type_by_value,
        )

    if left_const is not None and not _is_const(predicate.right):
        return _refinement_for_compare(
            opcode=predicate.source_opcode,
            tracked_value=predicate.right,
            constant=left_const,
            tracked_on_left=False,
            source_truth=source_truth,
            scalar_type_by_value=scalar_type_by_value,
        )

    return None


def _refinement_for_compare(
    *,
    opcode: str,
    tracked_value: SSAValue,
    constant: int,
    tracked_on_left: bool,
    source_truth: bool,
    scalar_type_by_value: Mapping[SSAValue, object],
) -> tuple[SSAValue, IntegerRange] | None:
    if opcode == "INT_SLESS":
        if tracked_on_left:
            if source_truth:
                return tracked_value, IntegerRange(upper=constant - 1)
            return tracked_value, IntegerRange(lower=constant)
        if source_truth:
            return tracked_value, IntegerRange(lower=constant + 1)
        return tracked_value, IntegerRange(upper=constant)

    if opcode == "INT_LESS":
        if tracked_on_left:
            if source_truth:
                return tracked_value, IntegerRange(lower=0, upper=constant - 1)
            return tracked_value, IntegerRange(lower=constant)
        if source_truth:
            return tracked_value, IntegerRange(lower=constant + 1)
        return tracked_value, IntegerRange(upper=constant)

    if opcode == "INT_EQUAL":
        if source_truth:
            return tracked_value, IntegerRange(constant, constant)
        if _is_bool_like(tracked_value, scalar_type_by_value) and constant == 0:
            return tracked_value, IntegerRange(1, 1)
        if _is_bool_like(tracked_value, scalar_type_by_value) and constant == 1:
            return tracked_value, IntegerRange(0, 0)
        return None

    if opcode == "INT_NOTEQUAL":
        if not _is_bool_like(tracked_value, scalar_type_by_value):
            return None
        if constant == 0:
            return tracked_value, IntegerRange(1, 1) if source_truth else IntegerRange(0, 0)
        if constant == 1:
            return tracked_value, IntegerRange(0, 0) if source_truth else IntegerRange(1, 1)
        return None

    return None


def _record_range(
    value_ranges: dict[SSAValue, IntegerRange],
    range_update_counts: dict[SSAValue, int],
    value: SSAValue,
    candidate: IntegerRange,
) -> bool:
    current = value_ranges.get(value)
    if current is None:
        value_ranges[value] = candidate
        range_update_counts[value] = 1
        return True

    merged = _union_ranges(current, candidate)
    if current == merged:
        return False

    update_count = range_update_counts.get(value, 1) + 1
    range_update_counts[value] = update_count
    # Widen after 3 monotone expansions to guarantee fixed-point convergence.
    if update_count >= 3:
        lower = merged.lower
        upper = merged.upper
        if current.lower is not None and merged.lower is not None and merged.lower < current.lower:
            lower = None
        if current.upper is not None and merged.upper is not None and merged.upper > current.upper:
            upper = None
        if lower is not None or upper is not None:
            merged = IntegerRange(lower=lower, upper=upper)

    value_ranges[value] = merged
    return True


def _range_of(
    value: SSAValue,
    value_ranges: dict[SSAValue, IntegerRange],
) -> IntegerRange | None:
    known = value_ranges.get(value)
    if known is not None:
        return known

    exact_const = _signed_const(value)
    if exact_const is None:
        return None
    return IntegerRange(exact_const, exact_const)


def _union_many(ranges: tuple[IntegerRange | None, ...]) -> IntegerRange | None:
    merged: IntegerRange | None = None
    for value_range in ranges:
        if value_range is None:
            return None
        merged = value_range if merged is None else _union_ranges(merged, value_range)
    return merged


def _union_ranges(left: IntegerRange, right: IntegerRange) -> IntegerRange:
    if left.lower is None or right.lower is None:
        lower = None
    else:
        lower = min(left.lower, right.lower)

    if left.upper is None or right.upper is None:
        upper = None
    else:
        upper = max(left.upper, right.upper)

    return IntegerRange(lower=lower, upper=upper)


def _shift_range(value_range: IntegerRange, delta: int) -> IntegerRange:
    lower = None if value_range.lower is None else value_range.lower + delta
    upper = None if value_range.upper is None else value_range.upper + delta
    return IntegerRange(lower=lower, upper=upper)


def _add_ranges(left: IntegerRange, right: IntegerRange) -> IntegerRange | None:
    lower = None if left.lower is None or right.lower is None else left.lower + right.lower
    upper = None if left.upper is None or right.upper is None else left.upper + right.upper
    if lower is None and upper is None:
        return None
    return IntegerRange(lower=lower, upper=upper)


def _exact_constant(
    value: SSAValue,
    value_ranges: dict[SSAValue, IntegerRange],
) -> int | None:
    literal = _signed_const(value)
    if literal is not None:
        return literal

    known = value_ranges.get(value)
    if known is None or known.lower is None or known.upper is None:
        return None
    if known.lower != known.upper:
        return None
    return known.lower


def _non_negative_exact_constant(
    value: SSAValue,
    value_ranges: dict[SSAValue, IntegerRange],
) -> int | None:
    constant = _exact_constant(value, value_ranges)
    if constant is None or constant < 0:
        return None
    return constant


def _is_bool_like(
    value: SSAValue,
    scalar_type_by_value: Mapping[SSAValue, object],
) -> bool:
    return getattr(scalar_type_by_value.get(value), "kind", None) == ScalarTypeKind.BOOL


_is_const = is_const_ssa

_signed_const = signed_const

_value_sort_key = value_sort_key

_opcode_text = opcode_text
