from __future__ import annotations

from dataclasses import dataclass

from tiny_dec.analysis.calls import analyze_program_calls
from tiny_dec.analysis.dataflow import (
    BlockDataflowFacts,
    FunctionDataflowFacts,
    ProgramDataflowFacts,
    RegisterState,
)
from tiny_dec.analysis.highvars import FunctionVariableFacts, ProgramVariableFacts
from tiny_dec.analysis.memory import FunctionMemoryFacts, ProgramMemoryFacts
from tiny_dec.analysis.range import ProgramRangeFacts, analyze_program_ranges
from tiny_dec.analysis.simplify import (
    CanonicalBlock,
    CanonicalFunctionIR,
    CanonicalInstruction,
    CanonicalProgramIR,
)
from tiny_dec.analysis.ssa import construct_program_ssa
from tiny_dec.analysis.stack import FunctionStackFacts, ProgramStackFacts, StackSlot
from tiny_dec.analysis.types import (
    FunctionAggregateTypeFacts,
    FunctionScalarTypeFacts,
    PartitionScalarTypeFact,
    ProgramAggregateTypeFacts,
    ProgramScalarTypeFacts,
    ValueScalarTypeFact,
)
from tiny_dec.analysis.types.aggregate_models import AggregateLayout
from tiny_dec.decode import decode_rv32i
from tiny_dec.disasm.models import BlockTerminator
from tiny_dec.ir.pcode import PcodeOp


@dataclass(frozen=True, slots=True)
class FunctionSpec:
    dataflow: FunctionDataflowFacts
    stack_slots: tuple[StackSlot, ...] = ()
    memory_partitions: tuple = ()
    partition_facts: tuple[PartitionScalarTypeFact, ...] = ()
    value_facts: tuple[ValueScalarTypeFact, ...] = ()
    variables: tuple = ()
    aggregate_layouts: tuple[AggregateLayout, ...] = ()
    frame_size: int | None = None
    dynamic_stack_pointer: bool = False


def instruction(address: int, *ops: PcodeOp) -> CanonicalInstruction:
    return CanonicalInstruction(
        instruction=decode_rv32i(0x00000013, address),
        ops=ops,
    )


def block(
    start: int,
    *instructions: CanonicalInstruction,
    successors=(),
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
    callsites=(),
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


def build_range_program(
    *,
    root_entry: int,
    function_specs: tuple[FunctionSpec, ...],
    pending_entries: tuple[int, ...] = (),
    invalidated_entries: tuple[int, ...] = (),
) -> ProgramRangeFacts:
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
    calls = analyze_program_calls(construct_program_ssa(dataflow_program))

    stack_functions = {
        spec.dataflow.function.entry: FunctionStackFacts(
            calls=calls.functions[spec.dataflow.function.entry],
            frame_size=spec.frame_size,
            dynamic_stack_pointer=spec.dynamic_stack_pointer,
            slots=spec.stack_slots,
        )
        for spec in function_specs
    }
    stack_program = ProgramStackFacts(
        calls=calls,
        functions=stack_functions,
        pending_entries=calls.pending_entries,
        invalidated_entries=calls.invalidated_entries,
    )

    memory_functions = {
        spec.dataflow.function.entry: FunctionMemoryFacts(
            stack=stack_functions[spec.dataflow.function.entry],
            partitions=spec.memory_partitions,
        )
        for spec in function_specs
    }
    memory_program = ProgramMemoryFacts(
        stack=stack_program,
        functions=memory_functions,
        pending_entries=stack_program.pending_entries,
        invalidated_entries=stack_program.invalidated_entries,
    )

    scalar_functions = {
        spec.dataflow.function.entry: FunctionScalarTypeFacts(
            memory=memory_functions[spec.dataflow.function.entry],
            partition_facts=spec.partition_facts,
            value_facts=spec.value_facts,
        )
        for spec in function_specs
    }
    scalar_program = ProgramScalarTypeFacts(
        memory=memory_program,
        functions=scalar_functions,
        pending_entries=memory_program.pending_entries,
        invalidated_entries=memory_program.invalidated_entries,
    )

    aggregate_functions = {
        spec.dataflow.function.entry: FunctionAggregateTypeFacts(
            scalar_types=scalar_functions[spec.dataflow.function.entry],
            layouts=spec.aggregate_layouts,
        )
        for spec in function_specs
    }
    aggregate_program = ProgramAggregateTypeFacts(
        scalar_types=scalar_program,
        functions=aggregate_functions,
        pending_entries=scalar_program.pending_entries,
        invalidated_entries=scalar_program.invalidated_entries,
    )

    variable_functions = {
        spec.dataflow.function.entry: FunctionVariableFacts(
            aggregate_types=aggregate_functions[spec.dataflow.function.entry],
            variables=spec.variables,
        )
        for spec in function_specs
    }
    variable_program = ProgramVariableFacts(
        aggregate_types=aggregate_program,
        functions=variable_functions,
        pending_entries=aggregate_program.pending_entries,
        invalidated_entries=aggregate_program.invalidated_entries,
    )
    return analyze_program_ranges(variable_program)
