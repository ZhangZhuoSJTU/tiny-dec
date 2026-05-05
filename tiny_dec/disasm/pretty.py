"""Deterministic pretty-printers for stage-3 disassembly snapshots."""

from __future__ import annotations

from tiny_dec.disasm.models import BasicBlock, DisasmFunction


def format_basic_block(block: BasicBlock) -> list[str]:
    lines = [block.header_pretty()]
    for lifted in block.instructions:
        lines.append(f"  {lifted.instruction.to_pretty_line()}")
        for op in lifted.pcode_ops:
            lines.append(f"    {op.to_pretty()}")
    return lines


def format_disasm(function: DisasmFunction) -> str:
    order_text = ", ".join(
        f"0x{address:x}" for address in function.ordered_block_starts()
    )
    lines = [
        f"entry: 0x{function.entry:x}",
        f"order: {order_text}" if order_text else "order:",
    ]

    for block in function.ordered_blocks():
        lines.extend(format_basic_block(block))

    return "\n".join(lines)
