"""Deterministic rerun scheduling for final pipeline coordination.

This module owns the explicit queue consumption logic that turns preserved
`pending_entries`, `invalidated_entries`, and scheduler invalidations into
real rebuild requests. The scheduler is intentionally generic over one
snapshot type so the pipeline can reuse it around the final rendered-C pass
without mutating any stage-owned artifacts in place.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Protocol, TypeVar, cast

from tiny_dec.analysis.interproc.models import InterprocInvalidation


class SchedulerSnapshot(Protocol):
    pending_entries: tuple[int, ...]
    invalidated_entries: tuple[int, ...]
    scheduler_invalidations: tuple[InterprocInvalidation, ...]


SnapshotT = TypeVar("SnapshotT")


@dataclass(slots=True)
class ScheduledPassRun[SnapshotT]:
    root_entry: int
    scheduled_roots: tuple[int, ...] = ()
    execution_order: tuple[int, ...] = ()
    results: dict[int, SnapshotT] = field(default_factory=dict)
    pending_entries: tuple[int, ...] = ()
    invalidated_entries: tuple[int, ...] = ()
    scheduler_invalidations: tuple[InterprocInvalidation, ...] = ()

    def __post_init__(self) -> None:
        if self.root_entry < 0:
            raise ValueError("scheduled-pass root entry must be non-negative")
        if not self.scheduled_roots:
            raise ValueError("scheduled-pass roots must not be empty")
        if self.scheduled_roots[0] != self.root_entry:
            raise ValueError("scheduled-pass roots must start with the selected root")
        if len(set(self.scheduled_roots)) != len(self.scheduled_roots):
            raise ValueError("scheduled-pass roots must be unique")

        scheduled = set(self.scheduled_roots)
        if any(entry not in scheduled for entry in self.execution_order):
            raise ValueError("scheduled-pass execution order must reference scheduled roots")
        if any(entry not in scheduled for entry in self.results):
            raise ValueError("scheduled-pass results must be keyed by scheduled roots")
        if len(set(self.pending_entries)) != len(self.pending_entries):
            raise ValueError("scheduled-pass pending entries must be unique")
        if len(set(self.invalidated_entries)) != len(self.invalidated_entries):
            raise ValueError("scheduled-pass invalidated entries must be unique")

        expected_scheduler = tuple(
            sorted(
                self.scheduler_invalidations,
                key=lambda item: (item.caller_entry, item.callee_entry, item.reason),
            )
        )
        if self.scheduler_invalidations != expected_scheduler:
            raise ValueError(
                "scheduled-pass scheduler invalidations must be ordered deterministically"
            )


def run_reanalysis_scheduler(
    root_entry: int,
    build: Callable[[int], SnapshotT],
) -> ScheduledPassRun[SnapshotT]:
    """Run one deterministic rerun loop around a pass builder."""

    if root_entry < 0:
        raise ValueError("scheduler root entry must be non-negative")

    queue: deque[int] = deque([root_entry])
    queued = {root_entry}
    scheduled_roots = [root_entry]
    scheduled_set = {root_entry}
    execution_order: list[int] = []
    results: dict[int, SnapshotT] = {}
    pending_entries: dict[int, None] = {}
    invalidated_entries: dict[int, None] = {}
    scheduler_invalidations: dict[tuple[int, int, str], InterprocInvalidation] = {}
    seen_invalidation_causes: set[tuple[str, int, int, str]] = set()

    def enqueue(entry: int, *, allow_rerun: bool) -> None:
        if entry < 0:
            raise ValueError("scheduler entries must be non-negative")

        if entry not in scheduled_set:
            scheduled_set.add(entry)
            scheduled_roots.append(entry)
            if entry not in queued:
                queue.append(entry)
                queued.add(entry)
            return

        if entry in results and not allow_rerun:
            return
        if entry in queued:
            return
        if entry in results and allow_rerun:
            queue.append(entry)
            queued.add(entry)
            return
        if entry not in results:
            queue.append(entry)
            queued.add(entry)

    while queue:
        entry = queue.popleft()
        queued.remove(entry)
        execution_order.append(entry)

        snapshot = build(entry)
        results[entry] = snapshot
        scheduler_snapshot = cast(SchedulerSnapshot, snapshot)
        pending_entries.pop(entry, None)
        invalidated_entries.pop(entry, None)

        for pending in scheduler_snapshot.pending_entries:
            if pending not in results:
                pending_entries.setdefault(pending, None)
            enqueue(pending, allow_rerun=False)

        for invalidated in scheduler_snapshot.invalidated_entries:
            cause = ("entry", invalidated, invalidated, "")
            if cause in seen_invalidation_causes:
                continue
            seen_invalidation_causes.add(cause)
            invalidated_entries.setdefault(invalidated, None)
            enqueue(invalidated, allow_rerun=True)

        for item in scheduler_snapshot.scheduler_invalidations:
            key = (item.caller_entry, item.callee_entry, item.reason)
            scheduler_invalidations.setdefault(key, item)
            cause = ("scheduler", item.caller_entry, item.callee_entry, item.reason)
            if cause in seen_invalidation_causes:
                continue
            seen_invalidation_causes.add(cause)
            invalidated_entries.setdefault(item.caller_entry, None)
            enqueue(item.caller_entry, allow_rerun=True)

    return ScheduledPassRun(
        root_entry=root_entry,
        scheduled_roots=tuple(scheduled_roots),
        execution_order=tuple(execution_order),
        results=results,
        pending_entries=tuple(pending_entries),
        invalidated_entries=tuple(invalidated_entries),
        scheduler_invalidations=tuple(
            sorted(
                scheduler_invalidations.values(),
                key=lambda item: (item.caller_entry, item.callee_entry, item.reason),
            )
        ),
    )
