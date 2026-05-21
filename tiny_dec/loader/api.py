"""Function-style loader entrypoints for stage-0 usage and tests."""

from __future__ import annotations

from pathlib import Path

from tiny_dec.loader.models import MainResolution
from tiny_dec.loader.program_view import ProgramView


def identify_main(
    binary_path: str | Path,
    *,
    scan_size: int = 512,
    strict: bool = False,
    checksec: bool = False,
    enforce_rv32i: bool = True,
) -> MainResolution:
    view = ProgramView(
        binary_path,
        checksec=checksec,
        enforce_rv32i=enforce_rv32i,
    )
    return view.identify_main(scan_size=scan_size, strict=strict)


def read_bytes(
    binary_path: str | Path,
    address: int,
    size: int,
    *,
    checksec: bool = False,
    enforce_rv32i: bool = True,
) -> bytes:
    view = ProgramView(
        binary_path,
        checksec=checksec,
        enforce_rv32i=enforce_rv32i,
    )
    return view.read_bytes(address, size)
