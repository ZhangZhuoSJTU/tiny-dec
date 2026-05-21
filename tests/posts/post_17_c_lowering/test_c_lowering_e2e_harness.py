from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.c_emit import build_program_c_lowered, format_program_c_lowered
from tiny_dec.loader import ProgramView


def _resolve_main_address(view: ProgramView) -> int:
    main_resolution = view.find_main()
    if main_resolution.address is not None:
        return main_resolution.address
    return view.entrypoint


def render_c_lowering_fixture_snapshots(fixture_bin_dir: Path) -> str:
    rendered: list[str] = []

    for binary in sorted(fixture_bin_dir.glob("*.elf")):
        view = ProgramView(binary)
        start = _resolve_main_address(view)
        rendered.extend(
            [
                f"binary: {binary.name}",
                f"start: {start:#x}",
                "c_lowering:",
            ]
        )
        snapshot = format_program_c_lowered(build_program_c_lowered(view, start))
        rendered.extend(f"  {line}" for line in snapshot.splitlines())
        rendered.append("")

    return "\n".join(rendered).rstrip()


def test_c_lowering_e2e_harness_renders_all_fixture_binaries(
    fixture_bin_dir: Path,
) -> None:
    binaries = sorted(fixture_bin_dir.glob("*.elf"))
    assert binaries, "expected at least one compiled fixture binary"

    combined = render_c_lowering_fixture_snapshots(fixture_bin_dir)
    combined_again = render_c_lowering_fixture_snapshots(fixture_bin_dir)

    assert combined == combined_again
    assert f"binary: {binaries[0].name}" in combined
    assert "\nc_lowering:\n" in combined
    assert "local_16_4 = malloc(32);" in combined
    assert "binary: fixture_stack_args_O0_nopie.elf" in combined
    assert "sum10(1, 2, 3, 4, 5, 6, 7, 8, 9, 10);" in combined
    assert "choose_op(&local_12_4);" in combined
    assert "run_steps(&local_40_4, 4, 6);" in combined
    assert "raw<x2_0:4>" not in combined
