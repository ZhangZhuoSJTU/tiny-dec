"""Stage-4 function-level IR containers built from stage-3 disassembly."""

from __future__ import annotations

from dataclasses import dataclass, field

from tiny_dec.disasm.models import (
    BasicBlock,
    BlockInstruction,
    BlockTerminator,
    DisasmFunction,
)


@dataclass(frozen=True, slots=True)
class CallSite:
    instruction_address: int
    block_start: int
    target: int | None = None
    target_name: str | None = None
    is_indirect: bool = False

    def __post_init__(self) -> None:
        if self.instruction_address < 0:
            raise ValueError("callsite instruction address must be non-negative")
        if self.block_start < 0:
            raise ValueError("callsite block start must be non-negative")
        if self.is_indirect and self.target is not None:
            raise ValueError("indirect callsite must not carry a direct target")
        if not self.is_indirect and self.target is None:
            raise ValueError("direct callsite must carry a target")

    def to_pretty(self) -> str:
        prefix = f"call 0x{self.instruction_address:x} block=0x{self.block_start:x} ->"
        if self.is_indirect:
            return f"{prefix} <indirect>"
        line = f"{prefix} 0x{self.target:x}"
        if self.target_name is not None:
            line += f" name={self.target_name}"
        return line


@dataclass(slots=True)
class FunctionIR:
    entry: int
    name: str | None
    disasm: DisasmFunction
    instruction_index: dict[int, BlockInstruction] = field(default_factory=dict)
    callsites: tuple[CallSite, ...] = ()
    return_blocks: tuple[int, ...] = ()
    direct_callees: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.entry < 0:
            raise ValueError("function ir entry must be non-negative")
        if self.disasm.entry != self.entry:
            raise ValueError("function ir entry must match owned disassembly entry")

        expected_index: dict[int, BlockInstruction] = {}
        expected_return_blocks: list[int] = []
        for block in self.disasm.ordered_blocks():
            if block.terminator == BlockTerminator.RETURN:
                expected_return_blocks.append(block.start)
            for lifted in block.instructions:
                expected_index.setdefault(lifted.address, lifted)

        if tuple(self.instruction_index) != tuple(expected_index):
            raise ValueError(
                "function ir instruction index must match disassembly instruction order"
            )
        if self.instruction_index != expected_index:
            raise ValueError(
                "function ir instruction index must match disassembly instruction mapping"
            )
        if self.return_blocks != tuple(expected_return_blocks):
            raise ValueError("function ir return blocks must match return terminators")
        if len(set(self.direct_callees)) != len(self.direct_callees):
            raise ValueError("function ir direct callees must be unique")

    @property
    def blocks_by_addr(self) -> dict[int, BasicBlock]:
        return self.disasm.blocks

    def ordered_blocks(self) -> tuple[BasicBlock, ...]:
        return self.disasm.ordered_blocks()
