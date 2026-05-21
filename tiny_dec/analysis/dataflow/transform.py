"""Stage-6 dataflow from canonical IR to block and target facts.

This file owns the transformation from stage-5 canonical IR into stage-6
intraprocedural dataflow facts.

Implementation notes:
- The solver is intentionally intraprocedural and block-local.
- Block `in` facts are recomputed from predecessor `out` facts whenever a
  predecessor changes, rather than accumulated incrementally, so joins can gain
  or lose precision as the worklist converges.
- Each instruction gets a fresh `unique` temporary map. This matches the stage
  contract that stage-6 does not reason across instruction boundaries yet.
- Unsupported or memory-dependent cases degrade to unknown instead of raising.

Educational note — the transfer function applies each p-code op to a
`RegisterState` snapshot.  At join points the solver intersects known
constants (meeting two different concrete values yields `unknown`).
This is a standard forward dataflow framework specialized for sparse
constant propagation: it recovers branch targets and indirect-call
addresses but does not attempt general value-range or pointer analysis.
"""

from __future__ import annotations

from collections import deque

from tiny_dec.analysis._helpers import mask_for_size, opcode_text, sign_extend, space_name
from tiny_dec.analysis.dataflow.models import (
    BlockDataflowFacts,
    FunctionDataflowFacts,
    ProgramDataflowFacts,
    RegisterState,
    RecoveredTarget,
    RecoveredTargetKind,
)
from tiny_dec.analysis.simplify import (
    CanonicalBlock,
    CanonicalFunctionIR,
    CanonicalInstruction,
    CanonicalProgramIR,
    build_canonical_function_ir,
    build_canonical_program_ir,
)
from tiny_dec.ir.pcode import PcodeOp, PcodeOpcode, PcodeSpace, Varnode
from tiny_dec.loader import ProgramView

type UniqueKey = tuple[int, int]


def analyze_function_dataflow(function: CanonicalFunctionIR) -> FunctionDataflowFacts:
    """Analyze one canonical function and emit stage-6 block facts."""
    block_order = function.ordered_block_starts()
    predecessors = _build_predecessor_map(function)
    in_states = {start: RegisterState.unreachable() for start in block_order}
    out_states = {start: RegisterState.unreachable() for start in block_order}
    recovered_by_block: dict[int, tuple[RecoveredTarget, ...]] = {
        start: () for start in block_order
    }

    entry_state = RegisterState()
    in_states[function.entry] = entry_state
    worklist: deque[int] = deque([function.entry])
    queued = {function.entry}

    while worklist:
        start = worklist.popleft()
        queued.remove(start)
        block = function.blocks[start]

        new_in = _recompute_in_state(
            block_start=start,
            function=function,
            predecessors=predecessors,
            out_states=out_states,
            entry_state=entry_state,
        )
        prior_out = out_states[start]
        prior_recovered = recovered_by_block[start]
        in_states[start] = new_in

        new_out, recovered_targets = _transfer_block(block, new_in)
        out_states[start] = new_out
        recovered_by_block[start] = recovered_targets

        if new_out == prior_out and recovered_targets == prior_recovered:
            continue

        for successor in block.successors:
            if successor.target not in function.blocks:
                continue
            if successor.target in queued:
                continue
            worklist.append(successor.target)
            queued.add(successor.target)

    blocks = {
        start: BlockDataflowFacts(
            start=start,
            in_state=in_states[start],
            out_state=out_states[start],
            recovered_targets=recovered_by_block[start],
        )
        for start in block_order
    }
    recovered_targets = tuple(
        target for start in block_order for target in recovered_by_block[start]
    )
    return FunctionDataflowFacts(
        function=function,
        blocks=blocks,
        recovered_targets=recovered_targets,
    )


