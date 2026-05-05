"""Stage-5 canonical IR containers built from stage-4 program and function IR."""

from __future__ import annotations

from dataclasses import dataclass, field

from tiny_dec.decode import RV32IInstruction
from tiny_dec.disasm.models import BlockEdge, BlockTerminator
from tiny_dec.ir.function_ir import CallSite
from tiny_dec.ir.pcode import PcodeOp, PcodeSpace
from tiny_dec.ir.program_ir import CallGraphEdge
from tiny_dec.loader import ExternalFunction


@dataclass(frozen=True, slots=True)
class CanonicalInstruction:
    instruction: RV32IInstruction
    ops: tuple[PcodeOp, ...]

    def __post_init__(self) -> None:
        if self.instruction.address < 0:
            raise ValueError("canonical instruction address must be non-negative")
        if _first_seen_unique_offsets(self.ops) != _dense_unique_offsets(self.ops):
            raise ValueError(
                "canonical instruction unique varnodes must be renumbered densely"
            )

    @property
    def address(self) -> int:
        return self.instruction.address


@dataclass(frozen=True, slots=True)
class CanonicalBlock:
    start: int
    instructions: tuple[CanonicalInstruction, ...]
    successors: tuple[BlockEdge, ...] = ()
    terminator: BlockTerminator = BlockTerminator.LINEAR
    call_targets: tuple[int, ...] = ()
    has_indirect_call: bool = False

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("canonical block start must be non-negative")
        if not self.instructions:
            raise ValueError("canonical block must contain at least one instruction")
        if self.instructions[0].address != self.start:
            raise ValueError("canonical block start must match first instruction address")

        edge_keys = {(edge.kind, edge.target) for edge in self.successors}
        if len(edge_keys) != len(self.successors):
            raise ValueError("canonical block successors must be unique")

        if len(set(self.call_targets)) != len(self.call_targets):
            raise ValueError("canonical block call targets must be unique")

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
class CanonicalFunctionIR:
    entry: int
    name: str | None
    blocks: dict[int, CanonicalBlock] = field(default_factory=dict)
    discovery_order: tuple[int, ...] = ()
    instruction_index: dict[int, CanonicalInstruction] = field(default_factory=dict)
    callsites: tuple[CallSite, ...] = ()
    return_blocks: tuple[int, ...] = ()
    direct_callees: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.entry < 0:
            raise ValueError("canonical function entry must be non-negative")
        if self.blocks and self.entry not in self.blocks:
            raise ValueError("canonical function entry must be present in blocks")
        if self.discovery_order:
            missing = [address for address in self.discovery_order if address not in self.blocks]
            if missing:
                raise ValueError(
                    "canonical function discovery order must reference known blocks"
                )
            if len(set(self.discovery_order)) != len(self.discovery_order):
                raise ValueError("canonical function discovery order must be unique")

        expected_index: dict[int, CanonicalInstruction] = {}
        expected_return_blocks: list[int] = []
        for block in self.ordered_blocks():
            if block.terminator == BlockTerminator.RETURN:
                expected_return_blocks.append(block.start)
            for lifted in block.instructions:
                expected_index.setdefault(lifted.address, lifted)

        if tuple(self.instruction_index) != tuple(expected_index):
            raise ValueError(
                "canonical function instruction index must match block instruction order"
            )
        if self.instruction_index != expected_index:
            raise ValueError(
                "canonical function instruction index must match block mapping"
            )
        if self.return_blocks != tuple(expected_return_blocks):
            raise ValueError("canonical function return blocks must match terminators")
        if len(set(self.direct_callees)) != len(self.direct_callees):
            raise ValueError("canonical function direct callees must be unique")

    def ordered_block_starts(self) -> tuple[int, ...]:
        if self.discovery_order:
            return self.discovery_order
        return tuple(sorted(self.blocks))

    def ordered_blocks(self) -> tuple[CanonicalBlock, ...]:
        return tuple(self.blocks[address] for address in self.ordered_block_starts())

    @property
    def instruction_count(self) -> int:
        return len(self.instruction_index)

    @property
    def op_count(self) -> int:
        return sum(len(instruction.ops) for instruction in self.instruction_index.values())


@dataclass(slots=True)
class CanonicalProgramIR:
    root_entry: int
    functions: dict[int, CanonicalFunctionIR] = field(default_factory=dict)
    discovery_order: tuple[int, ...] = ()
    externals: tuple[ExternalFunction, ...] = ()
    call_graph: tuple[CallGraphEdge, ...] = ()
    pending_entries: tuple[int, ...] = ()
    invalidated_entries: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if self.root_entry < 0:
            raise ValueError("canonical program root entry must be non-negative")
        if self.functions and self.root_entry not in self.functions:
            raise ValueError("canonical program root entry must be present in functions")
        if self.discovery_order:
            missing = [entry for entry in self.discovery_order if entry not in self.functions]
            if missing:
                raise ValueError(
                    "canonical program discovery order must reference known functions"
                )
            if len(set(self.discovery_order)) != len(self.discovery_order):
                raise ValueError("canonical program discovery order must be unique")
        if len(set(self.pending_entries)) != len(self.pending_entries):
            raise ValueError("canonical program pending entries must be unique")
        if len(set(self.invalidated_entries)) != len(self.invalidated_entries):
            raise ValueError("canonical program invalidated entries must be unique")

    def ordered_function_entries(self) -> tuple[int, ...]:
        if self.discovery_order:
            return self.discovery_order
        return tuple(sorted(self.functions))

    def ordered_functions(self) -> tuple[CanonicalFunctionIR, ...]:
        return tuple(self.functions[entry] for entry in self.ordered_function_entries())


def _dense_unique_offsets(ops: tuple[PcodeOp, ...]) -> tuple[int, ...]:
    return tuple(index * 4 for index, _offset in enumerate(_first_seen_unique_offsets(ops)))


def _first_seen_unique_offsets(ops: tuple[PcodeOp, ...]) -> tuple[int, ...]:
    offsets: list[int] = []
    seen: set[int] = set()
    for op in ops:
        for varnode in _ordered_varnodes(op):
            space = varnode.space.value if isinstance(varnode.space, PcodeSpace) else varnode.space
            if space != PcodeSpace.UNIQUE.value:
                continue
            if varnode.offset in seen:
                continue
            seen.add(varnode.offset)
            offsets.append(varnode.offset)
    return tuple(offsets)


def _ordered_varnodes(op: PcodeOp) -> tuple:  # output first, then inputs
    if op.output is None:
        return op.inputs
    return (op.output, *op.inputs)
