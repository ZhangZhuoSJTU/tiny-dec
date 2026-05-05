from __future__ import annotations

from tiny_dec.analysis.calls import analyze_program_calls
from tiny_dec.analysis.dataflow import (
    BlockDataflowFacts,
    FunctionDataflowFacts,
    ProgramDataflowFacts,
    RecoveredTarget,
    RecoveredTargetKind,
    RegisterState,
)
from tiny_dec.analysis.simplify import (
    CanonicalBlock,
    CanonicalFunctionIR,
    CanonicalInstruction,
    CanonicalProgramIR,
)
from tiny_dec.analysis.ssa import construct_program_ssa
from tiny_dec.decode import decode_rv32i
from tiny_dec.disasm.models import BlockEdge, BlockEdgeKind, BlockTerminator
from tiny_dec.ir.function_ir import CallSite
from tiny_dec.ir.pcode import (
    PcodeOp,
    PcodeOpcode,
    const_varnode,
    register_varnode,
    unique_varnode,
)
from tiny_dec.ir.program_ir import CallGraphEdge, CallGraphEdgeKind
from tiny_dec.loader import ExternalFunction


def _instruction(address: int, *ops: PcodeOp) -> CanonicalInstruction:
    return CanonicalInstruction(
        instruction=decode_rv32i(0x00000013, address),
        ops=ops,
    )


def _block(
    start: int,
    *instructions: CanonicalInstruction,
    successors: tuple[BlockEdge, ...] = (),
    terminator: BlockTerminator = BlockTerminator.LINEAR,
) -> CanonicalBlock:
    return CanonicalBlock(
        start=start,
        instructions=instructions,
        successors=successors,
        terminator=terminator,
    )


def _function(
    entry: int,
    blocks: tuple[CanonicalBlock, ...],
    *,
    callsites: tuple[CallSite, ...] = (),
    recovered_targets: tuple[RecoveredTarget, ...] = (),
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
        callsites=callsites,
        return_blocks=return_blocks,
    )
    dataflow_blocks = {
        block.start: BlockDataflowFacts(
            start=block.start,
            in_state=RegisterState(),
            out_state=RegisterState(),
            recovered_targets=tuple(
                target for target in recovered_targets if target.block_start == block.start
            ),
        )
        for block in blocks
    }
    return FunctionDataflowFacts(
        function=canonical,
        blocks=dataflow_blocks,
        recovered_targets=recovered_targets,
    )


def _ssa_program(
    root_entry: int,
    functions: tuple[FunctionDataflowFacts, ...],
    *,
    externals: tuple[ExternalFunction, ...] = (),
    call_graph: tuple[CallGraphEdge, ...] = (),
    pending_entries: tuple[int, ...] = (),
    invalidated_entries: tuple[int, ...] = (),
):
    canonical_program = CanonicalProgramIR(
        root_entry=root_entry,
        functions={function.function.entry: function.function for function in functions},
        discovery_order=tuple(function.function.entry for function in functions),
        externals=externals,
        call_graph=call_graph,
    )
    dataflow_program = ProgramDataflowFacts(
        program=canonical_program,
        functions={function.function.entry: function for function in functions},
        pending_entries=pending_entries,
        invalidated_entries=invalidated_entries,
    )
    return construct_program_ssa(dataflow_program)


