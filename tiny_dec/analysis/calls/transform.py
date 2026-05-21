"""Stage-8 call modeling from stage-7 SSA snapshots.

This file owns the transformation from stage-7 SSA into stage-8 call facts.

Implementation notes:
- The stage is read-only with respect to the caller's CFG and SSA shape.
- It may emit `pending_entries` for newly discovered internal callees that
  should trigger posts 01-04 for those entries on a later scheduler pass.
- It preserves upstream `invalidated_entries` from stage 6 rather than creating
  new CFG invalidation on its own.
- Argument carrier snapshots come from a dominator-tree walk over SSA blocks
  using the fixed RV32I ILP32 ABI model, not from prototype inference.

Simplifying assumptions:
- Varargs functions (e.g. printf) are modeled with the same fixed 8-register
  argument window as ordinary functions; no format-string–driven argument
  count inference is attempted.
- Tail calls (jalr x0, ...) that reach a known function are not modeled as
  calls; they appear as indirect branches.  A tail-call–heavy binary will
  show incomplete call graphs.
- The fixed ABI assumes all functions follow the standard RV32I ILP32
  convention; hand-written assembly or non-standard calling conventions
  will produce incorrect argument/return snapshots.
"""

from __future__ import annotations

from dataclasses import dataclass

from tiny_dec.analysis._helpers import (
    build_dominator_children,
    opcode_text,
    signed_const,
)
from tiny_dec.analysis.calls.models import (
    CallABI,
    CallRegisterValue,
    CallStackValue,
    FunctionCallFacts,
    KnownExternalSignature,
    ModeledCallSite,
    ProgramCallFacts,
    RV32I_ILP32_CALL_ABI,
)
from tiny_dec.analysis.calls.signatures import lookup_known_external_signature
from tiny_dec.analysis.dataflow.models import RecoveredTarget, RecoveredTargetKind
from tiny_dec.analysis.ssa import (
    MemoryVersion,
    SSAFunctionIR,
    SSAName,
    SSANameKind,
    SSAOp,
    SSAProgramIR,
    build_ssa_program_ir,
)
from tiny_dec.analysis.ssa.models import SSAValue
from tiny_dec.ir.function_ir import CallSite
from tiny_dec.ir.pcode import PcodeSpace, Varnode
from tiny_dec.ir.program_ir import CallGraphEdge, CallGraphEdgeKind
from tiny_dec.loader import ExternalFunction
from tiny_dec.loader import ProgramView

type CallsiteKey = tuple[int, int, bool]
type CallsiteSnapshot = tuple[
    SSAValue | None,
    tuple[CallRegisterValue, ...],
    tuple[CallStackValue, ...],
    MemoryVersion | None,
    MemoryVersion | None,
    tuple[CallRegisterValue, ...],
]


@dataclass
class _PendingStackArgument:
    absolute_stack_delta: int
    stack_offset: int
    value: SSAValue
    restored_to_same_register: bool = False


@dataclass
class _PendingCallsiteSnapshot:
    indirect_target_value: SSAValue | None
    argument_values: tuple[CallRegisterValue, ...]
    stack_arguments: tuple[_PendingStackArgument, ...]
    memory_before: MemoryVersion | None
    memory_after: MemoryVersion | None
    return_values: tuple[CallRegisterValue, ...]


def analyze_function_calls(function: SSAFunctionIR) -> FunctionCallFacts:
    """Analyze one SSA function and emit stage-8 call facts."""
    function_names = {function.entry: function.name}
    known_function_entries = {function.entry, *function.dataflow.function.direct_callees}
    known_non_entry_addresses = (
        set(function.dataflow.function.instruction_index) - {function.entry}
    )
    facts, _edges = _analyze_function(
        function=function,
        abi=RV32I_ILP32_CALL_ABI,
        direct_edges={},
        externals_by_address={},
        function_names=function_names,
        known_function_entries=known_function_entries,
        known_non_entry_addresses=known_non_entry_addresses,
    )
    return facts


