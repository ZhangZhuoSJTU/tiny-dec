from __future__ import annotations

from tiny_dec.analysis.calls import analyze_program_calls
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
from tiny_dec.analysis.ssa import construct_program_ssa
from tiny_dec.analysis.stack import (
    FunctionStackFacts,
    ProgramStackFacts,
    StackAccess,
    StackAccessKind,
    StackBaseKind,
    StackFrameBase,
    StackSlot,
    StackSlotRole,
    format_function_stack_facts,
    format_program_stack_facts,
    format_stack_access,
    format_stack_frame_base,
    format_stack_slot,
)
from tiny_dec.analysis.ssa.models import SSAName, SSANameKind
from tiny_dec.decode import decode_rv32i
from tiny_dec.disasm.models import BlockTerminator
from tiny_dec.ir.pcode import PcodeOp


def _instruction(address: int, *ops: PcodeOp) -> CanonicalInstruction:
    return CanonicalInstruction(
        instruction=decode_rv32i(0x00000013, address),
        ops=ops,
    )


def _function(entry: int) -> FunctionDataflowFacts:
    instruction = _instruction(0x1000)
    block = CanonicalBlock(
        start=entry,
        instructions=(instruction,),
        terminator=BlockTerminator.RETURN,
    )
    canonical = CanonicalFunctionIR(
        entry=entry,
        name="main",
        blocks={entry: block},
        discovery_order=(entry,),
        instruction_index={instruction.address: instruction},
        return_blocks=(entry,),
    )
    return FunctionDataflowFacts(
        function=canonical,
        blocks={
            entry: BlockDataflowFacts(
                start=entry,
                in_state=RegisterState(),
                out_state=RegisterState(),
            )
        },
    )


def _call_facts() -> ProgramStackFacts:
    function = _function(0x1000)
    canonical_program = CanonicalProgramIR(
        root_entry=0x1000,
        functions={0x1000: function.function},
        discovery_order=(0x1000,),
    )
    dataflow_program = ProgramDataflowFacts(
        program=canonical_program,
        functions={0x1000: function},
        pending_entries=(0x2000,),
        invalidated_entries=(0x1000,),
    )
    calls = analyze_program_calls(construct_program_ssa(dataflow_program))

    frame_pointer = StackFrameBase(
        kind=StackBaseKind.FRAME_POINTER,
        register=8,
        value=SSAName(SSANameKind.REGISTER, 8, 1, 4),
        frame_top_delta=0,
    )
    access = StackAccess(
        instruction_address=0x1004,
        block_start=0x1000,
        kind=StackAccessKind.STORE,
        frame_offset=-4,
        size=4,
        base_kind=StackBaseKind.FRAME_POINTER,
        base_register=8,
        value=SSAName(SSANameKind.REGISTER, 1, 0, 4),
    )
    slot = StackSlot(
        frame_offset=-4,
        size=4,
        role=StackSlotRole.SAVED_REGISTER,
        saved_register=1,
        accesses=(access,),
    )
    function_facts = FunctionStackFacts(
        calls=calls.functions[0x1000],
        frame_size=16,
        frame_pointer=frame_pointer,
        dynamic_stack_pointer=False,
        slots=(slot,),
    )
    return ProgramStackFacts(
        calls=calls,
        functions={0x1000: function_facts},
        pending_entries=calls.pending_entries,
        invalidated_entries=calls.invalidated_entries,
    )


def test_stack_model_pretty_output_is_stable() -> None:
    program = _call_facts()
    function = program.functions[0x1000]
    frame_pointer = function.frame_pointer
    assert frame_pointer is not None
    slot = function.slots[0]
    access = slot.accesses[0]

    assert format_stack_frame_base(frame_pointer) == (
        "frame_pointer x8=x8_1:4 delta=+0"
    )
    assert format_stack_access(access) == (
        "store 0x1004 block=0x1000 slot=-4 size=4 "
        "via=frame_pointer(x8) value=x1_0:4"
    )
    assert format_stack_slot(slot) == "slot -4 size=4 role=saved_register(x1) accesses=1"

    function_rendered = format_function_stack_facts(function)
    program_rendered = format_program_stack_facts(program)

    assert function_rendered == format_function_stack_facts(function)
    assert "frame_size=16" in function_rendered
    assert "pending=[]" in function_rendered
    assert "role=saved_register(x1)" in function_rendered

    assert program_rendered == format_program_stack_facts(program)
    assert "pending: 0x2000" in program_rendered
    assert "invalidated: 0x1000" in program_rendered
    assert "call_graph:" in program_rendered


def test_stack_slot_role_details_are_validated() -> None:
    access = StackAccess(
        instruction_address=0x1000,
        block_start=0x1000,
        kind=StackAccessKind.LOAD,
        frame_offset=-8,
        size=4,
        base_kind=StackBaseKind.STACK_POINTER,
        base_register=2,
        value=SSAName(SSANameKind.REGISTER, 8, 2, 4),
    )

    try:
        StackSlot(
            frame_offset=-8,
            size=4,
            role=StackSlotRole.SAVED_REGISTER,
            accesses=(access,),
        )
    except ValueError as exc:
        assert str(exc) == "saved-register slots must carry only a saved register detail"
    else:
        raise AssertionError("expected slot role validation failure")
