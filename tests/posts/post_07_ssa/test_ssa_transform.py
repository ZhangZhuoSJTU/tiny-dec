from __future__ import annotations

from tiny_dec.analysis.dataflow import (
    BlockDataflowFacts,
    FunctionDataflowFacts,
    ProgramDataflowFacts,
    RegisterState,
)
from tiny_dec.analysis.simplify import (
    CanonicalBlock,
    CanonicalFunctionIR,
    CanonicalInstruction,
    CanonicalProgramIR,
)
from tiny_dec.analysis.ssa import construct_function_ssa, construct_program_ssa, normalize_function_ssa
from tiny_dec.analysis.ssa.models import (
    MemoryVersion,
    SSABlock,
    SSAFunctionIR,
    SSAInstruction,
    SSAMemoryPhiInput,
    SSAMemoryPhiNode,
    SSAName,
    SSANameKind,
    SSAOp,
    SSAPhiInput,
    SSAPhiNode,
)
from tiny_dec.decode import decode_rv32i
from tiny_dec.disasm.models import BlockEdge, BlockEdgeKind, BlockTerminator
from tiny_dec.ir.pcode import (
    PcodeOp,
    PcodeOpcode,
    const_varnode,
    register_varnode,
    unique_varnode,
)
from tiny_dec.loader import ExternalFunction


def _instruction(address: int, *ops: PcodeOp) -> CanonicalInstruction:
    return CanonicalInstruction(
        instruction=decode_rv32i(0x00000013, address),
        ops=ops,
    )


def _block(
    start: int,
    *instructions: CanonicalInstruction,
    successors: tuple[BlockEdge, ...] = (),
    terminator: BlockTerminator = BlockTerminator.LINEAR,
) -> CanonicalBlock:
    return CanonicalBlock(
        start=start,
        instructions=instructions,
        successors=successors,
        terminator=terminator,
    )


def _canonical_function(
    entry: int,
    blocks: tuple[CanonicalBlock, ...],
    *,
    name: str = "main",
) -> CanonicalFunctionIR:
    instruction_index = {
        instruction.address: instruction
        for block in blocks
        for instruction in block.instructions
    }
    return_blocks = tuple(
        block.start for block in blocks if block.terminator == BlockTerminator.RETURN
    )
    return CanonicalFunctionIR(
        entry=entry,
        name=name,
        blocks={block.start: block for block in blocks},
        discovery_order=tuple(block.start for block in blocks),
        instruction_index=instruction_index,
        return_blocks=return_blocks,
    )


def _dataflow_function(
    entry: int,
    blocks: tuple[CanonicalBlock, ...],
    *,
    reachable_blocks: tuple[int, ...] | None = None,
    name: str = "main",
) -> FunctionDataflowFacts:
    canonical = _canonical_function(entry, blocks, name=name)
    reachable = set(reachable_blocks or tuple(block.start for block in blocks))
    dataflow_blocks = {
        block.start: BlockDataflowFacts(
            start=block.start,
            in_state=RegisterState() if block.start in reachable else RegisterState.unreachable(),
            out_state=RegisterState() if block.start in reachable else RegisterState.unreachable(),
        )
        for block in blocks
    }
    return FunctionDataflowFacts(function=canonical, blocks=dataflow_blocks)


def _dataflow_program(
    root_entry: int,
    functions: tuple[FunctionDataflowFacts, ...],
) -> ProgramDataflowFacts:
    canonical_program = CanonicalProgramIR(
        root_entry=root_entry,
        functions={function.function.entry: function.function for function in functions},
        discovery_order=tuple(function.function.entry for function in functions),
        externals=(
            ExternalFunction(
                name="puts",
                plt_address=None,
                got_address=None,
                symbol_address=0x5000,
            ),
        ),
    )
    return ProgramDataflowFacts(
        program=canonical_program,
        functions={function.function.entry: function for function in functions},
        pending_entries=(0x4000,),
    )