def test_analyze_program_calls_models_direct_internal_call_and_argument_snapshot() -> None:
    caller = _function(
        0x1000,
        (
            _block(
                0x1000,
                _instruction(
                    0x1000,
                    PcodeOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(const_varnode(7),),
                        output=register_varnode(10),
                    ),
                ),
                _instruction(
                    0x1004,
                    PcodeOp(
                        opcode=PcodeOpcode.CALL,
                        inputs=(const_varnode(0x1100),),
                    ),
                ),
                terminator=BlockTerminator.RETURN,
            ),
        ),
        callsites=(
            CallSite(
                instruction_address=0x1004,
                block_start=0x1000,
                target=0x1100,
                target_name="helper",
            ),
        ),
        name="main",
    )
    callee = _function(
        0x1100,
        (
            _block(
                0x1100,
                _instruction(0x1100),
                terminator=BlockTerminator.RETURN,
            ),
        ),
        name="helper",
    )
    program = _ssa_program(
        0x1000,
        (caller, callee),
        call_graph=(
            CallGraphEdge(
                caller=0x1000,
                callsite_address=0x1004,
                kind=CallGraphEdgeKind.INTERNAL,
                callee_address=0x1100,
                callee_name="helper",
            ),
        ),
    )

    calls = analyze_program_calls(program)
    modeled = calls.functions[0x1000].callsites[0]

    assert modeled.target_kind == CallGraphEdgeKind.INTERNAL
    assert modeled.target_address == 0x1100
    assert modeled.callee_name == "helper"
    assert [value.to_pretty() for value in modeled.argument_values] == ["x10=x10_1:4"]
    assert modeled.memory_before is not None
    assert modeled.memory_after is not None
    assert modeled.memory_before.to_pretty() == "m0"
    assert modeled.memory_after.to_pretty() == "m1"
    assert [value.to_pretty() for value in modeled.return_values] == [
        "x10=x10_2:4",
        "x11=x11_1:4",
    ]
    assert calls.pending_entries == ()
    assert calls.call_graph[0].kind == CallGraphEdgeKind.INTERNAL


def test_analyze_program_calls_uses_recovered_indirect_target_and_enqueues_entry() -> None:
    caller = _function(
        0x1000,
        (
            _block(
                0x1000,
                _instruction(
                    0x1000,
                    PcodeOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(const_varnode(3),),
                        output=register_varnode(10),
                    ),
                ),
                _instruction(
                    0x1004,
                    PcodeOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(const_varnode(0x1200),),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.CALLIND,
                        inputs=(unique_varnode(0),),
                    ),
                ),
                terminator=BlockTerminator.RETURN,
            ),
        ),
        callsites=(
            CallSite(
                instruction_address=0x1004,
                block_start=0x1000,
                is_indirect=True,
            ),
        ),
        recovered_targets=(
            RecoveredTarget(
                instruction_address=0x1004,
                block_start=0x1000,
                kind=RecoveredTargetKind.CALL,
                target=0x1200,
            ),
        ),
    )
    program = _ssa_program(0x1000, (caller,))

    calls = analyze_program_calls(program)
    modeled = calls.functions[0x1000].callsites[0]

    assert modeled.is_indirect is True
    assert modeled.resolved_from_recovered_target is True
    assert modeled.target_kind == CallGraphEdgeKind.INTERNAL
    assert modeled.target_address == 0x1200
    assert [value.to_pretty() for value in modeled.argument_values] == ["x10=x10_1:4"]
    assert modeled.memory_before is not None
    assert modeled.memory_after is not None
    assert [value.to_pretty() for value in modeled.return_values] == [
        "x10=x10_2:4",
        "x11=x11_1:4",
    ]
    assert calls.pending_entries == (0x1200,)
    assert calls.call_graph[0].callee_address == 0x1200


def test_analyze_program_calls_separates_indirect_target_carrier_from_arguments() -> None:
    caller = _function(
        0x1000,
        (
            _block(
                0x1000,
                _instruction(
                    0x1000,
                    PcodeOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(const_varnode(7),),
                        output=register_varnode(10),
                    ),
                ),
                _instruction(
                    0x1004,
                    PcodeOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(const_varnode(0x1200),),
                        output=register_varnode(12),
                    ),
                ),
                _instruction(
                    0x1008,
                    PcodeOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(register_varnode(12),),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.INT_AND,
                        inputs=(unique_varnode(0), const_varnode(-2)),
                        output=unique_varnode(4),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.CALLIND,
                        inputs=(unique_varnode(4),),
                    ),
                ),
                terminator=BlockTerminator.RETURN,
            ),
        ),
        callsites=(
            CallSite(
                instruction_address=0x1008,
                block_start=0x1000,
                is_indirect=True,
            ),
        ),
    )
    program = _ssa_program(0x1000, (caller,))

    calls = analyze_program_calls(program)
    modeled = calls.functions[0x1000].callsites[0]

    assert modeled.is_indirect is True
    assert modeled.target_kind == CallGraphEdgeKind.UNRESOLVED
    assert modeled.indirect_target_value is not None
    assert modeled.indirect_target_value.to_pretty() == "x12_1:4"
    assert [value.to_pretty() for value in modeled.argument_values] == ["x10=x10_1:4"]
    assert modeled.stack_argument_values == ()


