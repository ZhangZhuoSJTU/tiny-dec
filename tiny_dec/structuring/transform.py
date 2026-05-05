"""Stage-16 structured-control recovery from stage-15 interprocedural facts.

This file owns the transformation from stage-15 interprocedural summaries into
the stage-16 structured-control surface.

Implementation notes:
- The stage is read-only with respect to upstream CFG, SSA, call, stack,
  memory, scalar-type, aggregate-layout, variable, range, and interprocedural
  artifacts.
- It preserves upstream `pending_entries`, `invalidated_entries`, and
  `scheduler_invalidations` unchanged.
- The implemented algorithm targets one deterministic subset:
  straight-line block chains, two-way branches with one reconvergence point,
  and natural loops whose header has one in-loop successor and one exit
  successor.
- Unsupported edges remain explicit as `goto`, `break`, or `continue` leaves
  rather than being hidden behind guessed high-level regions.
- Structuring order is deterministic: natural loops first, then structured
  branches, then linear fallbacks in reachable SSA block order.

Simplifying assumptions:
- Only reducible control flow is structured.  Irreducible loops (multiple
  entry points into the same cycle) remain as goto spaghetti.  Most
  compiler-generated code is reducible, but hand-written assembly or
  heavy goto usage in the source can produce irreducible graphs.
- Two-way branches require a single reconvergence (immediate post-
  dominator) that is reachable from both sides.  Switch statements are
  structured only when they match a specific pattern of dense constant
  comparisons; sparse or indirect jump tables may degrade to if-chains.
- Multi-exit loops and loops with complex break/continue patterns may
  produce extra goto nodes rather than nested break/continue.
"""

from __future__ import annotations

from dataclasses import dataclass

from tiny_dec.analysis.interproc import (
    FunctionInterprocFacts,
    ProgramInterprocFacts,
    build_program_interproc_facts,
)
from tiny_dec.analysis.memory.models import MemoryAccessKind, MemoryPartition
from tiny_dec.analysis.ssa import SSAFunctionIR
from tiny_dec.analysis.ssa.models import SSAName, SSAOp, SSAValue
from tiny_dec.disasm.models import BlockEdge, BlockEdgeKind, BlockTerminator
from tiny_dec.ir.pcode import PcodeSpace, Varnode
from tiny_dec.loader import ProgramView
from tiny_dec.structuring.models import (
    FunctionStructuredFacts,
    ProgramStructuredFacts,
    StructuredBlock,
    StructuredBreak,
    StructuredContinue,
    StructuredGoto,
    StructuredIf,
    StructuredSequence,
    StructuredStmt,
    StructuredSwitch,
    StructuredSwitchCase,
    StructuredWhile,
)


_SYNTHETIC_EXIT = -1


@dataclass(frozen=True, slots=True)
class _LoopInfo:
    header: int
    body_entry: int
    exit_target: int
    nodes: frozenset[int]


@dataclass(frozen=True, slots=True)
class _LoopContext:
    header: int
    exit_target: int


@dataclass(frozen=True, slots=True)
class _StructureResult:
    body: StructuredSequence
    next_start: int | None


@dataclass(frozen=True, slots=True)
class _NodeResult:
    node: StructuredIf
    next_start: int | None


@dataclass(frozen=True, slots=True)
class _DefSite:
    op: SSAOp
    instruction_address: int
    block_start: int


@dataclass(frozen=True, slots=True)
class _StructuringContext:
    ssa: SSAFunctionIR
    def_sites: dict[SSAName, _DefSite]
    load_partitions_by_instruction: dict[int, MemoryPartition]
    unique_store_values_by_partition: dict[MemoryPartition, SSAValue]


@dataclass(frozen=True, slots=True)
class _SwitchCompareMatch:
    selector: SSAValue
    case_value: int


