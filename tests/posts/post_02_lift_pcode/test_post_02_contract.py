from tiny_dec.decode import decode_rv32i
from tiny_dec.ir import (
    PcodeOp,
    PcodeOpcode,
    PcodeSpace,
    Varnode,
    format_pcode_ops,
    lift_instruction,
)


def test_pcode_models_are_constructible() -> None:
    src = Varnode(space=PcodeSpace.REGISTER, offset=10, size=4)
    dst = Varnode(space=PcodeSpace.REGISTER, offset=11, size=4)
    op = PcodeOp(opcode=PcodeOpcode.COPY, inputs=(src,), output=dst)

    assert op.opcode == PcodeOpcode.COPY
    assert op.inputs[0] == src
    assert op.output == dst
    assert op.to_pretty() == "COPY register[0xb:4] <- register[0xa:4]"


def test_pcode_pretty_helpers_are_deterministic() -> None:
    src = Varnode(space=PcodeSpace.CONST, offset=4, size=4)
    dst = Varnode(space=PcodeSpace.REGISTER, offset=1, size=4)
    op = PcodeOp(opcode=PcodeOpcode.COPY, inputs=(src,), output=dst)

    assert format_pcode_ops((op,)) == ["COPY register[0x1:4] <- const[0x4:4]"]
    assert format_pcode_ops((op,)) == format_pcode_ops((op,))


def test_lift_instruction_contract_returns_low_level_pcode() -> None:
    insn = decode_rv32i(0x00410093, 0x1000)  # addi x1, x2, 4
    ops = lift_instruction(insn)

    assert ops
    assert ops[0].opcode == PcodeOpcode.INT_ADD
