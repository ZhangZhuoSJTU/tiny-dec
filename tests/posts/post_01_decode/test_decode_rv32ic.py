import pytest

from tiny_dec.decode import (
    DecodeError,
    Mnemonic,
    RV32IInstruction,
    Register,
    decode_rv32i,
    instruction_size,
)


def test_instruction_size_accepts_only_32bit_words() -> None:
    assert instruction_size(0x00010093) == 4

    with pytest.raises(DecodeError):
        instruction_size(0x0001)


def test_decode_rv32i_decodes_addi() -> None:
    # addi x1, x2, 0
    insn = decode_rv32i(0x00010093, 0x3000)
    assert isinstance(insn, RV32IInstruction)
    assert insn.size == 4
    assert insn.mnemonic == Mnemonic.ADDI
    assert insn.registers == (Register.X1, Register.X2)
    assert insn.immediates == (0,)
    assert str(insn) == "addi x1, x2, 0"


@pytest.mark.parametrize("word", [0x0001, 0x0002])
def test_decode_rv32i_rejects_non_32bit_length_words(word: int) -> None:
    with pytest.raises(DecodeError):
        decode_rv32i(word, 0x1000)


def test_decode_rv32i_all_zeros_returns_illegal() -> None:
    insn = decode_rv32i(0x0000, 0x1000)
    assert insn.mnemonic == Mnemonic.ILLEGAL
