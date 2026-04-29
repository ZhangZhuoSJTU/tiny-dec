"""Pretty-print helpers for stage-2 low-level pcode snapshots."""

from __future__ import annotations

from tiny_dec.decode import DecodeError, decode_rv32i
from tiny_dec.ir.lift_rv32i import lift_instruction
from tiny_dec.ir.pcode import format_pcode_ops
from tiny_dec.loader import AddressNotMappedError, ProgramView


def format_lifted_word(word: int, address: int) -> str:
    insn = decode_rv32i(word, address)
    op_lines = format_pcode_ops(lift_instruction(insn))
    lines = [f"0x{address:08x}: 0x{word:08x}  {insn}"]
    lines.extend(f"    {line}" for line in op_lines)
    return "\n".join(lines)


def lift_window_lines(
    view: ProgramView, start_address: int, *, limit: int = 8
) -> list[str]:
    if limit < 0:
        raise ValueError("limit must be non-negative")

    lines: list[str] = []
    current = start_address
    for _ in range(limit):
        try:
            word = view.read_u32(current)
        except AddressNotMappedError:
            lines.append(f"0x{current:08x}: <unmapped>")
            break

        try:
            rendered = format_lifted_word(word, current)
        except DecodeError as exc:
            lines.append(f"0x{current:08x}: 0x{word:08x}  <decode-error: {exc}>")
            break

        lines.extend(rendered.splitlines())
        current += 4
    return lines
