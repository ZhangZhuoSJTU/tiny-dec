"""Stage-15 interprocedural summaries from stage-14 range facts.

This file owns the transformation from stage-14 range facts into stage-15
interprocedural summaries and scheduler suggestions.

Implementation notes:
- The stage is read-only with respect to upstream CFG, SSA, call, stack,
  memory, scalar-type, aggregate-layout, variable, and range artifacts.
- Register-carried prototypes come from stage-13 parameter variables, stage-7
  SSA live-ins and uses, return-block register snapshots, and internal caller
  observations.
- Memory effects stay intentionally small: absolute partitions become global
  read/write addresses, while value-backed partitions only contribute indirect
  load/store booleans.
- The only scheduler effect emitted today is caller invalidation for internal
  no-return callees. Upstream `pending_entries` remain unchanged.
- Unsupported prototype or alias shapes bail out conservatively instead of
  widening the summary into guessed facts.

Simplifying assumptions:
- No-return inference is based on a single heuristic: a function with
  no reachable return block and at least one reachable call is treated
  as no-return.  Functions that loop forever without calling anything
  (e.g. spin-wait stubs) are not classified as no-return.
- Prototype recovery is single-pass (no fixed-point iteration across
  the call graph).  Recursive or mutually-recursive functions may have
  incomplete prototypes on the first pass.
- Stack parameter recovery only considers outgoing stack stores
  observed at known internal callsites; functions called only through
  indirect calls receive no stack-parameter evidence.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping

from tiny_dec.analysis._helpers import opcode_text
from tiny_dec.analysis.highvars.models import RecoveredVariable, VariableBindingKind, VariableKind
from tiny_dec.analysis.interproc.models import (
    FunctionEffectSummary,
    FunctionInterprocFacts,
    InferredPrototype,
    InterprocInvalidation,
    ProgramInterprocFacts,
    PrototypeRegister,
    PrototypeStackParameter,
    _prototype_sort_key,
)
from tiny_dec.analysis.memory.models import MemoryAccessKind, MemoryPartitionKind
from tiny_dec.analysis.range import (
    FunctionRangeFacts,
    ProgramRangeFacts,
    build_program_range_facts,
)
from tiny_dec.analysis.ssa.models import SSAFunctionIR, SSAName, SSANameKind, SSAOp, SSAValue
from tiny_dec.analysis.types.models import ScalarType, ScalarTypeKind
from tiny_dec.ir.program_ir import CallGraphEdgeKind
from tiny_dec.loader import ProgramView

_COMPARE_SCRATCH_OPCODES = {
    "INT_EQUAL",
    "INT_NOTEQUAL",
    "INT_LESS",
    "INT_SLESS",
}
_COMPARE_SCRATCH_USE_KINDS = _COMPARE_SCRATCH_OPCODES | {"PHI"}


def analyze_function_interproc(function: FunctionRangeFacts) -> FunctionInterprocFacts:
    """Analyze one function and emit a stage-15 summary."""

    return _analyze_function_interproc(
        function,
        observed_argument_hints={},
        observed_stack_argument_hints={},
    )


def analyze_program_interproc(program: ProgramRangeFacts) -> ProgramInterprocFacts:
    """Analyze a whole program and emit a stage-15 summary snapshot."""

    (
        observed_argument_hints,
        observed_stack_argument_hints,
        callers_by_callee,
    ) = _collect_program_callsite_hints(program)
    observed_secondary_return_consumption = (
        _collect_program_secondary_return_consumption(program)
    )
    functions = {
        function.entry: _analyze_function_interproc(
            function,
            observed_argument_hints=observed_argument_hints.get(function.entry, {}),
            observed_stack_argument_hints=observed_stack_argument_hints.get(
                function.entry,
                {},
            ),
        )
        for function in program.ordered_functions()
    }
    functions = _refine_program_prototypes(
        program,
        functions,
        observed_secondary_return_consumption=observed_secondary_return_consumption,
    )

    scheduler_invalidations = tuple(
        InterprocInvalidation(
            caller_entry=caller_entry,
            callee_entry=function.entry,
            reason="noreturn_callee",
        )
        for function in (functions[entry] for entry in program.ordered_function_entries())
        if function.prototype.no_return
        for caller_entry in sorted(callers_by_callee.get(function.entry, ()))
    )

    return ProgramInterprocFacts(
        ranges=program,
        functions=functions,
        scheduler_invalidations=scheduler_invalidations,
        pending_entries=program.pending_entries,
        invalidated_entries=tuple(
            sorted(
                {
                    *program.invalidated_entries,
                    *(item.caller_entry for item in scheduler_invalidations),
                }
            )
        ),
    )


def build_function_interproc_facts(
    view: ProgramView,
    entry: int,
) -> FunctionInterprocFacts:
    """Build stage-14 range facts first, then derive stage-15 summaries."""

    program = build_program_interproc_facts(view, entry)
    return program.functions[entry]


def build_program_interproc_facts(
    view: ProgramView,
    root_entry: int,
) -> ProgramInterprocFacts:
    """Build stage-14 range facts first, then derive stage-15 summaries."""

    program = build_program_range_facts(view, root_entry)
    return analyze_program_interproc(program)


def _analyze_function_interproc(
    function: FunctionRangeFacts,
    *,
    observed_argument_hints: Mapping[int, PrototypeRegister],
    observed_stack_argument_hints: Mapping[int, PrototypeStackParameter],
) -> FunctionInterprocFacts:
    scalar_types = function.variables.aggregate_types.scalar_types
    memory = scalar_types.memory
    ssa = memory.stack.calls.ssa
    abi = memory.stack.calls.abi
    value_types = {fact.value: fact.scalar_type for fact in scalar_types.value_facts}
    used_values = _collect_used_values(function)

    parameter_hints, root_only_parameter_hints = _collect_local_parameter_hints(
        function,
        used_values=used_values,
        value_types=value_types,
    )
    for carrier in observed_argument_hints.values():
        current = parameter_hints.get(carrier.register)
        if current is None:
            continue
        parameter_hints[carrier.register] = _merge_carrier_hint(
            current,
            register=carrier.register,
            size=carrier.size,
            scalar_type=carrier.scalar_type,
            variable_name=carrier.variable_name,
        )
    parameter_hints = _prune_root_only_parameter_hints(
        parameter_hints,
        observed_argument_hints=observed_argument_hints,
        root_only_parameter_hints=root_only_parameter_hints,
    )
    stack_parameter_hints = _collect_local_stack_parameter_hints(function)
    stack_parameter_hints = _refine_stack_parameter_hints(
        stack_parameter_hints,
        observed_stack_argument_hints=observed_stack_argument_hints,
    )

    no_return = not bool(ssa.dataflow.function.return_blocks)
    prototype = InferredPrototype(
        parameters=tuple(
            sorted(
                (
                    *parameter_hints.values(),
                    *stack_parameter_hints.values(),
                ),
                key=_prototype_sort_key,
            )
        ),
        returns=()
        if no_return
        else _collect_return_hints(
            call_facts=memory.stack.calls,
            abi_return_registers=abi.return_registers,
            value_types=value_types,
            parameter_hints=parameter_hints,
        ),
        no_return=no_return,
    )

    return FunctionInterprocFacts(
        ranges=function,
        prototype=prototype,
        effects=_collect_function_effects(function),
    )


def _collect_program_callsite_hints(
    program: ProgramRangeFacts,
) -> tuple[
    dict[int, dict[int, PrototypeRegister]],
    dict[int, dict[int, PrototypeStackParameter]],
    dict[int, set[int]],
]:
    observed_argument_hints: dict[int, dict[int, PrototypeRegister]] = defaultdict(dict)
    observed_stack_argument_hints: dict[int, dict[int, PrototypeStackParameter]] = (
        defaultdict(dict)
    )
    callers_by_callee: dict[int, set[int]] = defaultdict(set)

    for function in program.ordered_functions():
        scalar_types = function.variables.aggregate_types.scalar_types
        call_facts = scalar_types.memory.stack.calls
        caller_value_types = {
            fact.value: fact.scalar_type
            for fact in scalar_types.value_facts
        }

        for callsite in call_facts.callsites:
            if (
                callsite.target_kind != CallGraphEdgeKind.INTERNAL
                or callsite.target_address is None
            ):
                continue
            callers_by_callee[callsite.target_address].add(function.entry)
            seen_argument_values: set[SSAValue] = set()

            for register_argument in callsite.argument_values:
                if register_argument.value in seen_argument_values:
                    continue
                seen_argument_values.add(register_argument.value)
                current = observed_argument_hints[callsite.target_address].get(
                    register_argument.register
                )
                observed_argument_hints[callsite.target_address][
                    register_argument.register
                ] = (
                    _merge_carrier_hint(
                        current,
                        register=register_argument.register,
                        size=register_argument.value.size,
                        scalar_type=caller_value_types.get(register_argument.value),
                    )
                )
            for stack_argument in callsite.stack_argument_values:
                current_stack = observed_stack_argument_hints[
                    callsite.target_address
                ].get(stack_argument.stack_offset)
                observed_stack_argument_hints[callsite.target_address][
                    stack_argument.stack_offset
                ] = _merge_stack_parameter_hint(
                    current_stack,
                    stack_offset=stack_argument.stack_offset,
                    size=stack_argument.value.size,
                    scalar_type=caller_value_types.get(stack_argument.value),
                )

    return (
        dict(observed_argument_hints),
        dict(observed_stack_argument_hints),
        callers_by_callee,
    )


def _collect_local_parameter_hints(
    function: FunctionRangeFacts,
    *,
    used_values: set[SSAValue],
    value_types: Mapping[SSAValue, ScalarType],
) -> tuple[dict[int, PrototypeRegister], set[int]]:
    scalar_types = function.variables.aggregate_types.scalar_types
    memory = scalar_types.memory
    ssa = memory.stack.calls.ssa
    abi_argument_registers = set(memory.stack.calls.abi.argument_registers)
    live_in_by_register = {
        live_in.base: live_in
        for live_in in ssa.live_ins
        if live_in.kind == SSANameKind.REGISTER
    }

    hints: dict[int, PrototypeRegister] = {}
    root_only_hints: set[int] = set()
    strong_hints: set[int] = set()
    for variable in function.variables.variables:
        if variable.kind != VariableKind.PARAMETER:
            continue
        register = _parameter_register_of(variable)
        if register is None or register not in abi_argument_registers:
            continue
        if variable.binding.kind == VariableBindingKind.STACK_SLOT:
            strong_hints.add(register)
            root_only_hints.discard(register)
        elif register not in strong_hints:
            root_only_hints.add(register)
        hints[register] = _merge_carrier_hint(
            hints.get(register),
            register=register,
            size=variable.size,
            scalar_type=variable.scalar_type,
            variable_name=variable.name,
        )

    for register in sorted(abi_argument_registers):
        live_in = live_in_by_register.get(register)
        if live_in is None or live_in not in used_values:
            continue
        if register not in strong_hints:
            root_only_hints.add(register)
        hints[register] = _merge_carrier_hint(
            hints.get(register),
            register=register,
            size=live_in.size,
            scalar_type=value_types.get(live_in),
        )

    return hints, root_only_hints


def _collect_local_stack_parameter_hints(
    function: FunctionRangeFacts,
) -> dict[int, PrototypeStackParameter]:
    hints: dict[int, PrototypeStackParameter] = {}
    for variable in function.variables.variables:
        if variable.kind != VariableKind.LOCAL:
            continue
        if variable.binding.kind != VariableBindingKind.STACK_SLOT:
            continue
        assert variable.binding.stack_slot is not None
        if variable.binding.stack_slot.frame_offset < 0:
            continue
        stack_offset = variable.binding.stack_slot.frame_offset
        hints[stack_offset] = _merge_stack_parameter_hint(
            hints.get(stack_offset),
            stack_offset=stack_offset,
            size=variable.size,
            scalar_type=variable.scalar_type,
            variable_name=variable.name,
        )
    return hints


def _prune_root_only_parameter_hints(
    parameter_hints: Mapping[int, PrototypeRegister],
    *,
    observed_argument_hints: Mapping[int, PrototypeRegister],
    root_only_parameter_hints: set[int],
) -> dict[int, PrototypeRegister]:
    if not observed_argument_hints:
        return dict(parameter_hints)
    return {
        register: carrier
        for register, carrier in parameter_hints.items()
        if register not in root_only_parameter_hints or register in observed_argument_hints
    }


def _refine_stack_parameter_hints(
    stack_parameter_hints: Mapping[int, PrototypeStackParameter],
    *,
    observed_stack_argument_hints: Mapping[int, PrototypeStackParameter],
) -> dict[int, PrototypeStackParameter]:
    if not observed_stack_argument_hints:
        return {}

    refined: dict[int, PrototypeStackParameter] = {}
    for stack_offset, carrier in stack_parameter_hints.items():
        observed = observed_stack_argument_hints.get(stack_offset)
        if observed is None:
            continue
        refined[stack_offset] = _merge_stack_parameter_hint(
            carrier,
            stack_offset=stack_offset,
            size=observed.size,
            scalar_type=observed.scalar_type,
            variable_name=observed.variable_name,
        )
    return refined


def _collect_return_hints(
    *,
    call_facts,
    abi_return_registers: tuple[int, ...],
    value_types: Mapping[SSAValue, ScalarType],
    parameter_hints: Mapping[int, PrototypeRegister],
) -> tuple[PrototypeRegister, ...]:
    ssa = call_facts.ssa
    snapshots = _capture_return_snapshots(ssa, abi_return_registers)
    live_in_by_register = {
        live_in.base: live_in
        for live_in in ssa.live_ins
        if live_in.kind == SSANameKind.REGISTER
    }
    def_sites = _build_register_def_sites(ssa)
    phi_inputs = _build_register_phi_inputs(ssa)
    use_kinds = _build_register_use_kinds(ssa)
    unsupported_known_external_returns = {
        returned.value: callsite.external_signature
        for callsite in call_facts.callsites
        if callsite.external_signature is not None
        for returned in callsite.return_values
        if isinstance(returned.value, SSAName)
    }
    results: dict[int, PrototypeRegister] = {}

    for register in abi_return_registers:
        bindings = [
            snapshot[register]
            for snapshot in snapshots
            if register in snapshot
        ]
        if not bindings:
            continue
        if _bindings_are_same_register_compare_scratch(
            bindings,
            register=register,
            live_in_by_register=live_in_by_register,
            def_sites=def_sites,
            phi_inputs=phi_inputs,
            use_kinds=use_kinds,
        ):
            continue
        if _all_bindings_from_unsupported_known_external_return(
            bindings,
            register=register,
            unsupported_known_external_returns=unsupported_known_external_returns,
            def_sites=def_sites,
            phi_inputs=phi_inputs,
        ):
            continue

        meaningful = False
        size = bindings[0].size
        scalar_type: ScalarType | None = None
        for value in bindings:
            size = max(size, value.size)
            scalar_type = _merge_scalar_types(scalar_type, value_types.get(value))
            if _is_meaningful_return_value(
                value,
                register=register,
                live_in_by_register=live_in_by_register,
            ):
                meaningful = True

        if not meaningful:
            continue

        parameter_hint = parameter_hints.get(register)
        if parameter_hint is not None:
            size = max(size, parameter_hint.size)
            scalar_type = _merge_scalar_types(scalar_type, parameter_hint.scalar_type)

        results[register] = PrototypeRegister(
            register=register,
            size=size,
            scalar_type=scalar_type,
        )

    return tuple(sorted(results.values(), key=_prototype_sort_key))


def _all_bindings_from_unsupported_known_external_return(
    bindings: list[SSAName],
    *,
    register: int,
    unsupported_known_external_returns: Mapping[SSAName, object],
    def_sites: Mapping[SSAName, SSAOp],
    phi_inputs: Mapping[SSAName, tuple[SSAValue, ...]],
) -> bool:
    if not bindings:
        return False

    return all(
        _binding_from_unsupported_known_external_return(
            value,
            register=register,
            unsupported_known_external_returns=unsupported_known_external_returns,
            def_sites=def_sites,
            phi_inputs=phi_inputs,
            seen=set(),
        )
        for value in bindings
    )


def _binding_from_unsupported_known_external_return(
    value: SSAName,
    *,
    register: int,
    unsupported_known_external_returns: Mapping[SSAName, object],
    def_sites: Mapping[SSAName, SSAOp],
    phi_inputs: Mapping[SSAName, tuple[SSAValue, ...]],
    seen: set[SSAName],
) -> bool:
    if value in seen:
        return False
    if value.kind != SSANameKind.REGISTER or value.base != register:
        return False

    signature = unsupported_known_external_returns.get(value)
    if signature is not None:
        return register not in getattr(signature, "return_registers", ())

    seen.add(value)
    inputs = phi_inputs.get(value)
    if inputs is not None:
        return all(
            isinstance(item, SSAName)
            and _binding_from_unsupported_known_external_return(
                item,
                register=register,
                unsupported_known_external_returns=unsupported_known_external_returns,
                def_sites=def_sites,
                phi_inputs=phi_inputs,
                seen=set(seen),
            )
            for item in inputs
        )

    def_site = def_sites.get(value)
    if def_site is None or _opcode_text(def_site.opcode) != "COPY" or len(def_site.inputs) != 1:
        return False
    input_value = def_site.inputs[0]
    if not isinstance(input_value, SSAName):
        return False
    return _binding_from_unsupported_known_external_return(
        input_value,
        register=register,
        unsupported_known_external_returns=unsupported_known_external_returns,
        def_sites=def_sites,
        phi_inputs=phi_inputs,
        seen=set(seen),
    )


def _capture_return_snapshots(
    ssa: SSAFunctionIR,
    return_registers: tuple[int, ...],
) -> tuple[dict[int, SSAName], ...]:
    dominator_children: dict[int, tuple[int, ...]] = {
        start: tuple(
            sorted(
                (
                    child
                    for child, idom in ssa.immediate_dominators.items()
                    if idom == start
                )
            )
        )
        for start in ssa.immediate_dominators
    }
    return_blocks = set(ssa.dataflow.function.return_blocks)
    initial_registers = {
        live_in.base: live_in
        for live_in in ssa.live_ins
        if live_in.kind == SSANameKind.REGISTER
    }
    snapshots: list[dict[int, SSAName]] = []

    worklist: list[tuple[int, dict[int, SSAName]]] = [
        (ssa.entry, initial_registers)
    ]
    while worklist:
        start, incoming = worklist.pop()
        block = ssa.blocks[start]
        current = dict(incoming)

        for phi in block.phis:
            current[phi.output.base] = phi.output

        for instruction in block.instructions:
            for op in instruction.ops:
                output = op.output
                if output is None or output.kind != SSANameKind.REGISTER:
                    continue
                current[output.base] = output

        if block.start in return_blocks:
            snapshots.append(
                {
                    register: current[register]
                    for register in return_registers
                    if register in current
                }
            )

        for child in reversed(dominator_children[start]):
            worklist.append((child, current))
    return tuple(snapshots)


def _refine_program_prototypes(
    program: ProgramRangeFacts,
    functions: dict[int, FunctionInterprocFacts],
    *,
    observed_secondary_return_consumption: Mapping[int, Mapping[int, bool]],
) -> dict[int, FunctionInterprocFacts]:
    current = dict(functions)
    changed = True

    while changed:
        changed = False
        for function in program.ordered_functions():
            entry = function.entry
            refined = _refine_function_prototype(
                current[entry],
                functions_by_entry=current,
                observed_secondary_return_consumption=(
                    observed_secondary_return_consumption.get(entry, {})
                ),
            )
            if refined == current[entry].prototype:
                continue
            current[entry] = FunctionInterprocFacts(
                ranges=current[entry].ranges,
                prototype=refined,
                effects=current[entry].effects,
            )
            changed = True

    return current


def _refine_function_prototype(
    function: FunctionInterprocFacts,
    *,
    functions_by_entry: Mapping[int, FunctionInterprocFacts],
    observed_secondary_return_consumption: Mapping[int, bool],
) -> InferredPrototype:
    prototype = function.prototype
    if prototype.no_return or not prototype.returns:
        return prototype

    call_facts = function.ranges.variables.aggregate_types.scalar_types.memory.stack.calls
    snapshots = _capture_return_snapshots(call_facts.ssa, call_facts.abi.return_registers)
    primary_return_register = (
        call_facts.abi.return_registers[0]
        if call_facts.abi.return_registers
        else None
    )
    internal_return_sources = {
        returned.value: (callsite.target_address, returned.register)
        for callsite in call_facts.callsites
        if (
            callsite.target_kind == CallGraphEdgeKind.INTERNAL
            and callsite.target_address is not None
        )
        for returned in callsite.return_values
        if isinstance(returned.value, SSAName)
    }

    kept_returns: list[PrototypeRegister] = []
    for carrier in prototype.returns:
        bindings = [
            snapshot[carrier.register]
            for snapshot in snapshots
            if carrier.register in snapshot
        ]
        if _is_unconsumed_secondary_internal_return_carrier(
            carrier.register,
            primary_return_register=primary_return_register,
            observed_secondary_return_consumption=observed_secondary_return_consumption,
        ):
            continue
        if _all_bindings_from_unsupported_internal_return(
            bindings,
            register=carrier.register,
            internal_return_sources=internal_return_sources,
            functions_by_entry=functions_by_entry,
        ):
            continue
        kept_returns.append(
            _refine_forwarded_internal_return_type(
                carrier,
                bindings=bindings,
                internal_return_sources=internal_return_sources,
                functions_by_entry=functions_by_entry,
            )
        )
    kept_returns_tuple = tuple(kept_returns)
    if kept_returns_tuple == prototype.returns:
        return prototype
    return InferredPrototype(
        parameters=prototype.parameters,
        returns=kept_returns_tuple,
        no_return=prototype.no_return,
    )


def _collect_function_effects(function: FunctionRangeFacts) -> FunctionEffectSummary:
    memory = function.variables.aggregate_types.scalar_types.memory
    global_reads: set[int] = set()
    global_writes: set[int] = set()
    indirect_reads = False
    indirect_writes = False

    for partition in memory.partitions:
        if partition.kind == MemoryPartitionKind.ABSOLUTE:
            assert partition.absolute_address is not None
            if any(access.kind == MemoryAccessKind.LOAD for access in partition.accesses):
                global_reads.add(partition.absolute_address)
            if any(access.kind == MemoryAccessKind.STORE for access in partition.accesses):
                global_writes.add(partition.absolute_address)
            continue

        if partition.kind == MemoryPartitionKind.VALUE:
            if any(access.kind == MemoryAccessKind.LOAD for access in partition.accesses):
                indirect_reads = True
            if any(access.kind == MemoryAccessKind.STORE for access in partition.accesses):
                indirect_writes = True

    return FunctionEffectSummary(
        global_reads=tuple(sorted(global_reads)),
        global_writes=tuple(sorted(global_writes)),
        indirect_reads=indirect_reads,
        indirect_writes=indirect_writes,
    )


def _collect_used_values(function: FunctionRangeFacts) -> set[SSAValue]:
    used_values: set[SSAValue] = set()
    scalar_types = function.variables.aggregate_types.scalar_types
    memory = scalar_types.memory
    ssa = memory.stack.calls.ssa

    for block in ssa.ordered_blocks():
        for phi in block.phis:
            for phi_input in phi.inputs:
                used_values.add(phi_input.value)
        for instruction in block.instructions:
            for op in instruction.ops:
                used_values.update(op.inputs)

    for partition in memory.partitions:
        if partition.base_value is not None:
            used_values.add(partition.base_value)
        for access in partition.accesses:
            if access.value is not None:
                used_values.add(access.value)

    return used_values


def _collect_consumed_values(function: FunctionRangeFacts) -> set[SSAValue]:
    consumed_values = _collect_used_values(function)
    call_facts = function.variables.aggregate_types.scalar_types.memory.stack.calls
    for callsite in call_facts.callsites:
        for argument in callsite.argument_values:
            consumed_values.add(argument.value)
    return consumed_values


def _collect_program_secondary_return_consumption(
    program: ProgramRangeFacts,
) -> dict[int, dict[int, bool]]:
    observed_consumption: dict[int, dict[int, bool]] = defaultdict(dict)

    for function in program.ordered_functions():
        call_facts = function.variables.aggregate_types.scalar_types.memory.stack.calls
        if not call_facts.abi.return_registers:
            continue
        primary_return_register = call_facts.abi.return_registers[0]
        consumed_values = _collect_consumed_values(function)

        for callsite in call_facts.callsites:
            if (
                callsite.target_kind != CallGraphEdgeKind.INTERNAL
                or callsite.target_address is None
            ):
                continue

            per_register = observed_consumption[callsite.target_address]
            for returned in callsite.return_values:
                if returned.register == primary_return_register:
                    continue
                if not isinstance(returned.value, SSAName):
                    continue
                per_register[returned.register] = (
                    per_register.get(returned.register, False)
                    or returned.value in consumed_values
                )

    return {
        entry: dict(registers)
        for entry, registers in observed_consumption.items()
    }


def _is_meaningful_return_value(
    value: SSAName,
    *,
    register: int,
    live_in_by_register: Mapping[int, SSAName],
) -> bool:
    if value.kind != SSANameKind.REGISTER:
        return True
    if value.base != register:
        return True
    if value.version > 0:
        return True

    live_in = live_in_by_register.get(register)
    if live_in is None or value != live_in:
        return True

    return False


def _is_unconsumed_secondary_internal_return_carrier(
    register: int,
    *,
    primary_return_register: int | None,
    observed_secondary_return_consumption: Mapping[int, bool],
) -> bool:
    if primary_return_register is None or register == primary_return_register:
        return False
    if register not in observed_secondary_return_consumption:
        return False
    return not observed_secondary_return_consumption[register]


def _build_register_def_sites(ssa: SSAFunctionIR) -> dict[SSAName, SSAOp]:
    def_sites: dict[SSAName, SSAOp] = {}
    for block in ssa.ordered_blocks():
        for instruction in block.instructions:
            for op in instruction.ops:
                output = op.output
                if output is None or output.kind != SSANameKind.REGISTER:
                    continue
                def_sites[output] = op
    return def_sites


def _build_register_phi_inputs(
    ssa: SSAFunctionIR,
) -> dict[SSAName, tuple[SSAValue, ...]]:
    return {
        phi.output: tuple(phi_input.value for phi_input in phi.inputs)
        for block in ssa.ordered_blocks()
        for phi in block.phis
    }


def _build_register_use_kinds(
    ssa: SSAFunctionIR,
) -> dict[SSAName, tuple[str, ...]]:
    uses: dict[SSAName, list[str]] = defaultdict(list)
    for block in ssa.ordered_blocks():
        for phi in block.phis:
            for phi_input in phi.inputs:
                if isinstance(phi_input.value, SSAName):
                    uses[phi_input.value].append("PHI")
        for instruction in block.instructions:
            for op in instruction.ops:
                opcode = _opcode_text(op.opcode)
                for input_value in op.inputs:
                    if isinstance(input_value, SSAName):
                        uses[input_value].append(opcode)
    return {
        value: tuple(kinds)
        for value, kinds in uses.items()
    }


def _bindings_are_same_register_compare_scratch(
    bindings: list[SSAName],
    *,
    register: int,
    live_in_by_register: Mapping[int, SSAName],
    def_sites: Mapping[SSAName, SSAOp],
    phi_inputs: Mapping[SSAName, tuple[SSAValue, ...]],
    use_kinds: Mapping[SSAName, tuple[str, ...]],
) -> bool:
    live_in = live_in_by_register.get(register)
    if live_in is None:
        return False

    saw_compare_scratch = False
    for value in bindings:
        if value == live_in:
            continue
        if _is_same_register_compare_scratch_value(
            value,
            register=register,
            live_in=live_in,
            def_sites=def_sites,
            phi_inputs=phi_inputs,
            use_kinds=use_kinds,
            seen=set(),
        ):
            saw_compare_scratch = True
            continue
        return False
    return saw_compare_scratch


def _is_same_register_compare_scratch_value(
    value: SSAName,
    *,
    register: int,
    live_in: SSAName,
    def_sites: Mapping[SSAName, SSAOp],
    phi_inputs: Mapping[SSAName, tuple[SSAValue, ...]],
    use_kinds: Mapping[SSAName, tuple[str, ...]],
    seen: set[SSAName],
) -> bool:
    if value in seen:
        return False
    if value.kind != SSANameKind.REGISTER or value.base != register:
        return False
    if value == live_in:
        return True

    seen.add(value)
    inputs = phi_inputs.get(value)
    if inputs is not None:
        return all(
            isinstance(item, SSAName)
            and _is_same_register_compare_scratch_value(
                item,
                register=register,
                live_in=live_in,
                def_sites=def_sites,
                phi_inputs=phi_inputs,
                use_kinds=use_kinds,
                seen=set(seen),
            )
            for item in inputs
        )

    use_list = use_kinds.get(value, ())
    if not use_list:
        return False
    if any(kind not in _COMPARE_SCRATCH_USE_KINDS for kind in use_list):
        return False

    def_site = def_sites.get(value)
    if def_site is None or not hasattr(def_site, "opcode"):
        return False
    if _opcode_text(def_site.opcode) != "COPY" or len(def_site.inputs) != 1:
        return False
    input_value = def_site.inputs[0]
    if getattr(input_value, "space", None) == "const":
        return True
    if isinstance(input_value, SSAName):
        return _is_same_register_compare_scratch_value(
            input_value,
            register=register,
            live_in=live_in,
            def_sites=def_sites,
            phi_inputs=phi_inputs,
            use_kinds=use_kinds,
            seen=seen,
        )
    return False


def _all_bindings_from_unsupported_internal_return(
    bindings: list[SSAName],
    *,
    register: int,
    internal_return_sources: Mapping[SSAName, tuple[int, int]],
    functions_by_entry: Mapping[int, FunctionInterprocFacts],
) -> bool:
    if not bindings:
        return False

    for value in bindings:
        source = internal_return_sources.get(value)
        if source is None:
            return False
        callee_entry, source_register = source
        if source_register != register:
            return False
        callee = functions_by_entry.get(callee_entry)
        if callee is None:
            return False
        if any(item.register == register for item in callee.prototype.returns):
            return False
    return True


def _refine_forwarded_internal_return_type(
    carrier: PrototypeRegister,
    *,
    bindings: list[SSAName],
    internal_return_sources: Mapping[SSAName, tuple[int, int]],
    functions_by_entry: Mapping[int, FunctionInterprocFacts],
) -> PrototypeRegister:
    source = _consistent_internal_return_source(
        bindings,
        internal_return_sources=internal_return_sources,
        functions_by_entry=functions_by_entry,
    )
    if source is None:
        return carrier

    callee_entry, callee_carrier = source
    callee = functions_by_entry[callee_entry]
    if len(callee.prototype.returns) != 1:
        return carrier
    merged_scalar_type = _merge_scalar_types(
        carrier.scalar_type,
        callee_carrier.scalar_type,
    )
    merged_size = max(carrier.size, callee_carrier.size)
    if (
        merged_scalar_type is not None
        and merged_scalar_type.size != merged_size
    ):
        merged_scalar_type = None
    if merged_size == carrier.size and merged_scalar_type == carrier.scalar_type:
        return carrier
    return PrototypeRegister(
        register=carrier.register,
        size=merged_size,
        scalar_type=merged_scalar_type,
        variable_name=carrier.variable_name,
    )


def _consistent_internal_return_source(
    bindings: list[SSAName],
    *,
    internal_return_sources: Mapping[SSAName, tuple[int, int]],
    functions_by_entry: Mapping[int, FunctionInterprocFacts],
) -> tuple[int, PrototypeRegister] | None:
    if not bindings:
        return None

    source_entry: int | None = None
    source_register: int | None = None
    for value in bindings:
        source = internal_return_sources.get(value)
        if source is None:
            return None
        callee_entry, callee_register = source
        if source_entry is None:
            source_entry = callee_entry
            source_register = callee_register
            continue
        if callee_entry != source_entry or callee_register != source_register:
            return None

    assert source_entry is not None
    assert source_register is not None
    callee = functions_by_entry.get(source_entry)
    if callee is None:
        return None
    callee_carrier = next(
        (
            item
            for item in callee.prototype.returns
            if item.register == source_register
        ),
        None,
    )
    if callee_carrier is None:
        return None
    return source_entry, callee_carrier


_opcode_text = opcode_text


def _parameter_register_of(variable: RecoveredVariable) -> int | None:
    root_value = variable.root_value
    if (
        isinstance(root_value, SSAName)
        and root_value.kind == SSANameKind.REGISTER
        and root_value.version == 0
    ):
        return root_value.base

    if variable.binding.kind == VariableBindingKind.STACK_SLOT:
        assert variable.binding.stack_slot is not None
        return variable.binding.stack_slot.argument_register

    if variable.binding.kind == VariableBindingKind.ROOT_VALUE:
        assert variable.binding.root_value is not None
        binding_root = variable.binding.root_value
        if (
            isinstance(binding_root, SSAName)
            and binding_root.kind == SSANameKind.REGISTER
            and binding_root.version == 0
        ):
            return binding_root.base

    return None


def _merge_carrier_hint(
    current: PrototypeRegister | None,
    *,
    register: int,
    size: int,
    scalar_type: ScalarType | None = None,
    variable_name: str | None = None,
) -> PrototypeRegister:
    if current is None:
        return PrototypeRegister(
            register=register,
            size=size,
            scalar_type=scalar_type,
            variable_name=variable_name,
        )

    merged_size = max(current.size, size)
    merged_scalar_type = _merge_scalar_types(current.scalar_type, scalar_type)
    if merged_size != current.size and merged_scalar_type is not None and merged_scalar_type.size != merged_size:
        merged_scalar_type = None
    merged_variable_name = current.variable_name or variable_name

    return PrototypeRegister(
        register=register,
        size=merged_size,
        scalar_type=merged_scalar_type,
        variable_name=merged_variable_name,
    )


def _merge_stack_parameter_hint(
    current: PrototypeStackParameter | None,
    *,
    stack_offset: int,
    size: int,
    scalar_type: ScalarType | None = None,
    variable_name: str | None = None,
) -> PrototypeStackParameter:
    if current is None:
        return PrototypeStackParameter(
            stack_offset=stack_offset,
            size=size,
            scalar_type=scalar_type,
            variable_name=variable_name,
        )

    merged_size = max(current.size, size)
    merged_scalar_type = _merge_scalar_types(current.scalar_type, scalar_type)
    if (
        merged_size != current.size
        and merged_scalar_type is not None
        and merged_scalar_type.size != merged_size
    ):
        merged_scalar_type = None
    merged_variable_name = current.variable_name or variable_name

    return PrototypeStackParameter(
        stack_offset=stack_offset,
        size=merged_size,
        scalar_type=merged_scalar_type,
        variable_name=merged_variable_name,
    )


def _merge_scalar_types(
    current: ScalarType | None,
    other: ScalarType | None,
) -> ScalarType | None:
    if current is None:
        return other
    if other is None:
        return current
    if current == other:
        return current
    if current.size != other.size:
        return None
    if current.kind == ScalarTypeKind.WORD:
        return other
    if other.kind == ScalarTypeKind.WORD:
        return current
    return None
