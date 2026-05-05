from __future__ import annotations

from tiny_dec.analysis.calls import analyze_program_calls
from tiny_dec.analysis.dataflow import (
    BlockDataflowFacts,
    FunctionDataflowFacts,
    ProgramDataflowFacts,
    RegisterState,
)
from tiny_dec.analysis.highvars import (
    FunctionVariableFacts,
    ProgramVariableFacts,
    RecoveredVariable,
    VariableBinding,
    VariableBindingKind,
    VariableKind,
)
from tiny_dec.analysis.memory import (
    FunctionMemoryFacts,
    MemoryAccess,
    MemoryAccessKind,
    MemoryPartition,
    MemoryPartitionKind,
    ProgramMemoryFacts,
)
from tiny_dec.analysis.range import (
    BranchRangeRefinement,
    FunctionRangeFacts,
    IntegerRange,
    ProgramRangeFacts,
    ValueRangeFact,
    VariableRangeFact,
    format_branch_range_refinement,
    format_function_range_facts,
    format_integer_range,
    format_program_range_facts,
    format_value_range_fact,
    format_variable_range_fact,
)
from tiny_dec.analysis.simplify import (
    CanonicalBlock,
    CanonicalFunctionIR,
    CanonicalInstruction,
    CanonicalProgramIR,
)
from tiny_dec.analysis.ssa import construct_program_ssa
from tiny_dec.analysis.ssa.models import SSAName, SSANameKind
from tiny_dec.analysis.stack import (
    FunctionStackFacts,
    ProgramStackFacts,
    StackAccess,
    StackAccessKind,
    StackBaseKind,
    StackSlot,
    StackSlotRole,
)
from tiny_dec.analysis.types import (
    FunctionAggregateTypeFacts,
    FunctionScalarTypeFacts,
    PartitionScalarTypeFact,
    ProgramAggregateTypeFacts,
    ProgramScalarTypeFacts,
    ScalarType,
    ScalarTypeKind,
)
from tiny_dec.decode import decode_rv32i
from tiny_dec.disasm.models import BlockTerminator
from tiny_dec.ir.pcode import const_varnode


def _instruction(address: int) -> CanonicalInstruction:
    return CanonicalInstruction(
        instruction=decode_rv32i(0x00000013, address),
        ops=(),
    )


def _variable_program() -> ProgramVariableFacts:
    block = CanonicalBlock(
        start=0x1000,
        instructions=(_instruction(0x1000), _instruction(0x1004)),
        terminator=BlockTerminator.RETURN,
    )
    canonical = CanonicalFunctionIR(
        entry=0x1000,
        name="main",
        blocks={0x1000: block},
        discovery_order=(0x1000,),
        instruction_index={0x1000: block.instructions[0], 0x1004: block.instructions[1]},
        return_blocks=(0x1000,),
    )
    dataflow_function = FunctionDataflowFacts(
        function=canonical,
        blocks={
            0x1000: BlockDataflowFacts(
                start=0x1000,
                in_state=RegisterState(),
                out_state=RegisterState(),
            )
        },
    )
    dataflow_program = ProgramDataflowFacts(
        program=CanonicalProgramIR(
            root_entry=0x1000,
            functions={0x1000: canonical},
            discovery_order=(0x1000,),
        ),
        functions={0x1000: dataflow_function},
        pending_entries=(0x2000,),
        invalidated_entries=(0x1000,),
    )
    calls = analyze_program_calls(construct_program_ssa(dataflow_program))

    slot = StackSlot(
        frame_offset=-12,
        size=4,
        role=StackSlotRole.LOCAL,
        accesses=(
            StackAccess(
                instruction_address=0x1000,
                block_start=0x1000,
                kind=StackAccessKind.STORE,
                frame_offset=-12,
                size=4,
                base_kind=StackBaseKind.FRAME_POINTER,
                base_register=8,
                value=const_varnode(0),
            ),
            StackAccess(
                instruction_address=0x1004,
                block_start=0x1000,
                kind=StackAccessKind.STORE,
                frame_offset=-12,
                size=4,
                base_kind=StackBaseKind.FRAME_POINTER,
                base_register=8,
                value=const_varnode(7),
            ),
        ),
    )
    stack_function = FunctionStackFacts(
        calls=calls.functions[0x1000],
        frame_size=16,
        dynamic_stack_pointer=False,
        slots=(slot,),
    )
    stack_program = ProgramStackFacts(
        calls=calls,
        functions={0x1000: stack_function},
        pending_entries=calls.pending_entries,
        invalidated_entries=calls.invalidated_entries,
    )
    partition = MemoryPartition(
        kind=MemoryPartitionKind.STACK_SLOT,
        size=4,
        stack_slot=slot,
        accesses=(
            MemoryAccess(
                instruction_address=0x1000,
                block_start=0x1000,
                kind=MemoryAccessKind.STORE,
                size=4,
                value=const_varnode(0),
            ),
            MemoryAccess(
                instruction_address=0x1004,
                block_start=0x1000,
                kind=MemoryAccessKind.STORE,
                size=4,
                value=const_varnode(7),
            ),
        ),
    )
    memory_function = FunctionMemoryFacts(
        stack=stack_function,
        partitions=(partition,),
    )
    memory_program = ProgramMemoryFacts(
        stack=stack_program,
        functions={0x1000: memory_function},
        pending_entries=stack_program.pending_entries,
        invalidated_entries=stack_program.invalidated_entries,
    )
    scalar_function = FunctionScalarTypeFacts(
        memory=memory_function,
        partition_facts=(
            PartitionScalarTypeFact(
                partition=partition,
                scalar_type=ScalarType(ScalarTypeKind.INT, 4),
            ),
        ),
    )
    scalar_program = ProgramScalarTypeFacts(
        memory=memory_program,
        functions={0x1000: scalar_function},
        pending_entries=memory_program.pending_entries,
        invalidated_entries=memory_program.invalidated_entries,
    )
    aggregate_function = FunctionAggregateTypeFacts(
        scalar_types=scalar_function,
        layouts=(),
    )
    aggregate_program = ProgramAggregateTypeFacts(
        scalar_types=scalar_program,
        functions={0x1000: aggregate_function},
        pending_entries=scalar_program.pending_entries,
        invalidated_entries=scalar_program.invalidated_entries,
    )
    variable = RecoveredVariable(
        name="local_12_4",
        kind=VariableKind.LOCAL,
        size=4,
        binding=VariableBinding(
            kind=VariableBindingKind.STACK_SLOT,
            stack_slot=slot,
        ),
        scalar_type=ScalarType(ScalarTypeKind.INT, 4),
        partitions=(partition,),
    )
    function = FunctionVariableFacts(
        aggregate_types=aggregate_function,
        variables=(variable,),
    )
    return ProgramVariableFacts(
        aggregate_types=aggregate_program,
        functions={0x1000: function},
        pending_entries=aggregate_program.pending_entries,
        invalidated_entries=aggregate_program.invalidated_entries,
    )