def analyze_program_dataflow(program: CanonicalProgramIR) -> ProgramDataflowFacts:
    """Analyze one canonical program and emit stage-6 program facts."""
    functions = {
        function.entry: analyze_function_dataflow(function)
        for function in program.ordered_functions()
    }

    known_targets = set(program.functions)
    known_targets.update(_external_addresses(program))

    pending_entries: set[int] = set()
    invalidated_entries: set[int] = set()
    for function_facts in functions.values():
        known_blocks = set(function_facts.function.blocks)
        for target in function_facts.recovered_targets:
            if target.kind == RecoveredTargetKind.CALL and target.target not in known_targets:
                pending_entries.add(target.target)
            if target.kind == RecoveredTargetKind.BRANCH and target.target not in known_blocks:
                invalidated_entries.add(function_facts.function.entry)

    return ProgramDataflowFacts(
        program=program,
        functions=functions,
        pending_entries=tuple(sorted(pending_entries)),
        invalidated_entries=tuple(sorted(invalidated_entries)),
    )


def build_function_dataflow(view: ProgramView, entry: int) -> FunctionDataflowFacts:
    """Build canonical function IR first, then analyze its dataflow."""
    function = build_canonical_function_ir(view, entry)
    return analyze_function_dataflow(function)


def build_program_dataflow(view: ProgramView, root_entry: int) -> ProgramDataflowFacts:
    """Build canonical program IR first, then analyze its dataflow."""
    program = build_canonical_program_ir(view, root_entry)
    return analyze_program_dataflow(program)


def _build_predecessor_map(function: CanonicalFunctionIR) -> dict[int, tuple[int, ...]]:
    predecessors: dict[int, list[int]] = {start: [] for start in function.blocks}
    for block in function.ordered_blocks():
        for successor in block.successors:
            if successor.target in predecessors:
                predecessors[successor.target].append(block.start)
    return {
        start: tuple(sorted(sources))
        for start, sources in predecessors.items()
    }


def _recompute_in_state(
    *,
    block_start: int,
    function: CanonicalFunctionIR,
    predecessors: dict[int, tuple[int, ...]],
    out_states: dict[int, RegisterState],
    entry_state: RegisterState,
) -> RegisterState:
    if block_start == function.entry:
        return entry_state

    incoming = [out_states[source] for source in predecessors[block_start]]
    return _merge_states(incoming)


def _merge_states(states: list[RegisterState]) -> RegisterState:
    reachable_states = [state for state in states if state.reachable]
    if not reachable_states:
        return RegisterState.unreachable()

    merged = dict(reachable_states[0].known_registers)
    for state in reachable_states[1:]:
        merged = {
            register: value
            for register, value in merged.items()
            if state.known_registers.get(register) == value
        }
    return RegisterState(known_registers=merged)


def _transfer_block(
    block: CanonicalBlock,
    in_state: RegisterState,
) -> tuple[RegisterState, tuple[RecoveredTarget, ...]]:
    if not in_state.reachable:
        return RegisterState.unreachable(), ()

    registers = dict(in_state.known_registers)
    recovered_targets: list[RecoveredTarget] = []

    for instruction in block.instructions:
        unique_values: dict[UniqueKey, int] = {}
        _transfer_instruction(
            block=block,
            instruction=instruction,
            registers=registers,
            unique_values=unique_values,
            recovered_targets=recovered_targets,
        )

    return RegisterState(known_registers=registers), tuple(recovered_targets)


