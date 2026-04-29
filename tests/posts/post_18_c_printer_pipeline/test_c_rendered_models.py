from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.c_emit import (
    FunctionCRendered,
    ProgramCRendered,
    build_function_c_lowered,
    build_program_c_lowered,
    format_function_c_rendered,
)
from tiny_dec.loader import ProgramView


def test_function_c_rendered_formats_single_function_snapshot(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")
    view = ProgramView(binary)
    entry = view.find_main().address
    assert entry is not None

    lowered = build_function_c_lowered(view, entry)
    rendered = FunctionCRendered(
        c_lowered=lowered,
        function_name="main",
        return_type="int32_t",
        prototype="static int32_t main(void)",
        includes=("#include <stdint.h>",),
        local_declarations=("int32_t local_16_4;",),
        statement_lines=("local_16_4 = 7;", "return local_16_4;"),
    )

    assert (
        format_function_c_rendered(rendered)
        == "#include <stdint.h>\n\n"
        "static int32_t main(void) {\n"
        "  int32_t local_16_4;\n\n"
        "  local_16_4 = 7;\n"
        "  return local_16_4;\n"
        "}"
    )


def test_function_c_rendered_rejects_multiline_statement_text(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")
    view = ProgramView(binary)
    entry = view.find_main().address
    assert entry is not None

    lowered = build_function_c_lowered(view, entry)

    with pytest.raises(ValueError, match="statement lines must be single lines"):
        FunctionCRendered(
            c_lowered=lowered,
            function_name="main",
            return_type="int32_t",
            prototype="static int32_t main(void)",
            statement_lines=("return 0;\n",),
        )


def test_program_c_rendered_requires_full_function_coverage(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")
    view = ProgramView(binary)
    entry = view.find_main().address
    assert entry is not None

    lowered = build_program_c_lowered(view, entry)
    only_main = next(iter(lowered.ordered_function_entries()))
    rendered_main = FunctionCRendered(
        c_lowered=lowered.functions[only_main],
        function_name="main",
        return_type="int32_t",
        prototype="static int32_t main(void)",
        statement_lines=("return 0;",),
    )

    with pytest.raises(ValueError, match="cover lowered program exactly"):
        ProgramCRendered(
            c_lowered=lowered,
            functions={only_main: rendered_main},
            pending_entries=lowered.pending_entries,
            invalidated_entries=lowered.invalidated_entries,
            scheduler_invalidations=lowered.scheduler_invalidations,
        )
