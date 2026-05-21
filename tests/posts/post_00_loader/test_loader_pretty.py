from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.loader import ProgramView, format_loader_snapshot


def test_format_loader_snapshot_is_deterministic(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")
    view = ProgramView(binary)

    first = format_loader_snapshot(view)
    second = format_loader_snapshot(view)

    assert first == second
    assert "entrypoint:" in first
    assert "main_source:" in first
    assert "\nsections:\n" in first


def test_format_loader_snapshot_respects_section_order(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_calls_O0_nopie")
    view = ProgramView(binary)

    output = format_loader_snapshot(view, section_names=(".rodata", ".text"))
    rodata_index = output.find("  .rodata")
    text_index = output.find("  .text")

    assert rodata_index != -1
    assert text_index != -1
    assert rodata_index < text_index


def test_format_loader_snapshot_external_functions_are_sorted(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_calls_O0_nopie")
    view = ProgramView(binary)

    output = format_loader_snapshot(view, show_externals=True)
    lines = output.splitlines()
    externals_start = lines.index("external_functions:") + 1
    names = [line.strip().split()[0] for line in lines[externals_start:] if line.strip()]

    assert names
    assert names == sorted(names)
