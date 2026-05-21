"""Stage-9 stack recovery public data structures and pretty-printers."""

from tiny_dec.analysis.stack.models import (
    FunctionStackFacts,
    ProgramStackFacts,
    StackAccess,
    StackAccessKind,
    StackBaseKind,
    StackFrameBase,
    StackSlot,
    StackSlotRole,
)
from tiny_dec.analysis.stack.pretty import (
    format_function_stack_facts,
    format_program_stack_facts,
    format_stack_access,
    format_stack_frame_base,
    format_stack_slot,
)
from tiny_dec.analysis.stack.transform import (
    analyze_function_stack,
    analyze_program_stack,
    build_function_stack_facts,
    build_program_stack_facts,
)

__all__ = [
    "StackBaseKind",
    "StackFrameBase",
    "StackAccessKind",
    "StackSlotRole",
    "StackAccess",
    "StackSlot",
    "FunctionStackFacts",
    "ProgramStackFacts",
    "format_stack_frame_base",
    "format_stack_access",
    "format_stack_slot",
    "format_function_stack_facts",
    "format_program_stack_facts",
    "analyze_function_stack",
    "analyze_program_stack",
    "build_function_stack_facts",
    "build_program_stack_facts",
]