def analyze_program_calls(program: SSAProgramIR) -> ProgramCallFacts:
    """Analyze one SSA program and emit stage-8 call facts."""
    abi = RV32I_ILP32_CALL_ABI
    direct_edges = {
        (edge.caller, edge.callsite_address): edge
        for edge in program.dataflow.program.call_graph
    }
    externals_by_address = _external_addresses(program.dataflow.program.externals)
    function_names = {
        function.entry: function.name
        for function in program.ordered_functions()
    }
    known_function_entries = set(program.functions)
    known_non_entry_addresses = {
        address
        for function in program.ordered_functions()
        for address in function.dataflow.function.instruction_index
        if address != function.entry
    }

    functions: dict[int, FunctionCallFacts] = {}
    call_graph: list[CallGraphEdge] = []
    pending_entries = set(program.dataflow.pending_entries)

    for function in program.ordered_functions():
        facts, edges = _analyze_function(
            function=function,
            abi=abi,
            direct_edges=direct_edges,
            externals_by_address=externals_by_address,
            function_names=function_names,
            known_function_entries=known_function_entries,
            known_non_entry_addresses=known_non_entry_addresses,
        )
        functions[function.entry] = facts
        call_graph.extend(edges)
        pending_entries.update(facts.pending_entries)

    return ProgramCallFacts(
        ssa=program,
        abi=abi,
        functions=functions,
        call_graph=tuple(call_graph),
        pending_entries=tuple(sorted(pending_entries)),
        invalidated_entries=program.dataflow.invalidated_entries,
    )


def build_function_call_facts(view: ProgramView, entry: int) -> FunctionCallFacts:
    """Build stage-7 SSA first, then derive stage-8 call facts."""
    program = build_program_call_facts(view, entry)
    return program.functions[entry]


def build_program_call_facts(view: ProgramView, root_entry: int) -> ProgramCallFacts:
    """Build stage-7 SSA first, then derive stage-8 call facts."""
    program = build_ssa_program_ir(view, root_entry)
    return analyze_program_calls(program)


def _analyze_function(
    *,
    function: SSAFunctionIR,
    abi: CallABI,
    direct_edges: dict[tuple[int, int], CallGraphEdge],
    externals_by_address: dict[int, ExternalFunction],
    function_names: dict[int, str | None],
    known_function_entries: set[int],
    known_non_entry_addresses: set[int],
) -> tuple[FunctionCallFacts, tuple[CallGraphEdge, ...]]:
    callsite_snapshots = _capture_callsite_register_snapshots(function, abi)
    recovered_targets = {
        target.instruction_address: target
        for target in function.dataflow.recovered_targets
        if target.kind == RecoveredTargetKind.CALL
    }

    modeled_callsites: list[ModeledCallSite] = []
    call_graph: list[CallGraphEdge] = []
    pending_entries: set[int] = set()

    for raw_callsite in function.dataflow.function.callsites:
        key = (raw_callsite.instruction_address, raw_callsite.block_start, raw_callsite.is_indirect)
        if key not in callsite_snapshots:
            raise ValueError("call-model argument snapshot missing for upstream callsite")
        (
            indirect_target_value,
            argument_values,
            stack_argument_values,
            memory_before,
            memory_after,
            return_values,
        ) = callsite_snapshots[key]

        modeled = _model_callsite(
            function=function,
            raw_callsite=raw_callsite,
            indirect_target_value=indirect_target_value,
            abi_arguments=argument_values,
            stack_arguments=stack_argument_values,
            memory_before=memory_before,
            memory_after=memory_after,
            abi_returns=return_values,
            recovered_target=recovered_targets.get(raw_callsite.instruction_address),
            direct_edge=direct_edges.get((function.entry, raw_callsite.instruction_address)),
            externals_by_address=externals_by_address,
            function_names=function_names,
            known_function_entries=known_function_entries,
            known_non_entry_addresses=known_non_entry_addresses,
        )
        modeled_callsites.append(modeled)

        if _should_enqueue(modeled, known_function_entries, externals_by_address):
            assert modeled.target_address is not None
            pending_entries.add(modeled.target_address)

        edge = _call_graph_edge(function.entry, modeled)
        if edge is not None:
            call_graph.append(edge)

    facts = FunctionCallFacts(
        ssa=function,
        abi=abi,
        callsites=tuple(modeled_callsites),
        pending_entries=tuple(sorted(pending_entries)),
    )
    return facts, tuple(call_graph)


