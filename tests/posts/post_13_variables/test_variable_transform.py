from __future__ import annotations

from tiny_dec.analysis.calls import analyze_program_calls
from tiny_dec.analysis.dataflow import (
    BlockDataflowFacts,
    FunctionDataflowFacts,
    ProgramDataflowFacts,
    RegisterState,
)
from tiny_dec.analysis.highvars import (
    VariableBindingKind,
    VariableKind,
    analyze_program_variables,
)
from tiny_dec.analysis.memory import (
    FunctionMemoryFacts,
    MemoryPartition,
    MemoryPartitionKind,
    ProgramMemoryFacts,
)
from tiny_dec.analysis.simplify import (
    CanonicalBlock,
    CanonicalFunctionIR,
    CanonicalInstruction,
    CanonicalProgramIR,
)
from tiny_dec.analysis.ssa import construct_program_ssa
from tiny_dec.analysis.ssa.models import SSAName, SSANameKind
from tiny_dec.analysis.stack import (
    FunctionStackFacts,
    ProgramStackFacts,
    StackAccess,
    StackAccessKind,
    StackBaseKind,
    StackSlot,
    StackSlotRole,
)
from tiny_dec.analysis.types import (
    AggregateField,
    AggregateLayout,
    AggregateRoot,
    AggregateRootKind,
    FunctionAggregateTypeFacts,
    FunctionScalarTypeFacts,
    PartitionScalarTypeFact,
    ProgramAggregateTypeFacts,
    ProgramScalarTypeFacts,
    ScalarType,
    ScalarTypeKind,
    ValueScalarTypeFact,
)
from tiny_dec.decode import decode_rv32i
from tiny_dec.disasm.models import BlockTerminator
from tiny_dec.ir.pcode import PcodeOp, PcodeOpcode, register_varnode


def _instruction(address: int, *ops: PcodeOp) -> CanonicalInstruction:
    return CanonicalInstruction(
        instruction=decode_rv32i(0x00000013, address),
        ops=ops,
    )


def _function_dataflow() -> FunctionDataflowFacts:
    instruction = _instruction(
        0x1000,
        PcodeOp(
            opcode=PcodeOpcode.COPY,
            inputs=(register_varnode(1),),
            output=register_varnode(6),
        ),
        PcodeOp(
            opcode=PcodeOpcode.COPY,
            inputs=(register_varnode(10),),
            output=register_varnode(5),
        ),
    )
    block = CanonicalBlock(
        start=0x1000,
        instructions=(instruction,),
        terminator=BlockTerminator.RETURN,
    )
    canonical = CanonicalFunctionIR(
        entry=0x1000,
        name="main",
        blocks={0x1000: block},
        discovery_order=(0x1000,),
        instruction_index={instruction.address: instruction},
        return_blocks=(0x1000,),
    )
    return FunctionDataflowFacts(
        function=canonical,
        blocks={
            0x1000: BlockDataflowFacts(
                start=0x1000,
                in_state=RegisterState(),
                out_state=RegisterState(),
            )
        },
    )


def _aggregate_program(
    *,
    slots: tuple[StackSlot, ...] = (),
    partitions: tuple[MemoryPartition, ...] = (),
    partition_facts: tuple[PartitionScalarTypeFact, ...] = (),
    value_facts: tuple[ValueScalarTypeFact, ...] = (),
    layouts: tuple[AggregateLayout, ...] = (),
    pending_entries: tuple[int, ...] = (),
    invalidated_entries: tuple[int, ...] = (),
) -> ProgramAggregateTypeFacts:
    function = _function_dataflow()
    canonical_program = CanonicalProgramIR(
        root_entry=0x1000,
        functions={0x1000: function.function},
        discovery_order=(0x1000,),
    )
    dataflow_program = ProgramDataflowFacts(
        program=canonical_program,
        functions={0x1000: function},
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
        value_facts=value_facts,
    )
    scalar_program = ProgramScalarTypeFacts(
        memory=memory_program,
        functions={0x1000: scalar_function},
        pending_entries=memory_program.pending_entries,
        invalidated_entries=memory_program.invalidated_entries,
    )
    aggregate_function = FunctionAggregateTypeFacts(
        scalar_types=scalar_function,
        layouts=layouts,
    )
    return ProgramAggregateTypeFacts(
        scalar_types=scalar_program,
        functions={0x1000: aggregate_function},
        pending_entries=scalar_program.pending_entries,
        invalidated_entries=scalar_program.invalidated_entries,
    )


