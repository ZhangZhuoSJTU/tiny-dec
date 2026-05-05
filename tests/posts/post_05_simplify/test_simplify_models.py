from __future__ import annotations

import pytest

from tiny_dec.analysis.simplify import (
    CanonicalBlock,
    CanonicalFunctionIR,
    CanonicalInstruction,
    CanonicalProgramIR,
    format_canonical_function_ir,
    format_canonical_program_ir,
)
from tiny_dec.decode import decode_rv32i
from tiny_dec.disasm.models import BlockTerminator
from tiny_dec.ir.function_ir import CallSite
from tiny_dec.ir.pcode import PcodeOp, PcodeOpcode, const_varnode, register_varnode, unique_varnode
from tiny_dec.ir.program_ir import CallGraphEdge, CallGraphEdgeKind
from tiny_dec.loader import ExternalFunction


def _insn(word: int, address: int) -> CanonicalInstruction:
    return CanonicalInstruction(
        instruction=decode_rv32i(word, address),
        ops=(
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(const_varnode(4),),
                output=register_varnode(1),
            ),
        ),
    )


def test_canonical_instruction_rejects_sparse_unique_offsets() -> None:
    with pytest.raises(
        ValueError,
        match="unique varnodes must be renumbered densely",
    ):
        CanonicalInstruction(
            instruction=decode_rv32i(0x00410093, 0x1000),
            ops=(
                PcodeOp(
                    opcode=PcodeOpcode.COPY,
                    inputs=(const_varnode(4),),
                    output=unique_varnode(4),
                ),
            ),
        )


def test_canonical_function_pretty_is_deterministic_and_includes_blocks() -> None:
    instruction = _insn(0x00410093, 0x1000)
    block = CanonicalBlock(
        start=0x1000,
        instructions=(instruction,),
        terminator=BlockTerminator.RETURN,
    )
    function = CanonicalFunctionIR(
        entry=0x1000,
        name="main",
        blocks={0x1000: block},
        discovery_order=(0x1000,),
        instruction_index={0x1000: instruction},
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

    rendered = format_canonical_function_ir(function)

    assert rendered == format_canonical_function_ir(function)
    assert rendered.startswith("function 0x1000 name=main")
    assert "callsites:" in rendered
    assert "blocks:" in rendered
    assert "COPY register[0x1:4] <- const[0x4:4]" in rendered


def test_canonical_program_pretty_includes_edges_and_functions() -> None:
    instruction = _insn(0x00410093, 0x1000)
    block = CanonicalBlock(
        start=0x1000,
        instructions=(instruction,),
        terminator=BlockTerminator.RETURN,
    )
    function = CanonicalFunctionIR(
        entry=0x1000,
        name="main",
        blocks={0x1000: block},
        discovery_order=(0x1000,),
        instruction_index={0x1000: instruction},
        return_blocks=(0x1000,),
        direct_callees=(0x1100,),
    )
    program = CanonicalProgramIR(
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

    rendered = format_canonical_program_ir(program)

    assert rendered == format_canonical_program_ir(program)
    assert "root: 0x1000" in rendered
    assert "externals:" in rendered
    assert "puts" in rendered
    assert "call_graph:" in rendered
    assert "0x1000@0x1000 -> internal 0x1100" in rendered
    assert "functions:" in rendered
