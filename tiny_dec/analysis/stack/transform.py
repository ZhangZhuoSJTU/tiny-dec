"""Stage-9 stack recovery from stage-8 call facts.

This file owns the transformation from stage-8 call facts into stage-9 stack
facts.

Implementation notes:
- The stage is read-only with respect to the upstream CFG, SSA graph, and call
  graph.
- It preserves upstream `pending_entries` and `invalidated_entries` unchanged.
- The algorithm walks SSA blocks in dominator-tree order while tracking
  symbolic values of the form `frame_top + constant`.
- `x2` seeds the entry stack top and later constant `x2` updates describe the
  current stack-pointer delta.
- `x8` becomes a frame-pointer candidate only when its value resolves to the
  same symbolic form.
- `LOAD` and `STORE` ops become stack accesses only when their address resolves
  to a known stack base plus constant offset.
- Unsupported or non-constant stack-pointer arithmetic sets
  `dynamic_stack_pointer=yes` rather than guessing slots.

Simplifying assumptions:
- The stack frame is assumed to be contiguous from the minimum SP delta
  to the entry SP.  Variable-length arrays (alloca) create gaps that this
  model cannot represent; they trigger `dynamic_stack_pointer` bailout.
- Only x2 (sp) is treated as the stack pointer.  Architectures or ABIs
  that use a different register for the stack will not be recognized.
- Frame size is derived from the most negative observed SP delta.  If
  the frame is set up in a callee rather than the prologue, the size
  may be underestimated.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tiny_dec.analysis._helpers import (
    build_dominator_children,
    opcode_text,
    signed_const,
)
from tiny_dec.analysis.calls import FunctionCallFacts, ProgramCallFacts, build_program_call_facts
from tiny_dec.analysis.ssa import SSAName, SSANameKind, SSAOp
from tiny_dec.analysis.stack.models import (
    FunctionStackFacts,
    ProgramStackFacts,
    StackAccess,
    StackAccessKind,
    StackBaseKind,
    StackFrameBase,
    StackSlot,
    StackSlotRole,
)
from tiny_dec.ir.pcode import Varnode
from tiny_dec.loader import ProgramView


@dataclass(frozen=True, slots=True)
class _TrackedStackValue:
    base_kind: StackBaseKind
    base_register: int
    frame_top_delta: int


@dataclass(slots=True)
class _FunctionAnalysisState:
    min_stack_pointer_delta: int | None = None
    dynamic_stack_pointer: bool = False
    frame_pointer: StackFrameBase | None = None
    accesses: list[StackAccess] = field(default_factory=list)


def analyze_function_stack(function: FunctionCallFacts) -> FunctionStackFacts:
    """Analyze one function and emit stage-9 stack facts."""
    state = _FunctionAnalysisState()
    dominator_children = _build_dominator_children(function.ssa)
    current: dict[SSAName | Varnode, _TrackedStackValue] = {}

    for live_in in function.ssa.live_ins:
        if live_in.kind == SSANameKind.REGISTER and live_in.base == 2:
            current[live_in] = _TrackedStackValue(
                base_kind=StackBaseKind.ENTRY_SP,
                base_register=2,
                frame_top_delta=0,
            )
            state.min_stack_pointer_delta = 0

    worklist: list[tuple[int, dict[SSAName | Varnode, _TrackedStackValue]]] = [
        (function.entry, current)
    ]
    while worklist:
        start, incoming = worklist.pop()
        block = function.ssa.blocks[start]
        local = dict(incoming)

        for phi in block.phis:
            # Conservative: any phi merging x2 (SP) marks the frame as
            # dynamic rather than tracking which incoming deltas agree.
            # Loses precision for conditional SP adjustments but is safe.
            if phi.output.base == 2:
                state.dynamic_stack_pointer = True

        for instruction in block.instructions:
            for op in instruction.ops:
                access = _recover_stack_access(
                    op,
                    instruction_address=instruction.address,
                    block_start=block.start,
                    current=local,
                )
                if access is not None:
                    state.accesses.append(access)

                tracked_output = _recover_tracked_output(op, local)
                output = op.output
                if tracked_output is not None and output is not None:
                    local[output] = tracked_output
                    _record_tracked_register(
                        output=output,
                        tracked=tracked_output,
                        state=state,
                    )
                elif output is not None and output.kind == SSANameKind.REGISTER and output.base == 2:
                    state.dynamic_stack_pointer = True

        for child in reversed(dominator_children[start]):
            worklist.append((child, local))
    frame_size = _frame_size(state)
    return FunctionStackFacts(
        calls=function,
        frame_size=frame_size,
        frame_pointer=state.frame_pointer,
        dynamic_stack_pointer=state.dynamic_stack_pointer,
        slots=_build_slots(function, state.accesses),
    )


def analyze_program_stack(program: ProgramCallFacts) -> ProgramStackFacts:
    """Analyze a whole program and emit stage-9 stack facts."""
    functions = {
        function.entry: analyze_function_stack(function)
        for function in program.ordered_functions()
    }
    return ProgramStackFacts(
        calls=program,
        functions=functions,
        pending_entries=program.pending_entries,
        invalidated_entries=program.invalidated_entries,
    )


def build_function_stack_facts(view: ProgramView, entry: int) -> FunctionStackFacts:
    """Build stage-8 call facts first, then derive stage-9 stack facts."""
    program = build_program_stack_facts(view, entry)
    return program.functions[entry]


def build_program_stack_facts(view: ProgramView, root_entry: int) -> ProgramStackFacts:
    """Build stage-8 call facts first, then derive stage-9 stack facts."""
    program = build_program_call_facts(view, root_entry)
    return analyze_program_stack(program)


_build_dominator_children = build_dominator_children


def _recover_stack_access(
    op: SSAOp,
    *,
    instruction_address: int,
    block_start: int,
    current: dict[SSAName | Varnode, _TrackedStackValue],
) -> StackAccess | None:
    opcode = _opcode_text(op)
    if opcode == "LOAD":
        output = op.output
        if output is None or not op.inputs:
            return None
        address = current.get(op.inputs[0])
        if address is None:
            return None
        return StackAccess(
            instruction_address=instruction_address,
            block_start=block_start,
            kind=StackAccessKind.LOAD,
            frame_offset=address.frame_top_delta,
            size=output.size,
            base_kind=address.base_kind,
            base_register=address.base_register,
            value=output,
        )

    if opcode == "STORE" and len(op.inputs) >= 2:
        address = current.get(op.inputs[0])
        if address is None:
            return None
        value = op.inputs[1]
        return StackAccess(
            instruction_address=instruction_address,
            block_start=block_start,
            kind=StackAccessKind.STORE,
            frame_offset=address.frame_top_delta,
            size=value.size,
            base_kind=address.base_kind,
            base_register=address.base_register,
            value=value,
        )

    return None


def _recover_tracked_output(
    op: SSAOp,
    current: dict[SSAName | Varnode, _TrackedStackValue],
) -> _TrackedStackValue | None:
    output = op.output
    if output is None:
        return None

    opcode = _opcode_text(op)
    if opcode == "COPY" and op.inputs:
        source = current.get(op.inputs[0])
        if source is None:
            return None
        return _normalize_output(output, source)

    if opcode == "INT_ADD":
        return _recover_additive_output(op.inputs, output, current)

    if opcode == "INT_SUB":
        return _recover_subtractive_output(op.inputs, output, current)

    return None


def _recover_additive_output(
    inputs: tuple[SSAName | Varnode, ...],
    output: SSAName,
    current: dict[SSAName | Varnode, _TrackedStackValue],
) -> _TrackedStackValue | None:
    if len(inputs) != 2:
        return None

    left = current.get(inputs[0])
    right = current.get(inputs[1])
    left_const = _signed_const(inputs[0])
    right_const = _signed_const(inputs[1])

    if left is not None and right_const is not None:
        return _normalize_output(
            output,
            _TrackedStackValue(
                base_kind=left.base_kind,
                base_register=left.base_register,
                frame_top_delta=left.frame_top_delta + right_const,
            ),
        )

    if right is not None and left_const is not None:
        return _normalize_output(
            output,
            _TrackedStackValue(
                base_kind=right.base_kind,
                base_register=right.base_register,
                frame_top_delta=right.frame_top_delta + left_const,
            ),
        )

    return None


def _recover_subtractive_output(
    inputs: tuple[SSAName | Varnode, ...],
    output: SSAName,
    current: dict[SSAName | Varnode, _TrackedStackValue],
) -> _TrackedStackValue | None:
    if len(inputs) != 2:
        return None

    left = current.get(inputs[0])
    right_const = _signed_const(inputs[1])
    if left is None or right_const is None:
        return None
    return _normalize_output(
        output,
        _TrackedStackValue(
            base_kind=left.base_kind,
            base_register=left.base_register,
            frame_top_delta=left.frame_top_delta - right_const,
        ),
    )


def _normalize_output(output: SSAName, tracked: _TrackedStackValue) -> _TrackedStackValue:
    if output.kind != SSANameKind.REGISTER:
        return tracked
    if output.base == 2:
        return _TrackedStackValue(
            base_kind=StackBaseKind.STACK_POINTER,
            base_register=2,
            frame_top_delta=tracked.frame_top_delta,
        )
    if output.base == 8:
        return _TrackedStackValue(
            base_kind=StackBaseKind.FRAME_POINTER,
            base_register=8,
            frame_top_delta=tracked.frame_top_delta,
        )
    return tracked


def _record_tracked_register(
    *,
    output: SSAName,
    tracked: _TrackedStackValue,
    state: _FunctionAnalysisState,
) -> None:
    if output.kind != SSANameKind.REGISTER:
        return

    if output.base == 2:
        if state.min_stack_pointer_delta is None:
            state.min_stack_pointer_delta = tracked.frame_top_delta
        else:
            state.min_stack_pointer_delta = min(
                state.min_stack_pointer_delta,
                tracked.frame_top_delta,
            )
        return

    if output.base == 8 and state.frame_pointer is None:  # first x8 assignment wins
        state.frame_pointer = StackFrameBase(
            kind=StackBaseKind.FRAME_POINTER,
            register=8,
            value=output,
            frame_top_delta=tracked.frame_top_delta,
        )


def _build_slots(
    function: FunctionCallFacts,
    accesses: list[StackAccess],
) -> tuple[StackSlot, ...]:
    grouped: dict[tuple[int, int], list[StackAccess]] = {}
    ordered_accesses = sorted(
        accesses,
        key=lambda access: (
            access.frame_offset,
            access.size,
            access.instruction_address,
            access.kind.value,
            access.base_register,
        ),
    )
    for access in ordered_accesses:
        grouped.setdefault((access.frame_offset, access.size), []).append(access)

    slots: list[StackSlot] = []
    for frame_offset, size in sorted(grouped):
        slot_accesses = tuple(grouped[(frame_offset, size)])
        role, saved_register, argument_register = _classify_slot(
            function=function,
            accesses=slot_accesses,
        )
        slots.append(
            StackSlot(
                frame_offset=frame_offset,
                size=size,
                role=role,
                saved_register=saved_register,
                argument_register=argument_register,
                accesses=slot_accesses,
            )
        )
    return tuple(slots)


def _classify_slot(
    *,
    function: FunctionCallFacts,
    accesses: tuple[StackAccess, ...],
) -> tuple[StackSlotRole, int | None, int | None]:
    abi_argument_registers = set(function.abi.argument_registers)
    for access in accesses:
        if access.kind != StackAccessKind.STORE or access.block_start != function.entry:
            continue
        value = access.value
        if not isinstance(value, SSAName):
            break
        if value.kind != SSANameKind.REGISTER or value.version != 0:
            break
        register = value.base
        if register in abi_argument_registers:
            return StackSlotRole.ARGUMENT_HOME, None, register
        if register != 2:
            return StackSlotRole.SAVED_REGISTER, register, None
        break

    if accesses:
        return StackSlotRole.LOCAL, None, None
    return StackSlotRole.UNKNOWN, None, None


def _frame_size(state: _FunctionAnalysisState) -> int | None:
    if state.dynamic_stack_pointer or state.min_stack_pointer_delta is None:
        return None
    return max(0, -state.min_stack_pointer_delta)


_signed_const = signed_const

_opcode_text = opcode_text
