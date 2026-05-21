from __future__ import annotations

from tiny_dec.disasm.models import BlockEdge, BlockEdgeKind, BlockTerminator
from tiny_dec.structuring import (
    StructuredBlock,
    StructuredIf,
    StructuredWhile,
    analyze_program_structuring,
    format_function_structured_facts,
)
from _helpers import FunctionSpec, block, build_interproc_program, function, instruction


def test_analyze_program_structuring_recovers_pretested_while() -> None:
    interproc_program = build_interproc_program(
        root_entry=0x1000,
        function_specs=(
            FunctionSpec(
                dataflow=function(
                    0x1000,
                    (
                        block(
                            0x1000,
                            instruction(0x1000),
                            successors=(BlockEdge(BlockEdgeKind.JUMP, 0x1010),),
                            terminator=BlockTerminator.JUMP,
                        ),
                        block(
                            0x1010,
                            instruction(0x1010),
                            successors=(
                                BlockEdge(BlockEdgeKind.BRANCH_TAKEN, 0x1040),
                                BlockEdge(BlockEdgeKind.FALLTHROUGH, 0x1020),
                            ),
                            terminator=BlockTerminator.BRANCH,
                        ),
                        block(
                            0x1020,
                            instruction(0x1020),
                            successors=(BlockEdge(BlockEdgeKind.JUMP, 0x1030),),
                            terminator=BlockTerminator.JUMP,
                        ),
                        block(
                            0x1030,
                            instruction(0x1030),
                            successors=(BlockEdge(BlockEdgeKind.JUMP, 0x1010),),
                            terminator=BlockTerminator.JUMP,
                        ),
                        block(
                            0x1040,
                            instruction(0x1040),
                            terminator=BlockTerminator.RETURN,
                        ),
                    ),
                    name="sum_loop",
                )
            ),
        ),
        pending_entries=(0x2000,),
        invalidated_entries=(0x1000,),
    )

    program = analyze_program_structuring(interproc_program)
    facts = program.functions[0x1000]

    assert program.pending_entries == (0x2000,)
    assert program.invalidated_entries == (0x1000,)
    assert program.scheduler_invalidations == ()
    assert facts.loop_count == 1
    assert facts.if_count == 0
    assert [type(item) for item in facts.body.items] == [StructuredWhile, StructuredBlock]

    loop = facts.body.items[0]
    assert isinstance(loop, StructuredWhile)
    assert loop.header == 0x1010
    assert loop.body_entry == 0x1020
    assert loop.exit_target == 0x1040
    assert loop.body.items == ()
    assert isinstance(facts.body.items[1], StructuredBlock)
    assert facts.body.items[1].block_start == 0x1040
    assert "while header=0x1010 body=0x1020 exit=0x1040" in format_function_structured_facts(
        facts
    )


def test_analyze_program_structuring_recovers_nested_else_if() -> None:
    interproc_program = build_interproc_program(
        root_entry=0x2000,
        function_specs=(
            FunctionSpec(
                dataflow=function(
                    0x2000,
                    (
                        block(
                            0x2000,
                            instruction(0x2000),
                            successors=(
                                BlockEdge(BlockEdgeKind.BRANCH_TAKEN, 0x2010),
                                BlockEdge(BlockEdgeKind.FALLTHROUGH, 0x2020),
                            ),
                            terminator=BlockTerminator.BRANCH,
                        ),
                        block(
                            0x2010,
                            instruction(0x2010),
                            successors=(BlockEdge(BlockEdgeKind.JUMP, 0x2050),),
                            terminator=BlockTerminator.JUMP,
                        ),
                        block(
                            0x2020,
                            instruction(0x2020),
                            successors=(BlockEdge(BlockEdgeKind.JUMP, 0x2030),),
                            terminator=BlockTerminator.JUMP,
                        ),
                        block(
                            0x2030,
                            instruction(0x2030),
                            successors=(
                                BlockEdge(BlockEdgeKind.BRANCH_TAKEN, 0x2040),
                                BlockEdge(BlockEdgeKind.FALLTHROUGH, 0x2048),
                            ),
                            terminator=BlockTerminator.BRANCH,
                        ),
                        block(
                            0x2040,
                            instruction(0x2040),
                            successors=(BlockEdge(BlockEdgeKind.JUMP, 0x2050),),
                            terminator=BlockTerminator.JUMP,
                        ),
                        block(
                            0x2048,
                            instruction(0x2048),
                            successors=(BlockEdge(BlockEdgeKind.JUMP, 0x2050),),
                            terminator=BlockTerminator.JUMP,
                        ),
                        block(
                            0x2050,
                            instruction(0x2050),
                            terminator=BlockTerminator.RETURN,
                        ),
                    ),
                    name="dispatch",
                )
            ),
        ),
    )

    program = analyze_program_structuring(interproc_program)
    facts = program.functions[0x2000]

    assert facts.loop_count == 0
    assert facts.if_count == 2
    assert len(facts.body.items) == 2

    top = facts.body.items[0]
    assert isinstance(top, StructuredIf)
    assert top.header == 0x2000
    assert top.true_target == 0x2010
    assert top.false_target == 0x2020
    assert top.merge_target == 0x2050
    assert top.then_body.items == ()
    assert len(top.else_body.items) == 1
    nested = top.else_body.items[0]
    assert isinstance(nested, StructuredIf)
    assert nested.header == 0x2030
    assert nested.true_target == 0x2040
    assert nested.false_target == 0x2048
    assert nested.merge_target == 0x2050
    assert nested.then_body.items == ()
    assert nested.else_body.items == ()
    assert isinstance(facts.body.items[1], StructuredBlock)
    assert facts.body.items[1].block_start == 0x2050
    assert "switch header=" not in format_function_structured_facts(facts)
