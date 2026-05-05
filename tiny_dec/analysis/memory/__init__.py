"""Stage-10 memory modeling public API."""

from tiny_dec.analysis.memory.models import (
    FunctionMemoryFacts,
    MemoryAccess,
    MemoryAccessKind,
    MemoryPartition,
    MemoryPartitionKind,
    ProgramMemoryFacts,
)
from tiny_dec.analysis.memory.pretty import (
    format_function_memory_facts,
    format_memory_access,
    format_memory_partition,
    format_program_memory_facts,
)
from tiny_dec.analysis.memory.transform import (
    analyze_function_memory,
    analyze_program_memory,
    build_function_memory_facts,
    build_program_memory_facts,
)

__all__ = [
    "MemoryPartitionKind",
    "MemoryAccessKind",
    "MemoryAccess",
    "MemoryPartition",
    "FunctionMemoryFacts",
    "ProgramMemoryFacts",
    "format_memory_access",
    "format_memory_partition",
    "format_function_memory_facts",
    "format_program_memory_facts",
    "analyze_function_memory",
    "analyze_program_memory",
    "build_function_memory_facts",
    "build_program_memory_facts",
]
