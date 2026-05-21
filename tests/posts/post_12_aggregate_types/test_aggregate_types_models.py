from __future__ import annotations

from tiny_dec.analysis.calls import analyze_program_calls
from tiny_dec.analysis.dataflow import (
    BlockDataflowFacts,
    FunctionDataflowFacts,
    ProgramDataflowFacts,
    RegisterState,
)
from tiny_dec.analysis.memory import (
    FunctionMemoryFacts,
    MemoryAccess,
    MemoryAccessKind,
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
    format_aggregate_field,
    format_aggregate_layout,
    format_aggregate_root,
    format_function_aggregate_type_facts,
    format_program_aggregate_type_facts,
)
from tiny_dec.decode import decode_rv32i
from tiny_dec.disasm.models import BlockTerminator
from tiny_dec.ir.pcode import PcodeOp


def _instruction(address: int, *ops: PcodeOp) -> CanonicalInstruction:
    return CanonicalInstruction(
        instruction=decode_rv32i(0x00000013, address),
        ops=ops,
    )


def _scalar_program() -> ProgramScalarTypeFacts:
    instruction = _instruction(0x1000)
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

    stack_access = StackAccess(
        instruction_address=0x1004,
        block_start=0x1000,
        kind=StackAccessKind.STORE,
        frame_offset=-12,
        size=4,
        base_kind=StackBaseKind.FRAME_POINTER,
        base_register=8,
        value=SSAName(SSANameKind.REGISTER, 10, 0, 4),
    )
    stack_slot = StackSlot(
        frame_offset=-12,
        size=4,
        role=StackSlotRole.ARGUMENT_HOME,
        argument_register=10,
        accesses=(stack_access,),
    )
    stack_function = FunctionStackFacts(
        calls=calls.functions[0x1000],
        frame_size=16,
        dynamic_stack_pointer=False,
        slots=(stack_slot,),
    )
    stack_program = ProgramStackFacts(
        calls=calls,
        functions={0x1000: stack_function},
        pending_entries=calls.pending_entries,
        invalidated_entries=calls.invalidated_entries,
    )
    partition = MemoryPartition(
        kind=MemoryPartitionKind.VALUE,
        size=4,
        base_value=SSAName(SSANameKind.UNIQUE, 0, 0, 4),
        accesses=(
            MemoryAccess(
                instruction_address=0x1004,
                block_start=0x1000,
                kind=MemoryAccessKind.LOAD,
                size=4,
                value=SSAName(SSANameKind.REGISTER, 11, 0, 4),
            ),
        ),
    )
    memory_function = FunctionMemoryFacts(
        stack=stack_function,
        partitions=(partition,),
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
                partition=partition,
                scalar_type=ScalarType(ScalarTypeKind.INT, 4),
            ),
        ),
        value_facts=(),
    )
    return ProgramScalarTypeFacts(
        memory=memory_program,
        functions={0x1000: scalar_function},
        pending_entries=memory_program.pending_entries,
        invalidated_entries=memory_program.invalidated_entries,
    )



def test_aggregate_type_model_pretty_output_is_stable() -> None:
    scalar_program = _scalar_program()
    partition = scalar_program.functions[0x1000].memory.partitions[0]

    root = AggregateRoot(
        kind=AggregateRootKind.POINTER,
        pointer_value=SSAName(SSANameKind.REGISTER, 10, 0, 4),
        stride=8,
    )
    field = AggregateField(
        offset=0,
        scalar_type=ScalarType(ScalarTypeKind.INT, 4),
        partitions=(partition,),
    )
    layout = AggregateLayout(root=root, fields=(field,))
    function = FunctionAggregateTypeFacts(
        scalar_types=scalar_program.functions[0x1000],
        layouts=(layout,),
    )
    program = ProgramAggregateTypeFacts(
        scalar_types=scalar_program,
        functions={0x1000: function},
        pending_entries=scalar_program.pending_entries,
        invalidated_entries=scalar_program.invalidated_entries,
    )

    assert format_aggregate_root(root) == "pointer x10_0:4 stride=8"
    assert format_aggregate_field(field) == (
        "field +0 size=4 type=int:4 partitions=[value u0_0:4 offset=+0 size=4]"
    )
    assert "aggregate pointer x10_0:4 stride=8 fields=1" in format_aggregate_layout(layout)

    function_rendered = format_function_aggregate_type_facts(function)
    program_rendered = format_program_aggregate_type_facts(program)

    assert function_rendered == format_function_aggregate_type_facts(function)
    assert "aggregates=1" in function_rendered

    assert program_rendered == format_program_aggregate_type_facts(program)
    assert "pending: 0x2000" in program_rendered
    assert "invalidated: 0x1000" in program_rendered



def test_aggregate_field_validates_widths() -> None:
    scalar_program = _scalar_program()
    partition = scalar_program.functions[0x1000].memory.partitions[0]

    try:
        AggregateField(
            offset=0,
            scalar_type=ScalarType(ScalarTypeKind.BOOL, 1),
            partitions=(partition,),
        )
    except ValueError as exc:
        assert str(exc) == "aggregate field width must match referenced partitions"
    else:
        raise AssertionError("expected aggregate field width validation failure")
