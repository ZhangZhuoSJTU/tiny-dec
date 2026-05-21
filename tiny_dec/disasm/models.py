"""Stage-3 recursive disassembly data model."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from tiny_dec.decode import RV32IInstruction
from tiny_dec.ir.pcode import PcodeOp


class BlockEdgeKind(str, Enum):
    FALLTHROUGH = "fallthrough"
    BRANCH_TAKEN = "branch_taken"
    JUMP = "jump"


class BlockTerminator(str, Enum):
    LINEAR = "linear"
    BRANCH = "branch"
    JUMP = "jump"
    INDIRECT_JUMP = "indirect_jump"
    RETURN = "return"
    STOP = "stop"


@dataclass(frozen=True, slots=True)
class BlockInstruction:
    instruction: RV32IInstruction
    pcode_ops: tuple[PcodeOp, ...]

    @property
    def address(self) -> int:
        return self.instruction.address


@dataclass(frozen=True, slots=True)
class BlockEdge:
    kind: BlockEdgeKind
    target: int

    def __post_init__(self) -> None:
        if self.target < 0:
            raise ValueError("block edge target must be non-negative")

    def to_pretty(self) -> str:
        return f"{self.kind.value}:0x{self.target:x}"


@dataclass(slots=True)
class BasicBlock:
    start: int
    instructions: tuple[BlockInstruction, ...]
    successors: tuple[BlockEdge, ...] = ()
    terminator: BlockTerminator = BlockTerminator.LINEAR
    call_targets: tuple[int, ...] = ()
    has_indirect_call: bool = False

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("basic block start must be non-negative")
        if not self.instructions:
            raise ValueError("basic block must contain at least one instruction")
        if self.instructions[0].address != self.start:
            raise ValueError("basic block start must match first instruction address")

        edge_keys = {(edge.kind, edge.target) for edge in self.successors}
        if len(edge_keys) != len(self.successors):
            raise ValueError("basic block successors must be unique")

        if len(set(self.call_targets)) != len(self.call_targets):
            raise ValueError("basic block call targets must be unique")

    @property
    def end(self) -> int:
        return self.instructions[-1].address

    @property
    def next_address(self) -> int:
        return self.end + self.instructions[-1].instruction.size

    def header_pretty(self) -> str:
        successor_text = ", ".join(edge.to_pretty() for edge in self.successors)
        line = (
            f"block 0x{self.start:x} term={self.terminator.value} "
            f"succ=[{successor_text}]"
        )
        if self.call_targets:
            targets = ", ".join(f"0x{target:x}" for target in self.call_targets)
            line += f" calls=[{targets}]"
        if self.has_indirect_call:
            line += " indirect_call=yes"
        return line


@dataclass(slots=True)
class DisasmFunction:
    entry: int
    blocks: dict[int, BasicBlock] = field(default_factory=dict)
    discovery_order: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.entry < 0:
            raise ValueError("disasm function entry must be non-negative")
        if self.blocks and self.entry not in self.blocks:
            raise ValueError("disasm function entry must be present in blocks")

        if self.discovery_order:
            if len(set(self.discovery_order)) != len(self.discovery_order):
                raise ValueError("discovery order must contain unique addresses")
            missing = [address for address in self.discovery_order if address not in self.blocks]
            if missing:
                raise ValueError("discovery order must reference known blocks")
            uncovered = [address for address in self.blocks if address not in set(self.discovery_order)]
            if uncovered:
                raise ValueError("discovery order must cover all blocks")

    def ordered_block_starts(self) -> tuple[int, ...]:
        if self.discovery_order:
            return self.discovery_order
        return tuple(sorted(self.blocks))

    def ordered_blocks(self) -> tuple[BasicBlock, ...]:
        return tuple(self.blocks[address] for address in self.ordered_block_starts())
