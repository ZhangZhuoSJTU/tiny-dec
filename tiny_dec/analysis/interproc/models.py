"""Stage-15 interprocedural summary data structures built on stage-14 facts."""

from __future__ import annotations

from dataclasses import dataclass, field

from tiny_dec.analysis.range.models import FunctionRangeFacts, ProgramRangeFacts
from tiny_dec.analysis.types.models import ScalarType


def _prototype_sort_key(
    carrier: "PrototypeRegister | PrototypeStackParameter",
) -> tuple[int, int, int, str]:
    if isinstance(carrier, PrototypeRegister):
        return (0, carrier.register, carrier.size, carrier.variable_name or "")
    return (1, carrier.stack_offset, carrier.size, carrier.variable_name or "")


@dataclass(frozen=True, slots=True)
class PrototypeRegister:
    register: int
    size: int
    scalar_type: ScalarType | None = None
    variable_name: str | None = None

    def __post_init__(self) -> None:
        if self.register < 0:
            raise ValueError("prototype register number must be non-negative")
        if self.size <= 0:
            raise ValueError("prototype register size must be positive")
        if self.scalar_type is not None and self.scalar_type.size != self.size:
            raise ValueError("prototype register scalar type size must match carrier size")
        if self.variable_name == "":
            raise ValueError("prototype register variable name must not be empty")

    def to_pretty(self) -> str:
        text = f"x{self.register}:{self.size}"
        if self.scalar_type is not None:
            text += f" type={self.scalar_type.to_pretty()}"
        if self.variable_name is not None:
            text += f" name={self.variable_name}"
        return text


@dataclass(frozen=True, slots=True)
class PrototypeStackParameter:
    stack_offset: int
    size: int
    scalar_type: ScalarType | None = None
    variable_name: str | None = None

    def __post_init__(self) -> None:
        if self.stack_offset < 0:
            raise ValueError("prototype stack offset must be non-negative")
        if self.size <= 0:
            raise ValueError("prototype stack parameter size must be positive")
        if self.scalar_type is not None and self.scalar_type.size != self.size:
            raise ValueError(
                "prototype stack parameter scalar type size must match carrier size"
            )
        if self.variable_name == "":
            raise ValueError("prototype stack parameter variable name must not be empty")

    def to_pretty(self) -> str:
        text = f"stack+{self.stack_offset}:{self.size}"
        if self.scalar_type is not None:
            text += f" type={self.scalar_type.to_pretty()}"
        if self.variable_name is not None:
            text += f" name={self.variable_name}"
        return text


@dataclass(frozen=True, slots=True)
class InferredPrototype:
    parameters: tuple[PrototypeRegister | PrototypeStackParameter, ...] = ()
    returns: tuple[PrototypeRegister, ...] = ()
    no_return: bool = False

    def __post_init__(self) -> None:
        expected_parameters = tuple(sorted(self.parameters, key=_prototype_sort_key))
        if self.parameters != expected_parameters:
            raise ValueError("prototype parameters must be ordered deterministically")
        parameter_keys = {
            ("register", carrier.register)
            if isinstance(carrier, PrototypeRegister)
            else ("stack", carrier.stack_offset)
            for carrier in self.parameters
        }
        if len(parameter_keys) != len(self.parameters):
            raise ValueError("prototype parameters must be unique by carrier location")

        expected_returns = tuple(sorted(self.returns, key=_prototype_sort_key))
        if self.returns != expected_returns:
            raise ValueError("prototype returns must be ordered deterministically")
        if len({carrier.register for carrier in self.returns}) != len(self.returns):
            raise ValueError("prototype returns must be unique by register")

        if self.no_return and self.returns:
            raise ValueError("no-return prototypes must not carry return registers")

    def to_pretty(self) -> str:
        parameters = ", ".join(carrier.to_pretty() for carrier in self.parameters)
        returns = ", ".join(carrier.to_pretty() for carrier in self.returns)
        return (
            f"prototype params=[{parameters}] returns=[{returns}] "
            f"no_return={'yes' if self.no_return else 'no'}"
        )


