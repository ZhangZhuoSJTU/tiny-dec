from __future__ import annotations

from tiny_dec.decode import Mnemonic, RV32IInstruction, decode_rv32i
from tiny_dec.disasm.models import (
    BasicBlock,
    BlockEdge,
    BlockEdgeKind,
    BlockInstruction,
    BlockTerminator,
    DisasmFunction,
)
from tiny_dec.ir.lift_rv32i import lift_instruction
from tiny_dec.ir.pcode import PcodeOp, PcodeOpcode, PcodeSpace
from tiny_dec.loader import AddressNotMappedError, ProgramView


def disassemble_function(view: ProgramView, entry: int) -> DisasmFunction:
    """Build a deterministic intra-procedural disassembly from one function entry.

    This is a simplified recursive descent that does not retroactively split
    already-completed blocks when a new leader is discovered mid-block.  A
    production decompiler would need a second pass or incremental splitting.
    """
    known_leaders = {entry}
    scheduled = {entry}
    worklist = [entry]
    blocks: dict[int, BasicBlock] = {}
    discovery_order: list[int] = []

    while worklist:
        block_start = worklist.pop()
        if block_start in blocks:
            continue

        discovery_order.append(block_start)
        block = _decode_block(view, block_start, known_leaders)
        blocks[block_start] = block

        for successor in block.successors:
            known_leaders.add(successor.target)

        for successor in reversed(block.successors):
            if successor.target in scheduled:
                continue
            worklist.append(successor.target)
            scheduled.add(successor.target)

    return DisasmFunction(
        entry=entry,
        blocks=blocks,
        discovery_order=tuple(discovery_order),
    )


def _decode_block(
    view: ProgramView,
    start: int,
    known_leaders: set[int],
) -> BasicBlock:
    instructions: list[BlockInstruction] = []
    call_targets: list[int] = []
    has_indirect_call = False
    address = start

    while True:
        if address != start and address in known_leaders:
            # Truncated: a previously-discovered leader falls mid-block.
            # No retroactive split — emit FALLTHROUGH to the existing leader.
            return BasicBlock(
                start=start,
                instructions=tuple(instructions),
                successors=(BlockEdge(BlockEdgeKind.FALLTHROUGH, address),),
                terminator=BlockTerminator.LINEAR,
                call_targets=tuple(call_targets),
                has_indirect_call=has_indirect_call,
            )

        word = view.read_u32(address)
        instruction = decode_rv32i(word, address)
        lifted = BlockInstruction(
            instruction=instruction,
            pcode_ops=tuple(lift_instruction(instruction)),
        )
        instructions.append(lifted)

        target = _direct_call_target(lifted)
        if target is not None and target not in call_targets:
            call_targets.append(target)
        has_indirect_call = has_indirect_call or _has_indirect_call(lifted)

        kind = _classify_terminator(lifted)
        if kind == BlockTerminator.BRANCH:
            target = _direct_terminator_target(lifted)
            fallthrough = address + instruction.size
            known_leaders.update({target, fallthrough})
            return BasicBlock(
                start=start,
                instructions=tuple(instructions),
                successors=(
                    BlockEdge(BlockEdgeKind.BRANCH_TAKEN, target),
                    BlockEdge(BlockEdgeKind.FALLTHROUGH, fallthrough),
                ),
                terminator=BlockTerminator.BRANCH,
                call_targets=tuple(call_targets),
                has_indirect_call=has_indirect_call,
            )

        if kind == BlockTerminator.JUMP:
            target = _direct_terminator_target(lifted)
            known_leaders.add(target)
            return BasicBlock(
                start=start,
                instructions=tuple(instructions),
                successors=(BlockEdge(BlockEdgeKind.JUMP, target),),
                terminator=BlockTerminator.JUMP,
                call_targets=tuple(call_targets),
                has_indirect_call=has_indirect_call,
            )

        if kind in {
            BlockTerminator.INDIRECT_JUMP,
            BlockTerminator.RETURN,
            BlockTerminator.STOP,
        }:
            return BasicBlock(
                start=start,
                instructions=tuple(instructions),
                successors=(),
                terminator=kind,
                call_targets=tuple(call_targets),
                has_indirect_call=has_indirect_call,
            )

        address += instruction.size


def _classify_terminator(lifted: BlockInstruction) -> BlockTerminator | None:
    last_opcode = _last_opcode_text(lifted.pcode_ops)

    if last_opcode == PcodeOpcode.CBRANCH.value:
        return BlockTerminator.BRANCH
    if last_opcode == PcodeOpcode.BRANCH.value:
        return BlockTerminator.JUMP
    if last_opcode == PcodeOpcode.BRANCHIND.value:
        return BlockTerminator.INDIRECT_JUMP
    if last_opcode == PcodeOpcode.RETURN.value:
        return BlockTerminator.RETURN
    if _mnemonic_text(lifted.instruction) in _CALL_LIKE_MNEMONICS:
        return None
    if _has_opcode(lifted.pcode_ops, PcodeOpcode.TRAP):
        return BlockTerminator.STOP
    if _mnemonic_text(lifted.instruction) in _STOP_MNEMONICS:
        return BlockTerminator.STOP
    return None


def _direct_call_target(lifted: BlockInstruction) -> int | None:
    for op in lifted.pcode_ops:
        if _opcode_text(op) != PcodeOpcode.CALL.value:
            continue
        return _const_target(op)
    return None


def _has_indirect_call(lifted: BlockInstruction) -> bool:
    return _has_opcode(lifted.pcode_ops, PcodeOpcode.CALLIND)


def _direct_terminator_target(lifted: BlockInstruction) -> int:
    if not lifted.pcode_ops:
        raise AddressNotMappedError(
            f"expected direct control-flow target at {lifted.address:#x}"
        )
    return _const_target(lifted.pcode_ops[-1])


def _const_target(op: PcodeOp) -> int:
    if not op.inputs:
        raise AddressNotMappedError("expected direct control-flow target input")

    target = op.inputs[0]
    space_name = target.space.value if isinstance(target.space, PcodeSpace) else target.space
    if space_name != PcodeSpace.CONST.value:
        raise AddressNotMappedError("expected direct control-flow target to be constant")
    return target.offset


def _has_opcode(ops: tuple[PcodeOp, ...], opcode: PcodeOpcode) -> bool:
    expected = opcode.value
    return any(_opcode_text(op) == expected for op in ops)


def _last_opcode_text(ops: tuple[PcodeOp, ...]) -> str | None:
    if not ops:
        return None
    return _opcode_text(ops[-1])


def _opcode_text(op: PcodeOp) -> str:
    opcode = op.opcode
    if isinstance(opcode, PcodeOpcode):
        return opcode.value
    return opcode


def _mnemonic_text(instruction: RV32IInstruction) -> str:
    mnemonic = instruction.mnemonic
    if isinstance(mnemonic, Mnemonic):
        return mnemonic.value
    return mnemonic


_STOP_MNEMONICS = {
    Mnemonic.EBREAK.value,
    Mnemonic.ILLEGAL.value,
}

_CALL_LIKE_MNEMONICS = {
    Mnemonic.ECALL.value,
}