def analyze_function_structuring(function: FunctionInterprocFacts) -> FunctionStructuredFacts:
    """Analyze one function and emit a stage-16 structured snapshot."""

    ssa = function.ranges.variables.aggregate_types.scalar_types.memory.stack.calls.ssa
    context = _build_structuring_context(function)
    order = ssa.ordered_block_starts()
    order_index = {start: index for index, start in enumerate(order)}
    successors = _build_successor_map(ssa, order)
    predecessors = _build_predecessor_map(successors, order_index)
    immediate_postdominators = _compute_immediate_postdominators(
        order,
        successors,
        order_index,
    )
    loop_infos = _collect_loop_infos(
        ssa,
        order,
        successors,
        predecessors,
        order_index,
    )
    body = _build_sequence(
        ssa=ssa,
        current=ssa.entry,
        stop_at=None,
        region_nodes=frozenset(order),
        order_index=order_index,
        successors=successors,
        immediate_postdominators=immediate_postdominators,
        loop_infos=loop_infos,
        loop_context=None,
        active_headers=frozenset(),
    ).body
    body = _normalize_sequence(body, context)
    return FunctionStructuredFacts(interproc=function, body=body)


def analyze_program_structuring(program: ProgramInterprocFacts) -> ProgramStructuredFacts:
    """Analyze a whole program and emit a stage-16 structured snapshot."""

    functions = {
        function.entry: analyze_function_structuring(function)
        for function in program.ordered_functions()
    }
    return ProgramStructuredFacts(
        interproc=program,
        functions=functions,
        pending_entries=program.pending_entries,
        invalidated_entries=program.invalidated_entries,
        scheduler_invalidations=program.scheduler_invalidations,
    )


def build_function_structured_facts(
    view: ProgramView,
    entry: int,
) -> FunctionStructuredFacts:
    """Build stage-15 interproc facts first, then derive stage-16 structure."""

    program = build_program_structured_facts(view, entry)
    return program.functions[entry]


def build_program_structured_facts(
    view: ProgramView,
    root_entry: int,
) -> ProgramStructuredFacts:
    """Build stage-15 interproc facts first, then derive stage-16 structure."""

    program = build_program_interproc_facts(view, root_entry)
    return analyze_program_structuring(program)


def _build_structuring_context(function: FunctionInterprocFacts) -> _StructuringContext:
    ssa = function.ranges.variables.aggregate_types.scalar_types.memory.stack.calls.ssa
    memory_facts = function.ranges.variables.aggregate_types.scalar_types.memory
    def_sites: dict[SSAName, _DefSite] = {}
    for block in ssa.ordered_blocks():
        for instruction in block.instructions:
            for op in instruction.ops:
                if op.output is None:
                    continue
                def_sites[op.output] = _DefSite(
                    op=op,
                    instruction_address=instruction.address,
                    block_start=block.start,
                )

    load_partitions_by_instruction: dict[int, MemoryPartition] = {}
    unique_store_values_by_partition: dict[MemoryPartition, SSAValue] = {}
    for partition in memory_facts.partitions:
        store_values = tuple(
            access.value
            for access in partition.accesses
            if access.kind == MemoryAccessKind.STORE and access.value is not None
        )
        if len(store_values) == 1:
            unique_store_values_by_partition[partition] = store_values[0]
        for access in partition.accesses:
            if access.kind == MemoryAccessKind.LOAD:
                load_partitions_by_instruction[access.instruction_address] = partition

    return _StructuringContext(
        ssa=ssa,
        def_sites=def_sites,
        load_partitions_by_instruction=load_partitions_by_instruction,
        unique_store_values_by_partition=unique_store_values_by_partition,
    )


def _normalize_sequence(
    sequence: StructuredSequence,
    context: _StructuringContext,
) -> StructuredSequence:
    return StructuredSequence(
        tuple(_normalize_stmt(item, context) for item in sequence.items)
    )


