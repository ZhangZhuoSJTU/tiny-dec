from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.ir import lift_window_lines
from tiny_dec.loader import ProgramView

_MAX_PCODE_INSTRUCTIONS = 8


def _fixture_elfs(fixture_bin_dir: Path) -> list[Path]:
    return sorted(path for path in fixture_bin_dir.glob("*.elf") if path.is_file())


def render_pcode_fixture_snapshots(fixture_bin_dir: Path) -> str:
    blocks: list[str] = []
    for binary in _fixture_elfs(fixture_bin_dir):
        view = ProgramView(binary)
        main_resolution = view.find_main()
        start = (
            main_resolution.address
            if main_resolution.address is not None
            else view.entrypoint
        )
        header = [
            f"== {binary.name} ==",
            f"start: 0x{start:x}",
            f"main_source: {main_resolution.source}",
            "pcode:",
        ]
        body = [
            f"  {line}"
            for line in lift_window_lines(view, start, limit=_MAX_PCODE_INSTRUCTIONS)
        ]
        blocks.append("\n".join([*header, *body]))
    return "\n\n".join(blocks)


def test_pcode_e2e_harness_renders_all_fixture_binaries(fixture_bin_dir: Path) -> None:
    binaries = _fixture_elfs(fixture_bin_dir)
    assert binaries, "expected compiled fixture binaries under tests/fixtures/bin"

    combined = render_pcode_fixture_snapshots(fixture_bin_dir)
    combined_again = render_pcode_fixture_snapshots(fixture_bin_dir)

    assert combined == combined_again
    for binary in binaries:
        assert f"== {binary.name} ==" in combined
    assert "\npcode:\n" in combined
