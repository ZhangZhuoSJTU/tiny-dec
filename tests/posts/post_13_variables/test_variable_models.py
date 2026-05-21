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
    format_function_variable_facts,
    format_program_variable_facts,
    format_recovered_variable,
    format_variable_binding,
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


def _variable_program() -> ProgramAggregateTypeFacts:
    instruction = _instruction(
        0x1000,
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
    canonical_program = CanonicalProgramIR(
        root_entry=0x1000,
        functions={0x1000: canonical},
        discovery_order=(0x1000,),
    )
    dataflow_program = ProgramDataflowFacts(
        program=canonical_program,
        functions={0x1000: dataflow_function},
        pending_entries=(0x2000,),
        invalidated_entries=(0x1000,),
    )
    calls = analyze_program_calls(construct_program_ssa(dataflow_program))

    slot = StackSlot(
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
    stack_function = FunctionStackFacts(
        calls=calls.functions[0x1000],
        frame_size=16,
        dynamic_stack_pointer=False,
        slots=(slot,),
    )
    stack_program = ProgramStackFacts(
        calls=calls,
        functions={0x1000: stack_function},
        pending_entries=calls.pending_entries,
        invalidated_entries=calls.invalidated_entries,
    )
    slot_partition = MemoryPartition(
        kind=MemoryPartitionKind.STACK_SLOT,
        size=4,
        stack_slot=slot,
    )
    field_partition = MemoryPartition(
        kind=MemoryPartitionKind.VALUE,
        size=4,
        base_value=SSAName(SSANameKind.UNIQUE, 0, 0, 4),
    )
    memory_function = FunctionMemoryFacts(
        stack=stack_function,
        partitions=(slot_partition, field_partition),
    )
    memory_program = ProgramMemoryFacts(
        stack=stack_program,
        functions={0x1000: memory_function},
        pending_entries=stack_program.pending_entries,
        invalidated_entries=stack_program.invalidated_entries,
    )
    scalar_function = FunctionScalarTypeFacts(
        memory=memory_function,
        partition_facts=(
            PartitionScalarTypeFact(
                partition=slot_partition,
                scalar_type=ScalarType(ScalarTypeKind.POINTER, 4),
            ),
            PartitionScalarTypeFact(
                partition=field_partition,
                scalar_type=ScalarType(ScalarTypeKind.INT, 4),
            ),
        ),
        value_facts=(
            ValueScalarTypeFact(
                value=SSAName(SSANameKind.REGISTER, 10, 0, 4),
                scalar_type=ScalarType(ScalarTypeKind.POINTER, 4),
            ),
        ),
    )
    scalar_program = ProgramScalarTypeFacts(
        memory=memory_program,
        functions={0x1000: scalar_function},
        pending_entries=memory_program.pending_entries,
        invalidated_entries=memory_program.invalidated_entries,
    )
    layout = AggregateLayout(
        root=AggregateRoot(
            kind=AggregateRootKind.POINTER,
            pointer_value=SSAName(SSANameKind.REGISTER, 10, 0, 4),
            stride=8,
        ),
        fields=(
            AggregateField(
                offset=0,
                scalar_type=ScalarType(ScalarTypeKind.INT, 4),
                partitions=(field_partition,),
            ),
        ),
    )
    function = FunctionAggregateTypeFacts(
        scalar_types=scalar_program.functions[0x1000],
        layouts=(layout,),
    )
    return ProgramAggregateTypeFacts(
        scalar_types=scalar_program,
        functions={0x1000: function},
        pending_entries=scalar_program.pending_entries,
        invalidated_entries=scalar_program.invalidated_entries,
    )


def test_variable_model_pretty_output_is_stable() -> None:
    aggregate_program = _variable_program()
    aggregate_function = aggregate_program.functions[0x1000]
    slot_partition = aggregate_function.scalar_types.memory.partitions[0]
    layout = aggregate_function.layouts[0]

    binding = VariableBinding(
        kind=VariableBindingKind.STACK_SLOT,
        stack_slot=slot_partition.stack_slot,
    )
    variable = RecoveredVariable(
        name="arg_x10_4",
        kind=VariableKind.PARAMETER,
        size=4,
        binding=binding,
        scalar_type=ScalarType(ScalarTypeKind.POINTER, 4),
        root_value=SSAName(SSANameKind.REGISTER, 10, 0, 4),
        aggregate_layout=layout,
        partitions=(slot_partition, layout.fields[0].partitions[0]),
    )
    function = FunctionVariableFacts(
        aggregate_types=aggregate_function,
        variables=(variable,),
    )
    program = ProgramVariableFacts(
        aggregate_types=aggregate_program,
        functions={0x1000: function},
        pending_entries=aggregate_program.pending_entries,
        invalidated_entries=aggregate_program.invalidated_entries,
    )

    assert (
        format_variable_binding(binding)
        == "stack_slot -12 size=4 role=argument_home(x10)"
    )
    assert (
        format_recovered_variable(variable)
        == "variable arg_x10_4 kind=parameter size=4 "
        "binding=stack_slot -12 size=4 role=argument_home(x10) "
        "type=pointer:4 root=x10_0:4 aggregate_fields=1 partitions=2\n"
        "  aggregate pointer x10_0:4 stride=8 fields=1\n"
        "    field +0 size=4 type=int:4 partitions=[value u0_0:4 offset=+0 size=4]"
    )

    function_rendered = format_function_variable_facts(function)
    program_rendered = format_program_variable_facts(program)

    assert function_rendered == format_function_variable_facts(function)
    assert "variables=1" in function_rendered
    assert program_rendered == format_program_variable_facts(program)
    assert "pending: 0x2000" in program_rendered
    assert "invalidated: 0x1000" in program_rendered


def test_partition_binding_must_be_listed_in_variable_partitions() -> None:
    aggregate_program = _variable_program()
    partition = aggregate_program.functions[0x1000].scalar_types.memory.partitions[1]

    try:
        RecoveredVariable(
            name="deref_u0_0_p0_4",
            kind=VariableKind.INDIRECT,
            size=4,
            binding=VariableBinding(
                kind=VariableBindingKind.PARTITION,
                partition=partition,
            ),
            scalar_type=ScalarType(ScalarTypeKind.INT, 4),
            partitions=(),
        )
    except ValueError as exc:
        assert str(exc) == "partition-bound variables must include the binding partition"
    else:
        raise AssertionError("expected partition binding validation failure")