def _normalize_stmt(
    item: StructuredStmt,
    context: _StructuringContext,
) -> StructuredStmt:
    if isinstance(item, StructuredIf):
        collapsed = _try_collapse_switch(item, context)
        if collapsed is not None:
            return collapsed
        return StructuredIf(
            header=item.header,
            true_target=item.true_target,
            false_target=item.false_target,
            merge_target=item.merge_target,
            then_body=_normalize_sequence(item.then_body, context),
            else_body=_normalize_sequence(item.else_body, context),
        )
    if isinstance(item, StructuredSwitch):
        return StructuredSwitch(
            header=item.header,
            merge_target=item.merge_target,
            cases=tuple(
                StructuredSwitchCase(
                    value=case.value,
                    target=case.target,
                    body=_normalize_sequence(case.body, context),
                )
                for case in item.cases
            ),
            default_target=item.default_target,
            default_body=_normalize_sequence(item.default_body, context),
        )
    if isinstance(item, StructuredWhile):
        return StructuredWhile(
            header=item.header,
            body_entry=item.body_entry,
            exit_target=item.exit_target,
            body=_normalize_sequence(item.body, context),
        )
    return item


def _try_collapse_switch(
    node: StructuredIf,
    context: _StructuringContext,
) -> StructuredSwitch | None:
    merge_target = node.merge_target
    current = node
    selector: SSAValue | None = None
    seen_case_values: set[int] = set()
    cases: list[StructuredSwitchCase] = []

    while True:
        if current.merge_target != merge_target:
            return None
        match = _extract_switch_compare_match(
            context=context,
            block_start=current.header,
            case_target=current.true_target,
        )
        if match is None:
            return None
        current_selector = _canonicalize_selector_value(context, match.selector)
        if selector is None:
            selector = current_selector
        elif current_selector != selector:
            return None
        if match.case_value in seen_case_values:
            return None
        seen_case_values.add(match.case_value)
        cases.append(
            StructuredSwitchCase(
                value=match.case_value,
                target=current.true_target,
                body=_normalize_sequence(current.then_body, context),
            )
        )

        nested = _single_nested_if(current.else_body)
        if nested is None:
            if len(cases) < 2:
                return None
            default_body = _normalize_sequence(current.else_body, context)
            return StructuredSwitch(
                header=node.header,
                merge_target=merge_target,
                cases=tuple(cases),
                default_target=_sequence_entry_target(default_body, merge_target),
                default_body=default_body,
            )
        current = nested


def _extract_switch_compare_match(
    *,
    context: _StructuringContext,
    block_start: int,
    case_target: int,
) -> _SwitchCompareMatch | None:
    block = context.ssa.blocks[block_start]
    branch_target: int | None = None
    condition_value: SSAValue | None = None
    for instruction in reversed(block.instructions):
        for op in reversed(instruction.ops):
            if op.opcode_text != "CBRANCH" or len(op.inputs) < 2:
                continue
            branch_target = _branch_target(op.inputs[0])
            condition_value = op.inputs[-1]
            break
        if condition_value is not None:
            break
    if branch_target != case_target or condition_value is None:
        return None
    return _match_constant_equality(context, condition_value)


def _match_constant_equality(
    context: _StructuringContext,
    condition_value: SSAValue,
) -> _SwitchCompareMatch | None:
    compare_value = _unwrap_passthrough_value(context, condition_value)
    if not isinstance(compare_value, SSAName):
        return None
    def_site = context.def_sites.get(compare_value)
    if def_site is None or def_site.op.opcode_text != "INT_EQUAL" or len(def_site.op.inputs) != 2:
        return None
    left, right = def_site.op.inputs
    left_const = _signed_const_from_value(context, left)
    right_const = _signed_const_from_value(context, right)
    if left_const is None and right_const is None:
        return None
    if left_const is not None and right_const is not None:
        return None
    if left_const is not None:
        return _SwitchCompareMatch(selector=right, case_value=left_const)
    assert right_const is not None
    return _SwitchCompareMatch(selector=left, case_value=right_const)


def _canonicalize_selector_value(
    context: _StructuringContext,
    value: SSAValue,
    seen: frozenset[SSAValue] = frozenset(),
) -> SSAValue:
    if value in seen:
        return value
    if isinstance(value, SSAName):
        def_site = context.def_sites.get(value)
        if def_site is not None:
            op = def_site.op
            if op.opcode_text in {"COPY", "INT_ZEXT", "INT_SEXT"} and op.inputs:
                return _canonicalize_selector_value(context, op.inputs[0], seen | {value})
            if op.opcode_text == "LOAD":
                partition = context.load_partitions_by_instruction.get(def_site.instruction_address)
                stored_value = (
                    context.unique_store_values_by_partition.get(partition)
                    if partition is not None
                    else None
                )
                if stored_value is not None:
                    return _canonicalize_selector_value(
                        context,
                        stored_value,
                        seen | {value},
                    )
    return value


