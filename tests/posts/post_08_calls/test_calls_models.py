from __future__ import annotations

from tiny_dec.analysis.calls import (
    CallRegisterValue,
    CallStackValue,
    FunctionCallFacts,
    KnownExternalSignature,
    ModeledCallSite,
    ProgramCallFacts,
    RV32I_ILP32_CALL_ABI,
    format_call_abi,
    format_function_call_facts,
    format_program_call_facts,
)
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
from tiny_dec.analysis.ssa import SSABlock, SSAFunctionIR, SSAInstruction, SSAProgramIR
from tiny_dec.analysis.ssa.models import MemoryVersion, SSAName, SSANameKind, SSAOp
from tiny_dec.decode import decode_rv32i
from tiny_dec.disasm.models import BlockTerminator
from tiny_dec.ir.function_ir import CallSite
from tiny_dec.ir.pcode import PcodeOpcode, const_varnode
from tiny_dec.ir.program_ir import CallGraphEdge, CallGraphEdgeKind
from tiny_dec.loader import ExternalFunction


def _instruction(address: int) -> CanonicalInstruction:
    return CanonicalInstruction(
        instruction=decode_rv32i(0x00000013, address),
        ops=(),
    )


def test_call_abi_and_modeled_callsite_pretty_are_stable() -> None:
    argument = CallRegisterValue(
        register=10,
        value=SSAName(SSANameKind.REGISTER, 10, 3, 4),
    )
    stack_argument = CallStackValue(
        stack_offset=0,
        value=SSAName(SSANameKind.REGISTER, 18, 1, 4),
    )
    returned = CallRegisterValue(
        register=10,
        value=SSAName(SSANameKind.REGISTER, 10, 4, 4),
    )
    signature = KnownExternalSignature(
        name="malloc",
        parameter_registers=(10,),
        parameter_stack_offsets=(),
        return_registers=(10,),
    )
    callsite = ModeledCallSite(
        instruction_address=0x1004,
        block_start=0x1000,
        target_kind=CallGraphEdgeKind.EXTERNAL,
        target_address=0x1100,
        callee_name="malloc",
        argument_values=(argument,),
        stack_argument_values=(stack_argument,),
        memory_before=MemoryVersion(1),
        memory_after=MemoryVersion(2),
        return_values=(returned,),
        external_signature=signature,
    )

    assert format_call_abi(RV32I_ILP32_CALL_ABI).startswith("rv32i_ilp32 args=[x10, x11")
    assert argument.to_pretty() == "x10=x10_3:4"
    assert stack_argument.to_pretty() == "stack+0=x18_1:4"
    assert returned.to_pretty() == "x10=x10_4:4"
    assert (
        signature.to_pretty()
        == "malloc regs=[x10] stack=[] returns=[x10] no_return=no"
    )
    assert (
        callsite.to_pretty()
        == "call 0x1004 block=0x1000 via=direct -> external 0x1100 name=malloc sig=malloc regs=[x10] stack=[] returns=[x10] no_return=no args=[x10=x10_3:4] stack_args=[stack+0=x18_1:4] mem=[m1 -> m2] returns=[x10=x10_4:4]"
    )


def test_indirect_modeled_callsite_pretty_includes_target_value() -> None:
    callsite = ModeledCallSite(
        instruction_address=0x1008,
        block_start=0x1000,
        target_kind=CallGraphEdgeKind.UNRESOLVED,
        is_indirect=True,
        indirect_target_value=SSAName(SSANameKind.REGISTER, 12, 1, 4),
        argument_values=(
            CallRegisterValue(
                register=10,
                value=SSAName(SSANameKind.REGISTER, 10, 5, 4),
            ),
        ),
        return_values=(
            CallRegisterValue(
                register=10,
                value=SSAName(SSANameKind.REGISTER, 10, 6, 4),
            ),
        ),
    )

    assert (
        callsite.to_pretty()
        == "call 0x1008 block=0x1000 via=indirect -> unresolved target_value=x12_1:4 args=[x10=x10_5:4] returns=[x10=x10_6:4]"
    )


def test_function_and_program_call_pretty_include_queue_state_and_call_graph() -> None:
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
        callsites=(
            CallSite(
                instruction_address=0x1000,
                block_start=0x1000,
                target=0x1100,
            ),
        ),
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
        phis=(),
        instructions=(
            SSAInstruction(
                instruction=instruction.instruction,
                ops=(
                    SSAOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(const_varnode(4),),
                        output=SSAName(SSANameKind.REGISTER, 10, 1, 4),
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
        live_ins=(),
        memory_live_in=MemoryVersion(0),
        unreachable_blocks=(),
    )
    modeled = ModeledCallSite(
        instruction_address=0x1000,
        block_start=0x1000,
        target_kind=CallGraphEdgeKind.INTERNAL,
        target_address=0x1100,
        callee_name="helper",
        argument_values=(
            CallRegisterValue(
                register=10,
                value=SSAName(SSANameKind.REGISTER, 10, 1, 4),
            ),
        ),
        memory_before=MemoryVersion(0),
        memory_after=MemoryVersion(1),
        return_values=(
            CallRegisterValue(
                register=10,
                value=SSAName(SSANameKind.REGISTER, 10, 2, 4),
            ),
        ),
    )
    function_calls = FunctionCallFacts(
        ssa=ssa_function,
        callsites=(modeled,),
        pending_entries=(0x1200,),
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
        pending_entries=(0x1200,),
        invalidated_entries=(0x1000,),
    )
    ssa_program = SSAProgramIR(
        dataflow=dataflow_program,
        functions={0x1000: ssa_function},
    )
    program_calls = ProgramCallFacts(
        ssa=ssa_program,
        functions={0x1000: function_calls},
        call_graph=(
            CallGraphEdge(
                caller=0x1000,
                callsite_address=0x1000,
                kind=CallGraphEdgeKind.INTERNAL,
                callee_address=0x1100,
            ),
        ),
        pending_entries=(0x1200,),
        invalidated_entries=(0x1000,),
    )

    function_rendered = format_function_call_facts(function_calls)
    program_rendered = format_program_call_facts(program_calls)

    assert function_rendered == format_function_call_facts(function_calls)
    assert "pending=[0x1200]" in function_rendered
    assert "abi: rv32i_ilp32" in function_rendered
    assert "call 0x1000" in function_rendered
    assert "mem=[m0 -> m1]" in function_rendered
    assert "returns=[x10=x10_2:4]" in function_rendered

    assert program_rendered == format_program_call_facts(program_calls)
    assert "pending: 0x1200" in program_rendered
    assert "invalidated: 0x1000" in program_rendered
    assert "puts" in program_rendered
    assert "call_graph:" in program_rendered
