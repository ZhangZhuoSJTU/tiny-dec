from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, cast

from tiny_dec.analysis.interproc import (
    FunctionEffectSummary,
    FunctionInterprocFacts,
    InferredPrototype,
    InterprocInvalidation,
    ProgramInterprocFacts,
    PrototypeRegister,
    PrototypeStackParameter,
    format_function_effect_summary,
    format_function_interproc_facts,
    format_inferred_prototype,
    format_interproc_invalidation,
    format_program_interproc_facts,
    format_prototype_register,
    format_prototype_stack_parameter,
)
from tiny_dec.analysis.types import ScalarType, ScalarTypeKind


def _load_helpers() -> Any:
    spec = importlib.util.spec_from_file_location(
        "post_15_interproc_helpers_for_models",
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


def test_interproc_model_pretty_output_is_stable() -> None:
    range_program = build_range_program(
        root_entry=0x1000,
        function_specs=(
            FunctionSpec(
                dataflow=function(
                    0x1000,
                    (block(0x1000, instruction(0x1000)),),
                    name="main",
                ),
                frame_size=16,
            ),
        ),
        pending_entries=(0x2000,),
    )
    range_function = range_program.functions[0x1000]

    parameter = PrototypeRegister(
        register=10,
        size=4,
        scalar_type=ScalarType(ScalarTypeKind.INT, 4),
        variable_name="arg_x10_4",
    )
    stack_parameter = PrototypeStackParameter(
        stack_offset=0,
        size=4,
        scalar_type=ScalarType(ScalarTypeKind.INT, 4),
        variable_name="local_0_4",
    )
    returned = PrototypeRegister(
        register=10,
        size=4,
        scalar_type=ScalarType(ScalarTypeKind.INT, 4),
    )
    prototype = InferredPrototype(
        parameters=(parameter, stack_parameter),
        returns=(returned,),
    )
    effects = FunctionEffectSummary(
        global_reads=(0x2000,),
        global_writes=(0x2004,),
        indirect_reads=False,
        indirect_writes=True,
    )
    function_facts = FunctionInterprocFacts(
        ranges=range_function,
        prototype=prototype,
        effects=effects,
    )
    invalidation = InterprocInvalidation(
        caller_entry=0x1000,
        callee_entry=0x1200,
        reason="noreturn_callee",
    )
    program = ProgramInterprocFacts(
        ranges=range_program,
        functions={0x1000: function_facts},
        scheduler_invalidations=(invalidation,),
        pending_entries=range_program.pending_entries,
        invalidated_entries=(0x1000,),
    )

    assert format_prototype_register(parameter) == "x10:4 type=int:4 name=arg_x10_4"
    assert (
        format_prototype_stack_parameter(stack_parameter)
        == "stack+0:4 type=int:4 name=local_0_4"
    )
    assert (
        format_inferred_prototype(prototype)
        == "prototype params=[x10:4 type=int:4 name=arg_x10_4, stack+0:4 type=int:4 name=local_0_4] returns=[x10:4 type=int:4] no_return=no"
    )
    assert (
        format_function_effect_summary(effects)
        == "effects reads=[0x2000] writes=[0x2004] indirect_reads=no indirect_writes=yes"
    )
    assert (
        format_interproc_invalidation(invalidation)
        == "invalidate caller=0x1000 callee=0x1200 reason=noreturn_callee"
    )

    function_rendered = format_function_interproc_facts(function_facts)
    assert "function 0x1000 name=main frame_size=16 dynamic_sp=no params=2 returns=1 no_return=no globals_read=1 globals_written=1 pending=[]" in function_rendered
    assert "param x10:4 type=int:4 name=arg_x10_4" in function_rendered
    assert "param stack+0:4 type=int:4 name=local_0_4" in function_rendered
    assert "return x10:4 type=int:4" in function_rendered
    assert "effects reads=[0x2000] writes=[0x2004] indirect_reads=no indirect_writes=yes" in function_rendered

    program_rendered = format_program_interproc_facts(program)
    assert "pending: 0x2000" in program_rendered
    assert "invalidated: 0x1000" in program_rendered
    assert "scheduler_invalidations:" in program_rendered
    assert "invalidate caller=0x1000 callee=0x1200 reason=noreturn_callee" in program_rendered
