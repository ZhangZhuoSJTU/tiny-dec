from __future__ import annotations

from tiny_dec.analysis.calls import analyze_program_calls
from tiny_dec.analysis.dataflow import (
    BlockDataflowFacts,
    FunctionDataflowFacts,
    ProgramDataflowFacts,
    RegisterState,
)
from tiny_dec.analysis.memory import analyze_program_memory
from tiny_dec.analysis.simplify import (
    CanonicalBlock,
    CanonicalFunctionIR,
    CanonicalInstruction,
    CanonicalProgramIR,
)
from tiny_dec.analysis.ssa import construct_program_ssa
from tiny_dec.analysis.stack import analyze_program_stack
from tiny_dec.analysis.types import analyze_program_scalar_types
from tiny_dec.analysis.types.models import ScalarTypeKind
from tiny_dec.decode import decode_rv32i
from tiny_dec.disasm.models import BlockEdge, BlockEdgeKind, BlockTerminator
from tiny_dec.ir.pcode import (
    PcodeOp,
    PcodeOpcode,
    const_varnode,
    register_varnode,
    unique_varnode,
)


def _instruction(address: int, *ops: PcodeOp) -> CanonicalInstruction:
    return CanonicalInstruction(
        instruction=decode_rv32i(0x00000013, address),
        ops=ops,
    )


def _block(
    start: int,
    *instructions: CanonicalInstruction,
    successors: tuple[BlockEdge, ...] = (),
    terminator: BlockTerminator = BlockTerminator.RETURN,
) -> CanonicalBlock:
    return CanonicalBlock(
        start=start,
        instructions=instructions,
        successors=successors,
        terminator=terminator,
    )


def _function(
    entry: int,
    blocks: tuple[CanonicalBlock, ...],
    *,
    name: str = "main",
) -> FunctionDataflowFacts:
    instruction_index = {
        instruction.address: instruction
        for block in blocks
        for instruction in block.instructions
    }
    return_blocks = tuple(
        block.start for block in blocks if block.terminator == BlockTerminator.RETURN
    )
    canonical = CanonicalFunctionIR(
        entry=entry,
        name=name,
        blocks={block.start: block for block in blocks},
        discovery_order=tuple(block.start for block in blocks),
        instruction_index=instruction_index,
        return_blocks=return_blocks,
    )
    return FunctionDataflowFacts(
        function=canonical,
        blocks={
            block.start: BlockDataflowFacts(
                start=block.start,
                in_state=RegisterState(),
                out_state=RegisterState(),
            )
            for block in blocks
        },
    )


def _calls_program(
    root_entry: int,
    functions: tuple[FunctionDataflowFacts, ...],
    *,
    pending_entries: tuple[int, ...] = (),
    invalidated_entries: tuple[int, ...] = (),
):
    canonical_program = CanonicalProgramIR(
        root_entry=root_entry,
        functions={function.function.entry: function.function for function in functions},
        discovery_order=tuple(function.function.entry for function in functions),
    )
    dataflow_program = ProgramDataflowFacts(
        program=canonical_program,
        functions={function.function.entry: function for function in functions},
        pending_entries=pending_entries,
        invalidated_entries=invalidated_entries,
    )
    return analyze_program_calls(construct_program_ssa(dataflow_program))


