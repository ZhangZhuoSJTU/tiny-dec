"""Stage-5 canonicalization from raw IR containers to canonical IR snapshots.

This file owns the transformation from stage-4 `FunctionIR` / `ProgramIR`
snapshots into stage-5 canonical IR.

Implementation plan:
1. Canonicalize one instruction at a time; do not rewrite across instruction
   boundaries in this stage.
2. Apply local pure-op rewrites to a fixpoint:
   - fold constant-only arithmetic and predicate ops
   - collapse identity operations into `COPY`
   - forward a single-use `unique` temporary into a trailing `COPY` target
3. Renumber remaining `unique` temporaries densely in first-appearance order.
4. Rebuild canonical blocks and functions without changing block topology,
   callsites, return blocks, or direct-callee metadata.
5. Rebuild canonical programs without changing discovery order, externals,
   queue state, or call graph metadata.

Failure policy:
- Unsupported p-code patterns are preserved unchanged.
- Call, branch, and return targets must not change.
- Malformed stage-4 objects should fail through model invariants rather than
  being silently normalized.

Educational note — this is a peephole optimizer: it only looks at one
instruction at a time and applies local algebraic identities (x + 0 → x,
x & 0xFFFFFFFF → x, constant folding).  It does not perform global
optimizations like dead code elimination or common subexpression
elimination; those happen implicitly during SSA construction and later
stages.
"""

from __future__ import annotations

from tiny_dec.analysis._helpers import mask_for_size, opcode_text, sign_extend
from tiny_dec.analysis.simplify.models import (
    CanonicalBlock,
    CanonicalFunctionIR,
    CanonicalInstruction,
    CanonicalProgramIR,
)
from tiny_dec.disasm.models import BlockInstruction
from tiny_dec.ir.containers import build_function_ir, build_program_ir
from tiny_dec.ir.function_ir import FunctionIR
from tiny_dec.ir.pcode import PcodeOp, PcodeOpcode, PcodeSpace, Varnode, const_varnode
from tiny_dec.ir.program_ir import ProgramIR
from tiny_dec.loader import ProgramView

_FORWARDABLE_OPCODES = {
    PcodeOpcode.COPY.value,
    PcodeOpcode.LOAD.value,
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
    PcodeOpcode.INT_SEXT.value,
    PcodeOpcode.INT_ZEXT.value,
    PcodeOpcode.BOOL_NEGATE.value,
    PcodeOpcode.SUBPIECE.value,
}

