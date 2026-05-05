"""Scalar and aggregate type recovery public data structures and pretty-printers."""

from tiny_dec.analysis.types.aggregate_models import (
    AggregateField,
    AggregateLayout,
    AggregateRoot,
    AggregateRootKind,
    FunctionAggregateTypeFacts,
    ProgramAggregateTypeFacts,
)
from tiny_dec.analysis.types.aggregate_pretty import (
    format_aggregate_field,
    format_aggregate_layout,
    format_aggregate_root,
    format_function_aggregate_type_facts,
    format_program_aggregate_type_facts,
)
from tiny_dec.analysis.types.aggregate_transform import (
    analyze_function_aggregate_types,
    analyze_program_aggregate_types,
    build_function_aggregate_type_facts,
    build_program_aggregate_type_facts,
)
from tiny_dec.analysis.types.models import (
    FunctionScalarTypeFacts,
    PartitionScalarTypeFact,
    ProgramScalarTypeFacts,
    ScalarType,
    ScalarTypeKind,
    ValueScalarTypeFact,
)
from tiny_dec.analysis.types.pretty import (
    format_function_scalar_type_facts,
    format_partition_scalar_type_fact,
    format_program_scalar_type_facts,
    format_scalar_type,
    format_value_scalar_type_fact,
)
from tiny_dec.analysis.types.transform import (
    analyze_function_scalar_types,
    analyze_program_scalar_types,
    build_function_scalar_type_facts,
    build_program_scalar_type_facts,
)

__all__ = [
    "ScalarTypeKind",
    "ScalarType",
    "PartitionScalarTypeFact",
    "ValueScalarTypeFact",
    "FunctionScalarTypeFacts",
    "ProgramScalarTypeFacts",
    "AggregateRootKind",
    "AggregateRoot",
    "AggregateField",
    "AggregateLayout",
    "FunctionAggregateTypeFacts",
    "ProgramAggregateTypeFacts",
    "format_scalar_type",
    "format_partition_scalar_type_fact",
    "format_value_scalar_type_fact",
    "format_function_scalar_type_facts",
    "format_program_scalar_type_facts",
    "format_aggregate_root",
    "format_aggregate_field",
    "format_aggregate_layout",
    "format_function_aggregate_type_facts",
    "format_program_aggregate_type_facts",
    "analyze_function_scalar_types",
    "analyze_program_scalar_types",
    "build_function_scalar_type_facts",
    "build_program_scalar_type_facts",
    "analyze_function_aggregate_types",
    "analyze_program_aggregate_types",
    "build_function_aggregate_type_facts",
    "build_program_aggregate_type_facts",
]