def _unwrap_passthrough_value(
    context: _StructuringContext,
    value: SSAValue,
    seen: frozenset[SSAValue] = frozenset(),
) -> SSAValue:
    if value in seen or not isinstance(value, SSAName):
        return value
    def_site = context.def_sites.get(value)
    if def_site is None:
        return value
    if def_site.op.opcode_text in {"COPY", "INT_ZEXT", "INT_SEXT"} and def_site.op.inputs:
        return _unwrap_passthrough_value(context, def_site.op.inputs[0], seen | {value})
    return value


def _signed_const_from_value(
    context: _StructuringContext,
    value: SSAValue,
) -> int | None:
    value = _unwrap_passthrough_value(context, value)
    if not isinstance(value, Varnode) or value.space != PcodeSpace.CONST:
        return None
    bits = value.size * 8
    mask = (1 << bits) - 1
    masked = value.offset & mask
    sign_bit = 1 << (bits - 1)
    return masked - (1 << bits) if masked & sign_bit else masked


def _single_nested_if(sequence: StructuredSequence) -> StructuredIf | None:
    if len(sequence.items) != 1:
        return None
    item = sequence.items[0]
    if not isinstance(item, StructuredIf):
        return None
    return item


def _sequence_entry_target(
    sequence: StructuredSequence,
    fallback: int | None,
) -> int | None:
    if not sequence.items:
        return fallback
    first = sequence.items[0]
    if isinstance(first, StructuredBlock):
        return first.block_start
    if isinstance(first, (StructuredGoto, StructuredBreak, StructuredContinue)):
        return first.target
    return first.header


def _build_sequence(
    *,
    ssa: SSAFunctionIR,
    current: int | None,
    stop_at: int | None,
    region_nodes: frozenset[int],
    order_index: dict[int, int],
    successors: dict[int, tuple[int, ...]],
    immediate_postdominators: dict[int, int | None],
    loop_infos: dict[int, _LoopInfo],
    loop_context: _LoopContext | None,
    active_headers: frozenset[int],
) -> _StructureResult:
    items: list = []
    seen: set[int] = set()

    while current is not None:
        current = _normalize_trampoline_start(
            ssa=ssa,
            current=current,
            stop_at=stop_at,
            region_nodes=region_nodes,
            successors=successors,
            loop_context=loop_context,
        )
        if stop_at is not None and current == stop_at:
            return _StructureResult(body=StructuredSequence(tuple(items)), next_start=current)

        if current not in region_nodes:
            items.append(_fallback_leaf(current, loop_context))
            return _StructureResult(body=StructuredSequence(tuple(items)), next_start=None)

        if current in seen or current in active_headers:
            items.append(_fallback_leaf(current, loop_context))
            return _StructureResult(body=StructuredSequence(tuple(items)), next_start=None)
        seen.add(current)

        loop_info = loop_infos.get(current)
        if loop_info is not None:
            body_result = _build_sequence(
                ssa=ssa,
                current=loop_info.body_entry,
                stop_at=loop_info.header,
                region_nodes=frozenset(loop_info.nodes - {loop_info.header}),
                order_index=order_index,
                successors=successors,
                immediate_postdominators=immediate_postdominators,
                loop_infos=loop_infos,
                loop_context=_LoopContext(
                    header=loop_info.header,
                    exit_target=loop_info.exit_target,
                ),
                active_headers=active_headers | {loop_info.header},
            )
            exit_target = loop_info.exit_target
            if exit_target == _SYNTHETIC_EXIT:
                items.append(
                    StructuredWhile(
                        header=loop_info.header,
                        body_entry=loop_info.body_entry,
                        exit_target=loop_info.header,
                        body=body_result.body,
                    )
                )
                current = None
            else:
                items.append(
                    StructuredWhile(
                        header=loop_info.header,
                        body_entry=loop_info.body_entry,
                        exit_target=exit_target,
                        body=body_result.body,
                    )
                )
                current = exit_target
            continue

        if len(successors[current]) == 2:
            structured_if = _try_build_if(
                ssa=ssa,
                header=current,
                region_nodes=region_nodes,
                order_index=order_index,
                successors=successors,
                immediate_postdominators=immediate_postdominators,
                loop_infos=loop_infos,
                loop_context=loop_context,
                active_headers=active_headers,
            )
            if structured_if is not None:
                items.append(structured_if.node)
                current = structured_if.next_start
                continue

        items.append(StructuredBlock(block_start=current))
        next_targets = successors[current]
        if not next_targets:
            return _StructureResult(body=StructuredSequence(tuple(items)), next_start=None)

        if len(next_targets) != 1:
            for target in next_targets:
                items.append(_fallback_leaf(target, loop_context))
            return _StructureResult(body=StructuredSequence(tuple(items)), next_start=None)

        next_target = next_targets[0]
        if stop_at is not None and next_target == stop_at:
            return _StructureResult(body=StructuredSequence(tuple(items)), next_start=next_target)
        if loop_context is not None and next_target == loop_context.header:
            return _StructureResult(body=StructuredSequence(tuple(items)), next_start=next_target)
        if loop_context is not None and next_target == loop_context.exit_target:
            items.append(StructuredBreak(target=next_target))
            return _StructureResult(body=StructuredSequence(tuple(items)), next_start=None)
        if next_target not in region_nodes:
            items.append(_fallback_leaf(next_target, loop_context))
            return _StructureResult(body=StructuredSequence(tuple(items)), next_start=None)
        current = next_target

    return _StructureResult(body=StructuredSequence(tuple(items)), next_start=None)


