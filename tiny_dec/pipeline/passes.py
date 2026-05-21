"""Pipeline-owned scheduled views over the final rendered-C stage.

This module keeps stage-18 rendering itself in `tiny_dec.c_emit`, while the
pipeline owns the explicit rerun scheduler and the final merged translation
unit shown by `tiny-dec decompile --stage c` and `tiny-dec c program`.
"""

from __future__ import annotations

from dataclasses import dataclass

from tiny_dec.analysis.interproc.models import InterprocInvalidation
from tiny_dec.c_emit import build_program_c_rendered, format_function_c_rendered
from tiny_dec.loader import ProgramView
from tiny_dec.pipeline.scheduler import run_reanalysis_scheduler


@dataclass(frozen=True, slots=True)
class ScheduledFunctionRendering:
    entry: int
    prototype: str
    rendered: str

    def __post_init__(self) -> None:
        if self.entry < 0:
            raise ValueError("scheduled rendered-function entry must be non-negative")
        if not self.prototype:
            raise ValueError("scheduled rendered-function prototype must not be empty")
        if not self.rendered:
            raise ValueError("scheduled rendered-function body must not be empty")


@dataclass(slots=True)
class ScheduledCRenderedProgram:
    root_entry: int
    scheduled_roots: tuple[int, ...] = ()
    execution_order: tuple[int, ...] = ()
    includes: tuple[str, ...] = ()
    type_declarations: tuple[str, ...] = ()
    prototypes: tuple[str, ...] = ()
    functions: tuple[ScheduledFunctionRendering, ...] = ()
    pending_entries: tuple[int, ...] = ()
    invalidated_entries: tuple[int, ...] = ()
    scheduler_invalidations: tuple[InterprocInvalidation, ...] = ()

    def __post_init__(self) -> None:
        if self.root_entry < 0:
            raise ValueError("scheduled rendered-C root entry must be non-negative")
        if not self.scheduled_roots:
            raise ValueError("scheduled rendered-C roots must not be empty")
        if self.scheduled_roots[0] != self.root_entry:
            raise ValueError("scheduled rendered-C roots must start with root entry")
        if len(set(self.scheduled_roots)) != len(self.scheduled_roots):
            raise ValueError("scheduled rendered-C roots must be unique")
        if any(entry not in set(self.scheduled_roots) for entry in self.execution_order):
            raise ValueError("scheduled rendered-C execution order must reference roots")
        if len(set(self.includes)) != len(self.includes):
            raise ValueError("scheduled rendered-C includes must be unique")
        if len(set(self.type_declarations)) != len(self.type_declarations):
            raise ValueError("scheduled rendered-C type declarations must be unique")
        if len(set(self.prototypes)) != len(self.prototypes):
            raise ValueError("scheduled rendered-C prototypes must be unique")
        entries = tuple(function.entry for function in self.functions)
        if len(set(entries)) != len(entries):
            raise ValueError("scheduled rendered-C functions must be unique by entry")
        if len(set(self.pending_entries)) != len(self.pending_entries):
            raise ValueError("scheduled rendered-C pending entries must be unique")
        if len(set(self.invalidated_entries)) != len(self.invalidated_entries):
            raise ValueError("scheduled rendered-C invalidated entries must be unique")

        expected_scheduler = tuple(
            sorted(
                self.scheduler_invalidations,
                key=lambda item: (item.caller_entry, item.callee_entry, item.reason),
            )
        )
        if self.scheduler_invalidations != expected_scheduler:
            raise ValueError(
                "scheduled rendered-C scheduler invalidations must be ordered deterministically"
            )


def build_scheduled_c_rendered_program(
    view: ProgramView,
    root_entry: int,
) -> ScheduledCRenderedProgram:
    """Run the explicit rerun scheduler around the stage-18 builder."""

    scheduled = run_reanalysis_scheduler(
        root_entry,
        lambda entry: build_program_c_rendered(view, entry),
    )

    includes: list[str] = []
    type_declarations: list[str] = []
    functions: list[ScheduledFunctionRendering] = []
    seen_includes: set[str] = set()
    seen_type_declarations: set[str] = set()
    seen_functions: set[int] = set()

    for entry in scheduled.scheduled_roots:
        snapshot = scheduled.results[entry]
        for include in snapshot.includes:
            if include in seen_includes:
                continue
            seen_includes.add(include)
            includes.append(include)
        for declaration in snapshot.type_declarations:
            if declaration in seen_type_declarations:
                continue
            seen_type_declarations.add(declaration)
            type_declarations.append(declaration)
        for function in snapshot.ordered_functions():
            if function.entry in seen_functions:
                continue
            seen_functions.add(function.entry)
            functions.append(
                ScheduledFunctionRendering(
                    entry=function.entry,
                    prototype=function.prototype + ";",
                    rendered=format_function_c_rendered(function),
                )
            )

    return ScheduledCRenderedProgram(
        root_entry=root_entry,
        scheduled_roots=scheduled.scheduled_roots,
        execution_order=scheduled.execution_order,
        includes=tuple(includes),
        type_declarations=tuple(type_declarations),
        prototypes=tuple(function.prototype for function in functions),
        functions=tuple(functions),
        pending_entries=scheduled.pending_entries,
        invalidated_entries=scheduled.invalidated_entries,
        scheduler_invalidations=scheduled.scheduler_invalidations,
    )


def format_scheduled_c_rendered_program(program: ScheduledCRenderedProgram) -> str:
    """Format one scheduled final rendered-C snapshot deterministically."""

    scheduled_roots = ", ".join(f"0x{entry:x}" for entry in program.scheduled_roots)
    pending = ", ".join(f"0x{entry:x}" for entry in program.pending_entries) or "none"
    invalidated = (
        ", ".join(f"0x{entry:x}" for entry in program.invalidated_entries) or "none"
    )
    scheduler = (
        ", ".join(item.to_pretty() for item in program.scheduler_invalidations) or "none"
    )

    lines = [
        f"/* root: 0x{program.root_entry:x} */",
        f"/* scheduled_roots: {scheduled_roots} */",
        f"/* pending: {pending} */",
        f"/* invalidated: {invalidated} */",
        f"/* scheduler_invalidations: {scheduler} */",
    ]

    if program.includes:
        lines.append("")
        lines.extend(program.includes)

    if program.type_declarations:
        lines.append("")
        for index, declaration in enumerate(program.type_declarations):
            if index:
                lines.append("")
            lines.extend(declaration.splitlines())

    if program.prototypes:
        lines.append("")
        lines.extend(program.prototypes)

    for function in program.functions:
        lines.append("")
        lines.extend(function.rendered.splitlines())

    return "\n".join(lines).rstrip()


def render_scheduled_c_program(view: ProgramView, root_entry: int) -> str:
    """Build and format one scheduled final rendered-C snapshot."""

    return format_scheduled_c_rendered_program(
        build_scheduled_c_rendered_program(view, root_entry)
    )