def _capture_callsite_register_snapshots(
    function: SSAFunctionIR,
    abi: CallABI,
) -> dict[CallsiteKey, CallsiteSnapshot]:
    pending_snapshots: dict[CallsiteKey, _PendingCallsiteSnapshot] = {}
    dominator_children = _build_dominator_children(function)
    initial_registers: dict[int, SSAValue] = {
        live_in.base: live_in
        for live_in in function.live_ins
    }
    initial_memory = function.memory_live_in
    initial_stack_offsets: dict[SSAValue, int] = {
        live_in: 0
        for live_in in function.live_ins
        if live_in.kind == SSANameKind.REGISTER and live_in.base == 2
    }

    _WorkItem = tuple[
        int,
        dict[int, SSAValue],
        MemoryVersion | None,
        dict[SSAValue, int],
        dict[int, SSAValue],
        tuple[_PendingCallsiteSnapshot, ...],
    ]
    worklist: list[_WorkItem] = [
        (function.entry, initial_registers, initial_memory, initial_stack_offsets, {}, ())
    ]
    while worklist:
        start, incoming, incoming_memory, incoming_stack_offsets, incoming_stack_stores, active_calls = worklist.pop()
        block = function.blocks[start]
        current = dict(incoming)
        current_memory = incoming_memory
        current_stack_offsets = dict(incoming_stack_offsets)
        current_stack_stores = dict(incoming_stack_stores)
        current_active_calls = list(active_calls)

        if block.memory_phi is not None:
            current_memory = block.memory_phi.output
        for phi in block.phis:
            current[phi.output.base] = phi.output
            phi_offset = _phi_stack_offset(phi, current_stack_offsets)
            if phi_offset is not None:
                current_stack_offsets[phi.output] = phi_offset

        for instruction in block.instructions:
            callsite_key: CallsiteKey | None = None
            indirect_target_value: SSAValue | None = None
            argument_values: tuple[CallRegisterValue, ...] = ()
            stack_argument_values: tuple[_PendingStackArgument, ...] = ()
            call_memory_before: MemoryVersion | None = None
            call_memory_after: MemoryVersion | None = None
            return_values: list[CallRegisterValue] = []
            forwarded_values: dict[SSAName, SSAValue] = {}
            for op in instruction.ops:
                opcode = _opcode_text(op)
                if opcode in {"CALL", "CALLIND"}:
                    key = (instruction.address, block.start, opcode == "CALLIND")
                    if key in pending_snapshots:
                        raise ValueError("duplicate call-model snapshot for callsite")
                    callsite_key = key
                    if opcode == "CALLIND" and op.inputs:
                        indirect_target_value = _resolve_forwarded_value(
                            op.inputs[0],
                            forwarded_values,
                        )
                    # Exclude the indirect target carrier from the argument
                    # snapshot by SSA value identity.  Edge case: if the
                    # indirect callee carrier happens to share its SSA value
                    # with a legitimate argument register, that argument is
                    # suppressed.  Acceptable for typical compiler output where
                    # the target register is not also an ABI argument slot.
                    argument_values = tuple(
                        CallRegisterValue(register=register, value=current[register])
                        for register in abi.argument_registers
                        if register in current
                        and current[register] != indirect_target_value
                    )
                    stack_argument_values = _capture_stack_call_argument_candidates(
                        current=current,
                        stack_offsets=current_stack_offsets,
                        stack_stores=current_stack_stores,
                    )
                    if indirect_target_value is not None:
                        stack_argument_values = tuple(
                            value
                            for value in stack_argument_values
                            if value.value != indirect_target_value
                        )
                    call_memory_before = op.memory_before
                stack_restore = _capture_stack_load_restore(
                    op,
                    stack_offsets=current_stack_offsets,
                )
                if stack_restore is not None:
                    address_delta, register_base = stack_restore
                    _mark_reloaded_stack_arguments(
                        current_active_calls,
                        address_delta=address_delta,
                        register_base=register_base,
                    )
                if opcode == "STORE":
                    stack_store = _capture_stack_store(
                        op,
                        current=current,
                        stack_offsets=current_stack_offsets,
                    )
                    if stack_store is not None:
                        address_delta, stored_value = stack_store
                        current_stack_stores[address_delta] = stored_value
                _apply_register_output(current, op)
                _apply_stack_offset_output(current_stack_offsets, op)
                if op.memory_after is not None:
                    current_memory = op.memory_after
                elif op.memory_before is not None and current_memory is None:
                    current_memory = op.memory_before
                output = op.output
                forwarded_value = _forwarded_ssa_value(op)
                if output is not None:
                    forwarded_values.pop(output, None)
                    if forwarded_value is not None:
                        forwarded_values[output] = _resolve_forwarded_value(
                            forwarded_value,
                            forwarded_values,
                        )
                if (
                    opcode == "CALL_RETURN"
                    and output is not None
                    and output.kind == SSANameKind.REGISTER
                ):
                    return_values.append(
                        CallRegisterValue(register=output.base, value=output)
                    )
                if opcode in {"CALL", "CALLIND"}:
                    call_memory_after = op.memory_after or op.memory_before

            if callsite_key is not None:
                pending_snapshot = _PendingCallsiteSnapshot(
                    indirect_target_value=indirect_target_value,
                    argument_values=argument_values,
                    stack_arguments=stack_argument_values,
                    memory_before=call_memory_before,
                    memory_after=call_memory_after,
                    return_values=tuple(
                        sorted(return_values, key=lambda value: value.register)
                    ),
                )
                pending_snapshots[callsite_key] = pending_snapshot
                current_active_calls.append(pending_snapshot)

        for child in reversed(dominator_children[start]):
            worklist.append((
                child,
                current,
                current_memory,
                current_stack_offsets,
                current_stack_stores,
                tuple(current_active_calls),
            ))
    return {
        key: _finalize_callsite_snapshot(snapshot)
        for key, snapshot in pending_snapshots.items()
    }


