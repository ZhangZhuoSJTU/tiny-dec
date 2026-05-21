from __future__ import annotations

import pytest

from tiny_dec.decode import (
    DecodeError,
    InstructionFormat,
    Mnemonic,
    RV32IInstruction,
    Register,
    decode_rv32i,
)


def _enc_i(opcode: int, rd: int, funct3: int, rs1: int, imm: int) -> int:
    return (
        ((imm & 0xFFF) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
        | (opcode & 0x7F)
    )


def _enc_r(opcode: int, rd: int, funct3: int, rs1: int, rs2: int, funct7: int) -> int:
    return (
        ((funct7 & 0x7F) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
        | (opcode & 0x7F)
    )


def _enc_s(opcode: int, funct3: int, rs1: int, rs2: int, imm: int) -> int:
    imm12 = imm & 0xFFF
    return (
        ((imm12 >> 5) << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((imm12 & 0x1F) << 7)
        | (opcode & 0x7F)
    )


def _enc_b(opcode: int, funct3: int, rs1: int, rs2: int, imm: int) -> int:
    imm13 = imm & 0x1FFF
    bit12 = (imm13 >> 12) & 0x1
    bit11 = (imm13 >> 11) & 0x1
    bits10_5 = (imm13 >> 5) & 0x3F
    bits4_1 = (imm13 >> 1) & 0xF
    return (
        (bit12 << 31)
        | (bits10_5 << 25)
        | ((rs2 & 0x1F) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | (bits4_1 << 8)
        | (bit11 << 7)
        | (opcode & 0x7F)
    )


def _enc_u(opcode: int, rd: int, imm: int) -> int:
    return (imm & 0xFFFFF000) | ((rd & 0x1F) << 7) | (opcode & 0x7F)


def _enc_j(opcode: int, rd: int, imm: int) -> int:
    imm21 = imm & 0x1FFFFF
    bit20 = (imm21 >> 20) & 0x1
    bits10_1 = (imm21 >> 1) & 0x3FF
    bit11 = (imm21 >> 11) & 0x1
    bits19_12 = (imm21 >> 12) & 0xFF
    return (
        (bit20 << 31)
        | (bits19_12 << 12)
        | (bit11 << 20)
        | (bits10_1 << 21)
        | ((rd & 0x1F) << 7)
        | (opcode & 0x7F)
    )


@pytest.mark.parametrize(
    ("word", "address", "mnemonic", "fmt", "regs", "imm", "target", "render"),
    [
        (
            _enc_u(0x37, 5, 0x12345000),
            0x1000,
            Mnemonic.LUI,
            InstructionFormat.U,
            (Register.X5,),
            0x12345000,
            None,
            "lui x5, 305418240",
        ),
        (
            _enc_u(0x17, 6, 0x00012000),
            0x1004,
            Mnemonic.AUIPC,
            InstructionFormat.U,
            (Register.X6,),
            0x00012000,
            None,
            "auipc x6, 73728",
        ),
        (
            _enc_j(0x6F, 1, 8),
            0x1008,
            Mnemonic.JAL,
            InstructionFormat.J,
            (Register.X1,),
            8,
            0x1010,
            "jal x1, 0x1010",
        ),
        (
            _enc_i(0x67, 1, 0x0, 2, 12),
            0x100C,
            Mnemonic.JALR,
            InstructionFormat.I,
            (Register.X1, Register.X2),
            12,
            None,
            "jalr x1, 12(x2)",
        ),
        (
            _enc_b(0x63, 0x0, 1, 2, 16),
            0x1010,
            Mnemonic.BEQ,
            InstructionFormat.B,
            (Register.X1, Register.X2),
            16,
            0x1020,
            "beq x1, x2, 0x1020",
        ),
        (
            _enc_i(0x03, 3, 0x2, 4, -4),
            0x1014,
            Mnemonic.LW,
            InstructionFormat.I,
            (Register.X3, Register.X4),
            -4,
            None,
            "lw x3, -4(x4)",
        ),
        (
            _enc_s(0x23, 0x2, 6, 5, 8),
            0x1018,
            Mnemonic.SW,
            InstructionFormat.S,
            (Register.X6, Register.X5),
            8,
            None,
            "sw x5, 8(x6)",
        ),
        (
            _enc_i(0x13, 7, 0x0, 8, -1),
            0x101C,
            Mnemonic.ADDI,
            InstructionFormat.I,
            (Register.X7, Register.X8),
            -1,
            None,
            "addi x7, x8, -1",
        ),
        (
            _enc_i(0x13, 9, 0x1, 10, 3),
            0x1020,
            Mnemonic.SLLI,
            InstructionFormat.I,
            (Register.X9, Register.X10),
            3,
            None,
            "slli x9, x10, 3",
        ),
        (
            _enc_i(0x13, 9, 0x5, 10, 3),
            0x1024,
            Mnemonic.SRLI,
            InstructionFormat.I,
            (Register.X9, Register.X10),
            3,
            None,
            "srli x9, x10, 3",
        ),
        (
            _enc_i(0x13, 9, 0x5, 10, 0x403),
            0x1028,
            Mnemonic.SRAI,
            InstructionFormat.I,
            (Register.X9, Register.X10),
            3,
            None,
            "srai x9, x10, 3",
        ),
        (
            _enc_r(0x33, 1, 0x0, 2, 3, 0x00),
            0x102C,
            Mnemonic.ADD,
            InstructionFormat.R,
            (Register.X1, Register.X2, Register.X3),
            None,
            None,
            "add x1, x2, x3",
        ),
        (
            _enc_r(0x33, 1, 0x0, 2, 3, 0x20),
            0x1030,
            Mnemonic.SUB,
            InstructionFormat.R,
            (Register.X1, Register.X2, Register.X3),
            None,
            None,
            "sub x1, x2, x3",
        ),
        (
            0x0000000F,
            0x1034,
            Mnemonic.FENCE,
            InstructionFormat.I,
            (),
            None,
            None,
            "fence",
        ),
        (
            0x00000073,
            0x1038,
            Mnemonic.ECALL,
            InstructionFormat.I,
            (),
            None,
            None,
            "ecall",
        ),
        (
            0x00100073,
            0x103C,
            Mnemonic.EBREAK,
            InstructionFormat.I,
            (),
            None,
            None,
            "ebreak",
        ),
    ],
)
def test_decode_rv32i_opcode_matrix(
    word: int,
    address: int,
    mnemonic: Mnemonic,
    fmt: InstructionFormat,
    regs: tuple[Register, ...],
    imm: int | None,
    target: int | None,
    render: str,
) -> None:
    insn = decode_rv32i(word, address)
    assert isinstance(insn, RV32IInstruction)
    assert insn.size == 4
    assert insn.format == fmt
    assert insn.mnemonic == mnemonic
    assert insn.registers == regs
    assert insn.immediates == (() if imm is None else (imm,))
    assert insn.addresses == (() if target is None else (target,))
    assert str(insn) == render


def test_decode_rv32i_sign_extension_boundaries() -> None:
    min_imm = decode_rv32i(_enc_i(0x13, 1, 0x0, 2, -2048), 0x2000)
    max_imm = decode_rv32i(_enc_i(0x13, 1, 0x0, 2, 2047), 0x2004)

    assert min_imm.immediates == (-2048,)
    assert max_imm.immediates == (2047,)


def test_decode_rv32i_branch_negative_target() -> None:
    # branch back 4 bytes
    insn = decode_rv32i(_enc_b(0x63, 0x1, 1, 2, -4), 0x3000)
    assert isinstance(insn, RV32IInstruction)
    assert insn.mnemonic == Mnemonic.BNE
    assert insn.immediates == (-4,)
    assert insn.addresses == (0x2FFC,)
    assert str(insn) == "bne x1, x2, 0x2ffc"


def test_decode_pretty_line_is_deterministic() -> None:
    word = _enc_i(0x13, 1, 0x0, 2, 0)
    first = decode_rv32i(word, 0x4000)
    second = decode_rv32i(word, 0x4000)
    assert isinstance(first, RV32IInstruction)
    assert isinstance(second, RV32IInstruction)
    assert first.to_pretty_line() == second.to_pretty_line()
    assert first.to_pretty_line() == "0x00004000: 0x00010093  addi x1, x2, 0"


@pytest.mark.parametrize(
    "word",
    [
        0x0000007B,  # unsupported opcode with 32-bit length tag
        _enc_i(0x13, 1, 0x1, 2, 0x040),  # invalid slli selector
        0x00200073,  # unknown system immediate
    ],
)
def test_decode_rv32i_returns_illegal_for_unsupported_encodings(word: int) -> None:
    insn = decode_rv32i(word, 0x1000)
    assert isinstance(insn, RV32IInstruction)
    assert insn.mnemonic == Mnemonic.ILLEGAL
    assert insn.format == InstructionFormat.UNKNOWN


def test_decode_rv32i_rejects_non_32bit_length_words() -> None:
    with pytest.raises(DecodeError):
        decode_rv32i(0x0001, 0x1000)
