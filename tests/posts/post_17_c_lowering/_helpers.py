from __future__ import annotations

from dataclasses import dataclass

from tiny_dec.analysis.calls import analyze_program_calls
from tiny_dec.analysis.dataflow import FunctionDataflowFacts, ProgramDataflowFacts, RegisterState
from tiny_dec.analysis.dataflow.models import BlockDataflowFacts
from tiny_dec.analysis.highvars import analyze_program_variables
from tiny_dec.analysis.interproc import ProgramInterprocFacts, analyze_program_interproc
from tiny_dec.analysis.memory import analyze_program_memory
from tiny_dec.analysis.range import analyze_program_ranges
from tiny_dec.analysis.simplify import (
    CanonicalBlock,
    CanonicalFunctionIR,
    CanonicalInstruction,
    CanonicalProgramIR,
)
from tiny_dec.analysis.ssa import construct_program_ssa
from tiny_dec.analysis.stack import analyze_program_stack
from tiny_dec.analysis.types import (
    analyze_program_aggregate_types,
    analyze_program_scalar_types,
)
from tiny_dec.decode import decode_rv32i
from tiny_dec.disasm.models import BlockEdge, BlockTerminator
from tiny_dec.ir.function_ir import CallSite
from tiny_dec.ir.pcode import PcodeOp
from tiny_dec.structuring import ProgramStructuredFacts, analyze_program_structuring


@dataclass(frozen=True, slots=True)
class FunctionSpec:
    dataflow: FunctionDataflowFacts


def instruction(address: int, *ops: PcodeOp) -> CanonicalInstruction:
    return CanonicalInstruction(
        instruction=decode_rv32i(0x00000013, address),
        ops=ops,
    )


def block(
    start: int,
    *instructions: CanonicalInstruction,
    successors: tuple[BlockEdge, ...] = (),
    terminator: BlockTerminator = BlockTerminator.RETURN,
    call_targets: tuple[int, ...] = (),
    has_indirect_call: bool = False,
) -> CanonicalBlock:
    return CanonicalBlock(
        start=start,
        instructions=instructions,
        successors=successors,
        terminator=terminator,
        call_targets=call_targets,
        has_indirect_call=has_indirect_call,
    )


def function(
    entry: int,
    blocks: tuple[CanonicalBlock, ...],
    *,
    name: str = "main",
    callsites: tuple[CallSite, ...] = (),
    direct_callees: tuple[int, ...] = (),
) -> FunctionDataflowFacts:
    instruction_index = {
        item.address: item
        for current in blocks
        for item in current.instructions
    }
    canonical = CanonicalFunctionIR(
        entry=entry,
        name=name,
        blocks={current.start: current for current in blocks},
        discovery_order=tuple(current.start for current in blocks),
        instruction_index=instruction_index,
        callsites=callsites,
        direct_callees=direct_callees,
        return_blocks=tuple(
            current.start
            for current in blocks
            if current.terminator == BlockTerminator.RETURN
        ),
    )
    return FunctionDataflowFacts(
        function=canonical,
        blocks={
            current.start: BlockDataflowFacts(
                start=current.start,
                in_state=RegisterState(),
                out_state=RegisterState(),
            )
            for current in blocks
        },
    )


def build_interproc_program(
    *,
    root_entry: int,
    function_specs: tuple[FunctionSpec, ...],
    pending_entries: tuple[int, ...] = (),
    invalidated_entries: tuple[int, ...] = (),
) -> ProgramInterprocFacts:
    canonical_program = CanonicalProgramIR(
        root_entry=root_entry,
        functions={
            spec.dataflow.function.entry: spec.dataflow.function for spec in function_specs
        },
        discovery_order=tuple(spec.dataflow.function.entry for spec in function_specs),
    )
    dataflow_program = ProgramDataflowFacts(
        program=canonical_program,
        functions={
            spec.dataflow.function.entry: spec.dataflow for spec in function_specs
        },
        pending_entries=pending_entries,
        invalidated_entries=invalidated_entries,
    )
    return analyze_program_interproc(
        analyze_program_ranges(
            analyze_program_variables(
                analyze_program_aggregate_types(
                    analyze_program_scalar_types(
                        analyze_program_memory(
                            analyze_program_stack(
                                analyze_program_calls(construct_program_ssa(dataflow_program))
                            )
                        )
                    )
                )
            )
        )
    )


def build_structured_program(
    *,
    root_entry: int,
    function_specs: tuple[FunctionSpec, ...],
    pending_entries: tuple[int, ...] = (),
    invalidated_entries: tuple[int, ...] = (),
) -> ProgramStructuredFacts:
    return analyze_program_structuring(
        build_interproc_program(
            root_entry=root_entry,
            function_specs=function_specs,
            pending_entries=pending_entries,
            invalidated_entries=invalidated_entries,
        )
    )