def _model_callsite(
    *,
    function: SSAFunctionIR,
    raw_callsite: CallSite,
    indirect_target_value: SSAValue | None,
    abi_arguments: tuple[CallRegisterValue, ...],
    stack_arguments: tuple[CallStackValue, ...],
    memory_before: MemoryVersion | None,
    memory_after: MemoryVersion | None,
    abi_returns: tuple[CallRegisterValue, ...],
    recovered_target: RecoveredTarget | None,
    direct_edge: CallGraphEdge | None,
    externals_by_address: dict[int, ExternalFunction],
    function_names: dict[int, str | None],
    known_function_entries: set[int],
    known_non_entry_addresses: set[int],
) -> ModeledCallSite:
    if raw_callsite.is_indirect:
        target_kind = CallGraphEdgeKind.UNRESOLVED
        target_address = None
        callee_name = None
        resolved_from_recovered_target = False

        if recovered_target is not None:
            (
                target_kind,
                target_address,
                callee_name,
            ) = _classify_target(
                target=recovered_target.target,
                preferred_name=None,
                externals_by_address=externals_by_address,
                function_names=function_names,
                known_function_entries=known_function_entries,
                known_non_entry_addresses=known_non_entry_addresses,
            )
            resolved_from_recovered_target = True
        external_signature = _external_signature_for(
            target_kind=target_kind,
            callee_name=callee_name,
        )

        return ModeledCallSite(
            instruction_address=raw_callsite.instruction_address,
            block_start=raw_callsite.block_start,
            target_kind=target_kind,
            target_address=target_address,
            callee_name=callee_name,
            is_indirect=True,
            resolved_from_recovered_target=resolved_from_recovered_target,
            indirect_target_value=indirect_target_value,
            argument_values=abi_arguments,
            stack_argument_values=stack_arguments,
            memory_before=memory_before,
            memory_after=memory_after,
            return_values=abi_returns,
            external_signature=external_signature,
        )

    if direct_edge is not None:
        callee_name = direct_edge.callee_name or raw_callsite.target_name
        return ModeledCallSite(
            instruction_address=raw_callsite.instruction_address,
            block_start=raw_callsite.block_start,
            target_kind=direct_edge.kind,
            target_address=direct_edge.callee_address,
            callee_name=callee_name,
            is_indirect=False,
            argument_values=abi_arguments,
            stack_argument_values=stack_arguments,
            memory_before=memory_before,
            memory_after=memory_after,
            return_values=abi_returns,
            external_signature=_external_signature_for(
                target_kind=direct_edge.kind,
                callee_name=callee_name,
            ),
        )

    (
        target_kind,
        target_address,
        callee_name,
    ) = _classify_target(
        target=raw_callsite.target,
        preferred_name=raw_callsite.target_name,
        externals_by_address=externals_by_address,
        function_names=function_names,
        known_function_entries=known_function_entries,
        known_non_entry_addresses=known_non_entry_addresses,
    )
    return ModeledCallSite(
        instruction_address=raw_callsite.instruction_address,
        block_start=raw_callsite.block_start,
        target_kind=target_kind,
        target_address=target_address,
        callee_name=callee_name,
        is_indirect=False,
        argument_values=abi_arguments,
        stack_argument_values=stack_arguments,
        memory_before=memory_before,
        memory_after=memory_after,
        return_values=abi_returns,
        external_signature=_external_signature_for(
            target_kind=target_kind,
            callee_name=callee_name,
        ),
    )