def test_analyze_program_variables_recovers_aggregate_parameter_and_locals() -> None:
    parameter_slot = StackSlot(
        frame_offset=-12,
        size=4,
        role=StackSlotRole.ARGUMENT_HOME,
        argument_register=10,
        accesses=(
            StackAccess(
                instruction_address=0x1004,
                block_start=0x1000,
                kind=StackAccessKind.STORE,
                frame_offset=-12,
                size=4,
                base_kind=StackBaseKind.FRAME_POINTER,
                base_register=8,
                value=SSAName(SSANameKind.REGISTER, 10, 0, 4),
            ),
        ),
    )
    local_slot = StackSlot(
        frame_offset=-16,
        size=4,
        role=StackSlotRole.LOCAL,
        accesses=(
            StackAccess(
                instruction_address=0x1008,
                block_start=0x1000,
                kind=StackAccessKind.STORE,
                frame_offset=-16,
                size=4,
                base_kind=StackBaseKind.FRAME_POINTER,
                base_register=8,
                value=SSAName(SSANameKind.UNIQUE, 2, 0, 4),
            ),
        ),
    )
    saved_slot = StackSlot(
        frame_offset=-4,
        size=4,
        role=StackSlotRole.SAVED_REGISTER,
        saved_register=1,
        accesses=(
            StackAccess(
                instruction_address=0x100c,
                block_start=0x1000,
                kind=StackAccessKind.STORE,
                frame_offset=-4,
                size=4,
                base_kind=StackBaseKind.STACK_POINTER,
                base_register=2,
                value=SSAName(SSANameKind.REGISTER, 1, 0, 4),
            ),
        ),
    )

    parameter_partition = MemoryPartition(
        kind=MemoryPartitionKind.STACK_SLOT,
        size=4,
        stack_slot=parameter_slot,
    )
    local_partition = MemoryPartition(
        kind=MemoryPartitionKind.STACK_SLOT,
        size=4,
        stack_slot=local_slot,
    )
    saved_partition = MemoryPartition(
        kind=MemoryPartitionKind.STACK_SLOT,
        size=4,
        stack_slot=saved_slot,
    )
    field0_partition = MemoryPartition(
        kind=MemoryPartitionKind.VALUE,
        size=4,
        base_value=SSAName(SSANameKind.UNIQUE, 10, 0, 4),
    )
    field4_partition = MemoryPartition(
        kind=MemoryPartitionKind.VALUE,
        size=4,
        base_value=SSAName(SSANameKind.UNIQUE, 11, 0, 4),
        offset=4,
    )

    program = _aggregate_program(
        slots=(local_slot, parameter_slot, saved_slot),
        partitions=(
            local_partition,
            parameter_partition,
            saved_partition,
            field0_partition,
            field4_partition,
        ),
        partition_facts=(
            PartitionScalarTypeFact(
                partition=local_partition,
                scalar_type=ScalarType(ScalarTypeKind.INT, 4),
            ),
            PartitionScalarTypeFact(
                partition=parameter_partition,
                scalar_type=ScalarType(ScalarTypeKind.POINTER, 4),
            ),
            PartitionScalarTypeFact(
                partition=saved_partition,
                scalar_type=ScalarType(ScalarTypeKind.WORD, 4),
            ),
            PartitionScalarTypeFact(
                partition=field0_partition,
                scalar_type=ScalarType(ScalarTypeKind.INT, 4),
            ),
            PartitionScalarTypeFact(
                partition=field4_partition,
                scalar_type=ScalarType(ScalarTypeKind.INT, 4),
            ),
        ),
        value_facts=(
            ValueScalarTypeFact(
                value=SSAName(SSANameKind.REGISTER, 10, 0, 4),
                scalar_type=ScalarType(ScalarTypeKind.POINTER, 4),
            ),
        ),
        layouts=(
            AggregateLayout(
                root=AggregateRoot(
                    kind=AggregateRootKind.POINTER,
                    pointer_value=SSAName(SSANameKind.REGISTER, 10, 0, 4),
                    stride=8,
                ),
                fields=(
                    AggregateField(
                        offset=0,
                        scalar_type=ScalarType(ScalarTypeKind.INT, 4),
                        partitions=(field0_partition,),
                    ),
                    AggregateField(
                        offset=4,
                        scalar_type=ScalarType(ScalarTypeKind.INT, 4),
                        partitions=(field4_partition,),
                    ),
                ),
            ),
        ),
    )

    result = analyze_program_variables(program)
    function = result.functions[0x1000]

    assert [variable.name for variable in function.variables] == [
        "arg_x10_4",
        "local_16_4",
    ]

    parameter = function.variables[0]
    assert parameter.kind == VariableKind.PARAMETER
    assert parameter.binding.kind == VariableBindingKind.STACK_SLOT
    assert parameter.binding.stack_slot == parameter_slot
    assert parameter.scalar_type == ScalarType(ScalarTypeKind.POINTER, 4)
    assert parameter.root_value == SSAName(SSANameKind.REGISTER, 10, 0, 4)
    assert parameter.aggregate_layout == program.functions[0x1000].layouts[0]
    assert parameter.partitions == (
        parameter_partition,
        field0_partition,
        field4_partition,
    )

    local = function.variables[1]
    assert local.kind == VariableKind.LOCAL
    assert local.binding.kind == VariableBindingKind.STACK_SLOT
    assert local.binding.stack_slot == local_slot
    assert local.partitions == (local_partition,)