def test_analyze_program_calls_preserves_unresolved_direct_edge_and_upstream_invalidations() -> None:
    caller = _function(
        0x1000,
        (
            _block(
                0x1000,
                _instruction(
                    0x1000,
                    PcodeOp(
                        opcode=PcodeOpcode.CALL,
                        inputs=(const_varnode(0x1008),),
                    ),
                ),
                _instruction(0x1004),
                _instruction(0x1008),
                terminator=BlockTerminator.RETURN,
            ),
        ),
        callsites=(
            CallSite(
                instruction_address=0x1000,
                block_start=0x1000,
                target=0x1008,
            ),
        ),
    )
    program = _ssa_program(
        0x1000,
        (caller,),
        call_graph=(
            CallGraphEdge(
                caller=0x1000,
                callsite_address=0x1000,
                kind=CallGraphEdgeKind.UNRESOLVED,
                callee_address=0x1008,
            ),
        ),
        pending_entries=(0x4000,),
        invalidated_entries=(0x1000,),
    )

    calls = analyze_program_calls(program)
    modeled = calls.functions[0x1000].callsites[0]

    assert modeled.target_kind == CallGraphEdgeKind.UNRESOLVED
    assert modeled.target_address == 0x1008
    assert calls.pending_entries == (0x4000,)
    assert calls.invalidated_entries == (0x1000,)


def test_analyze_program_calls_uses_normalized_loop_header_carrier_for_call_args() -> None:
    caller = _function(
        0x1000,
        (
            _block(
                0x1000,
                _instruction(
                    0x1000,
                    PcodeOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(const_varnode(7),),
                        output=register_varnode(12),
                    ),
                ),
                successors=(BlockEdge(BlockEdgeKind.JUMP, 0x1010),),
                terminator=BlockTerminator.JUMP,
            ),
            _block(
                0x1010,
                _instruction(
                    0x1010,
                    PcodeOp(
                        opcode=PcodeOpcode.CALL,
                        inputs=(const_varnode(0x1100),),
                    ),
                ),
                _instruction(0x1014),
                successors=(
                    BlockEdge(BlockEdgeKind.BRANCH_TAKEN, 0x1030),
                    BlockEdge(BlockEdgeKind.FALLTHROUGH, 0x1020),
                ),
                terminator=BlockTerminator.BRANCH,
            ),
            _block(
                0x1020,
                _instruction(
                    0x1020,
                    PcodeOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(register_varnode(12),),
                        output=register_varnode(12),
                    ),
                ),
                successors=(BlockEdge(BlockEdgeKind.JUMP, 0x1010),),
                terminator=BlockTerminator.JUMP,
            ),
            _block(
                0x1030,
                _instruction(0x1030),
                terminator=BlockTerminator.RETURN,
            ),
        ),
        callsites=(
            CallSite(
                instruction_address=0x1010,
                block_start=0x1010,
                target=0x1100,
                target_name="helper",
            ),
        ),
        name="main",
    )

    callee = _function(
        0x1100,
        (
            _block(
                0x1100,
                _instruction(0x1100),
                terminator=BlockTerminator.RETURN,
            ),
        ),
        name="helper",
    )
    program = _ssa_program(
        0x1000,
        (caller, callee),
        call_graph=(
            CallGraphEdge(
                caller=0x1000,
                callsite_address=0x1010,
                kind=CallGraphEdgeKind.INTERNAL,
                callee_address=0x1100,
                callee_name="helper",
            ),
        ),
    )

    calls = analyze_program_calls(program)
    modeled = calls.functions[0x1000].callsites[0]

    assert [value.to_pretty() for value in modeled.argument_values] == ["x12=x12_2:4"]


