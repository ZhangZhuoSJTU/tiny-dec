from tiny_dec.analysis.simplify.models import (
    CanonicalBlock,
    CanonicalFunctionIR,
    CanonicalInstruction,
    CanonicalProgramIR,
)
from tiny_dec.analysis.simplify.pretty import (
    format_canonical_block,
    format_canonical_function_ir,
    format_canonical_instruction,
    format_canonical_program_ir,
)
from tiny_dec.analysis.simplify.transform import (
    build_canonical_function_ir,
    build_canonical_program_ir,
    canonicalize_function_ir,
    canonicalize_instruction,
    canonicalize_program_ir,
)

__all__ = [
    "CanonicalBlock",
    "CanonicalFunctionIR",
    "CanonicalInstruction",
    "CanonicalProgramIR",
    "build_canonical_function_ir",
    "build_canonical_program_ir",
    "canonicalize_function_ir",
    "canonicalize_instruction",
    "canonicalize_program_ir",
    "format_canonical_block",
    "format_canonical_function_ir",
    "format_canonical_instruction",
    "format_canonical_program_ir",
]
