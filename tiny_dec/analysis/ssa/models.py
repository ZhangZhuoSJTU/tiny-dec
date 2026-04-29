"""Stage-7 SSA data model built on top of stage-6 dataflow facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from tiny_dec.analysis.dataflow.models import FunctionDataflowFacts, ProgramDataflowFacts
from tiny_dec.decode import RV32IInstruction
from tiny_dec.disasm.models import BlockEdge, BlockTerminator
from tiny_dec.ir.pcode import PcodeOpcode, Varnode


class SSANameKind(str, Enum):
    REGISTER = "register"
    UNIQUE = "unique"


@dataclass(frozen=True, slots=True)
class SSAName:
    kind: SSANameKind
    base: int
    version: int
    size: int

    def __post_init__(self) -> None:
        if self.base < 0:
            raise ValueError("ssa name base must be non-negative")
        if self.version < 0:
            raise ValueError("ssa name version must be non-negative")
        if self.size <= 0:
            raise ValueError("ssa name size must be positive")

    def to_pretty(self) -> str:
        prefix = "x" if self.kind == SSANameKind.REGISTER else "u"
        return f"{prefix}{self.base}_{self.version}:{self.size}"


type SSAValue = SSAName | Varnode


@dataclass(frozen=True, slots=True)
class MemoryVersion:
    version: int

    def __post_init__(self) -> None:
        if self.version < 0:
            raise ValueError("memory version must be non-negative")

    def to_pretty(self) -> str:
        return f"m{self.version}"


@dataclass(frozen=True, slots=True)
class SSAOp:
    opcode: PcodeOpcode | str
    inputs: tuple[SSAValue, ...]
    output: SSAName | None = None
    memory_before: MemoryVersion | None = None
    memory_after: MemoryVersion | None = None

    def __post_init__(self) -> None:
        if self.memory_after is not None and self.memory_before is None:
            raise ValueError("ssa op memory_after requires memory_before")

    @property
    def opcode_text(self) -> str:
        if isinstance(self.opcode, PcodeOpcode):
            return self.opcode.value
        return self.opcode

    def to_pretty(self) -> str:
        inputs = ", ".join(_value_to_pretty(value) for value in self.inputs)
        if self.output is None:
            rendered = f"{self.opcode_text} {inputs}" if inputs else self.opcode_text
        else:
            rendered = f"{self.opcode_text} {self.output.to_pretty()} <- {inputs}"
        if self.memory_before is None:
            if self.memory_after is not None:
                raise ValueError("ssa op memory_after requires memory_before")
            return rendered
        if self.memory_after is None or self.memory_after == self.memory_before:
            return f"{rendered} [{self.memory_before.to_pretty()}]"
        return (
            f"{rendered} "
            f"[{self.memory_before.to_pretty()} -> {self.memory_after.to_pretty()}]"
        )


@dataclass(frozen=True, slots=True)
class SSAPhiInput:
    predecessor: int
    value: SSAValue

    def __post_init__(self) -> None:
        if self.predecessor < 0:
            raise ValueError("ssa phi predecessor must be non-negative")

    def to_pretty(self) -> str:
        return f"0x{self.predecessor:x}:{_value_to_pretty(self.value)}"


@dataclass(frozen=True, slots=True)
class SSAMemoryPhiInput:
    predecessor: int
    value: MemoryVersion

    def __post_init__(self) -> None:
        if self.predecessor < 0:
            raise ValueError("ssa memory phi predecessor must be non-negative")

    def to_pretty(self) -> str:
        return f"0x{self.predecessor:x}:{self.value.to_pretty()}"


@dataclass(frozen=True, slots=True)
class SSAMemoryPhiNode:
    output: MemoryVersion
    inputs: tuple[SSAMemoryPhiInput, ...] = ()

    def __post_init__(self) -> None:
        predecessors = tuple(phi_input.predecessor for phi_input in self.inputs)
        if predecessors != tuple(sorted(predecessors)):
            raise ValueError("ssa memory phi inputs must be sorted by predecessor")
        if len(set(predecessors)) != len(predecessors):
            raise ValueError("ssa memory phi inputs must be unique by predecessor")

    def to_pretty(self) -> str:
        incoming = ", ".join(phi_input.to_pretty() for phi_input in self.inputs)
        return (
            f"MEM_PHI {self.output.to_pretty()} <- {incoming}"
            if incoming
            else f"MEM_PHI {self.output.to_pretty()}"
        )


@dataclass(frozen=True, slots=True)
class SSAPhiNode:
    output: SSAName
    inputs: tuple[SSAPhiInput, ...] = ()

    def __post_init__(self) -> None:
        if self.output.kind != SSANameKind.REGISTER:
            raise ValueError("ssa phi output must be a register name")
        predecessors = tuple(phi_input.predecessor for phi_input in self.inputs)
        if predecessors != tuple(sorted(predecessors)):
            raise ValueError("ssa phi inputs must be sorted by predecessor")
        if len(set(predecessors)) != len(predecessors):
            raise ValueError("ssa phi inputs must be unique by predecessor")

    def to_pretty(self) -> str:
        incoming = ", ".join(phi_input.to_pretty() for phi_input in self.inputs)
        return f"PHI {self.output.to_pretty()} <- {incoming}" if incoming else f"PHI {self.output.to_pretty()}"


@dataclass(frozen=True, slots=True)
class SSAInstruction:
    instruction: RV32IInstruction
    ops: tuple[SSAOp, ...]

    def __post_init__(self) -> None:
        if self.instruction.address < 0:
            raise ValueError("ssa instruction address must be non-negative")

    @property
    def address(self) -> int:
        return self.instruction.address


@dataclass(slots=True)
class SSABlock:
    start: int
    phis: tuple[SSAPhiNode, ...]
    instructions: tuple[SSAInstruction, ...]
    memory_phi: SSAMemoryPhiNode | None = None
    successors: tuple[BlockEdge, ...] = ()
    terminator: BlockTerminator = BlockTerminator.LINEAR
    call_targets: tuple[int, ...] = ()
    has_indirect_call: bool = False

    def __post_init__(self) -> None:
        if self.start < 0:
            raise ValueError("ssa block start must be non-negative")
        if not self.instructions:
            raise ValueError("ssa block must contain at least one instruction")
        if self.instructions[0].address != self.start:
            raise ValueError("ssa block start must match first instruction address")

        phi_registers = tuple(phi.output.base for phi in self.phis)
        if len(set(phi_registers)) != len(phi_registers):
            raise ValueError("ssa block phi outputs must be unique per register")

        edge_keys = {(edge.kind, edge.target) for edge in self.successors}
        if len(edge_keys) != len(self.successors):
            raise ValueError("ssa block successors must be unique")

        if len(set(self.call_targets)) != len(self.call_targets):
            raise ValueError("ssa block call targets must be unique")

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
class SSAFunctionIR:
    dataflow: FunctionDataflowFacts
    blocks: dict[int, SSABlock] = field(default_factory=dict)
    immediate_dominators: dict[int, int | None] = field(default_factory=dict)
    dominance_frontiers: dict[int, tuple[int, ...]] = field(default_factory=dict)
    live_ins: tuple[SSAName, ...] = ()
    memory_live_in: MemoryVersion | None = None
    unreachable_blocks: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        reachable = {
            start
            for start, facts in self.dataflow.blocks.items()
            if facts.in_state.reachable
        }
        if set(self.blocks) != reachable:
            raise ValueError("ssa function blocks must cover reachable dataflow blocks exactly")
        if self.dataflow.function.entry not in self.blocks:
            raise ValueError("ssa function entry must remain reachable")

        all_blocks = set(self.dataflow.function.blocks)
        if set(self.unreachable_blocks) != all_blocks - reachable:
            raise ValueError("ssa function unreachable blocks must match non-reachable blocks")
        if len(set(self.unreachable_blocks)) != len(self.unreachable_blocks):
            raise ValueError("ssa function unreachable blocks must be unique")

        if set(self.immediate_dominators) != reachable:
            raise ValueError("ssa function idoms must cover reachable blocks exactly")
        if set(self.dominance_frontiers) != reachable:
            raise ValueError("ssa function dominance frontiers must cover reachable blocks exactly")
        if self.immediate_dominators[self.dataflow.function.entry] is not None:
            raise ValueError("ssa function entry idom must be None")

        for start, idom in self.immediate_dominators.items():
            if start == self.dataflow.function.entry:
                continue
            if idom not in reachable:
                raise ValueError("ssa function idom must reference a reachable block")
        for start, frontier in self.dominance_frontiers.items():
            if len(set(frontier)) != len(frontier):
                raise ValueError("ssa function dominance frontier entries must be unique")
            for target in frontier:
                if target not in reachable:
                    raise ValueError(
                        "ssa function dominance frontier must reference reachable blocks"
                    )

        if any(name.kind != SSANameKind.REGISTER for name in self.live_ins):
            raise ValueError("ssa function live-ins must be register names")
        if any(name.version != 0 for name in self.live_ins):
            raise ValueError("ssa function live-ins must use version 0")
        if tuple(name.base for name in self.live_ins) != tuple(
            sorted(name.base for name in self.live_ins)
        ):
            raise ValueError("ssa function live-ins must be sorted by register")
        if len({name.base for name in self.live_ins}) != len(self.live_ins):
            raise ValueError("ssa function live-ins must be unique by register")
        if self.memory_live_in is not None and self.memory_live_in.version != 0:
            raise ValueError("ssa function memory live-in must use version 0")

    @property
    def entry(self) -> int:
        return self.dataflow.function.entry

    @property
    def name(self) -> str | None:
        return self.dataflow.function.name

    def ordered_block_starts(self) -> tuple[int, ...]:
        return tuple(
            start
            for start in self.dataflow.function.ordered_block_starts()
            if start in self.blocks
        )

    def ordered_blocks(self) -> tuple[SSABlock, ...]:
        return tuple(self.blocks[start] for start in self.ordered_block_starts())

    @property
    def phi_count(self) -> int:
        return sum(len(block.phis) for block in self.blocks.values())


@dataclass(slots=True)
class SSAProgramIR:
    dataflow: ProgramDataflowFacts
    functions: dict[int, SSAFunctionIR] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if set(self.functions) != set(self.dataflow.program.functions):
            raise ValueError("ssa program functions must cover dataflow program functions exactly")

    def ordered_function_entries(self) -> tuple[int, ...]:
        return self.dataflow.program.ordered_function_entries()

    def ordered_functions(self) -> tuple[SSAFunctionIR, ...]:
        return tuple(self.functions[entry] for entry in self.ordered_function_entries())


def _value_to_pretty(value: SSAValue) -> str:
    if isinstance(value, SSAName):
        return value.to_pretty()
    return value.to_pretty()
