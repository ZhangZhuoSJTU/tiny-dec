from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.loader import ProgramView

_SECTION_ORDER = (".text", ".data", ".rodata", ".bss")


def _fixture_elfs(fixture_bin_dir: Path) -> list[Path]:
    return sorted(path for path in fixture_bin_dir.glob("*.elf") if path.is_file())


def render_loader_fixture_snapshots(fixture_bin_dir: Path) -> str:
    blocks: list[str] = []
    for binary in _fixture_elfs(fixture_bin_dir):
        view = ProgramView(binary)
        snapshot = view.format_snapshot(section_names=_SECTION_ORDER, show_externals=False)
        blocks.append(f"== {binary.name} ==\n{snapshot}")
    return "\n\n".join(blocks)


def test_loader_e2e_harness_renders_all_fixture_binaries(fixture_bin_dir: Path) -> None:
    binaries = _fixture_elfs(fixture_bin_dir)
    assert binaries, "expected compiled fixture binaries under tests/fixtures/bin"

    combined = render_loader_fixture_snapshots(fixture_bin_dir)
    combined_again = render_loader_fixture_snapshots(fixture_bin_dir)

    assert combined == combined_again
    for binary in binaries:
        marker = f"== {binary.name} =="
        assert marker in combined
    assert "entrypoint:" in combined
    assert "main_source:" in combined
    assert "\nsections:\n" in combined