_BINARY_CONST_FOLDERS = {
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


def canonicalize_instruction(instruction: BlockInstruction) -> CanonicalInstruction:
    """Canonicalize one stage-3 lifted instruction into stage-5 form."""
    ops = tuple(instruction.pcode_ops)
    while True:
        rewritten = _rewrite_ops_once(ops)
        if rewritten == ops:
            break
        ops = rewritten

    return CanonicalInstruction(
        instruction=instruction.instruction,
        ops=_renumber_unique_offsets(ops),
    )


def canonicalize_function_ir(function: FunctionIR) -> CanonicalFunctionIR:
    """Canonicalize one stage-4 function while preserving topology and metadata."""
    blocks: dict[int, CanonicalBlock] = {}
    instruction_index: dict[int, CanonicalInstruction] = {}

    for block in function.ordered_blocks():
        canonical_instructions = tuple(
            canonicalize_instruction(instruction) for instruction in block.instructions
        )
        canonical_block = CanonicalBlock(
            start=block.start,
            instructions=canonical_instructions,
            successors=block.successors,
            terminator=block.terminator,
            call_targets=block.call_targets,
            has_indirect_call=block.has_indirect_call,
        )
        blocks[block.start] = canonical_block
        for instruction in canonical_instructions:
            instruction_index.setdefault(instruction.address, instruction)

    return CanonicalFunctionIR(
        entry=function.entry,
        name=function.name,
        blocks=blocks,
        discovery_order=function.disasm.discovery_order,
        instruction_index=instruction_index,
        callsites=function.callsites,
        return_blocks=function.return_blocks,
        direct_callees=function.direct_callees,
    )


def canonicalize_program_ir(program: ProgramIR) -> CanonicalProgramIR:
    """Canonicalize one stage-4 program while preserving discovery metadata."""
    functions: dict[int, CanonicalFunctionIR] = {}
    for function in program.ordered_functions():
        functions[function.entry] = canonicalize_function_ir(function)

    return CanonicalProgramIR(
        root_entry=program.root_entry,
        functions=functions,
        discovery_order=program.discovery_order,
        externals=program.externals,
        call_graph=program.call_graph,
        pending_entries=program.pending_entries,
        invalidated_entries=program.invalidated_entries,
    )


def build_canonical_function_ir(view: ProgramView, entry: int) -> CanonicalFunctionIR:
    """Build stage-4 function IR first, then canonicalize it into stage 5."""
    function = build_function_ir(view, entry)
    return canonicalize_function_ir(function)


def build_canonical_program_ir(view: ProgramView, root_entry: int) -> CanonicalProgramIR:
    """Build stage-4 program IR first, then canonicalize it into stage 5."""
    program = build_program_ir(view, root_entry)
    return canonicalize_program_ir(program)


def _rewrite_ops_once(ops: tuple[PcodeOp, ...]) -> tuple[PcodeOp, ...]:
    rewritten = tuple(_rewrite_op(op) for op in ops)
    return _forward_single_use_temps(rewritten)


def _rewrite_op(op: PcodeOp) -> PcodeOp:
    folded = _fold_constant_op(op)
    if folded != op:
        return folded

    identity = _fold_identity_op(op)
    if identity is not None:
        return identity

    return op


def _fold_constant_op(op: PcodeOp) -> PcodeOp:
    if op.output is None:
        return op

    opcode = _opcode_text(op)
    if opcode == PcodeOpcode.COPY.value:
        return op

    if opcode in _BINARY_CONST_FOLDERS and len(op.inputs) == 2 and all(
        _is_const(input_) for input_ in op.inputs
    ):
        return PcodeOp(
            opcode=PcodeOpcode.COPY,
            inputs=(
                const_varnode(
                    _evaluate_binary_const(opcode, op.inputs[0], op.inputs[1], op.output),
                    size=op.output.size,
                ),
            ),
            output=op.output,
        )

    if opcode == PcodeOpcode.BOOL_NEGATE.value and len(op.inputs) == 1 and _is_const(
        op.inputs[0]
    ):
        return PcodeOp(
            opcode=PcodeOpcode.COPY,
            inputs=(const_varnode(0 if op.inputs[0].offset else 1, size=op.output.size),),
            output=op.output,
        )

    if opcode == PcodeOpcode.INT_ZEXT.value and len(op.inputs) == 1 and _is_const(
        op.inputs[0]
    ):
        return PcodeOp(
            opcode=PcodeOpcode.COPY,
            inputs=(const_varnode(op.inputs[0].offset, size=op.output.size),),
            output=op.output,
        )

    if opcode == PcodeOpcode.INT_SEXT.value and len(op.inputs) == 1 and _is_const(
        op.inputs[0]
    ):
        bits = op.inputs[0].size * 8
        return PcodeOp(
            opcode=PcodeOpcode.COPY,
            inputs=(
                const_varnode(_sign_extend(op.inputs[0].offset, bits), size=op.output.size),
            ),
            output=op.output,
        )

    if opcode == PcodeOpcode.SUBPIECE.value and len(op.inputs) == 2 and all(
        _is_const(input_) for input_ in op.inputs
    ):
        shift_bytes = op.inputs[1].offset
        shifted = op.inputs[0].offset >> (shift_bytes * 8)
        return PcodeOp(
            opcode=PcodeOpcode.COPY,
            inputs=(const_varnode(shifted, size=op.output.size),),
            output=op.output,
        )

    return op


def _fold_identity_op(op: PcodeOp) -> PcodeOp | None:
    if op.output is None or len(op.inputs) != 2:
        return None

    opcode = _opcode_text(op)
    lhs, rhs = op.inputs
    all_ones = _mask_for_size(op.output.size)

    if opcode == PcodeOpcode.INT_ADD.value:
        if _is_const_value(rhs, 0) and lhs.size == op.output.size:
            return _copy_op(lhs, op.output)
        if _is_const_value(lhs, 0) and rhs.size == op.output.size:
            return _copy_op(rhs, op.output)

    if opcode == PcodeOpcode.INT_SUB.value and _is_const_value(rhs, 0):
        if lhs.size == op.output.size:
            return _copy_op(lhs, op.output)

    if opcode in {
        PcodeOpcode.INT_OR.value,
        PcodeOpcode.INT_XOR.value,
        PcodeOpcode.INT_LEFT.value,
        PcodeOpcode.INT_RIGHT.value,
        PcodeOpcode.INT_SRIGHT.value,
    }:
        if _is_const_value(rhs, 0) and lhs.size == op.output.size:
            return _copy_op(lhs, op.output)
        if opcode in {PcodeOpcode.INT_OR.value, PcodeOpcode.INT_XOR.value} and _is_const_value(
            lhs, 0
        ):
            if rhs.size == op.output.size:
                return _copy_op(rhs, op.output)

    if opcode == PcodeOpcode.INT_AND.value:
        if _is_const_value(rhs, all_ones) and lhs.size == op.output.size:
            return _copy_op(lhs, op.output)
        if _is_const_value(lhs, all_ones) and rhs.size == op.output.size:
            return _copy_op(rhs, op.output)

    return None


def _forward_single_use_temps(ops: tuple[PcodeOp, ...]) -> tuple[PcodeOp, ...]:
    uses: dict[Varnode, list[int]] = {}
    for index, op in enumerate(ops):
        for input_ in op.inputs:
            if not _is_unique(input_):
                continue
            uses.setdefault(input_, []).append(index)

    skipped: set[int] = set()
    rewritten: list[PcodeOp] = []

    for index, op in enumerate(ops):
        if index in skipped:
            continue

        output = op.output
        if (
            output is not None
            and _is_unique(output)
            and _opcode_text(op) in _FORWARDABLE_OPCODES
            and len(uses.get(output, [])) == 1
        ):
            user_index = uses[output][0]
            user = ops[user_index]
            if (
                user_index > index
                and _opcode_text(user) == PcodeOpcode.COPY.value
                and user.inputs == (output,)
                and user.output is not None
                and user.output.size == output.size
            ):
                rewritten.append(PcodeOp(opcode=op.opcode, inputs=op.inputs, output=user.output))
                skipped.add(user_index)
                continue

        rewritten.append(op)

    return tuple(rewritten)


def _renumber_unique_offsets(ops: tuple[PcodeOp, ...]) -> tuple[PcodeOp, ...]:
    replacements: dict[tuple[int, int], Varnode] = {}
    next_offset = 0
    rewritten: list[PcodeOp] = []

    for op in ops:
        output = _renumber_varnode(op.output, replacements, next_offset)
        if output is not None and _is_unique(op.output):
            next_offset = _next_unique_offset(replacements)

        inputs: list[Varnode] = []
        for input_ in op.inputs:
            rewritten_input = _renumber_varnode(input_, replacements, next_offset)
            if rewritten_input is None:
                raise ValueError("canonical input varnode must not disappear")
            inputs.append(rewritten_input)
            if _is_unique(input_):
                next_offset = _next_unique_offset(replacements)

        rewritten.append(PcodeOp(opcode=op.opcode, inputs=tuple(inputs), output=output))

    return tuple(rewritten)


def _renumber_varnode(
    varnode: Varnode | None,
    replacements: dict[tuple[int, int], Varnode],
    next_offset: int,
) -> Varnode | None:
    if varnode is None or not _is_unique(varnode):
        return varnode

    key = (varnode.offset, varnode.size)
    if key not in replacements:
        replacements[key] = Varnode(space=varnode.space, offset=next_offset, size=varnode.size)
    return replacements[key]


def _next_unique_offset(replacements: dict[tuple[int, int], Varnode]) -> int:
    return len(replacements) * 4


def _evaluate_binary_const(
    opcode: str,
    lhs: Varnode,
    rhs: Varnode,
    output: Varnode,
) -> int:
    lhs_bits = lhs.size * 8
    rhs_bits = rhs.size * 8
    output_mask = _mask_for_size(output.size)

    if opcode == PcodeOpcode.INT_ADD.value:
        return (lhs.offset + rhs.offset) & output_mask
    if opcode == PcodeOpcode.INT_SUB.value:
        return (lhs.offset - rhs.offset) & output_mask
    if opcode == PcodeOpcode.INT_AND.value:
        return (lhs.offset & rhs.offset) & output_mask
    if opcode == PcodeOpcode.INT_OR.value:
        return (lhs.offset | rhs.offset) & output_mask
    if opcode == PcodeOpcode.INT_XOR.value:
        return (lhs.offset ^ rhs.offset) & output_mask
    if opcode == PcodeOpcode.INT_LEFT.value:
        shift = rhs.offset & (lhs_bits - 1)
        return (lhs.offset << shift) & output_mask
    if opcode == PcodeOpcode.INT_RIGHT.value:
        shift = rhs.offset & (lhs_bits - 1)
        return ((lhs.offset & _mask_for_size(lhs.size)) >> shift) & output_mask
    if opcode == PcodeOpcode.INT_SRIGHT.value:
        shift = rhs.offset & (lhs_bits - 1)
        signed = _sign_extend(lhs.offset, lhs_bits)
        return (signed >> shift) & output_mask
    if opcode == PcodeOpcode.INT_EQUAL.value:
        return int((lhs.offset & _mask_for_size(lhs.size)) == (rhs.offset & _mask_for_size(rhs.size)))
    if opcode == PcodeOpcode.INT_NOTEQUAL.value:
        return int((lhs.offset & _mask_for_size(lhs.size)) != (rhs.offset & _mask_for_size(rhs.size)))
    if opcode == PcodeOpcode.INT_SLESS.value:
        return int(_sign_extend(lhs.offset, lhs_bits) < _sign_extend(rhs.offset, rhs_bits))
    if opcode == PcodeOpcode.INT_LESS.value:
        return int((lhs.offset & _mask_for_size(lhs.size)) < (rhs.offset & _mask_for_size(rhs.size)))
    raise ValueError(f"unsupported const fold opcode: {opcode}")


def _copy_op(source: Varnode, dest: Varnode) -> PcodeOp:
    return PcodeOp(opcode=PcodeOpcode.COPY, inputs=(source,), output=dest)


_mask_for_size = mask_for_size

_sign_extend = sign_extend

_opcode_text = opcode_text


def _is_const(varnode: Varnode) -> bool:
    space = varnode.space.value if isinstance(varnode.space, PcodeSpace) else varnode.space
    return space == PcodeSpace.CONST.value


def _is_const_value(varnode: Varnode, value: int) -> bool:
    if not _is_const(varnode):
        return False
    return varnode.offset == (value & _mask_for_size(varnode.size))


def _is_unique(varnode: Varnode | None) -> bool:
    if varnode is None:
        return False
    space = varnode.space.value if isinstance(varnode.space, PcodeSpace) else varnode.space
    return space == PcodeSpace.UNIQUE.value
