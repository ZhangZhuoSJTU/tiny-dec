"""Deterministic pretty-print helpers for RV32I decode output."""

from __future__ import annotations

from tiny_dec.decode.decoder import DecodeError, decode_rv32i
from tiny_dec.loader import AddressNotMappedError, ProgramView


def format_decoded_word(word: int, address: int) -> str:
    """Decode one RV32I word and return a stable single-line rendering."""
    return decode_rv32i(word, address).to_pretty_line()


def decode_window_lines(
    view: ProgramView,
    start_address: int,
    *,
    limit: int = 8,
) -> list[str]:
    """Decode a linear instruction window into deterministic text lines."""
    if limit < 0:
        raise ValueError("limit must be non-negative")

    lines: list[str] = []
    address = start_address
    for _ in range(limit):
        try:
            word = view.read_u32(address)
        except AddressNotMappedError:
            lines.append(f"0x{address:08x}: <unmapped>")
            break

        try:
            lines.append(format_decoded_word(word, address))
        except DecodeError:
            lines.append(f"0x{address:08x}: 0x{word:08x}  <decode-error>")
            break
        address += 4

    return lines
