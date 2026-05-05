from __future__ import annotations

from typing import cast

import pytest

pytest.importorskip("pwn")

from tiny_dec.analysis.simplify import (
    build_canonical_program_ir,
    canonicalize_function_ir,
    canonicalize_instruction,
    format_canonical_program_ir,
)
from tiny_dec.disasm.models import BlockInstruction
from tiny_dec.ir.containers import build_function_ir
from tiny_dec.ir.lift_rv32i import lift_instruction
from tiny_dec.loader import AddressNotMappedError, ProgramView


def _enc_i(opcode: int, rd: int, funct3: int, rs1: int, imm: int) -> int:
    return (
        ((imm & 0xFFF) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
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
    def __init__(self, words: dict[int, int], *, symbol_names: dict[int, str] | None = None) -> None:
        self._words = dict(words)
        self._symbol_names = dict(symbol_names or {})

    def read_u32(self, address: int) -> int:
        if address not in self._words:
            raise AddressNotMappedError(f"missing word at {address:#x}")
        return self._words[address]

    def get_symbol_name(self, address: int) -> str | None:
        return self._symbol_names.get(address)

    def contains_address(self, address: int, *, size: int = 1) -> bool:
        if size <= 0:
            return size == 0
        return all((address + offset) in self._words for offset in range(0, size, 4))

    def external_functions(self) -> list:
        return []

    def external_function_by_address(self, address: int):
        return None


def _view(
    words: dict[int, int],
    *,
    symbol_names: dict[int, str] | None = None,
) -> ProgramView:
    return cast(ProgramView, FakeProgramView(words, symbol_names=symbol_names))


def _lifted(word: int, address: int) -> BlockInstruction:
    from tiny_dec.decode import decode_rv32i

    instruction = decode_rv32i(word, address)
    return BlockInstruction(
        instruction=instruction,
        pcode_ops=tuple(lift_instruction(instruction)),
    )


def test_canonicalize_instruction_folds_constant_add_into_copy() -> None:
    instruction = _lifted(0x00700513, 0x1000)  # addi x10, x0, 7

    canonical = canonicalize_instruction(instruction)

    assert canonical.address == 0x1000
    assert [op.to_pretty() for op in canonical.ops] == [
        "COPY register[0xa:4] <- const[0x7:4]"
    ]


def test_canonicalize_instruction_forwards_single_use_load_temp_into_register() -> None:
    instruction = _lifted(0xff442503, 0x1000)  # lw x10, -12(x8)

    canonical = canonicalize_instruction(instruction)
    rendered = [op.to_pretty() for op in canonical.ops]

    assert rendered == [
        "INT_ADD unique[0x0:4] <- register[0x8:4], const[0xfffffff4:4]",
        "LOAD register[0xa:4] <- unique[0x0:4]",
    ]


def test_canonicalize_function_ir_preserves_metadata_and_instruction_order() -> None:
    function = build_function_ir(
        _view(
            {
                0x1000: _enc_j(0x6F, 1, 0x100),
                0x1004: 0x00008067,
                0x1100: 0x00008067,
            },
            symbol_names={0x1000: "main", 0x1100: "helper"},
        ),
        0x1000,
    )

    canonical = canonicalize_function_ir(function)

    assert canonical.entry == function.entry
    assert canonical.name == function.name
    assert canonical.discovery_order == function.disasm.discovery_order
    assert tuple(canonical.instruction_index) == tuple(function.instruction_index)
    assert canonical.callsites == function.callsites
    assert canonical.return_blocks == function.return_blocks
    assert canonical.direct_callees == function.direct_callees


def test_build_canonical_program_ir_uses_stage4_discovery_for_basic_fixture(
    fixture_binary,
) -> None:
    from tiny_dec.loader import ProgramView

    view = ProgramView(fixture_binary("fixture_basic_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    program = build_canonical_program_ir(view, entry)

    assert program.root_entry == entry
    assert program.discovery_order == (entry, 0x11110)
    assert tuple(program.functions) == (entry, 0x11110)
    assert len(program.call_graph) == 1


def test_canonical_program_pretty_output_is_deterministic_for_calls_fixture(
    fixture_binary,
) -> None:
    from tiny_dec.loader import ProgramView

    view = ProgramView(fixture_binary("fixture_calls_O0_nopie"))
    entry = view.find_main().address
    assert entry is not None

    first = format_canonical_program_ir(build_canonical_program_ir(view, entry))
    second = format_canonical_program_ir(build_canonical_program_ir(view, entry))

    assert first == second
    assert "call_graph:" in first
    assert "functions:" in first
