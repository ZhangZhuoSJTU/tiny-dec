"""Stage-2 low-level pcode data model and deterministic pretty-printers."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class PcodeSpace(str, Enum):
    """Canonical varnode spaces used in low-level pcode."""

    REGISTER = "register"
    CONST = "const"
    RAM = "ram"
    UNIQUE = "unique"


class PcodeOpcode(str, Enum):
    """Subset of Ghidra-style pcode opcodes used by the RV32I lifter."""

    COPY = "COPY"
    LOAD = "LOAD"
    STORE = "STORE"
    BRANCH = "BRANCH"
    CBRANCH = "CBRANCH"
    BRANCHIND = "BRANCHIND"
    CALL = "CALL"
    CALLIND = "CALLIND"
    RETURN = "RETURN"
    CALLOTHER = "CALLOTHER"
    INT_ADD = "INT_ADD"
    INT_SUB = "INT_SUB"
    INT_AND = "INT_AND"
    INT_OR = "INT_OR"
    INT_XOR = "INT_XOR"
    INT_LEFT = "INT_LEFT"
    INT_RIGHT = "INT_RIGHT"
    INT_SRIGHT = "INT_SRIGHT"
    INT_EQUAL = "INT_EQUAL"
    INT_NOTEQUAL = "INT_NOTEQUAL"
    INT_SLESS = "INT_SLESS"
    INT_LESS = "INT_LESS"
    INT_SEXT = "INT_SEXT"
    INT_ZEXT = "INT_ZEXT"
    BOOL_NEGATE = "BOOL_NEGATE"
    SUBPIECE = "SUBPIECE"
    TRAP = "TRAP"


@dataclass(frozen=True, slots=True)
class Varnode:
    """A typed storage location/value reference used by pcode operations."""

    space: PcodeSpace | str
    offset: int
    size: int

    def __post_init__(self) -> None:
        if self.size <= 0:
            raise ValueError("varnode size must be positive")
        if self.offset < 0:
            raise ValueError("varnode offset must be non-negative")

    @property
    def space_name(self) -> str:
        return self.space.value if isinstance(self.space, PcodeSpace) else self.space

    def to_pretty(self) -> str:
        return f"{self.space_name}[0x{self.offset:x}:{self.size}]"


@dataclass(frozen=True, slots=True)
class PcodeOp:
    """One low-level pcode operation."""

    opcode: PcodeOpcode | str
    inputs: tuple[Varnode, ...]
    output: Varnode | None = None

    @property
    def opcode_text(self) -> str:
        if isinstance(self.opcode, PcodeOpcode):
            return self.opcode.value
        return self.opcode

    def to_pretty(self) -> str:
        inputs = ", ".join(v.to_pretty() for v in self.inputs)
        if self.output is None:
            return f"{self.opcode_text} {inputs}" if inputs else self.opcode_text
        return f"{self.opcode_text} {self.output.to_pretty()} <- {inputs}"


def register_varnode(index: int, *, size: int = 4) -> Varnode:
    if index < 0:
        raise ValueError("register index must be non-negative")
    return Varnode(space=PcodeSpace.REGISTER, offset=index, size=size)


def const_varnode(value: int, *, size: int = 4) -> Varnode:
    mask = (1 << (size * 8)) - 1
    return Varnode(space=PcodeSpace.CONST, offset=value & mask, size=size)


def ram_varnode(address: int, *, size: int = 4) -> Varnode:
    return Varnode(space=PcodeSpace.RAM, offset=address, size=size)


def unique_varnode(offset: int, *, size: int = 4) -> Varnode:
    return Varnode(space=PcodeSpace.UNIQUE, offset=offset, size=size)


def format_pcode_ops(ops: Iterable[PcodeOp]) -> list[str]:
    return [op.to_pretty() for op in ops]
