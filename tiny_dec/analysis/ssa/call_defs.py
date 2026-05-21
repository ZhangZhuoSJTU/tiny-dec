"""Synthetic SSA definitions for call-site return and clobber effects.

The spec's "Assumptions" section originally said this stage does not model full
clobber sets.  In practice downstream stages (calls, stack, memory) need every
caller-saved register killed across a call so pre-call values are not treated as
live.  The implementation therefore emits both CALL_RETURN (for the two ABI
return carriers) and CALL_CLOBBER (for all other caller-saved registers).
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from tiny_dec.analysis.ssa.models import SSAName, SSAOp
from tiny_dec.ir.pcode import const_varnode


RV32I_ILP32_RETURN_REGISTERS: tuple[int, ...] = (10, 11)

# All caller-saved (clobbered) registers per RISC-V ILP32 ABI:
# ra(x1), t0-t2(x5-x7), a0-a7(x10-x17), t3-t6(x28-x31)
RV32I_ILP32_CLOBBERED_REGISTERS: tuple[int, ...] = (
    1, 5, 6, 7, 10, 11, 12, 13, 14, 15, 16, 17, 28, 29, 30, 31,
)

_DEFAULT_RETURN_SIZE = 4


def build_call_return_ops(
    *,
    instruction_address: int,
    register_sizes: Mapping[int, int],
    define_register: Callable[[int, int], SSAName],
) -> tuple[SSAOp, ...]:
    """Build synthetic defs for all RV32I ILP32 clobbered registers.

    CALL_RETURN for the return carriers (x10, x11); CALL_CLOBBER for every
    other caller-saved register so downstream stages see the kill.
    """

    ops: list[SSAOp] = []
    for register in RV32I_ILP32_CLOBBERED_REGISTERS:
        opcode = "CALL_RETURN" if register in RV32I_ILP32_RETURN_REGISTERS else "CALL_CLOBBER"
        ops.append(
            SSAOp(
                opcode=opcode,
                inputs=(const_varnode(instruction_address),),
                output=define_register(register, register_sizes.get(register, _DEFAULT_RETURN_SIZE)),
            )
        )
    return tuple(ops)