def test_analyze_program_scalar_types_recovers_pointer_int_bool_and_word_facts() -> None:
    function = _function(
        0x1000,
        (
            _block(
                0x1000,
                _instruction(
                    0x1000,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(2), const_varnode(-16)),
                        output=register_varnode(2),
                    ),
                ),
                _instruction(
                    0x1004,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(2), const_varnode(0)),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.STORE,
                        inputs=(unique_varnode(0), register_varnode(10)),
                    ),
                ),
                _instruction(
                    0x1008,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(2), const_varnode(0)),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.LOAD,
                        inputs=(unique_varnode(0),),
                        output=register_varnode(10),
                    ),
                ),
                _instruction(
                    0x100C,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(10), const_varnode(4)),
                        output=register_varnode(12),
                    ),
                ),
                _instruction(
                    0x1010,
                    PcodeOp(
                        opcode=PcodeOpcode.LOAD,
                        inputs=(register_varnode(12),),
                        output=register_varnode(13),
                    ),
                ),
                _instruction(
                    0x1014,
                    PcodeOp(
                        opcode=PcodeOpcode.LOAD,
                        inputs=(const_varnode(0x2000),),
                        output=register_varnode(11),
                    ),
                ),
                _instruction(
                    0x1018,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(13), register_varnode(11)),
                        output=register_varnode(14),
                    ),
                ),
                _instruction(
                    0x101C,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_EQUAL,
                        inputs=(register_varnode(14), const_varnode(0)),
                        output=unique_varnode(0, size=1),
                    ),
                ),
                _instruction(
                    0x1020,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_SLESS,
                        inputs=(register_varnode(14), register_varnode(11)),
                        output=unique_varnode(0, size=1),
                    ),
                ),
            ),
        ),
    )

    program = analyze_program_scalar_types(
        analyze_program_memory(analyze_program_stack(_calls_program(0x1000, (function,))))
    )
    facts = program.functions[0x1000]

    partition_types = {
        fact.partition.identity_pretty(): fact.scalar_type.to_pretty()
        for fact in facts.partition_facts
    }
    value_types = {
        fact.value.to_pretty(): fact.scalar_type.to_pretty()
        for fact in facts.value_facts
    }

    assert partition_types["stack_slot -16 size=4 role=argument_home(x10)"] == "pointer:4"
    assert partition_types["absolute 0x2000 size=4"] == "int:4"
    assert partition_types["value x10_0:4 offset=+4 size=4"] == "int:4"
    assert value_types["x10_0:4"] == "pointer:4"
    assert value_types["x12_1:4"] == "pointer:4"
    assert value_types["x11_1:4"] == "int:4"
    assert value_types["x14_1:4"] == "int:4"
    assert value_types["u0_1:1"] == "bool:1"


def test_analyze_program_scalar_types_preserves_partition_root_through_pointer_phi_join() -> None:
    function = _function(
        0x1000,
        (
            _block(
                0x1000,
                _instruction(0x1000),
                successors=(
                    BlockEdge(BlockEdgeKind.BRANCH_TAKEN, 0x1010),
                    BlockEdge(BlockEdgeKind.FALLTHROUGH, 0x1020),
                ),
                terminator=BlockTerminator.BRANCH,
            ),
            _block(
                0x1010,
                _instruction(
                    0x1010,
                    PcodeOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(register_varnode(10),),
                        output=register_varnode(12),
                    ),
                ),
                successors=(BlockEdge(BlockEdgeKind.JUMP, 0x1030),),
                terminator=BlockTerminator.JUMP,
            ),
            _block(
                0x1020,
                _instruction(
                    0x1020,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(10), const_varnode(0)),
                        output=register_varnode(12),
                    ),
                ),
                successors=(BlockEdge(BlockEdgeKind.JUMP, 0x1030),),
                terminator=BlockTerminator.JUMP,
            ),
            _block(
                0x1030,
                _instruction(
                    0x1030,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(12), const_varnode(4)),
                        output=register_varnode(13),
                    ),
                ),
                _instruction(
                    0x1034,
                    PcodeOp(
                        opcode=PcodeOpcode.LOAD,
                        inputs=(register_varnode(13),),
                        output=register_varnode(14),
                    ),
                ),
                _instruction(
                    0x1038,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_EQUAL,
                        inputs=(register_varnode(14), const_varnode(0)),
                        output=unique_varnode(0, size=1),
                    ),
                ),
            ),
        ),
    )

    program = analyze_program_scalar_types(
        analyze_program_memory(analyze_program_stack(_calls_program(0x1000, (function,))))
    )
    facts = program.functions[0x1000]

    partition_types = {
        fact.partition.identity_pretty(): fact.scalar_type.to_pretty()
        for fact in facts.partition_facts
    }
    value_types = {
        fact.value.to_pretty(): fact.scalar_type.to_pretty()
        for fact in facts.value_facts
    }

    assert partition_types["value x10_0:4 offset=+4 size=4"] == "word:4"
    assert value_types["x10_0:4"] == "pointer:4"
    assert value_types["x12_3:4"] == "pointer:4"


