from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from tiny_dec.analysis.interproc.models import InterprocInvalidation
from tiny_dec.loader import ProgramView
from tiny_dec.pipeline.passes import (
    build_scheduled_c_rendered_program,
    format_scheduled_c_rendered_program,
)
from tiny_dec.pipeline.scheduler import run_reanalysis_scheduler


@dataclass(frozen=True, slots=True)
class _SchedulerSnapshot:
    pending_entries: tuple[int, ...] = ()
    invalidated_entries: tuple[int, ...] = ()
    scheduler_invalidations: tuple[InterprocInvalidation, ...] = ()


@dataclass(frozen=True, slots=True)
class _FakeFunction:
    entry: int
    prototype: str
    rendered: str


@dataclass(frozen=True, slots=True)
class _FakeProgram:
    includes: tuple[str, ...] = ()
    type_declarations: tuple[str, ...] = ()
    pending_entries: tuple[int, ...] = ()
    invalidated_entries: tuple[int, ...] = ()
    scheduler_invalidations: tuple[InterprocInvalidation, ...] = ()
    functions: tuple[_FakeFunction, ...] = ()

    def ordered_functions(self) -> tuple[_FakeFunction, ...]:
        return self.functions


def test_run_reanalysis_scheduler_consumes_pending_entries() -> None:
    def build(entry: int) -> _SchedulerSnapshot:
        if entry == 0x1000:
            return _SchedulerSnapshot(pending_entries=(0x1200,))
        assert entry == 0x1200
        return _SchedulerSnapshot()

    result = run_reanalysis_scheduler(0x1000, build)

    assert result.scheduled_roots == (0x1000, 0x1200)
    assert result.execution_order == (0x1000, 0x1200)
    assert tuple(result.results) == (0x1000, 0x1200)
    assert result.pending_entries == ()
    assert result.invalidated_entries == ()
    assert result.scheduler_invalidations == ()


def test_run_reanalysis_scheduler_reruns_invalidated_entry_once_per_cause() -> None:
    invalidation = InterprocInvalidation(
        caller_entry=0x1000,
        callee_entry=0x2000,
        reason="noreturn_callee",
    )
    build_count = 0

    def build(entry: int) -> _SchedulerSnapshot:
        nonlocal build_count
        assert entry == 0x1000
        build_count += 1
        return _SchedulerSnapshot(
            invalidated_entries=(0x1000,),
            scheduler_invalidations=(invalidation,),
        )

    result = run_reanalysis_scheduler(0x1000, build)

    assert build_count == 2
    assert result.scheduled_roots == (0x1000,)
    assert result.execution_order == (0x1000, 0x1000)
    assert result.pending_entries == ()
    assert result.invalidated_entries == ()
    assert result.scheduler_invalidations == (invalidation,)


def test_build_scheduled_c_rendered_program_merges_scheduled_roots(
    monkeypatch,
) -> None:
    snapshots = {
        0x1000: _FakeProgram(
            includes=("#include <stdint.h>",),
            type_declarations=("typedef struct agg_8 {\n  int32_t field_0;\n} agg_8;",),
            pending_entries=(0x1200,),
            functions=(
                _FakeFunction(
                    entry=0x1000,
                    prototype="static int32_t main(void)",
                    rendered="static int32_t main(void) {\n  return 1;\n}",
                ),
            ),
        ),
        0x1200: _FakeProgram(
            includes=("#include <stdint.h>",),
            type_declarations=("typedef struct agg_8 {\n  int32_t field_0;\n} agg_8;",),
            functions=(
                _FakeFunction(
                    entry=0x1200,
                    prototype="static int32_t helper(void)",
                    rendered="static int32_t helper(void) {\n  return 2;\n}",
                ),
            ),
        ),
    }

    def fake_build(_view: object, entry: int) -> _FakeProgram:
        return snapshots[entry]

    def fake_format(function: _FakeFunction) -> str:
        return function.rendered

    monkeypatch.setattr(
        "tiny_dec.pipeline.passes.build_program_c_rendered",
        fake_build,
    )
    monkeypatch.setattr(
        "tiny_dec.pipeline.passes.format_function_c_rendered",
        fake_format,
    )

    result = build_scheduled_c_rendered_program(cast(ProgramView, object()), 0x1000)
    rendered = format_scheduled_c_rendered_program(result)

    assert result.scheduled_roots == (0x1000, 0x1200)
    assert result.execution_order == (0x1000, 0x1200)
    assert result.pending_entries == ()
    assert result.invalidated_entries == ()
    assert result.scheduler_invalidations == ()
    assert result.includes == ("#include <stdint.h>",)
    assert result.prototypes == (
        "static int32_t main(void);",
        "static int32_t helper(void);",
    )
    assert "/* scheduled_roots: 0x1000, 0x1200 */" in rendered
    assert rendered.index("static int32_t main(void);") < rendered.index(
        "static int32_t helper(void);"
    )
    assert rendered.index("static int32_t main(void) {") < rendered.index(
        "static int32_t helper(void) {"
    )
