"""Shared utility functions used across analysis stages.

These helpers were extracted from duplicated private implementations in the
individual analysis sub-packages to keep the codebase DRY.  Each function
was verified to be semantically identical (or a strict superset) across all
call-sites before being consolidated here.

All analysis-level imports live behind ``TYPE_CHECKING`` to avoid circular
dependencies: several analysis sub-package ``__init__.py`` files trigger
transitive import chains that would re-enter ``_helpers`` before it finishes
loading.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from tiny_dec.ir.pcode import PcodeSpace, Varnode

if TYPE_CHECKING:
    from tiny_dec.analysis.memory.models import MemoryPartition
    from tiny_dec.analysis.ssa.models import SSAFunctionIR, SSAValue


# ---------------------------------------------------------------------------
# 1. opcode_text
# ---------------------------------------------------------------------------

def opcode_text(op_or_opcode: object) -> str:
    """Extract the opcode string from an SSAOp, PcodeOp, or raw opcode enum.

    Accepts any object and resolves the opcode string by first looking for an
    ``.opcode`` attribute (SSAOp / PcodeOp), then falling back to checking for a
    ``.value`` attribute (PcodeOpcode / str-enum), and finally to ``str()``.
    """
    target = getattr(op_or_opcode, "opcode", op_or_opcode)
    return target.value if hasattr(target, "value") else str(target)


# ---------------------------------------------------------------------------
# 2. build_dominator_children
# ---------------------------------------------------------------------------

def build_dominator_children(function: SSAFunctionIR) -> dict[int, tuple[int, ...]]:
    """Return a mapping from each block start to its children in the dominator tree."""
    order_index = {
        start: index for index, start in enumerate(function.ordered_block_starts())
    }
    children: dict[int, list[int]] = {
        start: [] for start in function.immediate_dominators
    }
    for start, dominator in function.immediate_dominators.items():
        if dominator is None:
            continue
        children[dominator].append(start)
    return {
        start: tuple(sorted(blocks, key=order_index.__getitem__))
        for start, blocks in children.items()
    }


# ---------------------------------------------------------------------------
# 3. signed_const
# ---------------------------------------------------------------------------

def signed_const(value: SSAValue) -> int | None:
    """Extract a signed constant from an SSAValue or Varnode, or return *None*."""
    if not isinstance(value, Varnode):
        return None
    space = value.space.value if isinstance(value.space, PcodeSpace) else value.space
    if space != PcodeSpace.CONST.value:
        return None
    bits = value.size * 8
    masked = value.offset & ((1 << bits) - 1)
    sign_bit = 1 << (bits - 1)
    if masked & sign_bit:
        return masked - (1 << bits)
    return masked


# ---------------------------------------------------------------------------
# 4. mask_for_size
# ---------------------------------------------------------------------------

def mask_for_size(size: int) -> int:
    """Return a bitmask covering *size* bytes (``(1 << (size * 8)) - 1``)."""
    return (1 << (size * 8)) - 1


# ---------------------------------------------------------------------------
# 5. sign_extend
# ---------------------------------------------------------------------------

def sign_extend(value: int, bits: int) -> int:
    """Sign-extend *value* from *bits* width to a Python ``int``."""
    sign_bit = 1 << (bits - 1)
    masked = value & ((1 << bits) - 1)
    return (masked ^ sign_bit) - sign_bit


# ---------------------------------------------------------------------------
# 6. space_name
# ---------------------------------------------------------------------------

def space_name(varnode: Varnode) -> str:
    """Return the canonical string name of a varnode's address space."""
    return varnode.space.value if isinstance(varnode.space, PcodeSpace) else varnode.space


# ---------------------------------------------------------------------------
# 7. partition_sort_key
# ---------------------------------------------------------------------------

def partition_sort_key(partition: MemoryPartition) -> tuple[int, int, int, str]:
    """Deterministic sort key for :class:`MemoryPartition` instances."""
    # Compare against the string values of ``MemoryPartitionKind`` to avoid
    # importing the enum at module level (which would create a circular import).
    kind = partition.kind.value if hasattr(partition.kind, "value") else partition.kind
    if kind == "stack_slot":
        assert partition.stack_slot is not None
        return (0, partition.stack_slot.frame_offset, partition.size, "")
    if kind == "absolute":
        assert partition.absolute_address is not None
        return (1, partition.absolute_address, partition.size, "")
    assert partition.base_value is not None
    return (2, partition.offset, partition.size, partition.base_value.to_pretty())


# ---------------------------------------------------------------------------
# 8. value_sort_key
# ---------------------------------------------------------------------------

def value_sort_key(value: SSAValue) -> tuple[int, int, int, int, str]:
    """Deterministic sort key for :class:`SSAValue` instances."""
    # Import at call time to avoid circular imports at module level.
    from tiny_dec.analysis.ssa.models import SSAName, SSANameKind

    if isinstance(value, SSAName):
        if value.kind == SSANameKind.REGISTER:
            return (0, value.base, value.version, value.size, "")
        return (1, value.base, value.version, value.size, "")
    return (2, value.offset, 0, value.size, value.to_pretty())


# ---------------------------------------------------------------------------
# 9. value_size
# ---------------------------------------------------------------------------

def value_size(value: SSAValue) -> int:
    """Return the size in bytes of an :class:`SSAValue`."""
    return value.size


# ---------------------------------------------------------------------------
# 10. is_const_ssa
# ---------------------------------------------------------------------------

def is_const_ssa(value: SSAValue) -> bool:
    """Return whether *value* is a constant varnode."""
    if not isinstance(value, Varnode):
        return False
    space = value.space.value if isinstance(value.space, PcodeSpace) else value.space
    return space == PcodeSpace.CONST.value