def _transfer_instruction(
    *,
    block: CanonicalBlock,
    instruction: CanonicalInstruction,
    registers: dict[int, int],
    unique_values: dict[UniqueKey, int],
    recovered_targets: list[RecoveredTarget],
) -> None:
    for op in instruction.ops:
        opcode = _opcode_text(op)

        if opcode == PcodeOpcode.COPY.value and op.output is not None and len(op.inputs) == 1:
            _assign_output(
                op.output,
                _evaluate_varnode(op.inputs[0], registers, unique_values),
                registers,
                unique_values,
            )
            continue

        if opcode == PcodeOpcode.LOAD.value and op.output is not None:
            _assign_output(op.output, None, registers, unique_values)
            continue

        if opcode == PcodeOpcode.STORE.value:
            continue

        if opcode == PcodeOpcode.BRANCHIND.value and op.inputs:
            _maybe_recover_target(
                block=block,
                instruction=instruction,
                kind=RecoveredTargetKind.BRANCH,
                target_input=op.inputs[0],
                registers=registers,
                unique_values=unique_values,
                recovered_targets=recovered_targets,
            )
            continue

        if opcode == PcodeOpcode.CALLIND.value and op.inputs:
            _maybe_recover_target(
                block=block,
                instruction=instruction,
                kind=RecoveredTargetKind.CALL,
                target_input=op.inputs[0],
                registers=registers,
                unique_values=unique_values,
                recovered_targets=recovered_targets,
            )
            registers.clear()
            continue

        if opcode in {PcodeOpcode.CALL.value, PcodeOpcode.CALLOTHER.value}:
            registers.clear()
            continue

        if opcode in {
            PcodeOpcode.BRANCH.value,
            PcodeOpcode.CBRANCH.value,
            PcodeOpcode.RETURN.value,
            PcodeOpcode.TRAP.value,
        }:
            continue

        value = _evaluate_op(op, registers, unique_values)
        if op.output is not None:
            _assign_output(op.output, value, registers, unique_values)


def _maybe_recover_target(
    *,
    block: CanonicalBlock,
    instruction: CanonicalInstruction,
    kind: RecoveredTargetKind,
    target_input: Varnode,
    registers: dict[int, int],
    unique_values: dict[UniqueKey, int],
    recovered_targets: list[RecoveredTarget],
) -> None:
    target = _evaluate_varnode(target_input, registers, unique_values)
    if target is None:
        return
    recovered_targets.append(
        RecoveredTarget(
            instruction_address=instruction.address,
            block_start=block.start,
            kind=kind,
            target=target,
        )
    )


def _evaluate_op(
    op: PcodeOp,
    registers: dict[int, int],
    unique_values: dict[UniqueKey, int],
) -> int | None:
    opcode = _opcode_text(op)
    if op.output is None:
        return None

    if opcode in _BINARY_OPCODES and len(op.inputs) == 2:
        lhs = _evaluate_varnode(op.inputs[0], registers, unique_values)
        rhs = _evaluate_varnode(op.inputs[1], registers, unique_values)
        if lhs is None or rhs is None:
            return None
        return _evaluate_binary(opcode, op.inputs[0], lhs, op.inputs[1], rhs, op.output)

    if opcode == PcodeOpcode.BOOL_NEGATE.value and len(op.inputs) == 1:
        value = _evaluate_varnode(op.inputs[0], registers, unique_values)
        if value is None:
            return None
        return 0 if value else 1

    if opcode == PcodeOpcode.INT_ZEXT.value and len(op.inputs) == 1:
        value = _evaluate_varnode(op.inputs[0], registers, unique_values)
        if value is None:
            return None
        return value & _mask_for_size(op.output.size)

    if opcode == PcodeOpcode.INT_SEXT.value and len(op.inputs) == 1:
        value = _evaluate_varnode(op.inputs[0], registers, unique_values)
        if value is None:
            return None
        return _sign_extend(value, op.inputs[0].size * 8) & _mask_for_size(op.output.size)

    if opcode == PcodeOpcode.SUBPIECE.value and len(op.inputs) == 2:
        value = _evaluate_varnode(op.inputs[0], registers, unique_values)
        shift_bytes = _evaluate_varnode(op.inputs[1], registers, unique_values)
        if value is None or shift_bytes is None:
            return None
        return (value >> (shift_bytes * 8)) & _mask_for_size(op.output.size)

    return None


_BINARY_OPCODES = {
    PcodeOpcode.INT_ADD.value,
    PcodeOpcode.INT_SUB.value,
    PcodeOpcode.INT_AND.value,
    PcodeOpcode.INT_OR.value,
    PcodeOpcode.INT_XOR.value,
    PcodeOpcode.INT_LEFT.value,
    PcodeOpcode.INT_RIGHT.value,
    PcodeOpcode.INT_SRIGHT.value,
    PcodeOpcode.INT_EQUAL.value,
    PcodeOpcode.INT_NOTEQUAL.value,
    PcodeOpcode.INT_SLESS.value,
    PcodeOpcode.INT_LESS.value,
}


