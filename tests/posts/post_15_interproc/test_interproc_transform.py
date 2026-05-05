from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, cast

import pytest

pytest.importorskip("pwn")

from tiny_dec.analysis.highvars import (
    RecoveredVariable,
    VariableBinding,
    VariableBindingKind,
    VariableKind,
)
from tiny_dec.analysis.interproc import (
    PrototypeRegister,
    PrototypeStackParameter,
    analyze_program_interproc,
    build_program_interproc_facts,
)
from tiny_dec.analysis.memory import (
    MemoryAccess,
    MemoryAccessKind,
    MemoryPartition,
    MemoryPartitionKind,
)
from tiny_dec.analysis.ssa.models import SSAName, SSANameKind
from tiny_dec.analysis.stack import StackSlot, StackSlotRole
from tiny_dec.analysis.types import (
    PartitionScalarTypeFact,
    ScalarType,
    ScalarTypeKind,
    ValueScalarTypeFact,
)
from tiny_dec.disasm.models import BlockEdge, BlockEdgeKind, BlockTerminator
from tiny_dec.ir.function_ir import CallSite
from tiny_dec.ir.pcode import PcodeOp, PcodeOpcode, const_varnode, register_varnode
from tiny_dec.loader import ProgramView


def _load_helpers() -> Any:
    spec = importlib.util.spec_from_file_location(
        "post_15_interproc_helpers",
        Path(__file__).with_name("_helpers.py"),
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return cast(Any, module)


_HELPERS = _load_helpers()
FunctionSpec = _HELPERS.FunctionSpec
block = _HELPERS.block
build_range_program = _HELPERS.build_range_program
function = _HELPERS.function
instruction = _HELPERS.instruction


def _parameter_registers(
    facts,
) -> tuple[int, ...]:
    return tuple(
        carrier.register
        for carrier in facts.prototype.parameters
        if isinstance(carrier, PrototypeRegister)
    )


def test_analyze_program_interproc_recovers_prototype_and_effect_summary() -> None:
    live_in_x10 = SSAName(SSANameKind.REGISTER, 10, 0, 4)
    live_in_x11 = SSAName(SSANameKind.REGISTER, 11, 0, 4)

    range_program = build_range_program(
        root_entry=0x1000,
        function_specs=(
            FunctionSpec(
                dataflow=function(
                    0x1000,
                    (
                        block(
                            0x1000,
                            instruction(
                                0x1000,
                                PcodeOp(
                                    opcode=PcodeOpcode.COPY,
                                    inputs=(register_varnode(10),),
                                    output=register_varnode(12),
                                ),
                            ),
                            instruction(
                                0x1004,
                                PcodeOp(
                                    opcode=PcodeOpcode.INT_ADD,
                                    inputs=(register_varnode(11), const_varnode(1)),
                                    output=register_varnode(13),
                                ),
                            ),
                            instruction(
                                0x1008,
                                PcodeOp(
                                    opcode=PcodeOpcode.COPY,
                                    inputs=(register_varnode(12),),
                                    output=register_varnode(10),
                                ),
                            ),
                        ),
                    ),
                    name="parse",
                ),
                stack_slots=(
                    StackSlot(
                        frame_offset=-16,
                        size=4,
                        role=StackSlotRole.ARGUMENT_HOME,
                        argument_register=11,
                    ),
                    StackSlot(
                        frame_offset=-12,
                        size=4,
                        role=StackSlotRole.ARGUMENT_HOME,
                        argument_register=10,
                    ),
                ),
                memory_partitions=(
                    MemoryPartition(
                        kind=MemoryPartitionKind.STACK_SLOT,
                        size=4,
                        stack_slot=StackSlot(
                            frame_offset=-16,
                            size=4,
                            role=StackSlotRole.ARGUMENT_HOME,
                            argument_register=11,
                        ),
                    ),
                    MemoryPartition(
                        kind=MemoryPartitionKind.STACK_SLOT,
                        size=4,
                        stack_slot=StackSlot(
                            frame_offset=-12,
                            size=4,
                            role=StackSlotRole.ARGUMENT_HOME,
                            argument_register=10,
                        ),
                    ),
                    MemoryPartition(
                        kind=MemoryPartitionKind.ABSOLUTE,
                        size=4,
                        absolute_address=0x2000,
                        accesses=(
                            MemoryAccess(
                                instruction_address=0x1000,
                                block_start=0x1000,
                                kind=MemoryAccessKind.LOAD,
                                size=4,
                            ),
                        ),
                    ),
                    MemoryPartition(
                        kind=MemoryPartitionKind.ABSOLUTE,
                        size=4,
                        absolute_address=0x2004,
                        accesses=(
                            MemoryAccess(
                                instruction_address=0x1004,
                                block_start=0x1000,
                                kind=MemoryAccessKind.STORE,
                                size=4,
                                value=live_in_x11,
                            ),
                        ),
                    ),
                    MemoryPartition(
                        kind=MemoryPartitionKind.VALUE,
                        size=4,
                        base_value=live_in_x10,
                        accesses=(
                            MemoryAccess(
                                instruction_address=0x1008,
                                block_start=0x1000,
                                kind=MemoryAccessKind.LOAD,
                                size=4,
                            ),
                        ),
                    ),
                ),
                partition_facts=(
                    PartitionScalarTypeFact(
                        partition=MemoryPartition(
                            kind=MemoryPartitionKind.STACK_SLOT,
                            size=4,
                            stack_slot=StackSlot(
                                frame_offset=-16,
                                size=4,
                                role=StackSlotRole.ARGUMENT_HOME,
                                argument_register=11,
                            ),
                        ),
                        scalar_type=ScalarType(ScalarTypeKind.INT, 4),
                    ),
                    PartitionScalarTypeFact(
                        partition=MemoryPartition(
                            kind=MemoryPartitionKind.STACK_SLOT,
                            size=4,
                            stack_slot=StackSlot(
                                frame_offset=-12,
                                size=4,
                                role=StackSlotRole.ARGUMENT_HOME,
                                argument_register=10,
                            ),
                        ),
                        scalar_type=ScalarType(ScalarTypeKind.POINTER, 4),
                    ),
                ),
                value_facts=(
                    ValueScalarTypeFact(
                        value=live_in_x10,
                        scalar_type=ScalarType(ScalarTypeKind.POINTER, 4),
                    ),
                    ValueScalarTypeFact(
                        value=live_in_x11,
                        scalar_type=ScalarType(ScalarTypeKind.INT, 4),
                    ),
                ),
                variables=(
                    RecoveredVariable(
                        name="arg_x11_4",
                        kind=VariableKind.PARAMETER,
                        size=4,
                        binding=VariableBinding(
                            kind=VariableBindingKind.STACK_SLOT,
                            stack_slot=StackSlot(
                                frame_offset=-16,
                                size=4,
                                role=StackSlotRole.ARGUMENT_HOME,
                                argument_register=11,
                            ),
                        ),
                        scalar_type=ScalarType(ScalarTypeKind.INT, 4),
                        root_value=live_in_x11,
                        partitions=(
                            MemoryPartition(
                                kind=MemoryPartitionKind.STACK_SLOT,
                                size=4,
                                stack_slot=StackSlot(
                                    frame_offset=-16,
                                    size=4,
                                    role=StackSlotRole.ARGUMENT_HOME,
                                    argument_register=11,
                                ),
                            ),
                        ),
                    ),
                    RecoveredVariable(
                        name="arg_x10_4",
                        kind=VariableKind.PARAMETER,
                        size=4,
                        binding=VariableBinding(
                            kind=VariableBindingKind.STACK_SLOT,
                            stack_slot=StackSlot(
                                frame_offset=-12,
                                size=4,
                                role=StackSlotRole.ARGUMENT_HOME,
                                argument_register=10,
                            ),
                        ),
                        scalar_type=ScalarType(ScalarTypeKind.POINTER, 4),
                        root_value=live_in_x10,
                        partitions=(
                            MemoryPartition(
                                kind=MemoryPartitionKind.STACK_SLOT,
                                size=4,
                                stack_slot=StackSlot(
                                    frame_offset=-12,
                                    size=4,
                                    role=StackSlotRole.ARGUMENT_HOME,
                                    argument_register=10,
                                ),
                            ),
                        ),
                    ),
                ),
                frame_size=16,
            ),
        ),
        pending_entries=(0x4000,),
        invalidated_entries=(0x1000,),
    )

    result = analyze_program_interproc(range_program)
    facts = result.functions[0x1000]

    assert result.pending_entries == (0x4000,)
    assert result.invalidated_entries == (0x1000,)
    assert facts.prototype.no_return is False
    assert _parameter_registers(facts) == (10, 11)
    assert facts.prototype.parameters[0].scalar_type == ScalarType(ScalarTypeKind.POINTER, 4)
    assert facts.prototype.parameters[1].scalar_type == ScalarType(ScalarTypeKind.INT, 4)
    assert facts.prototype.returns == ()
    assert facts.effects.global_reads == (0x2000,)
    assert facts.effects.global_writes == (0x2004,)
    assert facts.effects.indirect_reads is True
    assert facts.effects.indirect_writes is False


def test_analyze_program_interproc_invalidates_callers_of_noreturn_callees() -> None:
    range_program = build_range_program(
        root_entry=0x1000,
        function_specs=(
            FunctionSpec(
                dataflow=function(
                    0x1000,
                    (
                        block(
                            0x1000,
                            instruction(
                                0x1000,
                                PcodeOp(
                                    opcode=PcodeOpcode.CALL,
                                    inputs=(const_varnode(0x1200),),
                                ),
                            ),
                        ),
                    ),
                    name="main",
                    callsites=(
                        CallSite(
                            instruction_address=0x1000,
                            block_start=0x1000,
                            target=0x1200,
                        ),
                    ),
                    direct_callees=(0x1200,),
                ),
                frame_size=16,
            ),
            FunctionSpec(
                dataflow=function(
                    0x1200,
                    (
                        block(
                            0x1200,
                            instruction(0x1200),
                            terminator=BlockTerminator.STOP,
                        ),
                    ),
                    name="sink",
                ),
            ),
        ),
        invalidated_entries=(0x1200,),
    )

    result = analyze_program_interproc(range_program)
    sink = result.functions[0x1200]

    assert sink.prototype.no_return is True
    assert result.scheduler_invalidations
    assert result.scheduler_invalidations[0].caller_entry == 0x1000
    assert result.scheduler_invalidations[0].callee_entry == 0x1200
    assert result.scheduler_invalidations[0].reason == "noreturn_callee"
    assert result.invalidated_entries == (0x1000, 0x1200)


def test_analyze_program_interproc_drops_compare_scratch_and_unsupported_forwarded_returns() -> None:
    range_program = build_range_program(
        root_entry=0x1000,
        function_specs=(
            FunctionSpec(
                dataflow=function(
                    0x1000,
                    (
                        block(
                            0x1000,
                            instruction(
                                0x1000,
                                PcodeOp(
                                    opcode=PcodeOpcode.CALL,
                                    inputs=(const_varnode(0x1100),),
                                ),
                            ),
                            terminator=BlockTerminator.RETURN,
                            call_targets=(0x1100,),
                        ),
                    ),
                    name="main",
                    callsites=(
                        CallSite(
                            instruction_address=0x1000,
                            block_start=0x1000,
                            target=0x1100,
                            target_name="dispatch",
                        ),
                    ),
                    direct_callees=(0x1100,),
                ),
            ),
            FunctionSpec(
                dataflow=function(
                    0x1100,
                    (
                        block(
                            0x1100,
                            instruction(0x1100),
                            successors=(
                                BlockEdge(BlockEdgeKind.BRANCH_TAKEN, 0x1110),
                                BlockEdge(BlockEdgeKind.FALLTHROUGH, 0x1120),
                            ),
                            terminator=BlockTerminator.BRANCH,
                        ),
                        block(
                            0x1110,
                            instruction(
                                0x1110,
                                PcodeOp(
                                    opcode=PcodeOpcode.COPY,
                                    inputs=(const_varnode(1),),
                                    output=register_varnode(11),
                                ),
                                PcodeOp(
                                    opcode=PcodeOpcode.INT_EQUAL,
                                    inputs=(register_varnode(10), register_varnode(11)),
                                ),
                            ),
                            successors=(BlockEdge(BlockEdgeKind.JUMP, 0x1130),),
                            terminator=BlockTerminator.JUMP,
                        ),
                        block(
                            0x1120,
                            instruction(0x1120),
                            successors=(BlockEdge(BlockEdgeKind.JUMP, 0x1130),),
                            terminator=BlockTerminator.JUMP,
                        ),
                        block(
                            0x1130,
                            instruction(
                                0x1130,
                                PcodeOp(
                                    opcode=PcodeOpcode.COPY,
                                    inputs=(const_varnode(7),),
                                    output=register_varnode(10),
                                ),
                            ),
                            terminator=BlockTerminator.RETURN,
                        ),
                    ),
                    name="dispatch",
                ),
            ),
        ),
    )

    result = analyze_program_interproc(range_program)
    main_facts = result.functions[0x1000]
    dispatch_facts = result.functions[0x1100]

    assert tuple(carrier.register for carrier in dispatch_facts.prototype.returns) == (10,)
    assert tuple(carrier.register for carrier in main_facts.prototype.returns) == (10,)


def test_analyze_program_interproc_prunes_unobserved_root_only_internal_parameter_without_inventing_observed_one(
) -> None:
    range_program = build_range_program(
        root_entry=0x1000,
        function_specs=(
            FunctionSpec(
                dataflow=function(
                    0x1000,
                    (
                        block(
                            0x1000,
                            instruction(
                                0x1000,
                                PcodeOp(
                                    opcode=PcodeOpcode.COPY,
                                    inputs=(const_varnode(5),),
                                    output=register_varnode(10),
                                ),
                            ),
                            instruction(
                                0x1004,
                                PcodeOp(
                                    opcode=PcodeOpcode.CALL,
                                    inputs=(const_varnode(0x1100),),
                                ),
                            ),
                            terminator=BlockTerminator.RETURN,
                            call_targets=(0x1100,),
                        ),
                    ),
                    name="main",
                    callsites=(
                        CallSite(
                            instruction_address=0x1004,
                            block_start=0x1000,
                            target=0x1100,
                            target_name="sum_like",
                        ),
                    ),
                    direct_callees=(0x1100,),
                ),
            ),
            FunctionSpec(
                dataflow=function(
                    0x1100,
                    (
                        block(
                            0x1100,
                            instruction(
                                0x1100,
                                PcodeOp(
                                    opcode=PcodeOpcode.INT_ADD,
                                    inputs=(register_varnode(11), const_varnode(1)),
                                    output=register_varnode(13),
                                ),
                            ),
                            instruction(
                                0x1104,
                                PcodeOp(
                                    opcode=PcodeOpcode.COPY,
                                    inputs=(const_varnode(7),),
                                    output=register_varnode(10),
                                ),
                            ),
                            terminator=BlockTerminator.RETURN,
                        ),
                    ),
                    name="sum_like",
                ),
            ),
        ),
    )

    result = analyze_program_interproc(range_program)
    callee_facts = result.functions[0x1100]

    assert _parameter_registers(callee_facts) == ()


def test_analyze_program_interproc_ignores_observed_only_internal_parameter_without_local_support(
) -> None:
    range_program = build_range_program(
        root_entry=0x1000,
        function_specs=(
            FunctionSpec(
                dataflow=function(
                    0x1000,
                    (
                        block(
                            0x1000,
                            instruction(
                                0x1000,
                                PcodeOp(
                                    opcode=PcodeOpcode.COPY,
                                    inputs=(const_varnode(1),),
                                    output=register_varnode(10),
                                ),
                            ),
                            instruction(
                                0x1004,
                                PcodeOp(
                                    opcode=PcodeOpcode.COPY,
                                    inputs=(const_varnode(2),),
                                    output=register_varnode(11),
                                ),
                            ),
                            instruction(
                                0x1008,
                                PcodeOp(
                                    opcode=PcodeOpcode.COPY,
                                    inputs=(const_varnode(3),),
                                    output=register_varnode(12),
                                ),
                            ),
                            instruction(
                                0x100c,
                                PcodeOp(
                                    opcode=PcodeOpcode.CALL,
                                    inputs=(const_varnode(0x1100),),
                                ),
                            ),
                            terminator=BlockTerminator.RETURN,
                            call_targets=(0x1100,),
                        ),
                    ),
                    name="main",
                    callsites=(
                        CallSite(
                            instruction_address=0x100c,
                            block_start=0x1000,
                            target=0x1100,
                            target_name="adjust_like",
                        ),
                    ),
                    direct_callees=(0x1100,),
                ),
            ),
            FunctionSpec(
                dataflow=function(
                    0x1100,
                    (
                        block(
                            0x1100,
                            instruction(
                                0x1100,
                                PcodeOp(
                                    opcode=PcodeOpcode.INT_ADD,
                                    inputs=(register_varnode(10), register_varnode(11)),
                                    output=register_varnode(13),
                                ),
                            ),
                            instruction(
                                0x1104,
                                PcodeOp(
                                    opcode=PcodeOpcode.COPY,
                                    inputs=(register_varnode(13),),
                                    output=register_varnode(10),
                                ),
                            ),
                            terminator=BlockTerminator.RETURN,
                        ),
                    ),
                    name="adjust_like",
                ),
            ),
        ),
    )

    result = analyze_program_interproc(range_program)
    callee_facts = result.functions[0x1100]

    assert _parameter_registers(callee_facts) == (10, 11)


def test_analyze_program_interproc_prunes_unconsumed_secondary_internal_return() -> None:
    range_program = build_range_program(
        root_entry=0x1000,
        function_specs=(
            FunctionSpec(
                dataflow=function(
                    0x1000,
                    (
                        block(
                            0x1000,
                            instruction(
                                0x1000,
                                PcodeOp(
                                    opcode=PcodeOpcode.COPY,
                                    inputs=(const_varnode(5),),
                                    output=register_varnode(10),
                                ),
                            ),
                            instruction(
                                0x1004,
                                PcodeOp(
                                    opcode=PcodeOpcode.CALL,
                                    inputs=(const_varnode(0x1100),),
                                ),
                            ),
                            terminator=BlockTerminator.RETURN,
                            call_targets=(0x1100,),
                        ),
                    ),
                    name="main",
                    callsites=(
                        CallSite(
                            instruction_address=0x1004,
                            block_start=0x1000,
                            target=0x1100,
                            target_name="helper",
                        ),
                    ),
                    direct_callees=(0x1100,),
                ),
            ),
            FunctionSpec(
                dataflow=function(
                    0x1100,
                    (
                        block(
                            0x1100,
                            instruction(
                                0x1100,
                                PcodeOp(
                                    opcode=PcodeOpcode.COPY,
                                    inputs=(register_varnode(10),),
                                    output=register_varnode(11),
                                ),
                            ),
                            instruction(
                                0x1104,
                                PcodeOp(
                                    opcode=PcodeOpcode.INT_ADD,
                                    inputs=(register_varnode(11), const_varnode(1)),
                                    output=register_varnode(10),
                                ),
                            ),
                            terminator=BlockTerminator.RETURN,
                        ),
                    ),
                    name="helper",
                ),
            ),
        ),
    )

    result = analyze_program_interproc(range_program)
    main_facts = result.functions[0x1000]
    helper_facts = result.functions[0x1100]

    assert _parameter_registers(helper_facts) == (10,)
    assert tuple(carrier.register for carrier in helper_facts.prototype.returns) == (10,)
    assert tuple(carrier.register for carrier in main_facts.prototype.returns) == (10,)


def test_analyze_program_interproc_does_not_invent_internal_parameter_from_caller_only_carrier() -> None:
    range_program = build_range_program(
        root_entry=0x1000,
        function_specs=(
            FunctionSpec(
                dataflow=function(
                    0x1000,
                    (
                        block(
                            0x1000,
                            instruction(
                                0x1000,
                                PcodeOp(
                                    opcode=PcodeOpcode.COPY,
                                    inputs=(register_varnode(10),),
                                    output=register_varnode(12),
                                ),
                            ),
                            instruction(
                                0x1004,
                                PcodeOp(
                                    opcode=PcodeOpcode.CALL,
                                    inputs=(const_varnode(0x1100),),
                                ),
                            ),
                            terminator=BlockTerminator.RETURN,
                            call_targets=(0x1100,),
                        ),
                    ),
                    name="main",
                    callsites=(
                        CallSite(
                            instruction_address=0x1004,
                            block_start=0x1000,
                            target=0x1100,
                            target_name="helper",
                        ),
                    ),
                    direct_callees=(0x1100,),
                ),
            ),
            FunctionSpec(
                dataflow=function(
                    0x1100,
                    (
                        block(
                            0x1100,
                            instruction(
                                0x1100,
                                PcodeOp(
                                    opcode=PcodeOpcode.INT_ADD,
                                    inputs=(register_varnode(10), const_varnode(1)),
                                    output=register_varnode(10),
                                ),
                            ),
                            terminator=BlockTerminator.RETURN,
                        ),
                    ),
                    name="helper",
                ),
            ),
        ),
    )

    result = analyze_program_interproc(range_program)
    helper_facts = result.functions[0x1100]

    assert _parameter_registers(helper_facts) == (10,)


def test_analyze_program_interproc_keeps_secondary_return_used_as_later_call_argument() -> None:
    range_program = build_range_program(
        root_entry=0x1000,
        function_specs=(
            FunctionSpec(
                dataflow=function(
                    0x1000,
                    (
                        block(
                            0x1000,
                            instruction(
                                0x1000,
                                PcodeOp(
                                    opcode=PcodeOpcode.COPY,
                                    inputs=(const_varnode(5),),
                                    output=register_varnode(10),
                                ),
                            ),
                            instruction(
                                0x1004,
                                PcodeOp(
                                    opcode=PcodeOpcode.CALL,
                                    inputs=(const_varnode(0x1100),),
                                ),
                            ),
                            instruction(
                                0x1008,
                                PcodeOp(
                                    opcode=PcodeOpcode.CALL,
                                    inputs=(const_varnode(0x1200),),
                                ),
                            ),
                            terminator=BlockTerminator.RETURN,
                            call_targets=(0x1100, 0x1200),
                        ),
                    ),
                    name="main",
                    callsites=(
                        CallSite(
                            instruction_address=0x1004,
                            block_start=0x1000,
                            target=0x1100,
                            target_name="helper",
                        ),
                        CallSite(
                            instruction_address=0x1008,
                            block_start=0x1000,
                            target=0x1200,
                            target_name="consume",
                        ),
                    ),
                    direct_callees=(0x1100, 0x1200),
                ),
            ),
            FunctionSpec(
                dataflow=function(
                    0x1100,
                    (
                        block(
                            0x1100,
                            instruction(
                                0x1100,
                                PcodeOp(
                                    opcode=PcodeOpcode.COPY,
                                    inputs=(register_varnode(10),),
                                    output=register_varnode(11),
                                ),
                            ),
                            instruction(
                                0x1104,
                                PcodeOp(
                                    opcode=PcodeOpcode.INT_ADD,
                                    inputs=(register_varnode(11), const_varnode(1)),
                                    output=register_varnode(10),
                                ),
                            ),
                            terminator=BlockTerminator.RETURN,
                        ),
                    ),
                    name="helper",
                ),
            ),
            FunctionSpec(
                dataflow=function(
                    0x1200,
                    (
                        block(
                            0x1200,
                            instruction(
                                0x1200,
                                PcodeOp(
                                    opcode=PcodeOpcode.COPY,
                                    inputs=(register_varnode(10),),
                                    output=register_varnode(10),
                                ),
                            ),
                            terminator=BlockTerminator.RETURN,
                        ),
                    ),
                    name="consume",
                ),
            ),
        ),
    )

    result = analyze_program_interproc(range_program)
    helper_facts = result.functions[0x1100]

    assert tuple(carrier.register for carrier in helper_facts.prototype.returns) == (10, 11)


def test_build_program_interproc_recovers_stack_parameters_from_fixture(
    fixture_binary,
) -> None:
    view = ProgramView(fixture_binary("fixture_stack_args_O0_nopie"))
    entry = view.find_main().address
    sum10 = view.get_symbol_address("sum10")
    assert entry is not None
    assert sum10 is not None

    program = build_program_interproc_facts(view, entry)
    facts = program.functions[sum10]

    assert tuple(
        carrier.register
        for carrier in facts.prototype.parameters
        if isinstance(carrier, PrototypeRegister)
    ) == (10, 11, 12, 13, 14, 15, 16, 17)
    assert tuple(
        carrier.stack_offset
        for carrier in facts.prototype.parameters
        if isinstance(carrier, PrototypeStackParameter)
    ) == (0, 4)
    assert tuple(
        carrier.variable_name
        for carrier in facts.prototype.parameters
        if isinstance(carrier, PrototypeStackParameter)
    ) == ("local_0_4", "local_4_4")
    assert tuple(carrier.register for carrier in facts.prototype.returns) == (10,)
