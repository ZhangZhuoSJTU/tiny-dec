from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.analysis.ssa import build_ssa_program_ir, format_ssa_program_ir
from tiny_dec.loader import ProgramView


def _resolve_main_address(view: ProgramView) -> int:
    main_resolution = view.find_main()
    if main_resolution.address is not None:
        return main_resolution.address
    return view.entrypoint


def render_ssa_fixture_snapshots(fixture_bin_dir: Path) -> str:
    rendered: list[str] = []

    for binary in sorted(fixture_bin_dir.glob("*.elf")):
        view = ProgramView(binary)
        start = _resolve_main_address(view)
        rendered.extend(
            [
                f"binary: {binary.name}",
                f"start: {start:#x}",
                "ssa:",
            ]
        )
        try:
            snapshot = format_ssa_program_ir(build_ssa_program_ir(view, start))
            rendered.extend(f"  {line}" for line in snapshot.splitlines())
        except NotImplementedError as exc:
            rendered.append(f"  <not implemented: {exc}>")
        rendered.append("")

    return "\n".join(rendered).rstrip()


def test_ssa_e2e_harness_renders_all_fixture_binaries(
    fixture_bin_dir: Path,
) -> None:
    binaries = sorted(fixture_bin_dir.glob("*.elf"))
    assert binaries, "expected at least one compiled fixture binary"

    combined = render_ssa_fixture_snapshots(fixture_bin_dir)
    combined_again = render_ssa_fixture_snapshots(fixture_bin_dir)

    assert combined == combined_again
    assert f"binary: {binaries[0].name}" in combined
    assert "\nssa:\n" in combined
    assert "CALL_RETURN" in combined
    assert "memory_live_in:" in combined
    assert "[m" in combined
