from __future__ import annotations

import pytest

from tiny_dec.decode import decode_rv32i
from tiny_dec.disasm.models import BasicBlock, BlockInstruction, BlockTerminator, DisasmFunction
from tiny_dec.ir.function_ir import CallSite, FunctionIR
from tiny_dec.ir.lift_rv32i import lift_instruction
from tiny_dec.ir.pretty_containers import format_function_ir, format_program_ir
from tiny_dec.ir.program_ir import CallGraphEdge, CallGraphEdgeKind, ProgramIR
from tiny_dec.loader import ExternalFunction


def _lifted(word: int, address: int) -> BlockInstruction:
    instruction = decode_rv32i(word, address)
    return BlockInstruction(
        instruction=instruction,
        pcode_ops=tuple(lift_instruction(instruction)),
    )


def _sample_disasm() -> DisasmFunction:
    block = BasicBlock(
        start=0x1000,
        instructions=(
            _lifted(0x100000ef, 0x1000),
            _lifted(0x00008067, 0x1004),
        ),
        terminator=BlockTerminator.RETURN,
        call_targets=(0x1100,),
    )
    return DisasmFunction(entry=0x1000, blocks={0x1000: block}, discovery_order=(0x1000,))


def test_callsite_validates_direct_and_indirect_shapes() -> None:
    direct = CallSite(
        instruction_address=0x1000,
        block_start=0x1000,
        target=0x1100,
        target_name="helper",
    )
    indirect = CallSite(
        instruction_address=0x1004,
        block_start=0x1000,
        is_indirect=True,
    )

    assert direct.to_pretty() == "call 0x1000 block=0x1000 -> 0x1100 name=helper"
    assert indirect.to_pretty() == "call 0x1004 block=0x1000 -> <indirect>"

    with pytest.raises(ValueError, match="indirect callsite must not carry a direct target"):
        CallSite(
            instruction_address=0x1008,
            block_start=0x1000,
            target=0x1200,
            is_indirect=True,
        )


def test_function_ir_rejects_instruction_index_drift() -> None:
    disasm = _sample_disasm()

    with pytest.raises(ValueError, match="instruction index must match disassembly instruction order"):
        FunctionIR(
            entry=0x1000,
            name="main",
            disasm=disasm,
            instruction_index={0x1004: disasm.blocks[0x1000].instructions[1]},
            return_blocks=(0x1000,),
            direct_callees=(0x1100,),
        )


def test_function_ir_pretty_is_deterministic_and_includes_nested_disasm() -> None:
    disasm = _sample_disasm()
    function = FunctionIR(
        entry=0x1000,
        name="main",
        disasm=disasm,
        instruction_index={
            0x1000: disasm.blocks[0x1000].instructions[0],
            0x1004: disasm.blocks[0x1000].instructions[1],
        },
        callsites=(
            CallSite(
                instruction_address=0x1000,
                block_start=0x1000,
                target=0x1100,
                target_name="helper",
            ),
        ),
        return_blocks=(0x1000,),
        direct_callees=(0x1100,),
    )

    rendered = format_function_ir(function)

    assert rendered == format_function_ir(function)
    assert rendered.startswith("function 0x1000 name=main")
    assert "callsites:" in rendered
    assert "instructions: 0x1000, 0x1004" in rendered
    assert "disasm:" in rendered
    assert "block 0x1000" in rendered


def test_program_ir_pretty_includes_edges_and_functions() -> None:
    disasm = _sample_disasm()
    function = FunctionIR(
        entry=0x1000,
        name="main",
        disasm=disasm,
        instruction_index={
            0x1000: disasm.blocks[0x1000].instructions[0],
            0x1004: disasm.blocks[0x1000].instructions[1],
        },
        callsites=(
            CallSite(
                instruction_address=0x1000,
                block_start=0x1000,
                target=0x1100,
                target_name="helper",
            ),
        ),
        return_blocks=(0x1000,),
        direct_callees=(0x1100,),
    )
    program = ProgramIR(
        root_entry=0x1000,
        functions={0x1000: function},
        discovery_order=(0x1000,),
        externals=(
            ExternalFunction(
                name="puts",
                plt_address=0x2000,
                got_address=None,
                symbol_address=None,
            ),
        ),
        call_graph=(
            CallGraphEdge(
                caller=0x1000,
                callsite_address=0x1000,
                kind=CallGraphEdgeKind.INTERNAL,
                callee_address=0x1100,
            ),
        ),
    )

    rendered = format_program_ir(program)

    assert rendered == format_program_ir(program)
    assert "root: 0x1000" in rendered
    assert "externals:" in rendered
    assert "puts" in rendered
    assert "call_graph:" in rendered
    assert "0x1000@0x1000 -> internal 0x1100" in rendered
    assert "functions:" in rendered
