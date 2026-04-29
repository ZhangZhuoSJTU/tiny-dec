import pytest

from tiny_dec.decode import DecodeError, InstructionFormat, Mnemonic, RV32IInstruction, decode_rv32i


def test_decode_rv32i_contract_decodes_known_addi() -> None:
    # addi x1, x2, 0
    insn = decode_rv32i(0x00010093, 0x1000)
    assert isinstance(insn, RV32IInstruction)
    assert insn.format == InstructionFormat.I
    assert insn.mnemonic == Mnemonic.ADDI
    assert insn.to_pretty_line() == "0x00001000: 0x00010093  addi x1, x2, 0"


def test_decode_rv32i_rejects_non_32bit_length_words() -> None:
    with pytest.raises(DecodeError):
        decode_rv32i(0x0001, 0x1000)