def test_analyze_program_scalar_types_degrades_conflicting_evidence_to_word() -> None:
    function = _function(
        0x1000,
        (
            _block(
                0x1000,
                _instruction(
                    0x1000,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(2), const_varnode(-16)),
                        output=register_varnode(2),
                    ),
                ),
                _instruction(
                    0x1004,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(2), const_varnode(0)),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.STORE,
                        inputs=(unique_varnode(0), register_varnode(10)),
                    ),
                ),
                _instruction(
                    0x1008,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(2), const_varnode(0)),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.LOAD,
                        inputs=(unique_varnode(0),),
                        output=register_varnode(10),
                    ),
                ),
                _instruction(
                    0x100C,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(10), const_varnode(4)),
                        output=register_varnode(11),
                    ),
                ),
                _instruction(
                    0x1010,
                    PcodeOp(
                        opcode=PcodeOpcode.LOAD,
                        inputs=(const_varnode(0x2000),),
                        output=register_varnode(12),
                    ),
                ),
                _instruction(
                    0x1014,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(12), const_varnode(1)),
                        output=register_varnode(13),
                    ),
                ),
                _instruction(
                    0x1018,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(2), const_varnode(0)),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.STORE,
                        inputs=(unique_varnode(0), register_varnode(13)),
                    ),
                ),
            ),
        ),
    )

    program = analyze_program_scalar_types(
        analyze_program_memory(analyze_program_stack(_calls_program(0x1000, (function,))))
    )
    facts = program.functions[0x1000]

    partition_types = {
        fact.partition.identity_pretty(): fact.scalar_type.kind
        for fact in facts.partition_facts
    }

    assert partition_types["stack_slot -16 size=4 role=argument_home(x10)"] == ScalarTypeKind.WORD


def test_analyze_program_scalar_types_recovers_int_for_call_result_local_used_in_additive_arithmetic() -> None:
    function = _function(
        0x1000,
        (
            _block(
                0x1000,
                _instruction(
                    0x1000,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(2), const_varnode(-16)),
                        output=register_varnode(2),
                    ),
                ),
                _instruction(
                    0x1004,
                    PcodeOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(const_varnode(7),),
                        output=register_varnode(10),
                    ),
                ),
                _instruction(
                    0x1008,
                    PcodeOp(
                        opcode=PcodeOpcode.CALL,
                        inputs=(const_varnode(0x1100),),
                    ),
                ),
                _instruction(
                    0x100C,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(2), const_varnode(0)),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.STORE,
                        inputs=(unique_varnode(0), register_varnode(10)),
                    ),
                ),
                _instruction(
                    0x1010,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(2), const_varnode(0)),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.LOAD,
                        inputs=(unique_varnode(0),),
                        output=register_varnode(12),
                    ),
                ),
                _instruction(
                    0x1014,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(12), const_varnode(-2)),
                        output=register_varnode(13),
                    ),
                ),
            ),
        ),
    )

    program = analyze_program_scalar_types(
        analyze_program_memory(analyze_program_stack(_calls_program(0x1000, (function,))))
    )
    facts = program.functions[0x1000]

    partition_types = {
        fact.partition.identity_pretty(): fact.scalar_type.to_pretty()
        for fact in facts.partition_facts
    }
    value_types = {
        fact.value.to_pretty(): fact.scalar_type.to_pretty()
        for fact in facts.value_facts
    }

    assert partition_types["stack_slot -16 size=4 role=local"] == "int:4"
    assert value_types["x10_2:4"] == "int:4"
    assert value_types["x12_2:4"] == "int:4"
    assert value_types["x13_2:4"] == "int:4"


def test_analyze_program_scalar_types_preserves_upstream_queue_state() -> None:
    function = _function(0x1000, (_block(0x1000, _instruction(0x1000)),))

    program = analyze_program_scalar_types(
        analyze_program_memory(
            analyze_program_stack(
                _calls_program(
                    0x1000,
                    (function,),
                    pending_entries=(0x4000,),
                    invalidated_entries=(0x1000,),
                )
            )
        )
    )

    assert program.pending_entries == (0x4000,)
    assert program.invalidated_entries == (0x1000,)
