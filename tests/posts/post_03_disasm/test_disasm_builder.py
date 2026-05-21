from __future__ import annotations

from typing import cast

import pytest

from tiny_dec.disasm import (
    BlockEdge,
    BlockEdgeKind,
    BlockTerminator,
    disassemble_function,
)
from tiny_dec.loader import AddressNotMappedError, ProgramView


def _enc_i(opcode: int, rd: int, funct3: int, rs1: int, imm: int) -> int:
    return (
        ((imm & 0xFFF) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
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


class FakeProgramView:
    def __init__(self, words: dict[int, int]) -> None:
        self._words = dict(words)

    def read_u32(self, address: int) -> int:
        if address not in self._words:
            raise AddressNotMappedError(f"missing word at {address:#x}")
        return self._words[address]


def _view(words: dict[int, int]) -> ProgramView:
    return cast(ProgramView, FakeProgramView(words))


def test_disassemble_function_splits_conditional_branch_into_taken_and_fallthrough_blocks() -> None:
    function = disassemble_function(
        _view(
            {
                0x1000: _enc_b(0x63, 0x0, 1, 2, 8),
                0x1004: _enc_i(0x13, 10, 0x0, 0, 1),
                0x1008: 0x00008067,
            }
        ),
        0x1000,
    )

    assert set(function.blocks) == {0x1000, 0x1004, 0x1008}
    assert function.blocks[0x1000].terminator == BlockTerminator.BRANCH
    assert function.blocks[0x1000].successors == (
        BlockEdge(BlockEdgeKind.BRANCH_TAKEN, 0x1008),
        BlockEdge(BlockEdgeKind.FALLTHROUGH, 0x1004),
    )
    assert function.blocks[0x1004].terminator == BlockTerminator.LINEAR
    assert function.blocks[0x1004].successors == (
        BlockEdge(BlockEdgeKind.FALLTHROUGH, 0x1008),
    )
    assert function.blocks[0x1008].terminator == BlockTerminator.RETURN


def test_disassemble_function_keeps_direct_calls_inline_and_does_not_recurse_into_callee() -> None:
    function = disassemble_function(
        _view(
            {
                0x1000: _enc_j(0x6F, 1, 0x100),
                0x1004: _enc_i(0x13, 10, 0x0, 0, 7),
                0x1008: 0x00008067,
                0x1100: _enc_i(0x13, 10, 0x0, 0, 9),
                0x1104: 0x00008067,
            }
        ),
        0x1000,
    )

    assert set(function.blocks) == {0x1000}
    block = function.blocks[0x1000]
    assert [lifted.address for lifted in block.instructions] == [0x1000, 0x1004, 0x1008]
    assert block.call_targets == (0x1100,)
    assert 0x1100 not in function.blocks


def test_disassemble_function_marks_indirect_call_but_continues_with_fallthrough() -> None:
    function = disassemble_function(
        _view(
            {
                0x1000: _enc_i(0x67, 1, 0x0, 5, 0),
                0x1004: _enc_i(0x13, 10, 0x0, 0, 3),
                0x1008: 0x00008067,
            }
        ),
        0x1000,
    )

    assert set(function.blocks) == {0x1000}
    block = function.blocks[0x1000]
    assert block.has_indirect_call is True
    assert [lifted.address for lifted in block.instructions] == [0x1000, 0x1004, 0x1008]
    assert block.terminator == BlockTerminator.RETURN


def test_disassemble_function_stops_on_unresolved_indirect_jump() -> None:
    function = disassemble_function(
        _view(
            {
                0x1000: _enc_i(0x67, 0, 0x0, 5, 0),
            }
        ),
        0x1000,
    )

    assert set(function.blocks) == {0x1000}
    assert function.blocks[0x1000].terminator == BlockTerminator.INDIRECT_JUMP
    assert function.blocks[0x1000].successors == ()


def test_disassemble_function_rejects_unmapped_entry() -> None:
    with pytest.raises(AddressNotMappedError):
        disassemble_function(_view({}), 0x1000)
