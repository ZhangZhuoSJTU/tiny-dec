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
    format_function_memory_facts,
    format_memory_access,
    format_memory_partition,
    format_program_memory_facts,
)
from tiny_dec.analysis.simplify import (
    CanonicalBlock,
    CanonicalFunctionIR,
    CanonicalInstruction,
    CanonicalProgramIR,
)
from tiny_dec.analysis.ssa import construct_program_ssa
from tiny_dec.analysis.ssa.models import MemoryVersion, SSAName, SSANameKind
from tiny_dec.analysis.stack import (
    FunctionStackFacts,
    ProgramStackFacts,
    StackAccess,
    StackAccessKind,
    StackBaseKind,
    StackSlot,
    StackSlotRole,
)
from tiny_dec.decode import decode_rv32i
from tiny_dec.disasm.models import BlockTerminator
from tiny_dec.ir.pcode import PcodeOp


def _instruction(address: int, *ops: PcodeOp) -> CanonicalInstruction:
    return CanonicalInstruction(
        instruction=decode_rv32i(0x00000013, address),
        ops=ops,
    )


def _stack_program() -> ProgramStackFacts:
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
    function = FunctionStackFacts(
        calls=calls.functions[0x1000],
        frame_size=16,
        dynamic_stack_pointer=False,
        slots=(stack_slot,),
    )
    return ProgramStackFacts(
        calls=calls,
        functions={0x1000: function},
        pending_entries=calls.pending_entries,
        invalidated_entries=calls.invalidated_entries,
    )


def test_memory_model_pretty_output_is_stable() -> None:
    stack_program = _stack_program()
    stack_function = stack_program.functions[0x1000]
    stack_slot = stack_function.slots[0]

    stack_partition = MemoryPartition(
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
                memory_before=MemoryVersion(0),
                memory_after=MemoryVersion(1),
            ),
        ),
    )
    absolute_partition = MemoryPartition(
        kind=MemoryPartitionKind.ABSOLUTE,
        size=4,
        absolute_address=0x2000,
        accesses=(
            MemoryAccess(
                instruction_address=0x1008,
                block_start=0x1000,
                kind=MemoryAccessKind.LOAD,
                size=4,
                value=SSAName(SSANameKind.REGISTER, 11, 1, 4),
                memory_before=MemoryVersion(1),
            ),
        ),
    )
    value_partition = MemoryPartition(
        kind=MemoryPartitionKind.VALUE,
        size=4,
        base_value=SSAName(SSANameKind.REGISTER, 10, 0, 4),
        offset=4,
        accesses=(
            MemoryAccess(
                instruction_address=0x100C,
                block_start=0x1000,
                kind=MemoryAccessKind.LOAD,
                size=4,
                value=SSAName(SSANameKind.REGISTER, 12, 1, 4),
                memory_before=MemoryVersion(1),
            ),
        ),
    )
    function = FunctionMemoryFacts(
        stack=stack_function,
        partitions=(stack_partition, absolute_partition, value_partition),
    )
    program = ProgramMemoryFacts(
        stack=stack_program,
        functions={0x1000: function},
        pending_entries=stack_program.pending_entries,
        invalidated_entries=stack_program.invalidated_entries,
    )

    assert format_memory_access(stack_partition.accesses[0]) == (
        "store 0x1004 block=0x1000 size=4 value=x10_0:4 [m0 -> m1]"
    )
    assert format_memory_partition(stack_partition) == (
        "stack_slot -12 size=4 role=argument_home(x10) accesses=1"
    )
    assert format_memory_partition(absolute_partition) == (
        "absolute 0x2000 size=4 accesses=1"
    )
    assert format_memory_partition(value_partition) == (
        "value x10_0:4 offset=+4 size=4 accesses=1"
    )

    function_rendered = format_function_memory_facts(function)
    program_rendered = format_program_memory_facts(program)

    assert function_rendered == format_function_memory_facts(function)
    assert "frame_size=16" in function_rendered
    assert "partitions=3" in function_rendered
    assert "accesses=3" in function_rendered

    assert program_rendered == format_program_memory_facts(program)
    assert "pending: 0x2000" in program_rendered
    assert "invalidated: 0x1000" in program_rendered
    assert "call_graph:" in program_rendered


def test_memory_partition_details_are_validated() -> None:
    access = MemoryAccess(
        instruction_address=0x1000,
        block_start=0x1000,
        kind=MemoryAccessKind.LOAD,
        size=4,
        value=SSAName(SSANameKind.REGISTER, 10, 1, 4),
    )

    try:
        MemoryPartition(
            kind=MemoryPartitionKind.VALUE,
            size=4,
            accesses=(access,),
        )
    except ValueError as exc:
        assert str(exc) == "value memory partitions must carry a base value"
    else:
        raise AssertionError("expected value-partition validation failure")


def test_memory_access_requires_memory_before_when_memory_after_is_present() -> None:
    try:
        MemoryAccess(
            instruction_address=0x1000,
            block_start=0x1000,
            kind=MemoryAccessKind.STORE,
            size=4,
            value=SSAName(SSANameKind.REGISTER, 10, 1, 4),
            memory_after=MemoryVersion(1),
        )
    except ValueError as exc:
        assert str(exc) == "memory access memory_after requires memory_before"
    else:
        raise AssertionError("expected memory-access validation failure")
