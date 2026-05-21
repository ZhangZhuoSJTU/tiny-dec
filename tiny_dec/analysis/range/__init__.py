"""Range-refinement public data structures and deterministic pretty-printers."""

from tiny_dec.analysis.range.models import (
    BranchRangeRefinement,
    FunctionRangeFacts,
    IntegerRange,
    ProgramRangeFacts,
    ValueRangeFact,
    VariableRangeFact,
)
from tiny_dec.analysis.range.pretty import (
    format_branch_range_refinement,
    format_function_range_facts,
    format_integer_range,
    format_program_range_facts,
    format_value_range_fact,
    format_variable_range_fact,
)
from tiny_dec.analysis.range.transform import (
    analyze_function_ranges,
    analyze_program_ranges,
    build_function_range_facts,
    build_program_range_facts,
)

__all__ = [
    "IntegerRange",
    "ValueRangeFact",
    "VariableRangeFact",
    "BranchRangeRefinement",
    "FunctionRangeFacts",
    "ProgramRangeFacts",
    "format_integer_range",
    "format_value_range_fact",
    "format_variable_range_fact",
    "format_branch_range_refinement",
    "format_function_range_facts",
    "format_program_range_facts",
    "analyze_function_ranges",
    "analyze_program_ranges",
    "build_function_range_facts",
    "build_program_range_facts",
]