def _try_build_if(
    *,
    ssa: SSAFunctionIR,
    header: int,
    region_nodes: frozenset[int],
    order_index: dict[int, int],
    successors: dict[int, tuple[int, ...]],
    immediate_postdominators: dict[int, int | None],
    loop_infos: dict[int, _LoopInfo],
    loop_context: _LoopContext | None,
    active_headers: frozenset[int],
) -> _NodeResult | None:
    true_target, false_target = _ordered_branch_targets(ssa.blocks[header].successors)
    merge_target = immediate_postdominators[header]
    boundaries = {
        boundary
        for boundary in (
            merge_target,
            None if loop_context is None else loop_context.header,
            None if loop_context is None else loop_context.exit_target,
        )
        if boundary is not None
    }

    true_nodes = _reachable_region(
        ssa=ssa,
        start=true_target,
        region_nodes=region_nodes,
        successors=successors,
        boundaries=boundaries,
        header=header,
    )
    false_nodes = _reachable_region(
        ssa=ssa,
        start=false_target,
        region_nodes=region_nodes,
        successors=successors,
        boundaries=boundaries,
        header=header,
    )

    if true_nodes & false_nodes:
        return None

    true_result = _build_branch_body(
        ssa=ssa,
        start=true_target,
        stop_at=merge_target,
        region_nodes=true_nodes,
        order_index=order_index,
        successors=successors,
        immediate_postdominators=immediate_postdominators,
        loop_infos=loop_infos,
        loop_context=loop_context,
        active_headers=active_headers | {header},
    )
    false_result = _build_branch_body(
        ssa=ssa,
        start=false_target,
        stop_at=merge_target,
        region_nodes=false_nodes,
        order_index=order_index,
        successors=successors,
        immediate_postdominators=immediate_postdominators,
        loop_infos=loop_infos,
        loop_context=loop_context,
        active_headers=active_headers | {header},
    )

    if merge_target is not None:
        if true_target != merge_target and true_result.next_start != merge_target:
            return None
        if false_target != merge_target and false_result.next_start != merge_target:
            return None
    elif true_result.next_start is not None or false_result.next_start is not None:
        return None

    next_start = merge_target
    if loop_context is not None and next_start == loop_context.header:
        next_start = loop_context.header
    return _NodeResult(
        node=StructuredIf(
            header=header,
            true_target=true_target,
            false_target=false_target,
            merge_target=merge_target,
            then_body=true_result.body,
            else_body=false_result.body,
        ),
        next_start=next_start,
    )