@dataclass(frozen=True, slots=True)
class FunctionEffectSummary:
    global_reads: tuple[int, ...] = ()
    global_writes: tuple[int, ...] = ()
    indirect_reads: bool = False
    indirect_writes: bool = False

    def __post_init__(self) -> None:
        expected_reads = tuple(sorted(set(self.global_reads)))
        if self.global_reads != expected_reads:
            raise ValueError("effect-summary global reads must be unique and sorted")
        expected_writes = tuple(sorted(set(self.global_writes)))
        if self.global_writes != expected_writes:
            raise ValueError("effect-summary global writes must be unique and sorted")
        if any(address < 0 for address in self.global_reads):
            raise ValueError("effect-summary global reads must be non-negative")
        if any(address < 0 for address in self.global_writes):
            raise ValueError("effect-summary global writes must be non-negative")

    def to_pretty(self) -> str:
        reads = ", ".join(f"0x{address:x}" for address in self.global_reads)
        writes = ", ".join(f"0x{address:x}" for address in self.global_writes)
        return (
            f"effects reads=[{reads}] writes=[{writes}] "
            f"indirect_reads={'yes' if self.indirect_reads else 'no'} "
            f"indirect_writes={'yes' if self.indirect_writes else 'no'}"
        )


@dataclass(frozen=True, slots=True)
class InterprocInvalidation:
    caller_entry: int
    callee_entry: int
    reason: str

    def __post_init__(self) -> None:
        if self.caller_entry < 0:
            raise ValueError("interproc invalidation caller entry must be non-negative")
        if self.callee_entry < 0:
            raise ValueError("interproc invalidation callee entry must be non-negative")
        if not self.reason:
            raise ValueError("interproc invalidation reason must not be empty")

    def to_pretty(self) -> str:
        return (
            f"invalidate caller=0x{self.caller_entry:x} "
            f"callee=0x{self.callee_entry:x} reason={self.reason}"
        )


@dataclass(slots=True)
class FunctionInterprocFacts:
    ranges: FunctionRangeFacts
    prototype: InferredPrototype = InferredPrototype()
    effects: FunctionEffectSummary = FunctionEffectSummary()

    @property
    def entry(self) -> int:
        return self.ranges.entry

    @property
    def name(self) -> str | None:
        return self.ranges.name

    @property
    def pending_entries(self) -> tuple[int, ...]:
        return self.ranges.pending_entries

    @property
    def frame_size(self) -> int | None:
        return self.ranges.frame_size

    @property
    def dynamic_stack_pointer(self) -> bool:
        return self.ranges.dynamic_stack_pointer


@dataclass(slots=True)
class ProgramInterprocFacts:
    ranges: ProgramRangeFacts
    functions: dict[int, FunctionInterprocFacts] = field(default_factory=dict)
    scheduler_invalidations: tuple[InterprocInvalidation, ...] = ()
    pending_entries: tuple[int, ...] = ()
    invalidated_entries: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if set(self.functions) != set(self.ranges.functions):
            raise ValueError("program interproc facts must cover range functions exactly")

        expected_scheduler = tuple(
            sorted(
                self.scheduler_invalidations,
                key=lambda invalidation: (
                    invalidation.caller_entry,
                    invalidation.callee_entry,
                    invalidation.reason,
                ),
            )
        )
        if self.scheduler_invalidations != expected_scheduler:
            raise ValueError(
                "program interproc scheduler invalidations must be ordered deterministically"
            )
        keys = {
            (
                invalidation.caller_entry,
                invalidation.callee_entry,
                invalidation.reason,
            )
            for invalidation in self.scheduler_invalidations
        }
        if len(keys) != len(self.scheduler_invalidations):
            raise ValueError(
                "program interproc scheduler invalidations must be unique by caller, callee, and reason"
            )

        if self.pending_entries != self.ranges.pending_entries:
            raise ValueError(
                "program interproc pending entries must match stage-14 pending entries"
            )

        expected_invalidated = tuple(
            sorted(
                {
                    *self.ranges.invalidated_entries,
                    *(item.caller_entry for item in self.scheduler_invalidations),
                }
            )
        )
        if self.invalidated_entries != expected_invalidated:
            raise ValueError(
                "program interproc invalidated entries must equal upstream plus scheduler invalidations"
            )

    def ordered_function_entries(self) -> tuple[int, ...]:
        return self.ranges.ordered_function_entries()

    def ordered_functions(self) -> tuple[FunctionInterprocFacts, ...]:
        return tuple(self.functions[entry] for entry in self.ordered_function_entries())
