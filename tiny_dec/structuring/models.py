"""Stage-16 structured-control data structures built on top of stage-15 facts."""

from __future__ import annotations

from dataclasses import dataclass, field

from tiny_dec.analysis.interproc.models import (
    FunctionInterprocFacts,
    InterprocInvalidation,
    ProgramInterprocFacts,
)


@dataclass(frozen=True, slots=True)
class StructuredBlock:
    block_start: int

    def __post_init__(self) -> None:
        if self.block_start < 0:
            raise ValueError("structured block start must be non-negative")

    def to_pretty(self) -> str:
        return f"block 0x{self.block_start:x}"


@dataclass(frozen=True, slots=True)
class StructuredGoto:
    target: int

    def __post_init__(self) -> None:
        if self.target < 0:
            raise ValueError("structured goto target must be non-negative")

    def to_pretty(self) -> str:
        return f"goto 0x{self.target:x}"


@dataclass(frozen=True, slots=True)
class StructuredBreak:
    target: int

    def __post_init__(self) -> None:
        if self.target < 0:
            raise ValueError("structured break target must be non-negative")

    def to_pretty(self) -> str:
        return f"break 0x{self.target:x}"


@dataclass(frozen=True, slots=True)
class StructuredContinue:
    target: int

    def __post_init__(self) -> None:
        if self.target < 0:
            raise ValueError("structured continue target must be non-negative")

    def to_pretty(self) -> str:
        return f"continue 0x{self.target:x}"


type StructuredStmt = (
    StructuredBlock
    | StructuredIf
    | StructuredSwitch
    | StructuredWhile
    | StructuredGoto
    | StructuredBreak
    | StructuredContinue
)


@dataclass(frozen=True, slots=True)
class StructuredSequence:
    items: tuple[StructuredStmt, ...] = ()

    def statement_count(self) -> int:
        return sum(_statement_count(item) for item in self.items)

    def loop_count(self) -> int:
        return sum(_loop_count(item) for item in self.items)

    def if_count(self) -> int:
        return sum(_if_count(item) for item in self.items)

    def switch_count(self) -> int:
        return sum(_switch_count(item) for item in self.items)

    def goto_count(self) -> int:
        return sum(_goto_count(item) for item in self.items)


@dataclass(frozen=True, slots=True)
class StructuredSwitchCase:
    value: int
    target: int
    body: StructuredSequence = StructuredSequence()

    def __post_init__(self) -> None:
        if self.target < 0:
            raise ValueError("structured switch-case target must be non-negative")

    def to_pretty(self) -> str:
        return f"case {self.value} -> 0x{self.target:x}"


@dataclass(frozen=True, slots=True)
class StructuredIf:
    header: int
    true_target: int
    false_target: int
    merge_target: int | None
    then_body: StructuredSequence = StructuredSequence()
    else_body: StructuredSequence = StructuredSequence()

    def __post_init__(self) -> None:
        if self.header < 0:
            raise ValueError("structured if header must be non-negative")
        if self.true_target < 0:
            raise ValueError("structured if true target must be non-negative")
        if self.false_target < 0:
            raise ValueError("structured if false target must be non-negative")
        if self.true_target == self.false_target:
            raise ValueError("structured if branch targets must differ")
        if self.merge_target is not None and self.merge_target < 0:
            raise ValueError("structured if merge target must be non-negative when present")

    def to_pretty(self) -> str:
        merge = f"0x{self.merge_target:x}" if self.merge_target is not None else "?"
        return (
            f"if header=0x{self.header:x} true=0x{self.true_target:x} "
            f"false=0x{self.false_target:x} merge={merge}"
        )


@dataclass(frozen=True, slots=True)
class StructuredSwitch:
    header: int
    merge_target: int | None
    cases: tuple[StructuredSwitchCase, ...] = ()
    default_target: int | None = None
    default_body: StructuredSequence = StructuredSequence()

    def __post_init__(self) -> None:
        if self.header < 0:
            raise ValueError("structured switch header must be non-negative")
        if self.merge_target is not None and self.merge_target < 0:
            raise ValueError("structured switch merge target must be non-negative when present")
        if self.default_target is not None and self.default_target < 0:
            raise ValueError("structured switch default target must be non-negative when present")
        case_values = tuple(case.value for case in self.cases)
        if len(set(case_values)) != len(case_values):
            raise ValueError("structured switch cases must be unique by value")

    def to_pretty(self) -> str:
        merge = f"0x{self.merge_target:x}" if self.merge_target is not None else "?"
        default = f"0x{self.default_target:x}" if self.default_target is not None else "?"
        return (
            f"switch header=0x{self.header:x} cases={len(self.cases)} "
            f"default={default} merge={merge}"
        )