def _evaluate_binary(
    opcode: str,
    lhs_varnode: Varnode,
    lhs: int,
    rhs_varnode: Varnode,
    rhs: int,
    output: Varnode,
) -> int:
    lhs_bits = lhs_varnode.size * 8
    rhs_bits = rhs_varnode.size * 8
    output_mask = _mask_for_size(output.size)

    if opcode == PcodeOpcode.INT_ADD.value:
        return (lhs + rhs) & output_mask
    if opcode == PcodeOpcode.INT_SUB.value:
        return (lhs - rhs) & output_mask
    if opcode == PcodeOpcode.INT_AND.value:
        return (lhs & rhs) & output_mask
    if opcode == PcodeOpcode.INT_OR.value:
        return (lhs | rhs) & output_mask
    if opcode == PcodeOpcode.INT_XOR.value:
        return (lhs ^ rhs) & output_mask
    if opcode == PcodeOpcode.INT_LEFT.value:
        shift = rhs & (lhs_bits - 1)
        return (lhs << shift) & output_mask
    if opcode == PcodeOpcode.INT_RIGHT.value:
        shift = rhs & (lhs_bits - 1)
        return ((lhs & _mask_for_size(lhs_varnode.size)) >> shift) & output_mask
    if opcode == PcodeOpcode.INT_SRIGHT.value:
        shift = rhs & (lhs_bits - 1)
        return (_sign_extend(lhs, lhs_bits) >> shift) & output_mask
    if opcode == PcodeOpcode.INT_EQUAL.value:
        return int(
            (lhs & _mask_for_size(lhs_varnode.size))
            == (rhs & _mask_for_size(rhs_varnode.size))
        )
    if opcode == PcodeOpcode.INT_NOTEQUAL.value:
        return int(
            (lhs & _mask_for_size(lhs_varnode.size))
            != (rhs & _mask_for_size(rhs_varnode.size))
        )
    if opcode == PcodeOpcode.INT_SLESS.value:
        return int(_sign_extend(lhs, lhs_bits) < _sign_extend(rhs, rhs_bits))
    if opcode == PcodeOpcode.INT_LESS.value:
        return int(
            (lhs & _mask_for_size(lhs_varnode.size))
            < (rhs & _mask_for_size(rhs_varnode.size))
        )
    raise ValueError(f"unsupported dataflow opcode: {opcode}")


def _evaluate_varnode(
    varnode: Varnode,
    registers: dict[int, int],
    unique_values: dict[UniqueKey, int],
) -> int | None:
    space = _space_name(varnode)
    if space == PcodeSpace.CONST.value:
        return varnode.offset & _mask_for_size(varnode.size)
    if space == PcodeSpace.REGISTER.value:
        if varnode.offset == 0:
            return 0
        return registers.get(varnode.offset)
    if space == PcodeSpace.UNIQUE.value:
        return unique_values.get((varnode.offset, varnode.size))
    return None


def _assign_output(
    output: Varnode,
    value: int | None,
    registers: dict[int, int],
    unique_values: dict[UniqueKey, int],
) -> None:
    masked = None if value is None else value & _mask_for_size(output.size)
    space = _space_name(output)

    if space == PcodeSpace.REGISTER.value:
        if output.offset == 0:
            return
        if masked is None:
            registers.pop(output.offset, None)
            return
        registers[output.offset] = masked
        return

    if space == PcodeSpace.UNIQUE.value:
        key = (output.offset, output.size)
        if masked is None:
            unique_values.pop(key, None)
            return
        unique_values[key] = masked


def _external_addresses(program: CanonicalProgramIR) -> set[int]:
    addresses: set[int] = set()
    for external in program.externals:
        for candidate in (
            external.plt_address,
            external.got_address,
            external.symbol_address,
        ):
            if candidate is not None:
                addresses.add(candidate)
    return addresses


_space_name = space_name

_opcode_text = opcode_text

_mask_for_size = mask_for_size

_sign_extend = sign_extend
