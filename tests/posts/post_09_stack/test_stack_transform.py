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
from tiny_dec.analysis.stack import analyze_program_stack
from tiny_dec.decode import decode_rv32i
from tiny_dec.disasm.models import BlockTerminator
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
    terminator: BlockTerminator = BlockTerminator.RETURN,
) -> CanonicalBlock:
    return CanonicalBlock(
        start=start,
        instructions=instructions,
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


def test_analyze_program_stack_recovers_frame_pointer_and_slot_roles() -> None:
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
                        inputs=(register_varnode(2), const_varnode(12)),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.STORE,
                        inputs=(unique_varnode(0), register_varnode(1)),
                    ),
                ),
                _instruction(
                    0x1008,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(2), const_varnode(8)),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.STORE,
                        inputs=(unique_varnode(0), register_varnode(8)),
                    ),
                ),
                _instruction(
                    0x100C,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(2), const_varnode(16)),
                        output=register_varnode(8),
                    ),
                ),
                _instruction(
                    0x1010,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(8), const_varnode(-12)),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.STORE,
                        inputs=(unique_varnode(0), register_varnode(10)),
                    ),
                ),
                _instruction(
                    0x1014,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(8), const_varnode(-16)),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.STORE,
                        inputs=(unique_varnode(0), register_varnode(11)),
                    ),
                ),
            ),
        ),
    )

    stack = analyze_program_stack(_calls_program(0x1000, (function,)))
    facts = stack.functions[0x1000]

    assert facts.frame_size == 16
    assert facts.frame_pointer is not None
    assert facts.frame_pointer.register == 8
    assert facts.frame_pointer.frame_top_delta == 0
    assert facts.dynamic_stack_pointer is False
    assert [(slot.frame_offset, slot.role.value) for slot in facts.slots] == [
        (-16, "argument_home"),
        (-12, "argument_home"),
        (-8, "saved_register"),
        (-4, "saved_register"),
    ]
    assert facts.slots[0].argument_register == 11
    assert facts.slots[1].argument_register == 10
    assert facts.slots[2].saved_register == 8
    assert facts.slots[3].saved_register == 1


def test_analyze_program_stack_recovers_sp_relative_slots_without_frame_pointer() -> None:
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
                        inputs=(register_varnode(2), const_varnode(12)),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.STORE,
                        inputs=(unique_varnode(0), register_varnode(1)),
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
                        opcode=PcodeOpcode.STORE,
                        inputs=(unique_varnode(0), register_varnode(10)),
                    ),
                ),
            ),
        ),
    )

    stack = analyze_program_stack(_calls_program(0x1000, (function,)))
    facts = stack.functions[0x1000]

    assert facts.frame_size == 16
    assert facts.frame_pointer is None
    assert [(slot.frame_offset, slot.role.value) for slot in facts.slots] == [
        (-16, "argument_home"),
        (-4, "saved_register"),
    ]
    assert facts.slots[0].argument_register == 10
    assert facts.slots[1].saved_register == 1


def test_analyze_program_stack_marks_dynamic_stack_pointer_for_unsupported_x2_update() -> None:
    function = _function(
        0x1000,
        (
            _block(
                0x1000,
                _instruction(
                    0x1000,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(2), register_varnode(10)),
                        output=register_varnode(2),
                    ),
                ),
            ),
        ),
    )

    stack = analyze_program_stack(_calls_program(0x1000, (function,)))
    facts = stack.functions[0x1000]

    assert facts.frame_size is None
    assert facts.frame_pointer is None
    assert facts.dynamic_stack_pointer is True
    assert facts.slots == ()


def test_analyze_program_stack_preserves_upstream_queue_state() -> None:
    function = _function(0x1000, (_block(0x1000, _instruction(0x1000)),))

    stack = analyze_program_stack(
        _calls_program(
            0x1000,
            (function,),
            pending_entries=(0x4000,),
            invalidated_entries=(0x1000,),
        )
    )

    assert stack.pending_entries == (0x4000,)
    assert stack.invalidated_entries == (0x1000,)