@dataclass(frozen=True, slots=True)
class StructuredWhile:
    header: int
    body_entry: int
    exit_target: int
    body: StructuredSequence = StructuredSequence()

    def __post_init__(self) -> None:
        if self.header < 0:
            raise ValueError("structured while header must be non-negative")
        if self.body_entry < 0:
            raise ValueError("structured while body entry must be non-negative")
        if self.exit_target < 0:
            raise ValueError("structured while exit target must be non-negative")

    def to_pretty(self) -> str:
        return (
            f"while header=0x{self.header:x} body=0x{self.body_entry:x} "
            f"exit=0x{self.exit_target:x}"
        )


@dataclass(slots=True)
class FunctionStructuredFacts:
    interproc: FunctionInterprocFacts
    body: StructuredSequence = StructuredSequence()

    @property
    def entry(self) -> int:
        return self.interproc.entry

    @property
    def name(self) -> str | None:
        return self.interproc.name

    @property
    def pending_entries(self) -> tuple[int, ...]:
        return self.interproc.pending_entries

    @property
    def frame_size(self) -> int | None:
        return self.interproc.frame_size

    @property
    def dynamic_stack_pointer(self) -> bool:
        return self.interproc.dynamic_stack_pointer

    @property
    def statement_count(self) -> int:
        return self.body.statement_count()

    @property
    def loop_count(self) -> int:
        return self.body.loop_count()

    @property
    def if_count(self) -> int:
        return self.body.if_count()

    @property
    def switch_count(self) -> int:
        return self.body.switch_count()

    @property
    def goto_count(self) -> int:
        return self.body.goto_count()


@dataclass(slots=True)
class ProgramStructuredFacts:
    interproc: ProgramInterprocFacts
    functions: dict[int, FunctionStructuredFacts] = field(default_factory=dict)
    pending_entries: tuple[int, ...] = ()
    invalidated_entries: tuple[int, ...] = ()
    scheduler_invalidations: tuple[InterprocInvalidation, ...] = ()

    def __post_init__(self) -> None:
        if set(self.functions) != set(self.interproc.functions):
            raise ValueError(
                "program structured facts must cover interproc functions exactly"
            )
        if self.pending_entries != self.interproc.pending_entries:
            raise ValueError(
                "program structured facts pending entries must match interproc facts"
            )
        if self.invalidated_entries != self.interproc.invalidated_entries:
            raise ValueError(
                "program structured facts invalidated entries must match interproc facts"
            )
        if self.scheduler_invalidations != self.interproc.scheduler_invalidations:
            raise ValueError(
                "program structured facts scheduler invalidations must match interproc facts"
            )

    def ordered_function_entries(self) -> tuple[int, ...]:
        return self.interproc.ordered_function_entries()

    def ordered_functions(self) -> tuple[FunctionStructuredFacts, ...]:
        return tuple(self.functions[entry] for entry in self.ordered_function_entries())


def _statement_count(item: StructuredStmt) -> int:
    if isinstance(item, StructuredIf):
        return 1 + item.then_body.statement_count() + item.else_body.statement_count()
    if isinstance(item, StructuredSwitch):
        return (
            1
            + sum(case.body.statement_count() for case in item.cases)
            + item.default_body.statement_count()
        )
    if isinstance(item, StructuredWhile):
        return 1 + item.body.statement_count()
    return 1


def _loop_count(item: StructuredStmt) -> int:
    if isinstance(item, StructuredIf):
        return item.then_body.loop_count() + item.else_body.loop_count()
    if isinstance(item, StructuredSwitch):
        return (
            sum(case.body.loop_count() for case in item.cases)
            + item.default_body.loop_count()
        )
    if isinstance(item, StructuredWhile):
        return 1 + item.body.loop_count()
    return 0


def _if_count(item: StructuredStmt) -> int:
    if isinstance(item, StructuredIf):
        return 1 + item.then_body.if_count() + item.else_body.if_count()
    if isinstance(item, StructuredSwitch):
        return (
            sum(case.body.if_count() for case in item.cases)
            + item.default_body.if_count()
        )
    if isinstance(item, StructuredWhile):
        return item.body.if_count()
    return 0


def _switch_count(item: StructuredStmt) -> int:
    if isinstance(item, StructuredIf):
        return item.then_body.switch_count() + item.else_body.switch_count()
    if isinstance(item, StructuredSwitch):
        return (
            1
            + sum(case.body.switch_count() for case in item.cases)
            + item.default_body.switch_count()
        )
    if isinstance(item, StructuredWhile):
        return item.body.switch_count()
    return 0


def _goto_count(item: StructuredStmt) -> int:
    if isinstance(item, StructuredGoto):
        return 1
    if isinstance(item, StructuredIf):
        return item.then_body.goto_count() + item.else_body.goto_count()
    if isinstance(item, StructuredSwitch):
        return (
            sum(case.body.goto_count() for case in item.cases)
            + item.default_body.goto_count()
        )
    if isinstance(item, StructuredWhile):
        return item.body.goto_count()
    return 0
