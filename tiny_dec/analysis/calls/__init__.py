"""Stage-8 call modeling on top of SSA."""
from tiny_dec.analysis.calls.models import (
    CallABI,
    CallRegisterValue,
    CallStackValue,
    FunctionCallFacts,
    KnownExternalSignature,
    ModeledCallSite,
    ProgramCallFacts,
    RV32I_ILP32_CALL_ABI,
)
from tiny_dec.analysis.calls.pretty import (
    format_call_abi,
    format_call_register_value,
    format_call_stack_value,
    format_function_call_facts,
    format_known_external_signature,
    format_modeled_callsite,
    format_program_call_facts,
)
from tiny_dec.analysis.calls.transform import (
    analyze_function_calls,
    analyze_program_calls,
    build_function_call_facts,
    build_program_call_facts,
)

__all__ = [
    "CallABI",
    "CallRegisterValue",
    "CallStackValue",
    "KnownExternalSignature",
    "FunctionCallFacts",
    "ModeledCallSite",
    "ProgramCallFacts",
    "RV32I_ILP32_CALL_ABI",
    "format_call_abi",
    "format_call_register_value",
    "format_call_stack_value",
    "format_known_external_signature",
    "format_function_call_facts",
    "format_modeled_callsite",
    "format_program_call_facts",
    "analyze_function_calls",
    "analyze_program_calls",
    "build_function_call_facts",
    "build_program_call_facts",
]
