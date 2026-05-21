from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.analysis.types import (
    build_program_scalar_type_facts,
    format_program_scalar_type_facts,
)
from tiny_dec.loader import ProgramView


def _resolve_main_address(view: ProgramView) -> int:
    main_resolution = view.find_main()
    if main_resolution.address is not None:
        return main_resolution.address
    return view.entrypoint


def render_scalar_type_fixture_snapshots(fixture_bin_dir: Path) -> str:
    rendered: list[str] = []

    for binary in sorted(fixture_bin_dir.glob("*.elf")):
        view = ProgramView(binary)
        start = _resolve_main_address(view)
        rendered.extend(
            [
                f"binary: {binary.name}",
                f"start: {start:#x}",
                "scalar_types:",
            ]
        )
        snapshot = format_program_scalar_type_facts(build_program_scalar_type_facts(view, start))
        rendered.extend(f"  {line}" for line in snapshot.splitlines())
        rendered.append("")

    return "\n".join(rendered).rstrip()


def test_scalar_types_e2e_harness_renders_all_fixture_binaries(
    fixture_bin_dir: Path,
) -> None:
    binaries = sorted(fixture_bin_dir.glob("*.elf"))
    assert binaries, "expected at least one compiled fixture binary"

    combined = render_scalar_type_fixture_snapshots(fixture_bin_dir)
    combined_again = render_scalar_type_fixture_snapshots(fixture_bin_dir)

    assert combined == combined_again
    assert f"binary: {binaries[0].name}" in combined
    assert "\nscalar_types:\n" in combined