def test_analyze_program_variables_recovers_register_only_globals_and_indirects() -> None:
    absolute_partition = MemoryPartition(
        kind=MemoryPartitionKind.ABSOLUTE,
        size=4,
        absolute_address=0x2000,
    )
    value_partition = MemoryPartition(
        kind=MemoryPartitionKind.VALUE,
        size=4,
        base_value=SSAName(SSANameKind.UNIQUE, 20, 0, 4),
        offset=4,
    )

    program = _aggregate_program(
        partitions=(absolute_partition, value_partition),
        partition_facts=(
            PartitionScalarTypeFact(
                partition=absolute_partition,
                scalar_type=ScalarType(ScalarTypeKind.WORD, 4),
            ),
            PartitionScalarTypeFact(
                partition=value_partition,
                scalar_type=ScalarType(ScalarTypeKind.INT, 4),
            ),
        ),
        value_facts=(
            ValueScalarTypeFact(
                value=SSAName(SSANameKind.REGISTER, 10, 0, 4),
                scalar_type=ScalarType(ScalarTypeKind.INT, 4),
            ),
            ValueScalarTypeFact(
                value=SSAName(SSANameKind.UNIQUE, 20, 0, 4),
                scalar_type=ScalarType(ScalarTypeKind.POINTER, 4),
            ),
        ),
    )

    result = analyze_program_variables(program)
    function = result.functions[0x1000]

    assert [variable.name for variable in function.variables] == [
        "arg_x10_4",
        "global_0x2000_4",
        "deref_u20_0_p4_4",
    ]
    assert function.variables[0].binding.kind == VariableBindingKind.ROOT_VALUE
    assert function.variables[0].kind == VariableKind.PARAMETER
    assert function.variables[1].binding.kind == VariableBindingKind.ABSOLUTE
    assert function.variables[1].kind == VariableKind.GLOBAL
    assert function.variables[2].binding.kind == VariableBindingKind.PARTITION
    assert function.variables[2].kind == VariableKind.INDIRECT


def test_analyze_program_variables_preserves_upstream_queue_state() -> None:
    program = _aggregate_program(
        pending_entries=(0x4000,),
        invalidated_entries=(0x1000,),
    )

    result = analyze_program_variables(program)

    assert result.pending_entries == (0x4000,)
    assert result.invalidated_entries == (0x1000,)