def _build_branch_body(
    *,
    ssa: SSAFunctionIR,
    start: int,
    stop_at: int | None,
    region_nodes: frozenset[int],
    order_index: dict[int, int],
    successors: dict[int, tuple[int, ...]],
    immediate_postdominators: dict[int, int | None],
    loop_infos: dict[int, _LoopInfo],
    loop_context: _LoopContext | None,
    active_headers: frozenset[int],
) -> _StructureResult:
    if stop_at is not None and start == stop_at:
        return _StructureResult(body=StructuredSequence(), next_start=stop_at)
    if start not in region_nodes:
        return _StructureResult(
            body=StructuredSequence(( _fallback_leaf(start, loop_context), )),
            next_start=None,
        )
    return _build_sequence(
        ssa=ssa,
        current=start,
        stop_at=stop_at,
        region_nodes=region_nodes,
        order_index=order_index,
        successors=successors,
        immediate_postdominators=immediate_postdominators,
        loop_infos=loop_infos,
        loop_context=loop_context,
        active_headers=active_headers,
    )


def _normalize_trampoline_start(
    *,
    ssa: SSAFunctionIR,
    current: int,
    stop_at: int | None,
    region_nodes: frozenset[int],
    successors: dict[int, tuple[int, ...]],
    loop_context: _LoopContext | None,
) -> int:
    seen: set[int] = set()
    while current not in seen:
        if stop_at is not None and current == stop_at:
            return current
        if loop_context is not None and current in {
            loop_context.header,
            loop_context.exit_target,
        }:
            return current
        if current not in region_nodes:
            return current
        if not _is_jump_trampoline_block(ssa.blocks[current], successors[current]):
            return current
        seen.add(current)
        current = successors[current][0]
    return current


def _is_jump_trampoline_block(
    block,
    next_targets: tuple[int, ...],
) -> bool:
    if block.terminator != BlockTerminator.JUMP:
        return False
    if len(next_targets) != 1:
        return False
    if block.phis or block.memory_phi is not None:
        return False
    if block.call_targets or block.has_indirect_call:
        return False
    for instruction in block.instructions:
        for op in instruction.ops:
            if op.output is not None or op.opcode_text != "BRANCH":
                return False
    return True


def _reachable_region(
    *,
    ssa: SSAFunctionIR,
    start: int,
    region_nodes: frozenset[int],
    successors: dict[int, tuple[int, ...]],
    boundaries: set[int],
    header: int,
) -> frozenset[int]:
    if start in boundaries or start == header or start not in region_nodes:
        return frozenset()

    seen: set[int] = set()
    worklist = [start]
    while worklist:
        node = worklist.pop()
        if node in seen or node in boundaries or node == header or node not in region_nodes:
            continue
        if not _dominates(ssa, header, node):
            continue
        seen.add(node)
        for successor in successors[node]:
            if successor not in seen:
                worklist.append(successor)
    return frozenset(seen)


def _build_successor_map(
    ssa: SSAFunctionIR,
    order: tuple[int, ...],
) -> dict[int, tuple[int, ...]]:
    return {
        start: tuple(
            edge.target
            for edge in ssa.blocks[start].successors
            if edge.target in ssa.blocks
        )
        for start in order
    }


def _build_predecessor_map(
    successors: dict[int, tuple[int, ...]],
    order_index: dict[int, int],
) -> dict[int, tuple[int, ...]]:
    predecessors: dict[int, list[int]] = {start: [] for start in successors}
    for start, targets in successors.items():
        for target in targets:
            predecessors[target].append(start)
    return {
        start: tuple(sorted(sources, key=order_index.__getitem__))
        for start, sources in predecessors.items()
    }


