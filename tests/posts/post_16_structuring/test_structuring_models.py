from __future__ import annotations

import pytest

from tiny_dec.structuring import (
    FunctionStructuredFacts,
    ProgramStructuredFacts,
    StructuredBlock,
    StructuredBreak,
    StructuredContinue,
    StructuredGoto,
    StructuredIf,
    StructuredSequence,
    StructuredSwitch,
    StructuredSwitchCase,
    StructuredWhile,
    format_function_structured_facts,
    format_program_structured_facts,
    format_structured_block,
    format_structured_break,
    format_structured_continue,
    format_structured_goto,
    format_structured_if,
    format_structured_sequence,
    format_structured_switch,
    format_structured_switch_case,
    format_structured_while,
)
from _helpers import FunctionSpec, block, build_interproc_program, function, instruction


def test_structuring_model_pretty_output_is_stable() -> None:
    interproc_program = build_interproc_program(
        root_entry=0x1000,
        function_specs=(
            FunctionSpec(
                dataflow=function(
                    0x1000,
                    (block(0x1000, instruction(0x1000)),),
                    name="main",
                )
            ),
        ),
        pending_entries=(0x2000,),
        invalidated_entries=(0x1000,),
    )
    interproc_function = interproc_program.functions[0x1000]

    conditional = StructuredIf(
        header=0x1100,
        true_target=0x1110,
        false_target=0x1120,
        merge_target=0x1130,
        then_body=StructuredSequence((StructuredBlock(0x1110),)),
        else_body=StructuredSequence((StructuredBreak(0x1130),)),
    )
    loop = StructuredWhile(
        header=0x1200,
        body_entry=0x1210,
        exit_target=0x1230,
        body=StructuredSequence(
            (
                StructuredBlock(0x1210),
                StructuredContinue(0x1200),
            )
        ),
    )
    switch = StructuredSwitch(
        header=0x1300,
        merge_target=0x1340,
        cases=(
            StructuredSwitchCase(
                value=0,
                target=0x1310,
                body=StructuredSequence((StructuredBlock(0x1310),)),
            ),
            StructuredSwitchCase(
                value=1,
                target=0x1320,
                body=StructuredSequence((StructuredBlock(0x1320),)),
            ),
        ),
        default_target=0x1330,
        default_body=StructuredSequence((StructuredBlock(0x1330),)),
    )
    function_facts = FunctionStructuredFacts(
        interproc=interproc_function,
        body=StructuredSequence(
            (
                StructuredBlock(0x1000),
                conditional,
                loop,
                StructuredGoto(0x1300),
            )
        ),
    )
    program = ProgramStructuredFacts(
        interproc=interproc_program,
        functions={0x1000: function_facts},
        pending_entries=interproc_program.pending_entries,
        invalidated_entries=interproc_program.invalidated_entries,
        scheduler_invalidations=interproc_program.scheduler_invalidations,
    )

    assert format_structured_block(StructuredBlock(0x1000)) == "block 0x1000"
    assert format_structured_goto(StructuredGoto(0x1300)) == "goto 0x1300"
    assert format_structured_break(StructuredBreak(0x1130)) == "break 0x1130"
    assert format_structured_continue(StructuredContinue(0x1200)) == "continue 0x1200"
    assert (
        format_structured_if(conditional)
        == "if header=0x1100 true=0x1110 false=0x1120 merge=0x1130"
    )
    assert (
        format_structured_while(loop)
        == "while header=0x1200 body=0x1210 exit=0x1230"
    )
    assert format_structured_switch_case(switch.cases[1]) == "case 1 -> 0x1320"
    assert (
        format_structured_switch(switch)
        == "switch header=0x1300 cases=2 default=0x1330 merge=0x1340"
    )
    assert format_structured_sequence(
        StructuredSequence((StructuredBlock(0x1000), StructuredGoto(0x1300))),
        indent="  ",
    ) == "  block 0x1000\n  goto 0x1300"
    assert format_structured_sequence(
        StructuredSequence((switch,)),
        indent="  ",
    ) == (
        "  switch header=0x1300 cases=2 default=0x1330 merge=0x1340\n"
        "  cases:\n"
        "    case 0 -> 0x1310\n"
        "      block 0x1310\n"
        "    case 1 -> 0x1320\n"
        "      block 0x1320\n"
        "  default:\n"
        "      block 0x1330"
    )

    function_rendered = format_function_structured_facts(function_facts)
    assert (
        "function 0x1000 name=main frame_size=? dynamic_sp=no stmts=8 loops=1 ifs=1 switches=0 gotos=1 pending=[]"
        in function_rendered
    )
    assert "body:" in function_rendered
    assert "then:" in function_rendered
    assert "else:" in function_rendered
    assert "while header=0x1200 body=0x1210 exit=0x1230" in function_rendered
    assert "continue 0x1200" in function_rendered

    program_rendered = format_program_structured_facts(program)
    assert "pending: 0x2000" in program_rendered
    assert "invalidated: 0x1000" in program_rendered
    assert "functions:" in program_rendered
    assert "goto 0x1300" in program_rendered


def test_structuring_model_rejects_invalid_if_targets() -> None:
    with pytest.raises(ValueError, match="branch targets must differ"):
        StructuredIf(
            header=0x1000,
            true_target=0x1010,
            false_target=0x1010,
            merge_target=0x1020,
        )


def test_program_structured_facts_rejects_scheduler_state_drift() -> None:
    interproc_program = build_interproc_program(
        root_entry=0x1000,
        function_specs=(
            FunctionSpec(
                dataflow=function(
                    0x1000,
                    (block(0x1000, instruction(0x1000)),),
                    name="main",
                )
            ),
        ),
        pending_entries=(0x2000,),
    )
    function_facts = FunctionStructuredFacts(
        interproc=interproc_program.functions[0x1000],
        body=StructuredSequence((StructuredBlock(0x1000),)),
    )

    with pytest.raises(ValueError, match="pending entries must match interproc facts"):
        ProgramStructuredFacts(
            interproc=interproc_program,
            functions={0x1000: function_facts},
            pending_entries=(),
            invalidated_entries=interproc_program.invalidated_entries,
            scheduler_invalidations=interproc_program.scheduler_invalidations,
        )
