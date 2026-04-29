"""Stable loader-stage data models used by tests and debug snapshots."""

from __future__ import annotations

from dataclasses import dataclass


def _fmt_hex(value: int | None) -> str:
    return f"{value:#x}" if value is not None else "-"


@dataclass(frozen=True, slots=True)
class SectionLayout:
    """Deterministic section metadata for loader snapshots."""

    name: str
    virtual_address: int
    size: int

    @property
    def end_address(self) -> int:
        return self.virtual_address + self.size

    def to_pretty_line(self) -> str:
        return (
            f"{self.name:8s} vaddr={self.virtual_address:#x} "
            f"size={self.size:#x} end={self.end_address:#x}"
        )


@dataclass(frozen=True, slots=True)
class ExternalFunction:
    """External symbol mapping visible from loader tables."""

    name: str
    plt_address: int | None
    got_address: int | None
    symbol_address: int | None

    def to_pretty_line(self) -> str:
        return (
            f"{self.name:32s} "
            f"plt={_fmt_hex(self.plt_address):>12s} "
            f"got={_fmt_hex(self.got_address):>12s} "
            f"sym={_fmt_hex(self.symbol_address):>12s}"
        )


@dataclass(frozen=True, slots=True)
class SymbolInfo:
    """Deterministic symbol metadata for CLI info snapshots."""

    name: str
    address: int

    def to_pretty_line(self) -> str:
        return f"{self.name:32s} addr={self.address:#x}"


@dataclass(frozen=True, slots=True)
class MainResolution:
    """Best-effort `main` address recovery status."""

    address: int | None
    source: str
    entrypoint: int

    def to_pretty_line(self) -> str:
        resolved = f"{self.address:#x}" if self.address is not None else "<unresolved>"
        return f"main: {resolved} (source={self.source}, entrypoint={self.entrypoint:#x})"
