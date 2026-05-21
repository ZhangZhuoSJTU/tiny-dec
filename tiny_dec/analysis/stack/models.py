"""Stage-9 stack recovery data structures built on top of stage-8 call facts."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from tiny_dec.analysis.calls.models import FunctionCallFacts, ProgramCallFacts
from tiny_dec.analysis.ssa.models import SSAName, SSANameKind, SSAValue


class StackBaseKind(str, Enum):
    ENTRY_SP = "entry_sp"
    STACK_POINTER = "stack_pointer"
    FRAME_POINTER = "frame_pointer"


class StackAccessKind(str, Enum):
    LOAD = "load"
    STORE = "store"


class StackSlotRole(str, Enum):
    SAVED_REGISTER = "saved_register"
    ARGUMENT_HOME = "argument_home"
    LOCAL = "local"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class StackFrameBase:
    kind: StackBaseKind
    register: int
    value: SSAName
    frame_top_delta: int

    def __post_init__(self) -> None:
        if self.register < 0:
            raise ValueError("stack frame base register must be non-negative")
        if self.value.kind != SSANameKind.REGISTER:
            raise ValueError("stack frame base value must be a register SSA name")
        if self.value.base != self.register:
            raise ValueError("stack frame base register must match SSA name base")

    def to_pretty(self) -> str:
        return (
            f"{self.kind.value} x{self.register}={self.value.to_pretty()} "
            f"delta={self.frame_top_delta:+d}"
        )


@dataclass(frozen=True, slots=True)
class StackAccess:
    instruction_address: int
    block_start: int
    kind: StackAccessKind
    frame_offset: int
    size: int
    base_kind: StackBaseKind
    base_register: int
    value: SSAValue | None = None

    def __post_init__(self) -> None:
        if self.instruction_address < 0:
            raise ValueError("stack access instruction address must be non-negative")
        if self.block_start < 0:
            raise ValueError("stack access block start must be non-negative")
        if self.size <= 0:
            raise ValueError("stack access size must be positive")
        if self.base_register < 0:
            raise ValueError("stack access base register must be non-negative")

    def to_pretty(self) -> str:
        text = (
            f"{self.kind.value} 0x{self.instruction_address:x} "
            f"block=0x{self.block_start:x} slot={self.frame_offset:+d} "
            f"size={self.size} via={self.base_kind.value}(x{self.base_register})"
        )
        if self.value is not None:
            text += f" value={self.value.to_pretty()}"
        return text


@dataclass(frozen=True, slots=True)
class StackSlot:
    frame_offset: int
    size: int
    role: StackSlotRole
    saved_register: int | None = None
    argument_register: int | None = None
    accesses: tuple[StackAccess, ...] = ()

    def __post_init__(self) -> None:
        if self.size <= 0:
            raise ValueError("stack slot size must be positive")
        if self.saved_register is not None and self.saved_register < 0:
            raise ValueError("stack slot saved register must be non-negative")
        if self.argument_register is not None and self.argument_register < 0:
            raise ValueError("stack slot argument register must be non-negative")
        if self.role == StackSlotRole.SAVED_REGISTER:
            if self.saved_register is None or self.argument_register is not None:
                raise ValueError(
                    "saved-register slots must carry only a saved register detail"
                )
        elif self.role == StackSlotRole.ARGUMENT_HOME:
            if self.argument_register is None or self.saved_register is not None:
                raise ValueError(
                    "argument-home slots must carry only an argument register detail"
                )
        elif self.saved_register is not None or self.argument_register is not None:
            raise ValueError("only detailed slot roles may carry register detail")

        expected = tuple(
            sorted(
                self.accesses,
                key=lambda access: (
                    access.instruction_address,
                    access.kind.value,
                    access.base_register,
                ),
            )
        )
        if self.accesses != expected:
            raise ValueError("stack slot accesses must be ordered deterministically")
        for access in self.accesses:
            if access.frame_offset != self.frame_offset or access.size != self.size:
                raise ValueError(
                    "stack slot accesses must match the owning slot offset and size"
                )

    def role_pretty(self) -> str:
        if self.role == StackSlotRole.SAVED_REGISTER:
            assert self.saved_register is not None
            return f"{self.role.value}(x{self.saved_register})"
        if self.role == StackSlotRole.ARGUMENT_HOME:
            assert self.argument_register is not None
            return f"{self.role.value}(x{self.argument_register})"
        return self.role.value

    def to_pretty(self) -> str:
        return (
            f"slot {self.frame_offset:+d} size={self.size} "
            f"role={self.role_pretty()} accesses={len(self.accesses)}"
        )


@dataclass(slots=True)
class FunctionStackFacts:
    calls: FunctionCallFacts
    frame_size: int | None = None
    frame_pointer: StackFrameBase | None = None
    dynamic_stack_pointer: bool = False
    slots: tuple[StackSlot, ...] = ()

    def __post_init__(self) -> None:
        if self.frame_size is not None and self.frame_size < 0:
            raise ValueError("stack frame size must be non-negative when present")
        expected = tuple(
            sorted(self.slots, key=lambda slot: (slot.frame_offset, slot.size))
        )
        if self.slots != expected:
            raise ValueError("function stack slots must be ordered by offset and size")
        keys = {(slot.frame_offset, slot.size) for slot in self.slots}
        if len(keys) != len(self.slots):
            raise ValueError("function stack slots must be unique by offset and size")

    @property
    def entry(self) -> int:
        return self.calls.entry

    @property
    def name(self) -> str | None:
        return self.calls.name

    @property
    def pending_entries(self) -> tuple[int, ...]:
        return self.calls.pending_entries


@dataclass(slots=True)
class ProgramStackFacts:
    calls: ProgramCallFacts
    functions: dict[int, FunctionStackFacts] = field(default_factory=dict)
    pending_entries: tuple[int, ...] = ()
    invalidated_entries: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if set(self.functions) != set(self.calls.functions):
            raise ValueError("program stack facts must cover call-fact functions exactly")
        if self.pending_entries != self.calls.pending_entries:
            raise ValueError("program stack facts pending entries must match call facts")
        if self.invalidated_entries != self.calls.invalidated_entries:
            raise ValueError(
                "program stack facts invalidated entries must match call facts"
            )

    def ordered_function_entries(self) -> tuple[int, ...]:
        return self.calls.ordered_function_entries()

    def ordered_functions(self) -> tuple[FunctionStackFacts, ...]:
        return tuple(self.functions[entry] for entry in self.ordered_function_entries())