def test_construct_function_ssa_renames_straight_line_registers_and_uniques() -> None:
    block = _block(
        0x1000,
        _instruction(
            0x1000,
            PcodeOp(
                opcode=PcodeOpcode.INT_ADD,
                inputs=(register_varnode(2), const_varnode(1)),
                output=register_varnode(2),
            ),
        ),
        _instruction(
            0x1004,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(register_varnode(2),),
                output=unique_varnode(0),
            ),
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(unique_varnode(0),),
                output=register_varnode(3),
            ),
        ),
        terminator=BlockTerminator.RETURN,
    )
    function = _dataflow_function(0x1000, (block,))

    ssa = construct_function_ssa(function)

    assert [name.to_pretty() for name in ssa.live_ins] == ["x2_0:4"]
    assert ssa.immediate_dominators == {0x1000: None}
    assert ssa.dominance_frontiers == {0x1000: ()}
    assert ssa.blocks[0x1000].phis == ()
    assert [op.to_pretty() for op in ssa.blocks[0x1000].instructions[0].ops] == [
        "INT_ADD x2_1:4 <- x2_0:4, const[0x1:4]"
    ]
    assert [op.to_pretty() for op in ssa.blocks[0x1000].instructions[1].ops] == [
        "COPY u0_1:4 <- x2_1:4",
        "COPY x3_1:4 <- u0_1:4",
    ]


def test_construct_function_ssa_synthesizes_call_return_defs() -> None:
    block = _block(
        0x1000,
        _instruction(
            0x1000,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(const_varnode(7),),
                output=register_varnode(10),
            ),
        ),
        _instruction(
            0x1004,
            PcodeOp(
                opcode=PcodeOpcode.CALL,
                inputs=(const_varnode(0x1100),),
            ),
        ),
        _instruction(
            0x1008,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(register_varnode(10),),
                output=register_varnode(11),
            ),
        ),
        terminator=BlockTerminator.RETURN,
    )
    function = _dataflow_function(0x1000, (block,))

    ssa = construct_function_ssa(function)

    call_ops = [op.to_pretty() for op in ssa.blocks[0x1000].instructions[1].ops]
    assert call_ops[0] == "CALL const[0x1100:4] [m0 -> m1]"
    # CALL_RETURN for a0 and a1 (return registers)
    call_return_ops = [op for op in call_ops if op.startswith("CALL_RETURN")]
    assert len(call_return_ops) == 2
    assert any("x10_" in op for op in call_return_ops)
    assert any("x11_" in op for op in call_return_ops)
    # CALL_CLOBBER for all other caller-saved registers (ra, t0-t2, a2-a7, t3-t6)
    call_clobber_ops = [op for op in call_ops if op.startswith("CALL_CLOBBER")]
    assert len(call_clobber_ops) == 14
    # After the call, COPY reads the clobbered x10
    post_call_ops = [op.to_pretty() for op in ssa.blocks[0x1000].instructions[2].ops]
    assert len(post_call_ops) == 1
    assert post_call_ops[0].startswith("COPY x11_")
    assert "x10_" in post_call_ops[0]


def test_construct_function_ssa_inserts_phi_at_diamond_join() -> None:
    entry = _block(
        0x1000,
        _instruction(0x1000),
        successors=(
            BlockEdge(BlockEdgeKind.BRANCH_TAKEN, 0x1010),
            BlockEdge(BlockEdgeKind.FALLTHROUGH, 0x1020),
        ),
        terminator=BlockTerminator.BRANCH,
    )
    left = _block(
        0x1010,
        _instruction(
            0x1010,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(const_varnode(1),),
                output=register_varnode(10),
            ),
        ),
        successors=(BlockEdge(BlockEdgeKind.JUMP, 0x1030),),
        terminator=BlockTerminator.JUMP,
    )
    right = _block(
        0x1020,
        _instruction(
            0x1020,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(const_varnode(2),),
                output=register_varnode(10),
            ),
        ),
        successors=(BlockEdge(BlockEdgeKind.JUMP, 0x1030),),
        terminator=BlockTerminator.JUMP,
    )
    join = _block(
        0x1030,
        _instruction(
            0x1030,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(register_varnode(10),),
                output=register_varnode(11),
            ),
        ),
        terminator=BlockTerminator.RETURN,
    )
    function = _dataflow_function(0x1000, (entry, left, right, join))

    ssa = construct_function_ssa(function)
    phi = ssa.blocks[0x1030].phis[0]

    assert ssa.immediate_dominators == {
        0x1000: None,
        0x1010: 0x1000,
        0x1020: 0x1000,
        0x1030: 0x1000,
    }
    assert ssa.dominance_frontiers[0x1010] == (0x1030,)
    assert ssa.dominance_frontiers[0x1020] == (0x1030,)
    assert phi.to_pretty() == "PHI x10_3:4 <- 0x1010:x10_1:4, 0x1020:x10_2:4"
    assert [op.to_pretty() for op in ssa.blocks[0x1030].instructions[0].ops] == [
        "COPY x11_1:4 <- x10_3:4"
    ]


