from __future__ import annotations

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
from tiny_dec.analysis.ssa import (
    MemoryVersion,
    SSABlock,
    SSAFunctionIR,
    SSAInstruction,
    SSAMemoryPhiInput,
    SSAMemoryPhiNode,
    SSAName,
    SSANameKind,
    SSAOp,
    SSAProgramIR,
    SSAPhiInput,
    SSAPhiNode,
    format_ssa_function_ir,
    format_ssa_program_ir,
)
from tiny_dec.decode import decode_rv32i
from tiny_dec.disasm.models import BlockTerminator
from tiny_dec.ir.pcode import PcodeOpcode, const_varnode
from tiny_dec.ir.program_ir import CallGraphEdge, CallGraphEdgeKind
from tiny_dec.loader import ExternalFunction


def _instruction(address: int) -> CanonicalInstruction:
    return CanonicalInstruction(
        instruction=decode_rv32i(0x00000013, address),
        ops=(),
    )


def test_ssa_name_and_phi_pretty_are_stable() -> None:
    register_name = SSAName(SSANameKind.REGISTER, 10, 3, 4)
    unique_name = SSAName(SSANameKind.UNIQUE, 0, 2, 4)
    memory = MemoryVersion(0)
    phi = SSAPhiNode(
        output=register_name,
        inputs=(
            SSAPhiInput(predecessor=0x1010, value=SSAName(SSANameKind.REGISTER, 10, 1, 4)),
            SSAPhiInput(predecessor=0x1020, value=SSAName(SSANameKind.REGISTER, 10, 2, 4)),
        ),
    )
    memory_phi = SSAMemoryPhiNode(
        output=MemoryVersion(2),
        inputs=(
            SSAMemoryPhiInput(predecessor=0x1010, value=MemoryVersion(0)),
            SSAMemoryPhiInput(predecessor=0x1020, value=MemoryVersion(1)),
        ),
    )
    op = SSAOp(
        opcode=PcodeOpcode.INT_ADD,
        inputs=(register_name, const_varnode(1)),
        output=unique_name,
    )
    load = SSAOp(
        opcode=PcodeOpcode.LOAD,
        inputs=(unique_name,),
        output=register_name,
        memory_before=memory,
    )

    assert memory.to_pretty() == "m0"
    assert register_name.to_pretty() == "x10_3:4"
    assert unique_name.to_pretty() == "u0_2:4"
    assert phi.to_pretty() == "PHI x10_3:4 <- 0x1010:x10_1:4, 0x1020:x10_2:4"
    assert memory_phi.to_pretty() == "MEM_PHI m2 <- 0x1010:m0, 0x1020:m1"
    assert op.to_pretty() == "INT_ADD u0_2:4 <- x10_3:4, const[0x1:4]"
    assert load.to_pretty() == "LOAD x10_3:4 <- u0_2:4 [m0]"


def test_ssa_call_return_op_pretty_is_stable() -> None:
    op = SSAOp(
        opcode="CALL_RETURN",
        inputs=(const_varnode(0x1004),),
        output=SSAName(SSANameKind.REGISTER, 10, 4, 4),
    )

    assert op.to_pretty() == "CALL_RETURN x10_4:4 <- const[0x1004:4]"


def test_ssa_function_and_program_pretty_include_live_ins_and_queue_state() -> None:
    instruction = _instruction(0x1000)
    canonical_block = CanonicalBlock(
        start=0x1000,
        instructions=(instruction,),
        terminator=BlockTerminator.RETURN,
    )
    canonical_function = CanonicalFunctionIR(
        entry=0x1000,
        name="main",
        blocks={0x1000: canonical_block},
        discovery_order=(0x1000,),
        instruction_index={0x1000: instruction},
        return_blocks=(0x1000,),
    )
    dataflow_function = FunctionDataflowFacts(
        function=canonical_function,
        blocks={
            0x1000: BlockDataflowFacts(
                start=0x1000,
                in_state=RegisterState(),
                out_state=RegisterState(),
            )
        },
    )
    ssa_block = SSABlock(
        start=0x1000,
        phis=(
            SSAPhiNode(
                output=SSAName(SSANameKind.REGISTER, 10, 1, 4),
                inputs=(),
            ),
        ),
        memory_phi=SSAMemoryPhiNode(output=MemoryVersion(1), inputs=()),
        instructions=(
            SSAInstruction(
                instruction=instruction.instruction,
                ops=(
                    SSAOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(const_varnode(4),),
                        output=SSAName(SSANameKind.REGISTER, 1, 1, 4),
                    ),
                    SSAOp(
                        opcode=PcodeOpcode.STORE,
                        inputs=(const_varnode(0x2000), SSAName(SSANameKind.REGISTER, 1, 1, 4)),
                        memory_before=MemoryVersion(1),
                        memory_after=MemoryVersion(2),
                    ),
                ),
            ),
        ),
        terminator=BlockTerminator.RETURN,
    )
    ssa_function = SSAFunctionIR(
        dataflow=dataflow_function,
        blocks={0x1000: ssa_block},
        immediate_dominators={0x1000: None},
        dominance_frontiers={0x1000: ()},
        live_ins=(SSAName(SSANameKind.REGISTER, 2, 0, 4),),
        memory_live_in=MemoryVersion(0),
        unreachable_blocks=(),
    )

    canonical_program = CanonicalProgramIR(
        root_entry=0x1000,
        functions={0x1000: canonical_function},
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
    dataflow_program = ProgramDataflowFacts(
        program=canonical_program,
        functions={0x1000: dataflow_function},
        pending_entries=(0x4000,),
        invalidated_entries=(0x1000,),
    )
    ssa_program = SSAProgramIR(
        dataflow=dataflow_program,
        functions={0x1000: ssa_function},
    )

    function_rendered = format_ssa_function_ir(ssa_function)
    program_rendered = format_ssa_program_ir(ssa_program)

    assert function_rendered == format_ssa_function_ir(ssa_function)
    assert "live_ins:" in function_rendered
    assert "x2_0:4" in function_rendered
    assert "memory_live_in:" in function_rendered
    assert "m0" in function_rendered
    assert "MEM_PHI m1" in function_rendered
    assert "PHI x10_1:4" in function_rendered
    assert "COPY x1_1:4 <- const[0x4:4]" in function_rendered
    assert "STORE const[0x2000:4], x1_1:4 [m1 -> m2]" in function_rendered

    assert program_rendered == format_ssa_program_ir(ssa_program)
    assert "pending: 0x4000" in program_rendered
    assert "invalidated: 0x1000" in program_rendered
    assert "puts" in program_rendered
    assert "functions:" in program_rendered
