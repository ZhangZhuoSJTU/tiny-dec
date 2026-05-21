from __future__ import annotations

import pytest

from tiny_dec.ir import (
    PcodeOp,
    PcodeOpcode,
    PcodeSpace,
    Varnode,
    const_varnode,
    register_varnode,
    unique_varnode,
)


def test_varnode_validation_rejects_invalid_size_and_offset() -> None:
    with pytest.raises(ValueError):
        Varnode(space=PcodeSpace.REGISTER, offset=0, size=0)
    with pytest.raises(ValueError):
        Varnode(space=PcodeSpace.REGISTER, offset=-1, size=4)


def test_varnode_helpers_are_masked_and_deterministic() -> None:
    assert register_varnode(3).to_pretty() == "register[0x3:4]"
    assert const_varnode(-1, size=4).to_pretty() == "const[0xffffffff:4]"
    assert unique_varnode(8, size=1).to_pretty() == "unique[0x8:1]"


def test_pcodeop_pretty_without_output() -> None:
    op = PcodeOp(
        opcode=PcodeOpcode.BRANCH,
        inputs=(const_varnode(0x1000),),
    )
    assert op.to_pretty() == "BRANCH const[0x1000:4]"
