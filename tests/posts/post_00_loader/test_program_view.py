from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

pytest.importorskip("pwn")

from tiny_dec.loader import AddressNotMappedError, MainResolutionError, ProgramView
from tiny_dec.loader.models import MainResolution


def test_sections_entry_points_and_main_resolution(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")
    view = ProgramView(binary)

    section_names = {section.name for section in view.sections()}
    assert ".text" in section_names

    main_resolution = view.find_main()
    assert main_resolution.address is not None
    assert main_resolution.entrypoint == view.entrypoint
    assert view.entry_points[0] == view.entrypoint


def test_read_bytes_and_scalar_helpers(fixture_binary: Callable[[str], Path]) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")
    view = ProgramView(binary)

    text_section = view.sections([".text"])[0]
    address = text_section.virtual_address

    raw = view.read_bytes(address, 4)
    assert len(raw) == 4

    assert view.read_u8(address) == raw[0]
    assert view.read_u16(address) == int.from_bytes(raw[:2], byteorder=view.endian)
    assert view.read_u32(address) == int.from_bytes(raw, byteorder=view.endian)


def test_read_bytes_zero_size_returns_empty(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")
    view = ProgramView(binary)

    assert view.read_bytes(view.entrypoint, 0) == b""


def test_read_bytes_negative_size_raises_value_error(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")
    view = ProgramView(binary)

    with pytest.raises(ValueError, match="size must be non-negative"):
        view.read_bytes(view.entrypoint, -1)


def test_invalid_virtual_address_read_raises(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")
    view = ProgramView(binary)

    with pytest.raises(AddressNotMappedError):
        view.read_bytes(0x7FFF_FFFF_FFFF, 8)


def test_external_functions_include_libc_calls(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_calls_O0_nopie")
    view = ProgramView(binary)

    externals = view.external_functions()
    assert externals

    normalized_names = {fn.name.split("@", 1)[0] for fn in externals}
    assert {"puts", "malloc", "free"} & normalized_names


def test_identify_main_alias_matches_find_main(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")
    view = ProgramView(binary)

    assert view.identify_main() == view.find_main()


def test_find_main_strict_raises_when_unresolved(
    fixture_binary: Callable[[str], Path],
) -> None:
    binary = fixture_binary("fixture_basic_O0_nopie")
    view = ProgramView(binary)
    view._main_resolution_cache = MainResolution(
        address=None,
        source="unresolved",
        entrypoint=view.entrypoint,
    )

    with pytest.raises(MainResolutionError):
        view.find_main(strict=True)
