from __future__ import annotations

import pytest

from tiny_dec.decode import decode_rv32i
from tiny_dec.ir import PcodeOpcode, format_pcode_ops, lift_instruction


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


def _lift_lines(word: int, *, address: int = 0x1000) -> list[str]:
    insn = decode_rv32i(word, address)
    return format_pcode_ops(lift_instruction(insn))


def test_lift_addi_basic() -> None:
    lines = _lift_lines(_enc_i(0x13, 1, 0x0, 2, 4))
    assert lines == [
        "INT_ADD register[0x1:4] <- register[0x2:4], const[0x4:4]",
    ]


def test_lift_addi_uses_const_zero_for_x0_reads() -> None:
    lines = _lift_lines(_enc_i(0x13, 1, 0x0, 0, 7))
    assert lines == [
        "INT_ADD register[0x1:4] <- const[0x0:4], const[0x7:4]",
    ]


def test_lift_addi_drops_x0_writes_when_side_effect_free() -> None:
    lines = _lift_lines(_enc_i(0x13, 0, 0x0, 2, 4))
    assert lines == []


def test_lift_lw_to_x0_keeps_memory_effects() -> None:
    lines = _lift_lines(_enc_i(0x03, 0, 0x2, 2, 8))
    assert lines == [
        "INT_ADD unique[0x0:4] <- register[0x2:4], const[0x8:4]",
        "LOAD unique[0x4:4] <- unique[0x0:4]",
    ]


def test_lift_branch_bgeu_negates_unsigned_less() -> None:
    lines = _lift_lines(_enc_b(0x63, 0x7, 1, 2, 16), address=0x2000)
    assert lines == [
        "INT_LESS unique[0x0:1] <- register[0x1:4], register[0x2:4]",
        "BOOL_NEGATE unique[0x4:1] <- unique[0x0:1]",
        "CBRANCH const[0x2010:4], unique[0x4:1]",
    ]


def test_lift_jal_x0_omits_link_write() -> None:
    lines = _lift_lines(_enc_j(0x6F, 0, 8), address=0x3000)
    assert lines == [
        "BRANCH const[0x3008:4]",
    ]


def test_lift_jal_writes_link_and_emits_call() -> None:
    lines = _lift_lines(_enc_j(0x6F, 1, 8), address=0x3000)
    assert lines == [
        "COPY register[0x1:4] <- const[0x3004:4]",
        "CALL const[0x3008:4]",
    ]


def test_lift_jalr_callind_masks_target_lsb() -> None:
    lines = _lift_lines(_enc_i(0x67, 1, 0x0, 2, 12), address=0x4000)
    assert lines == [
        "INT_ADD unique[0x0:4] <- register[0x2:4], const[0xc:4]",
        "INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]",
        "COPY register[0x1:4] <- const[0x4004:4]",
        "CALLIND unique[0x4:4]",
    ]


def test_lift_ret_uses_return_opcode() -> None:
    lines = _lift_lines(_enc_i(0x67, 0, 0x0, 1, 0), address=0x4000)
    assert lines == [
        "INT_ADD unique[0x0:4] <- register[0x1:4], const[0x0:4]",
        "INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]",
        "RETURN unique[0x4:4]",
    ]


def test_lift_system_and_illegal_encodings() -> None:
    ecall = _lift_lines(0x00000073)
    ebreak = _lift_lines(0x00100073)
    illegal = _lift_lines(0x0000007B)

    assert ecall == ["CALLOTHER const[0x1:4]"]
    assert ebreak == ["CALLOTHER const[0x2:4]"]
    assert illegal == ["TRAP const[0x7b:4]"]


@pytest.mark.parametrize(
    "word",
    [
        _enc_u(0x37, 5, 0x12345000),  # lui
        _enc_u(0x17, 6, 0x00012000),  # auipc
        _enc_i(0x03, 3, 0x0, 4, -4),  # lb
        _enc_i(0x03, 3, 0x1, 4, -4),  # lh
        _enc_i(0x03, 3, 0x2, 4, -4),  # lw
        _enc_i(0x03, 3, 0x4, 4, -4),  # lbu
        _enc_i(0x03, 3, 0x5, 4, -4),  # lhu
        _enc_s(0x23, 0x0, 6, 5, 8),  # sb
        _enc_s(0x23, 0x1, 6, 5, 8),  # sh
        _enc_s(0x23, 0x2, 6, 5, 8),  # sw
        _enc_i(0x13, 7, 0x2, 8, -1),  # slti
        _enc_i(0x13, 7, 0x3, 8, -1),  # sltiu
        _enc_i(0x13, 7, 0x4, 8, -1),  # xori
        _enc_i(0x13, 7, 0x6, 8, -1),  # ori
        _enc_i(0x13, 7, 0x7, 8, -1),  # andi
        _enc_i(0x13, 9, 0x1, 10, 3),  # slli
        _enc_i(0x13, 9, 0x5, 10, 3),  # srli
        _enc_i(0x13, 9, 0x5, 10, 0x403),  # srai
        _enc_r(0x33, 1, 0x0, 2, 3, 0x00),  # add
        _enc_r(0x33, 1, 0x0, 2, 3, 0x20),  # sub
        _enc_r(0x33, 1, 0x1, 2, 3, 0x00),  # sll
        _enc_r(0x33, 1, 0x2, 2, 3, 0x00),  # slt
        _enc_r(0x33, 1, 0x3, 2, 3, 0x00),  # sltu
        _enc_r(0x33, 1, 0x4, 2, 3, 0x00),  # xor
        _enc_r(0x33, 1, 0x5, 2, 3, 0x00),  # srl
        _enc_r(0x33, 1, 0x5, 2, 3, 0x20),  # sra
        _enc_r(0x33, 1, 0x6, 2, 3, 0x00),  # or
        _enc_r(0x33, 1, 0x7, 2, 3, 0x00),  # and
        _enc_i(0x67, 1, 0x0, 2, 12),  # jalr
        _enc_j(0x6F, 1, 8),  # jal
        _enc_b(0x63, 0x0, 1, 2, 16),  # beq
        _enc_b(0x63, 0x1, 1, 2, 16),  # bne
        _enc_b(0x63, 0x4, 1, 2, 16),  # blt
        _enc_b(0x63, 0x5, 1, 2, 16),  # bge
        _enc_b(0x63, 0x6, 1, 2, 16),  # bltu
        _enc_b(0x63, 0x7, 1, 2, 16),  # bgeu
        0x0000000F,  # fence
    ],
)
def test_lift_supports_all_decoded_rv32i_mnemonics(word: int) -> None:
    ops = lift_instruction(decode_rv32i(word, 0x1000))
    assert isinstance(ops, list)
    assert all(op.opcode != PcodeOpcode.TRAP for op in ops)
