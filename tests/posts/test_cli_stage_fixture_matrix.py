from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.cli import STAGE_CHOICES, main as cli_main


@pytest.mark.parametrize(
    ("fixture_name", "func_name", "c_anchor"),
    (
        (
            "fixture_indirect_const_O0_nopie",
            "main",
            "call_indirect(local_12_4, 7);",
        ),
        (
            "fixture_indirect_select_O0_nopie",
            "main",
            "static uint32_t choose_op(agg_4* arg_x10_4);",
        ),
        (
            "fixture_nested_O0_nopie",
            "main",
            "static int32_t sweep(uint32_t arg_x10_4, int32_t arg_x11_4);",
        ),
        (
            "fixture_lookup_O0_nopie",
            "main",
            "static int32_t run_lookup(int32_t arg_x10_4);",
        ),
    ),
)
@pytest.mark.parametrize("stage", STAGE_CHOICES)
def test_cli_decompile_stage_matrix_handles_expanded_fixture_corpus(
    fixture_binary: Callable[[str], Path],
    capsys: pytest.CaptureFixture[str],
    fixture_name: str,
    func_name: str,
    c_anchor: str,
    stage: str,
) -> None:
    binary = fixture_binary(fixture_name)
    argv = ["decompile", str(binary), "--stage", stage, "--func", func_name]

    first_exit = cli_main(argv)
    first_output = capsys.readouterr().out
    second_exit = cli_main(argv)
    second_output = capsys.readouterr().out

    assert first_exit == 0
    assert second_exit == 0
    assert first_output == second_output

    if stage == "c":
        assert "/* root:" in first_output
        assert "/* scheduled_roots: " in first_output
        assert c_anchor in first_output
        assert "stage:" not in first_output
        return

    assert f"binary: {binary}" in first_output
    assert f"target_function: {func_name}" in first_output
    assert f"stage: {stage}" in first_output
    assert f"{stage}:" in first_output
    assert "<unresolved>" not in first_output