def test_construct_function_ssa_inserts_loop_header_phi() -> None:
    entry = _block(
        0x1000,
        _instruction(
            0x1000,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(const_varnode(0),),
                output=register_varnode(10),
            ),
        ),
        successors=(BlockEdge(BlockEdgeKind.JUMP, 0x1010),),
        terminator=BlockTerminator.JUMP,
    )
    header = _block(
        0x1010,
        _instruction(
            0x1010,
            PcodeOp(
                opcode=PcodeOpcode.INT_LESS,
                inputs=(register_varnode(10), const_varnode(3)),
                output=unique_varnode(0, size=1),
            ),
        ),
        successors=(
            BlockEdge(BlockEdgeKind.BRANCH_TAKEN, 0x1030),
            BlockEdge(BlockEdgeKind.FALLTHROUGH, 0x1020),
        ),
        terminator=BlockTerminator.BRANCH,
    )
    body = _block(
        0x1020,
        _instruction(
            0x1020,
            PcodeOp(
                opcode=PcodeOpcode.INT_ADD,
                inputs=(register_varnode(10), const_varnode(1)),
                output=register_varnode(10),
            ),
        ),
        successors=(BlockEdge(BlockEdgeKind.JUMP, 0x1010),),
        terminator=BlockTerminator.JUMP,
    )
    exit_block = _block(
        0x1030,
        _instruction(
            0x1030,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(register_varnode(10),),
                output=register_varnode(11),
            ),
        ),
        terminator=BlockTerminator.RETURN,
    )
    function = _dataflow_function(0x1000, (entry, header, body, exit_block))

    ssa = construct_function_ssa(function)
    phi = ssa.blocks[0x1010].phis[0]

    assert phi.to_pretty() == "PHI x10_2:4 <- 0x1000:x10_1:4, 0x1020:x10_3:4"
    assert ssa.dominance_frontiers[0x1010] == (0x1010,)
    assert ssa.dominance_frontiers[0x1020] == (0x1010,)
    assert [op.to_pretty() for op in ssa.blocks[0x1030].instructions[0].ops] == [
        "COPY x11_1:4 <- x10_2:4"
    ]


def test_construct_function_ssa_threads_coarse_memory_versions_through_store_and_load() -> None:
    block = _block(
        0x1000,
        _instruction(
            0x1000,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(const_varnode(0x2000),),
                output=unique_varnode(0),
            ),
            PcodeOp(
                opcode=PcodeOpcode.STORE,
                inputs=(unique_varnode(0), const_varnode(7)),
            ),
        ),
        _instruction(
            0x1004,
            PcodeOp(
                opcode=PcodeOpcode.LOAD,
                inputs=(unique_varnode(0),),
                output=register_varnode(10),
            ),
        ),
        terminator=BlockTerminator.RETURN,
    )
    function = _dataflow_function(0x1000, (block,))

    ssa = construct_function_ssa(function)

    assert ssa.memory_live_in is not None
    assert ssa.memory_live_in.to_pretty() == "m0"
    assert ssa.blocks[0x1000].memory_phi is None
    assert [op.to_pretty() for op in ssa.blocks[0x1000].instructions[0].ops] == [
        "COPY u0_1:4 <- const[0x2000:4]",
        "STORE u0_1:4, const[0x7:4] [m0 -> m1]",
    ]
    assert [op.to_pretty() for op in ssa.blocks[0x1000].instructions[1].ops] == [
        "LOAD x10_1:4 <- u0_0:4 [m1]"
    ]