def test_range_model_pretty_output_is_stable() -> None:
    program = _variable_program()
    function = program.functions[0x1000]
    variable = function.variables[0]
    value = SSAName(SSANameKind.REGISTER, 10, 0, 4)

    value_fact = ValueRangeFact(value=value, value_range=IntegerRange(7, 7))
    variable_fact = VariableRangeFact(variable=variable, value_range=IntegerRange(0, 7))
    branch_fact = BranchRangeRefinement(
        block_start=0x1000,
        successor=0x1010,
        sense=True,
        source_opcode="INT_EQUAL",
        value=value,
        value_range=IntegerRange(7, 7),
    )
    function_facts = FunctionRangeFacts(
        variables=function,
        value_ranges=(value_fact,),
        variable_ranges=(variable_fact,),
        branch_refinements=(branch_fact,),
    )
    program_facts = ProgramRangeFacts(
        variables=program,
        functions={0x1000: function_facts},
        pending_entries=program.pending_entries,
        invalidated_entries=program.invalidated_entries,
    )

    assert format_integer_range(IntegerRange(0, 7)) == "[0, 7]"
    assert format_value_range_fact(value_fact) == "value x10_0:4 range=[7, 7]"
    assert format_variable_range_fact(variable_fact) == "variable local_12_4 range=[0, 7]"
    assert (
        format_branch_range_refinement(branch_fact)
        == "branch 0x1000 -> 0x1010 sense=true source=INT_EQUAL value=x10_0:4 range=[7, 7]"
    )
    assert (
        format_function_range_facts(function_facts)
        == "function 0x1000 name=main frame_size=16 dynamic_sp=no value_ranges=1 "
        "variable_ranges=1 branch_refinements=1 pending=[]\n"
        "variables:\n"
        "  variable local_12_4 range=[0, 7]\n"
        "values:\n"
        "  value x10_0:4 range=[7, 7]\n"
        "branches:\n"
        "  branch 0x1000 -> 0x1010 sense=true source=INT_EQUAL value=x10_0:4 range=[7, 7]"
    )
    assert (
        format_program_range_facts(program_facts)
        == "root: 0x1000\n"
        "order: 0x1000\n"
        "pending: 0x2000\n"
        "invalidated: 0x1000\n"
        "externals:\n"
        "  <none>\n"
        "call_graph:\n"
        "  <none>\n"
        "functions:\n"
        "  function 0x1000 name=main frame_size=16 dynamic_sp=no value_ranges=1 "
        "variable_ranges=1 branch_refinements=1 pending=[]\n"
        "  variables:\n"
        "    variable local_12_4 range=[0, 7]\n"
        "  values:\n"
        "    value x10_0:4 range=[7, 7]\n"
        "  branches:\n"
        "    branch 0x1000 -> 0x1010 sense=true source=INT_EQUAL value=x10_0:4 range=[7, 7]"
    )