def _classify_target(
    *,
    target: int | None,
    preferred_name: str | None,
    externals_by_address: dict[int, ExternalFunction],
    function_names: dict[int, str | None],
    known_function_entries: set[int],
    known_non_entry_addresses: set[int],
) -> tuple[CallGraphEdgeKind, int | None, str | None]:
    if target is None:
        return CallGraphEdgeKind.UNRESOLVED, None, preferred_name

    external = externals_by_address.get(target)
    if external is not None:
        return CallGraphEdgeKind.EXTERNAL, target, external.name

    if target in known_function_entries:
        return CallGraphEdgeKind.INTERNAL, target, function_names.get(target) or preferred_name

    if target in known_non_entry_addresses:
        return CallGraphEdgeKind.UNRESOLVED, target, preferred_name

    return CallGraphEdgeKind.INTERNAL, target, function_names.get(target) or preferred_name


def _should_enqueue(
    callsite: ModeledCallSite,
    known_function_entries: set[int],
    externals_by_address: dict[int, ExternalFunction],
) -> bool:
    if callsite.target_kind != CallGraphEdgeKind.INTERNAL or callsite.target_address is None:
        return False
    if callsite.target_address in known_function_entries:
        return False
    if callsite.target_address in externals_by_address:
        return False
    return True


def _call_graph_edge(
    caller: int,
    callsite: ModeledCallSite,
) -> CallGraphEdge | None:
    if callsite.target_address is None:
        return None
    return CallGraphEdge(
        caller=caller,
        callsite_address=callsite.instruction_address,
        kind=callsite.target_kind,
        callee_address=callsite.target_address,
        callee_name=callsite.callee_name,
    )


_build_dominator_children = build_dominator_children


def _apply_register_output(current: dict[int, SSAValue], op: SSAOp) -> None:
    output = op.output
    if output is None:
        return
    if output.kind != SSANameKind.REGISTER or output.base == 0:
        return
    current[output.base] = _forwarded_register_value(op) or output


def _forwarded_register_value(op: SSAOp) -> SSAValue | None:
    output = op.output
    if output is None or output.kind != SSANameKind.REGISTER:
        return None
    if _opcode_text(op) != "COPY" or len(op.inputs) != 1:
        return None
    input_value = op.inputs[0]
    if not isinstance(input_value, SSAName):
        return None
    if input_value.kind != SSANameKind.REGISTER or input_value.size != output.size:
        return None
    return input_value


