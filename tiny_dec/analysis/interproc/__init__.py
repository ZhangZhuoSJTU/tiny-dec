"""Interprocedural summary public data structures and deterministic formatters."""

from tiny_dec.analysis.interproc.models import (
    FunctionEffectSummary,
    FunctionInterprocFacts,
    InferredPrototype,
    InterprocInvalidation,
    ProgramInterprocFacts,
    PrototypeRegister,
    PrototypeStackParameter,
)
from tiny_dec.analysis.interproc.pretty import (
    format_function_effect_summary,
    format_function_interproc_facts,
    format_inferred_prototype,
    format_interproc_invalidation,
    format_program_interproc_facts,
    format_prototype_register,
    format_prototype_stack_parameter,
)
from tiny_dec.analysis.interproc.transform import (
    analyze_function_interproc,
    analyze_program_interproc,
    build_function_interproc_facts,
    build_program_interproc_facts,
)

__all__ = [
    "PrototypeRegister",
    "PrototypeStackParameter",
    "InferredPrototype",
    "FunctionEffectSummary",
    "InterprocInvalidation",
    "FunctionInterprocFacts",
    "ProgramInterprocFacts",
    "format_prototype_register",
    "format_prototype_stack_parameter",
    "format_inferred_prototype",
    "format_function_effect_summary",
    "format_interproc_invalidation",
    "format_function_interproc_facts",
    "format_program_interproc_facts",
    "analyze_function_interproc",
    "analyze_program_interproc",
    "build_function_interproc_facts",
    "build_program_interproc_facts",
]