def test_analyze_program_calls_canonicalizes_trivial_register_forwarding_copy_for_args() -> None:
    caller = _function(
        0x1000,
        (
            _block(
                0x1000,
                _instruction(
                    0x1000,
                    PcodeOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(register_varnode(10),),
                        output=register_varnode(12),
                    ),
                ),
                _instruction(
                    0x1004,
                    PcodeOp(
                        opcode=PcodeOpcode.CALL,
                        inputs=(const_varnode(0x1100),),
                    ),
                ),
                terminator=BlockTerminator.RETURN,
            ),
        ),
        callsites=(
            CallSite(
                instruction_address=0x1004,
                block_start=0x1000,
                target=0x1100,
                target_name="helper",
            ),
        ),
        name="main",
    )
    callee = _function(
        0x1100,
        (
            _block(
                0x1100,
                _instruction(0x1100),
                terminator=BlockTerminator.RETURN,
            ),
        ),
        name="helper",
    )
    program = _ssa_program(
        0x1000,
        (caller, callee),
        call_graph=(
            CallGraphEdge(
                caller=0x1000,
                callsite_address=0x1004,
                kind=CallGraphEdgeKind.INTERNAL,
                callee_address=0x1100,
                callee_name="helper",
            ),
        ),
    )

    calls = analyze_program_calls(program)
    modeled = calls.functions[0x1000].callsites[0]

    assert [value.to_pretty() for value in modeled.argument_values] == [
        "x10=x10_0:4",
        "x12=x10_0:4",
    ]


def test_analyze_program_calls_records_current_sp_relative_stack_arguments() -> None:
    caller = _function(
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
                        inputs=(register_varnode(2), const_varnode(0)),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.STORE,
                        inputs=(unique_varnode(0), register_varnode(18)),
                    ),
                ),
                _instruction(
                    0x1008,
                    PcodeOp(
                        opcode=PcodeOpcode.CALL,
                        inputs=(const_varnode(0x1100),),
                    ),
                ),
                terminator=BlockTerminator.RETURN,
            ),
        ),
        callsites=(
            CallSite(
                instruction_address=0x1008,
                block_start=0x1000,
                target=0x1100,
                target_name="helper",
            ),
        ),
        name="main",
    )
    callee = _function(
        0x1100,
        (
            _block(
                0x1100,
                _instruction(0x1100),
                terminator=BlockTerminator.RETURN,
            ),
        ),
        name="helper",
    )
    program = _ssa_program(
        0x1000,
        (caller, callee),
        call_graph=(
            CallGraphEdge(
                caller=0x1000,
                callsite_address=0x1008,
                kind=CallGraphEdgeKind.INTERNAL,
                callee_address=0x1100,
                callee_name="helper",
            ),
        ),
    )

    calls = analyze_program_calls(program)
    modeled = calls.functions[0x1000].callsites[0]

    assert modeled.target_kind == CallGraphEdgeKind.INTERNAL
    assert [value.to_pretty() for value in modeled.stack_argument_values] == [
        "stack+0=x18_0:4"
    ]


def test_analyze_program_calls_omits_later_restored_stack_slots_from_stack_arguments() -> None:
    caller = _function(
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
                    0x100c,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(2), const_varnode(0)),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.STORE,
                        inputs=(unique_varnode(0), register_varnode(18)),
                    ),
                ),
                _instruction(
                    0x1010,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(2), const_varnode(4)),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.STORE,
                        inputs=(unique_varnode(0), register_varnode(19)),
                    ),
                ),
                _instruction(
                    0x1014,
                    PcodeOp(
                        opcode=PcodeOpcode.CALL,
                        inputs=(const_varnode(0x1100),),
                    ),
                ),
                _instruction(
                    0x1018,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(2), const_varnode(8)),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.LOAD,
                        inputs=(unique_varnode(0),),
                        output=register_varnode(8),
                    ),
                ),
                _instruction(
                    0x101c,
                    PcodeOp(
                        opcode=PcodeOpcode.INT_ADD,
                        inputs=(register_varnode(2), const_varnode(12)),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.LOAD,
                        inputs=(unique_varnode(0),),
                        output=register_varnode(1),
                    ),
                ),
                terminator=BlockTerminator.RETURN,
            ),
        ),
        callsites=(
            CallSite(
                instruction_address=0x1014,
                block_start=0x1000,
                target=0x1100,
                target_name="helper",
            ),
        ),
        name="main",
    )
    callee = _function(
        0x1100,
        (
            _block(
                0x1100,
                _instruction(0x1100),
                terminator=BlockTerminator.RETURN,
            ),
        ),
        name="helper",
    )
    program = _ssa_program(
        0x1000,
        (caller, callee),
        call_graph=(
            CallGraphEdge(
                caller=0x1000,
                callsite_address=0x1014,
                kind=CallGraphEdgeKind.INTERNAL,
                callee_address=0x1100,
                callee_name="helper",
            ),
        ),
    )

    calls = analyze_program_calls(program)
    modeled = calls.functions[0x1000].callsites[0]

    assert [value.to_pretty() for value in modeled.stack_argument_values] == [
        "stack+0=x18_0:4",
        "stack+4=x19_0:4",
    ]


