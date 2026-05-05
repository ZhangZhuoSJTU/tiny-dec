from __future__ import annotations

from tiny_dec.analysis.dataflow import (
    BlockDataflowFacts,
    FunctionDataflowFacts,
    ProgramDataflowFacts,
    RegisterState,
    RecoveredTarget,
    RecoveredTargetKind,
    format_function_dataflow,
    format_program_dataflow,
)
from tiny_dec.analysis.simplify import (
    CanonicalBlock,
    CanonicalFunctionIR,
    CanonicalInstruction,
    CanonicalProgramIR,
)
from tiny_dec.decode import decode_rv32i
from tiny_dec.disasm.models import BlockTerminator
from tiny_dec.ir.pcode import PcodeOp, PcodeOpcode, const_varnode, register_varnode
from tiny_dec.ir.program_ir import CallGraphEdge, CallGraphEdgeKind
from tiny_dec.loader import ExternalFunction


def _instruction(address: int) -> CanonicalInstruction:
    return CanonicalInstruction(
        instruction=decode_rv32i(0x00000013, address),
        ops=(
            PcodeOp(
                opcode=PcodeOpcode.COPY,
                inputs=(const_varnode(4),),
                output=register_varnode(1),
            ),
        ),
    )


def test_register_state_pretty_and_validation_are_stable() -> None:
    state = RegisterState(known_registers={2: 0x100000002, 1: 7})

    assert state.known_registers == {1: 7, 2: 2}
    assert state.to_pretty() == "x1=0x7, x2=0x2"
    assert RegisterState.unreachable().to_pretty() == "<unreachable>"


def test_function_and_program_dataflow_pretty_include_recovery_and_queue_state() -> None:
    instruction = _instruction(0x1000)
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
    )
    recovered = RecoveredTarget(
        instruction_address=0x1000,
        block_start=0x1000,
        kind=RecoveredTargetKind.CALL,
        target=0x1100,
    )
    function_facts = FunctionDataflowFacts(
        function=function,
        blocks={
            0x1000: BlockDataflowFacts(
                start=0x1000,
                in_state=RegisterState(),
                out_state=RegisterState(known_registers={1: 4}),
                recovered_targets=(recovered,),
            )
        },
        recovered_targets=(recovered,),
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
    program_facts = ProgramDataflowFacts(
        program=program,
        functions={0x1000: function_facts},
        pending_entries=(0x4000,),
        invalidated_entries=(0x1000,),
    )

    function_rendered = format_function_dataflow(function_facts)
    program_rendered = format_program_dataflow(program_facts)

    assert function_rendered == format_function_dataflow(function_facts)
    assert "recovered_targets:" in function_rendered
    assert "recover call 0x1000 -> 0x1100" in function_rendered
    assert "in=[<empty>]" in function_rendered
    assert "out=[x1=0x4]" in function_rendered

    assert program_rendered == format_program_dataflow(program_facts)
    assert "pending: 0x4000" in program_rendered
    assert "invalidated: 0x1000" in program_rendered
    assert "puts" in program_rendered
    assert "0x1000@0x1000 -> internal 0x1100" in program_rendered
