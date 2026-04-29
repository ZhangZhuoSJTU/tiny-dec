from __future__ import annotations

from tiny_dec.analysis.dataflow import (
    RecoveredTargetKind,
    analyze_function_dataflow,
    analyze_program_dataflow,
)
from tiny_dec.analysis.simplify import (
    CanonicalBlock,
    CanonicalFunctionIR,
    CanonicalInstruction,
    CanonicalProgramIR,
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
    call_targets: tuple[int, ...] = (),
    has_indirect_call: bool = False,
) -> CanonicalBlock:
    return CanonicalBlock(
        start=start,
        instructions=instructions,
        successors=successors,
        terminator=terminator,
        call_targets=call_targets,
        has_indirect_call=has_indirect_call,
    )


def _function(
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
    direct_callees = tuple(
        dict.fromkeys(target for block in blocks for target in block.call_targets)
    )
    return CanonicalFunctionIR(
        entry=entry,
        name=name,
        blocks={block.start: block for block in blocks},
        discovery_order=tuple(block.start for block in blocks),
        instruction_index=instruction_index,
        return_blocks=return_blocks,
        direct_callees=direct_callees,
    )


def _program(
    root_entry: int,
    functions: tuple[CanonicalFunctionIR, ...],
    *,
    externals: tuple[ExternalFunction, ...] = (),
) -> CanonicalProgramIR:
    return CanonicalProgramIR(
        root_entry=root_entry,
        functions={function.entry: function for function in functions},
        discovery_order=tuple(function.entry for function in functions),
        externals=externals,
    )


def test_analyze_function_dataflow_merges_constants_at_block_joins() -> None:
    entry = _block(
        0x1000,
        _instruction(
            0x1000,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(const_varnode(1),),
                output=register_varnode(1),
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
                opcode=PcodeOpcode.COPY,
                inputs=(const_varnode(7),),
                output=register_varnode(2),
            ),
        ),
        _instruction(
            0x1014,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(const_varnode(9),),
                output=register_varnode(3),
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
                inputs=(const_varnode(7),),
                output=register_varnode(2),
            ),
        ),
        _instruction(
            0x1024,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(const_varnode(10),),
                output=register_varnode(3),
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
                inputs=(register_varnode(2),),
                output=register_varnode(4),
            ),
        ),
        terminator=BlockTerminator.RETURN,
    )
    function = _function(0x1000, (entry, left, right, join))

    facts = analyze_function_dataflow(function)

    assert facts.blocks[0x1000].in_state.known_registers == {}
    assert facts.blocks[0x1000].out_state.known_registers == {1: 1}
    assert facts.blocks[0x1010].in_state.known_registers == {1: 1}
    assert facts.blocks[0x1020].in_state.known_registers == {1: 1}
    assert facts.blocks[0x1030].in_state.known_registers == {1: 1, 2: 7}
    assert 3 not in facts.blocks[0x1030].in_state.known_registers
    assert facts.blocks[0x1030].out_state.known_registers == {1: 1, 2: 7, 4: 7}


def test_analyze_function_dataflow_kills_load_results_and_ignores_x0_writes() -> None:
    block = _block(
        0x1000,
        _instruction(
            0x1000,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(const_varnode(0x20),),
                output=register_varnode(5),
            ),
        ),
        _instruction(
            0x1004,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(const_varnode(1),),
                output=register_varnode(6),
            ),
        ),
        _instruction(
            0x1008,
            PcodeOp(
                opcode=PcodeOpcode.LOAD,
                inputs=(register_varnode(5),),
                output=register_varnode(6),
            ),
        ),
        _instruction(
            0x100C,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(const_varnode(9),),
                output=register_varnode(0),
            ),
        ),
        _instruction(
            0x1010,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(register_varnode(0),),
                output=register_varnode(7),
            ),
        ),
        terminator=BlockTerminator.RETURN,
    )
    function = _function(0x1000, (block,))

    facts = analyze_function_dataflow(function)

    assert facts.blocks[0x1000].in_state.known_registers == {}
    assert facts.blocks[0x1000].out_state.known_registers == {5: 0x20, 7: 0}


def test_analyze_function_dataflow_recovers_constant_branchind_targets() -> None:
    block = _block(
        0x1000,
        _instruction(
            0x1000,
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(const_varnode(0x1200),),
                output=unique_varnode(0),
            ),
            PcodeOp(
                opcode=PcodeOpcode.BRANCHIND,
                inputs=(unique_varnode(0),),
            ),
        ),
        terminator=BlockTerminator.INDIRECT_JUMP,
    )
    function = _function(0x1000, (block,))

    facts = analyze_function_dataflow(function)
    recovered = facts.recovered_targets

    assert len(recovered) == 1
    assert recovered[0].instruction_address == 0x1000
    assert recovered[0].block_start == 0x1000
    assert recovered[0].kind == RecoveredTargetKind.BRANCH
    assert recovered[0].target == 0x1200


def test_analyze_program_dataflow_derives_pending_and_invalidated_entries() -> None:
    pending_function = _function(
        0x1000,
        (
            _block(
                0x1000,
                _instruction(
                    0x1000,
                    PcodeOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(const_varnode(0x4000),),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.CALLIND,
                        inputs=(unique_varnode(0),),
                    ),
                ),
                terminator=BlockTerminator.RETURN,
                has_indirect_call=True,
            ),
        ),
        name="root",
    )
    invalidated_function = _function(
        0x2000,
        (
            _block(
                0x2000,
                _instruction(
                    0x2000,
                    PcodeOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(const_varnode(0x2300),),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.BRANCHIND,
                        inputs=(unique_varnode(0),),
                    ),
                ),
                terminator=BlockTerminator.INDIRECT_JUMP,
            ),
        ),
        name="switcher",
    )
    known_internal_target = _function(
        0x3000,
        (
            _block(
                0x3000,
                _instruction(
                    0x3000,
                    PcodeOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(const_varnode(0x2000),),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.CALLIND,
                        inputs=(unique_varnode(0),),
                    ),
                ),
                terminator=BlockTerminator.RETURN,
                has_indirect_call=True,
            ),
        ),
        name="known-call",
    )
    known_external_target = _function(
        0x3500,
        (
            _block(
                0x3500,
                _instruction(
                    0x3500,
                    PcodeOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(const_varnode(0x5000),),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.CALLIND,
                        inputs=(unique_varnode(0),),
                    ),
                ),
                terminator=BlockTerminator.RETURN,
                has_indirect_call=True,
            ),
        ),
        name="external-call",
    )
    program = _program(
        0x1000,
        (
            pending_function,
            invalidated_function,
            known_internal_target,
            known_external_target,
        ),
        externals=(
            ExternalFunction(
                name="puts",
                plt_address=None,
                got_address=None,
                symbol_address=0x5000,
            ),
        ),
    )

    facts = analyze_program_dataflow(program)

    assert facts.pending_entries == (0x4000,)
    assert facts.invalidated_entries == (0x2000,)
    assert facts.functions[0x1000].recovered_targets[0].target == 0x4000
    assert facts.functions[0x2000].recovered_targets[0].target == 0x2300