def test_construct_function_ssa_inserts_memory_phi_at_join() -> None:
    entry = _block(
        0x1000,
        _instruction(
            0x1000,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(const_varnode(0x2000),),
                output=unique_varnode(0),
            ),
        ),
        successors=(
            BlockEdge(BlockEdgeKind.BRANCH_TAKEN, 0x1010),
            BlockEdge(BlockEdgeKind.FALLTHROUGH, 0x1020),
        ),
        terminator=BlockTerminator.BRANCH,
    )
    left = _block(
        0x1010,
        _instruction(
            0x1010,
            PcodeOp(
                opcode=PcodeOpcode.STORE,
                inputs=(unique_varnode(0), const_varnode(1)),
            ),
        ),
        successors=(BlockEdge(BlockEdgeKind.JUMP, 0x1030),),
        terminator=BlockTerminator.JUMP,
    )
    right = _block(
        0x1020,
        _instruction(0x1020),
        successors=(BlockEdge(BlockEdgeKind.JUMP, 0x1030),),
        terminator=BlockTerminator.JUMP,
    )
    join = _block(
        0x1030,
        _instruction(
            0x1030,
            PcodeOp(
                opcode=PcodeOpcode.LOAD,
                inputs=(unique_varnode(0),),
                output=register_varnode(10),
            ),
        ),
        terminator=BlockTerminator.RETURN,
    )
    function = _dataflow_function(0x1000, (entry, left, right, join))

    ssa = construct_function_ssa(function)

    memory_phi = ssa.blocks[0x1030].memory_phi
    assert memory_phi is not None
    assert memory_phi.to_pretty() == "MEM_PHI m2 <- 0x1010:m1, 0x1020:m0"
    assert [op.to_pretty() for op in ssa.blocks[0x1010].instructions[0].ops] == [
        "STORE u0_0:4, const[0x1:4] [m0 -> m1]"
    ]
    assert [op.to_pretty() for op in ssa.blocks[0x1030].instructions[0].ops] == [
        "LOAD x10_1:4 <- u0_0:4 [m2]"
    ]


def test_construct_function_ssa_records_unreachable_blocks() -> None:
    entry = _block(
        0x1000,
        _instruction(0x1000),
        terminator=BlockTerminator.RETURN,
    )
    dead = _block(
        0x2000,
        _instruction(0x2000),
        terminator=BlockTerminator.RETURN,
    )
    function = _dataflow_function(0x1000, (entry, dead), reachable_blocks=(0x1000,))

    ssa = construct_function_ssa(function)

    assert tuple(ssa.blocks) == (0x1000,)
    assert ssa.unreachable_blocks == (0x2000,)


def test_construct_function_ssa_normalizes_identity_loop_phi() -> None:
    entry = _block(
        0x1000,
        _instruction(
            0x1000,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(const_varnode(7),),
                output=register_varnode(8),
            ),
        ),
        successors=(BlockEdge(BlockEdgeKind.JUMP, 0x1010),),
        terminator=BlockTerminator.JUMP,
    )
    header = _block(
        0x1010,
        _instruction(
            0x1010,
            PcodeOp(
                opcode=PcodeOpcode.CALL,
                inputs=(const_varnode(0x1100),),
            ),
        ),
        _instruction(0x1014),
        successors=(
            BlockEdge(BlockEdgeKind.BRANCH_TAKEN, 0x1030),
            BlockEdge(BlockEdgeKind.FALLTHROUGH, 0x1020),
        ),
        terminator=BlockTerminator.BRANCH,
    )
    body = _block(
        0x1020,
        _instruction(
            0x1020,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(register_varnode(8),),
                output=register_varnode(8),
            ),
        ),
        successors=(BlockEdge(BlockEdgeKind.JUMP, 0x1010),),
        terminator=BlockTerminator.JUMP,
    )
    exit_block = _block(
        0x1030,
        _instruction(0x1030),
        terminator=BlockTerminator.RETURN,
    )
    function = _dataflow_function(0x1000, (entry, header, body, exit_block))

    ssa = construct_function_ssa(function)

    assert ssa.blocks[0x1010].phis == ()
    assert ssa.blocks[0x1020].instructions[0].ops == ()
    header_ops = [op.to_pretty() for op in ssa.blocks[0x1010].instructions[0].ops]
    assert header_ops[0] == "CALL const[0x1100:4] [m1 -> m2]"
    assert "CALL_RETURN x10_1:4 <- const[0x1010:4]" in header_ops
    assert "CALL_RETURN x11_1:4 <- const[0x1010:4]" in header_ops


def test_construct_function_ssa_rewrites_later_uses_of_trivial_register_forwarding_copy() -> None:
    block = _block(
        0x1000,
        _instruction(
            0x1000,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(register_varnode(10),),
                output=register_varnode(12),
            ),
        ),
        _instruction(
            0x1004,
            PcodeOp(
                opcode=PcodeOpcode.INT_ADD,
                inputs=(register_varnode(12), const_varnode(1)),
                output=register_varnode(13),
            ),
        ),
        terminator=BlockTerminator.RETURN,
    )
    function = _dataflow_function(0x1000, (block,))

    ssa = construct_function_ssa(function)

    assert [op.to_pretty() for op in ssa.blocks[0x1000].instructions[0].ops] == [
        "COPY x12_1:4 <- x10_0:4"
    ]
    assert [op.to_pretty() for op in ssa.blocks[0x1000].instructions[1].ops] == [
        "INT_ADD x13_1:4 <- x10_0:4, const[0x1:4]"
    ]


