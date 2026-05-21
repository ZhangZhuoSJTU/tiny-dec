from __future__ import annotations

from tiny_dec.analysis.calls import analyze_program_calls
from tiny_dec.analysis.dataflow import (
    BlockDataflowFacts,
    FunctionDataflowFacts,
    ProgramDataflowFacts,
    RegisterState,
)
from tiny_dec.analysis.highvars import (
    FunctionVariableFacts,
    ProgramVariableFacts,
    RecoveredVariable,
    VariableBinding,
    VariableBindingKind,
    VariableKind,
    analyze_program_variables,
)
from tiny_dec.analysis.memory import (
    FunctionMemoryFacts,
    MemoryAccess,
    MemoryAccessKind,
    MemoryPartition,
    MemoryPartitionKind,
    ProgramMemoryFacts,
    analyze_program_memory,
)
from tiny_dec.analysis.range import analyze_program_ranges
from tiny_dec.analysis.simplify import (
    CanonicalBlock,
    CanonicalFunctionIR,
    CanonicalInstruction,
    CanonicalProgramIR,
)
from tiny_dec.analysis.ssa import construct_program_ssa
from tiny_dec.analysis.stack import (
    FunctionStackFacts,
    ProgramStackFacts,
    StackAccess,
    StackAccessKind,
    StackBaseKind,
    StackSlot,
    StackSlotRole,
    analyze_program_stack,
)
from tiny_dec.analysis.types import (
    FunctionAggregateTypeFacts,
    FunctionScalarTypeFacts,
    PartitionScalarTypeFact,
    ProgramAggregateTypeFacts,
    ProgramScalarTypeFacts,
    ScalarType,
    ScalarTypeKind,
    analyze_program_aggregate_types,
    analyze_program_scalar_types,
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


def _variables_program(
    *,
    root_entry: int,
    functions: tuple[FunctionDataflowFacts, ...],
    pending_entries: tuple[int, ...] = (),
    invalidated_entries: tuple[int, ...] = (),
) -> ProgramVariableFacts:
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
    return analyze_program_variables(
        analyze_program_aggregate_types(
            analyze_program_scalar_types(
                analyze_program_memory(
                    analyze_program_stack(analyze_program_calls(construct_program_ssa(dataflow_program)))
                )
            )
        )
    )


def _manual_variable_program(
    *,
    slots: tuple[StackSlot, ...],
    partitions: tuple[MemoryPartition, ...],
    partition_facts: tuple[PartitionScalarTypeFact, ...],
    variables: tuple[RecoveredVariable, ...],
    pending_entries: tuple[int, ...] = (),
    invalidated_entries: tuple[int, ...] = (),
) -> ProgramVariableFacts:
    block = CanonicalBlock(
        start=0x1000,
        instructions=(_instruction(0x1000), _instruction(0x1004)),
        terminator=BlockTerminator.RETURN,
    )
    canonical = CanonicalFunctionIR(
        entry=0x1000,
        name="main",
        blocks={0x1000: block},
        discovery_order=(0x1000,),
        instruction_index={0x1000: block.instructions[0], 0x1004: block.instructions[1]},
        return_blocks=(0x1000,),
    )
    dataflow_function = FunctionDataflowFacts(
        function=canonical,
        blocks={
            0x1000: BlockDataflowFacts(
                start=0x1000,
                in_state=RegisterState(),
                out_state=RegisterState(),
            )
        },
    )
    dataflow_program = ProgramDataflowFacts(
        program=CanonicalProgramIR(
            root_entry=0x1000,
            functions={0x1000: canonical},
            discovery_order=(0x1000,),
        ),
        functions={0x1000: dataflow_function},
        pending_entries=pending_entries,
        invalidated_entries=invalidated_entries,
    )
    calls = analyze_program_calls(construct_program_ssa(dataflow_program))
    stack_function = FunctionStackFacts(
        calls=calls.functions[0x1000],
        frame_size=16,
        dynamic_stack_pointer=False,
        slots=slots,
    )
    stack_program = ProgramStackFacts(
        calls=calls,
        functions={0x1000: stack_function},
        pending_entries=calls.pending_entries,
        invalidated_entries=calls.invalidated_entries,
    )
    memory_function = FunctionMemoryFacts(
        stack=stack_function,
        partitions=partitions,
    )
    memory_program = ProgramMemoryFacts(
        stack=stack_program,
        functions={0x1000: memory_function},
        pending_entries=stack_program.pending_entries,
        invalidated_entries=stack_program.invalidated_entries,
    )
    scalar_function = FunctionScalarTypeFacts(
        memory=memory_function,
        partition_facts=partition_facts,
    )
    scalar_program = ProgramScalarTypeFacts(
        memory=memory_program,
        functions={0x1000: scalar_function},
        pending_entries=memory_program.pending_entries,
        invalidated_entries=memory_program.invalidated_entries,
    )
    aggregate_function = FunctionAggregateTypeFacts(
        scalar_types=scalar_function,
        layouts=(),
    )
    aggregate_program = ProgramAggregateTypeFacts(
        scalar_types=scalar_program,
        functions={0x1000: aggregate_function},
        pending_entries=scalar_program.pending_entries,
        invalidated_entries=scalar_program.invalidated_entries,
    )
    variable_function = FunctionVariableFacts(
        aggregate_types=aggregate_function,
        variables=variables,
    )
    return ProgramVariableFacts(
        aggregate_types=aggregate_program,
        functions={0x1000: variable_function},
        pending_entries=aggregate_program.pending_entries,
        invalidated_entries=aggregate_program.invalidated_entries,
    )


def test_analyze_program_ranges_recovers_loop_value_ranges_and_branch_refinements() -> None:
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
        _instruction(
            0x1004,
            PcodeOp(
                opcode=PcodeOpcode.BRANCH,
                inputs=(const_varnode(0x1010),),
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
                opcode=PcodeOpcode.INT_SLESS,
                inputs=(register_varnode(10), const_varnode(3)),
                output=unique_varnode(0, size=1),
            ),
            PcodeOp(
                opcode=PcodeOpcode.CBRANCH,
                inputs=(const_varnode(0x1020), unique_varnode(0, size=1)),
            ),
        ),
        successors=(
            BlockEdge(BlockEdgeKind.BRANCH_TAKEN, 0x1020),
            BlockEdge(BlockEdgeKind.FALLTHROUGH, 0x1030),
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
        _instruction(
            0x1024,
            PcodeOp(
                opcode=PcodeOpcode.BRANCH,
                inputs=(const_varnode(0x1010),),
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

    result = analyze_program_ranges(
        _variables_program(root_entry=0x1000, functions=(_function(0x1000, (entry, header, body, exit_block)),))
    )
    facts = result.functions[0x1000]

    value_ranges = {
        fact.value.to_pretty(): fact.value_range.to_pretty()
        for fact in facts.value_ranges
    }
    branch_ranges = [fact.to_pretty() for fact in facts.branch_refinements]

    assert value_ranges["u0_1:1"] == "[0, 1]"
    assert value_ranges["x10_1:4"] == "[0, 0]"
    assert value_ranges["x10_2:4"] == "[0, +inf]"
    assert value_ranges["x10_3:4"] == "[1, +inf]"
    assert value_ranges["x11_1:4"] == "[0, +inf]"
    assert branch_ranges == [
        "branch 0x1010 -> 0x1020 sense=true source=INT_SLESS value=x10_2:4 range=[-inf, 2]",
        "branch 0x1010 -> 0x1030 sense=false source=INT_SLESS value=x10_2:4 range=[3, +inf]",
    ]


def test_analyze_program_ranges_projects_variable_ranges_from_accesses_and_bool_types() -> None:
    counter_slot = StackSlot(
        frame_offset=-12,
        size=4,
        role=StackSlotRole.LOCAL,
        accesses=(
            StackAccess(
                instruction_address=0x1000,
                block_start=0x1000,
                kind=StackAccessKind.STORE,
                frame_offset=-12,
                size=4,
                base_kind=StackBaseKind.FRAME_POINTER,
                base_register=8,
                value=const_varnode(0),
            ),
            StackAccess(
                instruction_address=0x1004,
                block_start=0x1000,
                kind=StackAccessKind.STORE,
                frame_offset=-12,
                size=4,
                base_kind=StackBaseKind.FRAME_POINTER,
                base_register=8,
                value=const_varnode(5),
            ),
        ),
    )
    flag_slot = StackSlot(
        frame_offset=-8,
        size=1,
        role=StackSlotRole.LOCAL,
    )
    counter_partition = MemoryPartition(
        kind=MemoryPartitionKind.STACK_SLOT,
        size=4,
        stack_slot=counter_slot,
        accesses=(
            MemoryAccess(
                instruction_address=0x1000,
                block_start=0x1000,
                kind=MemoryAccessKind.STORE,
                size=4,
                value=const_varnode(0),
            ),
            MemoryAccess(
                instruction_address=0x1004,
                block_start=0x1000,
                kind=MemoryAccessKind.STORE,
                size=4,
                value=const_varnode(5),
            ),
        ),
    )
    flag_partition = MemoryPartition(
        kind=MemoryPartitionKind.STACK_SLOT,
        size=1,
        stack_slot=flag_slot,
    )

    result = analyze_program_ranges(
        _manual_variable_program(
            slots=(counter_slot, flag_slot),
            partitions=(counter_partition, flag_partition),
            partition_facts=(
                PartitionScalarTypeFact(
                    partition=counter_partition,
                    scalar_type=ScalarType(ScalarTypeKind.INT, 4),
                ),
                PartitionScalarTypeFact(
                    partition=flag_partition,
                    scalar_type=ScalarType(ScalarTypeKind.BOOL, 1),
                ),
            ),
            variables=(
                RecoveredVariable(
                    name="local_12_4",
                    kind=VariableKind.LOCAL,
                    size=4,
                    binding=VariableBinding(
                        kind=VariableBindingKind.STACK_SLOT,
                        stack_slot=counter_slot,
                    ),
                    scalar_type=ScalarType(ScalarTypeKind.INT, 4),
                    partitions=(counter_partition,),
                ),
                RecoveredVariable(
                    name="local_8_1",
                    kind=VariableKind.LOCAL,
                    size=1,
                    binding=VariableBinding(
                        kind=VariableBindingKind.STACK_SLOT,
                        stack_slot=flag_slot,
                    ),
                    scalar_type=ScalarType(ScalarTypeKind.BOOL, 1),
                    partitions=(flag_partition,),
                ),
            ),
        )
    )
    facts = result.functions[0x1000]

    variable_ranges = {
        fact.variable.name: fact.value_range.to_pretty()
        for fact in facts.variable_ranges
    }

    assert variable_ranges == {
        "local_12_4": "[0, 5]",
        "local_8_1": "[0, 1]",
    }


def test_analyze_program_ranges_preserves_upstream_queue_state() -> None:
    function = _function(
        0x1000,
        (
            _block(
                0x1000,
                _instruction(0x1000),
            ),
        ),
    )

    result = analyze_program_ranges(
        _variables_program(
            root_entry=0x1000,
            functions=(function,),
            pending_entries=(0x4000,),
            invalidated_entries=(0x1000,),
        )
    )

    assert result.pending_entries == (0x4000,)
    assert result.invalidated_entries == (0x1000,)
