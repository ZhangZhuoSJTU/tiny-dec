from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.loader import ProgramView, identify_main, read_bytes


def test_identify_main_function_returns_main_resolution(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")
    resolution = identify_main(binary)

    assert resolution.address is not None
    assert resolution.entrypoint > 0


def test_read_bytes_function_matches_program_view(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")
    view = ProgramView(binary)
    address = view.sections([".text"])[0].virtual_address

    assert read_bytes(binary, address, 8) == view.read_bytes(address, 8)


def test_read_bytes_function_rejects_negative_size(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")
    with pytest.raises(ValueError, match="size must be non-negative"):
        read_bytes(binary, 0, -1)