def test_normalize_function_ssa_elides_trivial_register_and_memory_phis() -> None:
    entry_instruction = _instruction(0x1000)
    header_instruction = _instruction(0x1010)
    dataflow = _dataflow_function(
        0x1000,
        (
            _block(
                0x1000,
                entry_instruction,
                successors=(BlockEdge(BlockEdgeKind.JUMP, 0x1010),),
                terminator=BlockTerminator.JUMP,
            ),
            _block(
                0x1010,
                header_instruction,
                terminator=BlockTerminator.RETURN,
            ),
        ),
    )
    x10_live_in = SSAName(SSANameKind.REGISTER, 10, 0, 4)
    x10_phi = SSAName(SSANameKind.REGISTER, 10, 1, 4)
    normalized = normalize_function_ssa(
        SSAFunctionIR(
            dataflow=dataflow,
            blocks={
                0x1000: SSABlock(
                    start=0x1000,
                    phis=(),
                    instructions=(SSAInstruction(entry_instruction.instruction, ()),),
                    successors=(BlockEdge(BlockEdgeKind.JUMP, 0x1010),),
                    terminator=BlockTerminator.JUMP,
                ),
                0x1010: SSABlock(
                    start=0x1010,
                    phis=(
                        SSAPhiNode(
                            output=x10_phi,
                            inputs=(
                                SSAPhiInput(predecessor=0x1000, value=x10_live_in),
                                SSAPhiInput(predecessor=0x1010, value=x10_phi),
                            ),
                        ),
                    ),
                    memory_phi=SSAMemoryPhiNode(
                        output=MemoryVersion(1),
                        inputs=(
                            SSAMemoryPhiInput(predecessor=0x1000, value=MemoryVersion(0)),
                            SSAMemoryPhiInput(predecessor=0x1010, value=MemoryVersion(1)),
                        ),
                    ),
                    instructions=(
                        SSAInstruction(
                            header_instruction.instruction,
                            (
                                SSAOp(
                                    opcode=PcodeOpcode.COPY,
                                    inputs=(x10_phi,),
                                    output=SSAName(SSANameKind.REGISTER, 11, 1, 4),
                                ),
                                SSAOp(
                                    opcode=PcodeOpcode.LOAD,
                                    inputs=(const_varnode(0x2000),),
                                    output=SSAName(SSANameKind.REGISTER, 12, 1, 4),
                                    memory_before=MemoryVersion(1),
                                ),
                            ),
                        ),
                    ),
                    terminator=BlockTerminator.RETURN,
                ),
            },
            immediate_dominators={0x1000: None, 0x1010: 0x1000},
            dominance_frontiers={0x1000: (), 0x1010: ()},
            live_ins=(x10_live_in,),
            memory_live_in=MemoryVersion(0),
            unreachable_blocks=(),
        )
    )

    assert normalized.blocks[0x1010].phis == ()
    assert normalized.blocks[0x1010].memory_phi is None
    assert [op.to_pretty() for op in normalized.blocks[0x1010].instructions[0].ops] == [
        "COPY x11_1:4 <- x10_0:4",
        "LOAD x12_1:4 <- const[0x2000:4] [m0]",
    ]


def test_construct_program_ssa_preserves_program_order_and_queue_state() -> None:
    first = _dataflow_function(
        0x1000,
        (
            _block(
                0x1000,
                _instruction(0x1000),
                terminator=BlockTerminator.RETURN,
            ),
        ),
        name="main",
    )
    second = _dataflow_function(
        0x1100,
        (
            _block(
                0x1100,
                _instruction(0x1100),
                terminator=BlockTerminator.RETURN,
            ),
        ),
        name="helper",
    )
    program = _dataflow_program(0x1000, (first, second))

    ssa_program = construct_program_ssa(program)

    assert ssa_program.ordered_function_entries() == (0x1000, 0x1100)
    assert ssa_program.dataflow.pending_entries == (0x4000,)
