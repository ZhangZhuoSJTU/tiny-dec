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
from tiny_dec.analysis.types import analyze_program_aggregate_types, analyze_program_scalar_types
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



def test_analyze_program_aggregate_types_recovers_root_stride_and_fields() -> None:
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
                        opcode=PcodeOpcode.COPY,
                        inputs=(register_varnode(13),),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.LOAD,
                        inputs=(unique_varnode(0),),
                        output=register_varnode(14),
                    ),
                ),
                _instruction(
                    0x100C,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(13), const_varnode(4)),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.LOAD,
                        inputs=(unique_varnode(0),),
                        output=register_varnode(15),
                    ),
                ),
                _instruction(
                    0x1010,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(14), register_varnode(15)),
                        output=register_varnode(16),
                    ),
                ),
                _instruction(
                    0x1014,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_SLESS,
                        inputs=(register_varnode(16), register_varnode(15)),
                        output=unique_varnode(0, size=1),
                    ),
                ),
            ),
        ),
    )

    program = analyze_program_aggregate_types(
        analyze_program_scalar_types(
            analyze_program_memory(analyze_program_stack(_calls_program(0x1000, (function,))))
        )
    )
    facts = program.functions[0x1000]

    assert len(facts.layouts) == 1
    layout = facts.layouts[0]
    assert layout.root.pointer_value is not None
    assert layout.root.pointer_value.to_pretty() == "x10_0:4"
    assert layout.root.stride is None
    assert [
        (field.offset, field.scalar_type.to_pretty())
        for field in layout.fields
    ] == [(0, "int:4"), (4, "int:4")]



def test_analyze_program_aggregate_types_preserves_upstream_queue_state() -> None:
    function = _function(0x1000, (_block(0x1000, _instruction(0x1000)),))

    program = analyze_program_aggregate_types(
        analyze_program_scalar_types(
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
    )

    assert program.pending_entries == (0x4000,)
    assert program.invalidated_entries == (0x1000,)