def _external_addresses(
    externals: tuple[ExternalFunction, ...],
) -> dict[int, ExternalFunction]:
    addresses: dict[int, ExternalFunction] = {}
    for external in externals:
        for candidate in (
            external.plt_address,
            external.got_address,
            external.symbol_address,
        ):
            if candidate is not None:
                addresses[candidate] = external
    return addresses


def _external_signature_for(
    *,
    target_kind: CallGraphEdgeKind,
    callee_name: str | None,
) -> KnownExternalSignature | None:
    if target_kind != CallGraphEdgeKind.EXTERNAL:
        return None
    return lookup_known_external_signature(callee_name)


def _capture_stack_call_argument_candidates(
    *,
    current: dict[int, SSAValue],
    stack_offsets: dict[SSAValue, int],
    stack_stores: dict[int, SSAValue],
) -> tuple[_PendingStackArgument, ...]:
    current_sp_delta = _current_stack_pointer_delta(current, stack_offsets)
    if current_sp_delta is None:
        return ()
    candidates = [
        (address_delta, address_delta - current_sp_delta, value)
        for address_delta, value in sorted(stack_stores.items())
        if address_delta >= current_sp_delta
    ]
    stack_values: list[_PendingStackArgument] = []
    expected_offset = 0
    for address_delta, stack_offset, value in candidates:
        if stack_offset != expected_offset:
            break
        stack_values.append(
            _PendingStackArgument(
                absolute_stack_delta=address_delta,
                stack_offset=stack_offset,
                value=value,
            )
        )
        expected_offset += max(4, value.size)
    return tuple(stack_values)


def _capture_stack_load_restore(
    op: SSAOp,
    *,
    stack_offsets: dict[SSAValue, int],
) -> tuple[int, int] | None:
    if _opcode_text(op) != "LOAD" or not op.inputs:
        return None
    output = op.output
    if output is None or output.kind != SSANameKind.REGISTER:
        return None
    address_delta = _stack_value_delta(op.inputs[0], stack_offsets)
    if address_delta is None:
        return None
    return address_delta, output.base


def _mark_reloaded_stack_arguments(
    active_calls: list[_PendingCallsiteSnapshot],
    *,
    address_delta: int,
    register_base: int,
) -> None:
    for snapshot in active_calls:
        for candidate in snapshot.stack_arguments:
            if candidate.absolute_stack_delta != address_delta:
                continue
            if candidate.restored_to_same_register:
                break
            if not isinstance(candidate.value, SSAName):
                break
            if candidate.value.base != register_base:
                break
            candidate.restored_to_same_register = True
            break


def _finalize_callsite_snapshot(
    snapshot: _PendingCallsiteSnapshot,
) -> CallsiteSnapshot:
    stack_arguments: list[CallStackValue] = []
    expected_offset = 0
    for candidate in snapshot.stack_arguments:
        if candidate.restored_to_same_register:
            continue
        if candidate.stack_offset != expected_offset:
            break
        stack_arguments.append(
            CallStackValue(
                stack_offset=candidate.stack_offset,
                value=candidate.value,
            )
        )
        expected_offset += max(4, candidate.value.size)
    return (
        snapshot.indirect_target_value,
        snapshot.argument_values,
        tuple(stack_arguments),
        snapshot.memory_before,
        snapshot.memory_after,
        snapshot.return_values,
    )


def _capture_stack_store(
    op: SSAOp,
    *,
    current: dict[int, SSAValue],
    stack_offsets: dict[SSAValue, int],
) -> tuple[int, SSAValue] | None:
    if len(op.inputs) < 2:
        return None
    current_sp_delta = _current_stack_pointer_delta(current, stack_offsets)
    if current_sp_delta is None:
        return None
    address_delta = _stack_value_delta(op.inputs[0], stack_offsets)
    if address_delta is None or address_delta < current_sp_delta:
        return None
    return address_delta, op.inputs[1]


