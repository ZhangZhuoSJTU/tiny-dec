"""ELF-backed program view used as stage-0 pipeline output."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable, Literal, SupportsInt, cast

from pwn import ELF

from tiny_dec.loader.errors import (
    AddressNotMappedError,
    MainResolutionError,
    UnsupportedArchitectureError,
)
from tiny_dec.loader.main_locator import MainLocator
from tiny_dec.loader.models import (
    ExternalFunction,
    MainResolution,
    SectionLayout,
    SymbolInfo,
)

_DEFAULT_SECTION_NAMES = (".text", ".data", ".rodata", ".bss")


def _to_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if value is None:
        return None
    if isinstance(value, str):
        try:
            return int(value, 0)
        except ValueError:
            return None
    if isinstance(value, (bytes, bytearray)):
        try:
            return int(value)
        except ValueError:
            return None
    try:
        return int(cast(SupportsInt, cast(Any, value)))
    except (TypeError, ValueError):
        return None


def _header_int(header: object, key: str, *, default: int = 0) -> int:
    value: object | None = None
    if hasattr(header, key):
        value = getattr(header, key)
    else:
        try:
            value = header[key]  # type: ignore[index]
        except Exception:
            value = None

    converted = _to_int(value)
    return converted if converted is not None else default


def _normalize_symbol_table(symbols: object) -> dict[str, int | None]:
    if not isinstance(symbols, dict):
        return {}

    normalized: dict[str, int | None] = {}
    for name, value in symbols.items():
        normalized[str(name)] = _to_int(value)
    return normalized


def _undefined_external_symbols(elf: ELF) -> set[str]:
    return set(_ordered_undefined_external_symbols(elf))


def _ordered_undefined_external_symbols(elf: ELF) -> tuple[str, ...]:
    names: set[str] = set()
    ordered: list[str] = []
    for section_name in (".dynsym", ".symtab"):
        section = elf.get_section_by_name(section_name)
        if section is None or not hasattr(section, "iter_symbols"):
            continue

        for symbol in section.iter_symbols():
            name = str(getattr(symbol, "name", ""))
            if not name:
                continue

            bind = str(symbol["st_info"]["bind"])
            shndx = str(symbol["st_shndx"])
            if shndx == "SHN_UNDEF" and bind in {"STB_GLOBAL", "STB_WEAK"}:
                if name in names:
                    continue
                names.add(name)
                ordered.append(name)

    return tuple(ordered)


class ProgramView:
    """High-level ELF view for the RV32I teaching pipeline."""

    def __init__(
        self,
        binary_path: str | Path,
        *,
        checksec: bool = False,
        enforce_rv32i: bool = True,
    ) -> None:
        self.path = str(binary_path)
        self.elf = ELF(self.path, checksec=checksec)

        self.arch = str(getattr(self.elf, "arch", "unknown"))
        self.bits = int(getattr(self.elf, "bits", 0))
        self.entrypoint = int(self.elf.entry)

        endian = str(getattr(self.elf, "endian", "little")).lower()
        self.endian: Literal["big", "little"] = "big" if endian == "big" else "little"

        if enforce_rv32i and not self._is_rv32i():
            raise UnsupportedArchitectureError(
                f"Expected RV32I-compatible ELF, got arch={self.arch}, bits={self.bits}, endian={self.endian}"
            )

        self._main_resolution_cache: MainResolution | None = None

    def _is_rv32i(self) -> bool:
        arch_lower = self.arch.lower()
        is_riscv = "riscv" in arch_lower
        return is_riscv and self.bits == 32 and self.endian == "little"

    @property
    def entry_points(self) -> tuple[int, ...]:
        points = [self.entrypoint]
        main_address = self.find_main().address
        if main_address is not None:
            points.append(main_address)

        deduplicated: list[int] = []
        for point in points:
            if point not in deduplicated:
                deduplicated.append(point)
        return tuple(deduplicated)

    def identify_main(
        self, *, scan_size: int = 512, strict: bool = False
    ) -> MainResolution:
        """Stage-0 public API alias for `find_main()`."""
        return self.find_main(scan_size=scan_size, strict=strict)

    def find_main(
        self, *, scan_size: int = 512, strict: bool = False
    ) -> MainResolution:
        # Resolution is intentionally two-phase:
        # 1) direct symbol table hit
        # 2) startup disassembly scan around entrypoint for libc trampoline patterns
        if scan_size == 512 and self._main_resolution_cache is not None:
            resolution = self._main_resolution_cache
        else:
            locator = MainLocator(self.elf, self.entrypoint)
            resolution = locator.resolve(scan_size=scan_size)
            if scan_size == 512:
                self._main_resolution_cache = resolution

        if strict and resolution.address is None:
            raise MainResolutionError("Unable to resolve main() from startup flow.")

        return resolution

    def format_snapshot(
        self,
        *,
        section_names: Iterable[str] | None = None,
        show_externals: bool = False,
        scan_size: int = 512,
    ) -> str:
        # Local import prevents module cycle: pretty -> program_view for type usage.
        from tiny_dec.loader.pretty import format_loader_snapshot

        return format_loader_snapshot(
            self,
            section_names=section_names,
            show_externals=show_externals,
            scan_size=scan_size,
        )

    def sections(self, names: Iterable[str] | None = None) -> list[SectionLayout]:
        selected_names = tuple(names) if names is not None else _DEFAULT_SECTION_NAMES
        layouts: list[SectionLayout] = []

        for section_name in selected_names:
            section = self.elf.get_section_by_name(section_name)
            if section is None:
                continue

            header = section.header
            layouts.append(
                SectionLayout(
                    name=section_name,
                    virtual_address=_header_int(header, "sh_addr"),
                    size=_header_int(header, "sh_size"),
                )
            )

        return layouts

    def all_sections(self) -> list[SectionLayout]:
        layouts: list[SectionLayout] = []
        iterator = getattr(self.elf, "iter_sections", None)
        if callable(iterator):
            for section in iterator():
                name = str(getattr(section, "name", ""))
                if not name:
                    continue
                header = section.header
                layouts.append(
                    SectionLayout(
                        name=name,
                        virtual_address=_header_int(header, "sh_addr"),
                        size=_header_int(header, "sh_size"),
                    )
                )
            return layouts
        return self.sections()

    def read_bytes(self, address: int, size: int) -> bytes:
        if size < 0:
            raise ValueError("size must be non-negative")
        if size == 0:
            return b""

        try:
            data = self.elf.read(address, size)
        except Exception as exc:
            raise AddressNotMappedError(
                f"Failed to read bytes at {address:#x}, size {size}"
            ) from exc

        if len(data) != size:
            raise AddressNotMappedError(
                f"Read returned {len(data)} bytes, expected {size}"
            )

        return data

    def read_u8(self, address: int) -> int:
        return int.from_bytes(self.read_bytes(address, 1), byteorder=self.endian)

    def read_u16(self, address: int) -> int:
        return int.from_bytes(self.read_bytes(address, 2), byteorder=self.endian)

    def read_u32(self, address: int) -> int:
        return int.from_bytes(self.read_bytes(address, 4), byteorder=self.endian)

    def get_symbol_address(self, symbol_name: str) -> int | None:
        symbols = _normalize_symbol_table(getattr(self.elf, "symbols", {}))
        return symbols.get(symbol_name)

    def symbol_names_for_address(self, address: int) -> tuple[str, ...]:
        symbols = _normalize_symbol_table(getattr(self.elf, "symbols", {}))
        matches = [
            name
            for name, symbol_address in symbols.items()
            if symbol_address == address and not name.startswith("$")
        ]
        return tuple(sorted(matches))

    def get_symbol_name(self, address: int) -> str | None:
        names = self.symbol_names_for_address(address)
        if not names:
            return None
        return names[0]

    def symbols(self) -> list[SymbolInfo]:
        symbols = _normalize_symbol_table(getattr(self.elf, "symbols", {}))
        result = [
            SymbolInfo(name=name, address=address)
            for name, address in symbols.items()
            if address is not None and name and not name.startswith("$")
        ]
        return sorted(result, key=lambda item: (item.address, item.name))

    def contains_address(self, address: int, *, size: int = 1) -> bool:
        try:
            self.read_bytes(address, size)
        except (AddressNotMappedError, ValueError):
            return False
        return True

    def external_functions(self) -> list[ExternalFunction]:
        plt_symbols = _normalize_symbol_table(getattr(self.elf, "plt", {}))
        got_symbols = _normalize_symbol_table(getattr(self.elf, "got", {}))
        all_symbols = _normalize_symbol_table(getattr(self.elf, "symbols", {}))
        undefined_symbols = _undefined_external_symbols(self.elf)

        names: set[str] = (set(plt_symbols.keys()) | set(got_symbols.keys())) & set(
            all_symbols.keys()
        )
        names.update(name for name in all_symbols.keys() if "@" in name)
        names.update(undefined_symbols)

        result: list[ExternalFunction] = []
        for name in sorted(names):
            result.append(
                ExternalFunction(
                    name=name,
                    plt_address=plt_symbols.get(name),
                    got_address=got_symbols.get(name),
                    symbol_address=all_symbols.get(name),
                )
            )

        return result

    def ordered_unresolved_external_functions(self) -> tuple[ExternalFunction, ...]:
        plt_symbols = _normalize_symbol_table(getattr(self.elf, "plt", {}))
        got_symbols = _normalize_symbol_table(getattr(self.elf, "got", {}))
        all_symbols = _normalize_symbol_table(getattr(self.elf, "symbols", {}))

        ordered: list[ExternalFunction] = []
        for name in _ordered_undefined_external_symbols(self.elf):
            external = ExternalFunction(
                name=name,
                plt_address=plt_symbols.get(name),
                got_address=got_symbols.get(name),
                symbol_address=all_symbols.get(name),
            )
            if (
                external.plt_address is not None
                or external.got_address is not None
                or external.symbol_address is not None
            ):
                continue
            ordered.append(external)
        return tuple(ordered)

    def external_function_by_address(self, address: int) -> ExternalFunction | None:
        for external in self.external_functions():
            addresses = (
                external.plt_address,
                external.got_address,
                external.symbol_address,
            )
            if address in addresses:
                return external
        return None
