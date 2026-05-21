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
    FunctionScalarTypeFacts,
    PartitionScalarTypeFact,
    ProgramScalarTypeFacts,
    ScalarType,
    ScalarTypeKind,
    ValueScalarTypeFact,
    format_function_scalar_type_facts,
    format_partition_scalar_type_fact,
    format_program_scalar_type_facts,
    format_scalar_type,
    format_value_scalar_type_fact,
)
from tiny_dec.decode import decode_rv32i
from tiny_dec.disasm.models import BlockTerminator
from tiny_dec.ir.pcode import PcodeOp


def _instruction(address: int, *ops: PcodeOp) -> CanonicalInstruction:
    return CanonicalInstruction(
        instruction=decode_rv32i(0x00000013, address),
        ops=ops,
    )


def _memory_program() -> ProgramMemoryFacts:
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
        kind=MemoryPartitionKind.STACK_SLOT,
        size=4,
        stack_slot=stack_slot,
        accesses=(
            MemoryAccess(
                instruction_address=0x1004,
                block_start=0x1000,
                kind=MemoryAccessKind.STORE,
                size=4,
                value=SSAName(SSANameKind.REGISTER, 10, 0, 4),
            ),
        ),
    )
    function = FunctionMemoryFacts(
        stack=stack_function,
        partitions=(partition,),
    )
    return ProgramMemoryFacts(
        stack=stack_program,
        functions={0x1000: function},
        pending_entries=stack_program.pending_entries,
        invalidated_entries=stack_program.invalidated_entries,
    )


def test_scalar_type_model_pretty_output_is_stable() -> None:
    memory_program = _memory_program()
    memory_function = memory_program.functions[0x1000]
    partition = memory_function.partitions[0]

    partition_fact = PartitionScalarTypeFact(
        partition=partition,
        scalar_type=ScalarType(ScalarTypeKind.POINTER, 4),
    )
    value_fact = ValueScalarTypeFact(
        value=SSAName(SSANameKind.REGISTER, 10, 0, 4),
        scalar_type=ScalarType(ScalarTypeKind.POINTER, 4),
    )
    function = FunctionScalarTypeFacts(
        memory=memory_function,
        partition_facts=(partition_fact,),
        value_facts=(value_fact,),
    )
    program = ProgramScalarTypeFacts(
        memory=memory_program,
        functions={0x1000: function},
        pending_entries=memory_program.pending_entries,
        invalidated_entries=memory_program.invalidated_entries,
    )

    assert format_scalar_type(ScalarType(ScalarTypeKind.BOOL, 1)) == "bool:1"
    assert format_partition_scalar_type_fact(partition_fact) == (
        "stack_slot -12 size=4 role=argument_home(x10) type=pointer:4"
    )
    assert format_value_scalar_type_fact(value_fact) == "x10_0:4 type=pointer:4"

    function_rendered = format_function_scalar_type_facts(function)
    program_rendered = format_program_scalar_type_facts(program)

    assert function_rendered == format_function_scalar_type_facts(function)
    assert "typed_partitions=1" in function_rendered
    assert "typed_values=1" in function_rendered

    assert program_rendered == format_program_scalar_type_facts(program)
    assert "pending: 0x2000" in program_rendered
    assert "invalidated: 0x1000" in program_rendered


def test_scalar_type_facts_validate_widths() -> None:
    memory_program = _memory_program()
    partition = memory_program.functions[0x1000].partitions[0]

    try:
        PartitionScalarTypeFact(
            partition=partition,
            scalar_type=ScalarType(ScalarTypeKind.BOOL, 1),
        )
    except ValueError as exc:
        assert str(exc) == "partition scalar type width must match partition size"
    else:
        raise AssertionError("expected partition width validation failure")