def _compute_immediate_postdominators(
    order: tuple[int, ...],
    successors: dict[int, tuple[int, ...]],
    order_index: dict[int, int],
) -> dict[int, int | None]:
    all_nodes = frozenset((*order, _SYNTHETIC_EXIT))
    postdominators = {
        start: set(all_nodes)
        for start in order
    }
    postdominators[_SYNTHETIC_EXIT] = {_SYNTHETIC_EXIT}

    changed = True
    while changed:
        changed = False
        for start in reversed(order):
            next_targets = successors[start] or (_SYNTHETIC_EXIT,)
            new_postdominators = {start} | set.intersection(
                *(postdominators[target] for target in next_targets)
            )
            if new_postdominators != postdominators[start]:
                postdominators[start] = new_postdominators
                changed = True

    def sort_key(target: int) -> tuple[int, int]:
        if target == _SYNTHETIC_EXIT:
            return (1, 0)
        return (0, order_index[target])

    results: dict[int, int | None] = {}
    for start in order:
        strict = tuple(
            sorted(
                postdominators[start] - {start},
                key=sort_key,
            )
        )
        candidate: int | None = None
        for postdominator in reversed(strict):
            if all(
                other in postdominators[postdominator]
                for other in strict
                if other != postdominator
            ):
                candidate = postdominator
                break
        results[start] = None if candidate == _SYNTHETIC_EXIT else candidate
    return results


def _collect_loop_infos(
    ssa: SSAFunctionIR,
    order: tuple[int, ...],
    successors: dict[int, tuple[int, ...]],
    predecessors: dict[int, tuple[int, ...]],
    order_index: dict[int, int],
) -> dict[int, _LoopInfo]:
    backedge_sources: dict[int, set[int]] = {}
    for source in order:
        for target in successors[source]:
            if _dominates(ssa, target, source):
                backedge_sources.setdefault(target, set()).add(source)

    loop_infos: dict[int, _LoopInfo] = {}
    for header, sources in backedge_sources.items():
        block_successors = successors[header]
        if len(block_successors) != 2:
            continue

        nodes = {header}
        worklist = list(sorted(sources, key=order_index.__getitem__))
        while worklist:
            node = worklist.pop()
            if node in nodes:
                continue
            nodes.add(node)
            for predecessor in predecessors[node]:
                if predecessor not in nodes:
                    worklist.append(predecessor)

        in_loop_successors = [
            successor
            for successor in block_successors
            if successor in nodes and successor != header
        ]
        exit_successors = [
            successor for successor in block_successors if successor not in nodes
        ]

        if len(in_loop_successors) == 1 and len(exit_successors) == 1:
            loop_infos[header] = _LoopInfo(
                header=header,
                body_entry=in_loop_successors[0],
                exit_target=exit_successors[0],
                nodes=frozenset(nodes),
            )
        elif len(exit_successors) == 0 and len(in_loop_successors) >= 1:
            body_entry = min(in_loop_successors, key=order_index.__getitem__)
            loop_infos[header] = _LoopInfo(
                header=header,
                body_entry=body_entry,
                exit_target=_SYNTHETIC_EXIT,
                nodes=frozenset(nodes),
            )
    return loop_infos


def _dominates(ssa: SSAFunctionIR, dominator: int, node: int) -> bool:
    current: int | None = node
    while current is not None:
        if current == dominator:
            return True
        current = ssa.immediate_dominators[current]
    return False


def _ordered_branch_targets(successors: tuple[BlockEdge, ...]) -> tuple[int, int]:
    branch_taken = next(
        (edge.target for edge in successors if edge.kind == BlockEdgeKind.BRANCH_TAKEN),
        None,
    )
    if branch_taken is None:
        return successors[0].target, successors[1].target
    fallthrough = next(edge.target for edge in successors if edge.target != branch_taken)
    return branch_taken, fallthrough


def _branch_target(value: SSAValue) -> int | None:
    if isinstance(value, Varnode) and value.space == PcodeSpace.CONST:
        return value.offset
    return None


def _fallback_leaf(target: int, loop_context: _LoopContext | None):
    if loop_context is not None and target == loop_context.header:
        return StructuredContinue(target=target)
    if loop_context is not None and target == loop_context.exit_target:
        return StructuredBreak(target=target)
    return StructuredGoto(target=target)