def test_analyze_program_calls_attaches_known_external_signature_to_named_external_call() -> None:
    caller = _function(
        0x1000,
        (
            _block(
                0x1000,
                _instruction(
                    0x1000,
                    PcodeOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(const_varnode(32),),
                        output=register_varnode(10),
                    ),
                ),
                _instruction(
                    0x1004,
                    PcodeOp(
                        opcode=PcodeOpcode.CALL,
                        inputs=(const_varnode(0x2000),),
                    ),
                ),
                terminator=BlockTerminator.RETURN,
            ),
        ),
        callsites=(
            CallSite(
                instruction_address=0x1004,
                block_start=0x1000,
                target=0x2000,
                target_name="malloc",
            ),
        ),
        name="main",
    )
    program = _ssa_program(
        0x1000,
        (caller,),
        externals=(
            ExternalFunction(
                name="malloc",
                plt_address=None,
                got_address=None,
                symbol_address=None,
            ),
        ),
        call_graph=(
            CallGraphEdge(
                caller=0x1000,
                callsite_address=0x1004,
                kind=CallGraphEdgeKind.EXTERNAL,
                callee_address=0x2000,
                callee_name="malloc",
            ),
        ),
    )

    calls = analyze_program_calls(program)
    modeled = calls.functions[0x1000].callsites[0]

    assert modeled.target_kind == CallGraphEdgeKind.EXTERNAL
    assert modeled.callee_name == "malloc"
    assert modeled.external_signature is not None
    assert modeled.external_signature.parameter_registers == (10,)
    assert modeled.external_signature.return_registers == (10,)


def test_analyze_program_calls_classifies_recovered_indirect_target_as_external_via_got_address() -> None:
    caller = _function(
        0x1000,
        (
            _block(
                0x1000,
                _instruction(
                    0x1000,
                    PcodeOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(const_varnode(0x100D4),),
                        output=register_varnode(10),
                    ),
                ),
                _instruction(
                    0x1004,
                    PcodeOp(
                        opcode=PcodeOpcode.COPY,
                        inputs=(const_varnode(0x3000),),
                        output=unique_varnode(0),
                    ),
                    PcodeOp(
                        opcode=PcodeOpcode.CALLIND,
                        inputs=(unique_varnode(0),),
                    ),
                ),
                terminator=BlockTerminator.RETURN,
            ),
        ),
        callsites=(
            CallSite(
                instruction_address=0x1004,
                block_start=0x1000,
                is_indirect=True,
            ),
        ),
        recovered_targets=(
            RecoveredTarget(
                instruction_address=0x1004,
                block_start=0x1000,
                kind=RecoveredTargetKind.CALL,
                target=0x3000,
            ),
        ),
    )
    program = _ssa_program(
        0x1000,
        (caller,),
        externals=(
            ExternalFunction(
                name="puts",
                plt_address=None,
                got_address=0x3000,
                symbol_address=None,
            ),
        ),
    )

    calls = analyze_program_calls(program)
    modeled = calls.functions[0x1000].callsites[0]

    assert modeled.is_indirect is True
    assert modeled.resolved_from_recovered_target is True
    assert modeled.target_kind == CallGraphEdgeKind.EXTERNAL
    assert modeled.target_address == 0x3000
    assert modeled.callee_name == "puts"
    assert modeled.external_signature is not None
    assert modeled.external_signature.parameter_registers == (10,)
    assert modeled.external_signature.return_registers == (10,)
    assert calls.pending_entries == ()
    assert calls.call_graph[0].kind == CallGraphEdgeKind.EXTERNAL
    assert calls.call_graph[0].callee_name == "puts"
