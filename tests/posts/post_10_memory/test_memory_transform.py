from __future__ import annotations

from tiny_dec.analysis.calls import analyze_program_calls
from tiny_dec.analysis.dataflow import (
    BlockDataflowFacts,
    FunctionDataflowFacts,
    ProgramDataflowFacts,
    RegisterState,
)
from tiny_dec.analysis.memory import analyze_program_memory
from tiny_dec.analysis.memory.models import MemoryPartitionKind
from tiny_dec.analysis.simplify import (
    CanonicalBlock,
    CanonicalFunctionIR,
    CanonicalInstruction,
    CanonicalProgramIR,
)
from tiny_dec.analysis.ssa import construct_program_ssa
from tiny_dec.analysis.ssa.models import MemoryVersion, SSAName, SSANameKind
from tiny_dec.analysis.stack import analyze_program_stack
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


def test_analyze_program_memory_recovers_stack_absolute_and_value_partitions() -> None:
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
                        opcode=PcodeOpcode.LOAD,
                        inputs=(const_varnode(0x2000),),
                        output=register_varnode(11),
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
                        opcode=PcodeOpcode.LOAD,
                        inputs=(unique_varnode(0),),
                        output=register_varnode(10),
                    ),
                ),
                _instruction(
                    0x1010,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(10), const_varnode(4)),
                        output=register_varnode(12),
                    ),
                ),
                _instruction(
                    0x1014,
                    PcodeOp(
                        opcode=PcodeOpcode.LOAD,
                        inputs=(register_varnode(12),),
                        output=register_varnode(13),
                    ),
                ),
            ),
        ),
    )

    stack = analyze_program_stack(_calls_program(0x1000, (function,)))
    memory = analyze_program_memory(stack)
    facts = memory.functions[0x1000]

    assert [partition.kind.value for partition in facts.partitions] == [
        "stack_slot",
        "absolute",
        "value",
    ]

    stack_partition = facts.partitions[0]
    assert stack_partition.kind == MemoryPartitionKind.STACK_SLOT
    assert stack_partition.stack_slot is not None
    assert stack_partition.stack_slot.frame_offset == -16
    assert [access.instruction_address for access in stack_partition.accesses] == [
        0x1004,
        0x100C,
    ]
    assert [
        (access.memory_before, access.memory_after)
        for access in stack_partition.accesses
    ] == [
        (MemoryVersion(0), MemoryVersion(1)),
        (MemoryVersion(1), None),
    ]

    absolute_partition = facts.partitions[1]
    assert absolute_partition.kind == MemoryPartitionKind.ABSOLUTE
    assert absolute_partition.absolute_address == 0x2000
    assert [access.instruction_address for access in absolute_partition.accesses] == [
        0x1008
    ]
    assert absolute_partition.accesses[0].memory_before == MemoryVersion(1)
    assert absolute_partition.accesses[0].memory_after is None

    value_partition = facts.partitions[2]
    assert value_partition.kind == MemoryPartitionKind.VALUE
    assert value_partition.base_value == SSAName(SSANameKind.REGISTER, 10, 0, 4)
    assert value_partition.offset == 4
    assert [access.instruction_address for access in value_partition.accesses] == [
        0x1014
    ]
    assert value_partition.accesses[0].memory_before == MemoryVersion(1)
    assert value_partition.accesses[0].memory_after is None


def test_analyze_program_memory_preserves_pointer_root_through_compatible_phi_join() -> None:
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
            ),
        ),
    )

    stack = analyze_program_stack(_calls_program(0x1000, (function,)))
    memory = analyze_program_memory(stack)
    facts = memory.functions[0x1000]

    assert [partition.kind.value for partition in facts.partitions] == ["value"]
    value_partition = facts.partitions[0]
    assert value_partition.kind == MemoryPartitionKind.VALUE
    assert value_partition.base_value == SSAName(SSANameKind.REGISTER, 10, 0, 4)
    assert value_partition.offset == 4
    assert [access.instruction_address for access in value_partition.accesses] == [0x1034]


def test_analyze_program_memory_normalizes_scaled_indexed_field_accesses() -> None:
    function = _function(
        0x1000,
        (
            _block(
                0x1000,
                _instruction(
                    0x1000,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_LEFT,
                        inputs=(register_varnode(11), const_varnode(3)),
                        output=register_varnode(12),
                    ),
                ),
                _instruction(
                    0x1004,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(10), register_varnode(12)),
                        output=register_varnode(13),
                    ),
                ),
                _instruction(
                    0x1008,
                    PcodeOp(
                        opcode=PcodeOpcode.LOAD,
                        inputs=(register_varnode(13),),
                        output=register_varnode(14),
                    ),
                ),
                _instruction(
                    0x100C,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(13), const_varnode(4)),
                        output=register_varnode(15),
                    ),
                ),
                _instruction(
                    0x1010,
                    PcodeOp(
                        opcode=PcodeOpcode.LOAD,
                        inputs=(register_varnode(15),),
                        output=register_varnode(16),
                    ),
                ),
            ),
        ),
    )

    stack = analyze_program_stack(_calls_program(0x1000, (function,)))
    memory = analyze_program_memory(stack)
    facts = memory.functions[0x1000]

    assert [partition.kind.value for partition in facts.partitions] == [
        "value",
        "value",
    ]
    first_partition, second_partition = facts.partitions
    assert first_partition.kind == MemoryPartitionKind.VALUE
    assert first_partition.base_value == SSAName(SSANameKind.REGISTER, 10, 0, 4)
    assert first_partition.offset == 0
    assert [access.instruction_address for access in first_partition.accesses] == [
        0x1008
    ]
    assert second_partition.kind == MemoryPartitionKind.VALUE
    assert second_partition.base_value == SSAName(SSANameKind.REGISTER, 10, 0, 4)
    assert second_partition.offset == 4
    assert [access.instruction_address for access in second_partition.accesses] == [
        0x1010
    ]


def test_analyze_program_memory_falls_back_to_raw_address_value_for_unsupported_arithmetic() -> None:
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
                        inputs=(register_varnode(10), register_varnode(11)),
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
            ),
        ),
    )

    stack = analyze_program_stack(_calls_program(0x1000, (function,)))
    memory = analyze_program_memory(stack)
    facts = memory.functions[0x1000]

    assert [partition.kind.value for partition in facts.partitions] == [
        "stack_slot",
        "value",
    ]

    value_partition = facts.partitions[1]
    assert value_partition.kind == MemoryPartitionKind.VALUE
    assert value_partition.base_value == SSAName(SSANameKind.REGISTER, 12, 1, 4)
    assert value_partition.offset == 0
    assert [access.instruction_address for access in value_partition.accesses] == [
        0x1010
    ]


def test_analyze_program_memory_preserves_upstream_queue_state() -> None:
    function = _function(0x1000, (_block(0x1000, _instruction(0x1000)),))

    memory = analyze_program_memory(
        analyze_program_stack(
            _calls_program(
                0x1000,
                (function,),
                pending_entries=(0x4000,),
                invalidated_entries=(0x1000,),
            )
        )
    )

    assert memory.pending_entries == (0x4000,)
    assert memory.invalidated_entries == (0x1000,)