def _apply_stack_offset_output(
    stack_offsets: dict[SSAValue, int],
    op: SSAOp,
) -> None:
    output = op.output
    if output is None:
        return
    offset = _stack_output_delta(op, stack_offsets)
    if offset is None:
        return
    stack_offsets[output] = offset


def _stack_output_delta(
    op: SSAOp,
    stack_offsets: dict[SSAValue, int],
) -> int | None:
    output = op.output
    if output is None:
        return None
    opcode = _opcode_text(op)
    if opcode == "COPY" and len(op.inputs) == 1:
        return _stack_value_delta(op.inputs[0], stack_offsets)
    if opcode == "INT_ADD" and len(op.inputs) == 2:
        left_delta = _stack_value_delta(op.inputs[0], stack_offsets)
        right_delta = _stack_value_delta(op.inputs[1], stack_offsets)
        left_const = _signed_constant(op.inputs[0])
        right_const = _signed_constant(op.inputs[1])
        if left_delta is not None and right_const is not None:
            return left_delta + right_const
        if right_delta is not None and left_const is not None:
            return right_delta + left_const
        return None
    if opcode == "INT_SUB" and len(op.inputs) == 2:
        left_delta = _stack_value_delta(op.inputs[0], stack_offsets)
        right_const = _signed_constant(op.inputs[1])
        if left_delta is not None and right_const is not None:
            return left_delta - right_const
    return None


def _phi_stack_offset(
    phi,
    stack_offsets: dict[SSAValue, int],
) -> int | None:
    offsets: list[int] = []
    for phi_input in phi.inputs:
        offset = _stack_value_delta(phi_input.value, stack_offsets)
        if offset is None:
            return None
        offsets.append(offset)
    if not offsets:
        return None
    first = offsets[0]
    if any(offset != first for offset in offsets[1:]):
        return None
    return first


def _current_stack_pointer_delta(
    current: dict[int, SSAValue],
    stack_offsets: dict[SSAValue, int],
) -> int | None:
    current_sp = current.get(2)
    if current_sp is None:
        return None
    return _stack_value_delta(current_sp, stack_offsets)


def _stack_value_delta(
    value: SSAValue,
    stack_offsets: dict[SSAValue, int],
) -> int | None:
    return stack_offsets.get(value)


_signed_constant = signed_const


def _unsigned_constant(value: SSAValue) -> int | None:
    if not isinstance(value, Varnode):
        return None
    space = value.space.value if isinstance(value.space, PcodeSpace) else value.space
    if space != PcodeSpace.CONST.value:
        return None
    bits = value.size * 8
    return value.offset & ((1 << bits) - 1)


def _forwarded_ssa_value(op: SSAOp) -> SSAValue | None:
    output = op.output
    if output is None:
        return None
    if len(op.inputs) == 1 and _opcode_text(op) == "COPY":
        return op.inputs[0]
    if len(op.inputs) != 2:
        return None

    opcode = _opcode_text(op)
    if opcode == "INT_ADD":
        left_const = _signed_constant(op.inputs[0])
        right_const = _signed_constant(op.inputs[1])
        if left_const == 0:
            return op.inputs[1]
        if right_const == 0:
            return op.inputs[0]
        return None

    if opcode == "INT_AND":
        left_mask = _unsigned_constant(op.inputs[0])
        right_mask = _unsigned_constant(op.inputs[1])
        clear_low_bit_mask = (1 << (output.size * 8)) - 2
        if left_mask == clear_low_bit_mask:
            return op.inputs[1]
        if right_mask == clear_low_bit_mask:
            return op.inputs[0]
    return None


def _resolve_forwarded_value(
    value: SSAValue,
    forwarded_values: dict[SSAName, SSAValue],
) -> SSAValue:
    current = value
    seen: set[SSAName] = set()
    while isinstance(current, SSAName) and current in forwarded_values and current not in seen:
        seen.add(current)
        current = forwarded_values[current]
    return current


_opcode_text = opcode_text
