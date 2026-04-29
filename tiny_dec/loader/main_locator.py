"""Startup-sequence heuristics for resolving `main` from ELF entrypoint code."""

from __future__ import annotations

import re
from pwn import ELF

from tiny_dec.loader.models import MainResolution

_LIBC_START_MAIN_TOKEN = "__libc_start_main"
_LINE_ADDRESS_RE = re.compile(r"^\s*([0-9a-fA-F]+):")
_HEX_LITERAL_RE = re.compile(r"0x[0-9a-fA-F]+")
_COMMENT_HEX_RE = re.compile(r"#\s*(0x[0-9a-fA-F]+)")
_CONTROL_TRANSFER_MARKERS = ("jal", "jalr", "call", "bl", "tail")
_A0_REGISTER_MARKERS = ("a0", "x10")
_A0_ASSIGNMENT_MARKERS = ("li", "la", "auipc", "addi", "lui")


class MainLocator:
    """Best-effort main() resolver from entrypoint startup code."""

    def __init__(self, elf: ELF, entrypoint: int) -> None:
        self._elf = elf
        self._entrypoint = entrypoint

    def resolve(self, *, scan_size: int = 512) -> MainResolution:
        # Prefer exact symbol table data first; startup heuristics are fallback-only.
        address = self._resolve_from_symbol_table()
        source = "symbol_table"

        if address is None:
            address = self._resolve_from_entrypoint(scan_size=scan_size)
            source = (
                "entrypoint_libc_start_main" if address is not None else "unresolved"
            )

        return MainResolution(
            address=address,
            source=source,
            entrypoint=self._entrypoint,
        )

    def _resolve_from_entrypoint(self, *, scan_size: int) -> int | None:
        try:
            disassembly = self._elf.disasm(self._entrypoint, scan_size)
        except Exception:
            return None

        libc_targets = self._find_libc_start_main_targets()
        lines = [line for line in disassembly.splitlines() if line.strip()]
        for index, line in enumerate(lines):
            if not self._is_libc_start_main_call(line, libc_targets=libc_targets):
                continue
            main_address = self._extract_main_address(lines, index)
            if main_address is not None:
                return main_address

        return None

    def _is_libc_start_main_call(
        self,
        line: str,
        *,
        libc_targets: set[int],
    ) -> bool:
        lower = line.lower()
        if not any(marker in lower for marker in _CONTROL_TRANSFER_MARKERS):
            return False

        if libc_targets and any(
            value in libc_targets for value in self._extract_numeric_literals(line)
        ):
            return True

        tokens = {_LIBC_START_MAIN_TOKEN, "libc_start_main"}
        return any(token.lower() in lower for token in tokens)

    def _extract_main_address(self, lines: list[str], call_index: int) -> int | None:
        # Walk backward from the startup call and recover the closest `a0` setup.
        # This approximates the first argument passed to __libc_start_main.
        # 20 instructions is enough for gcc/clang _start stubs; atypical or
        # obfuscated startup code may place the setup outside this window.
        window_start = max(0, call_index - 20)
        window = lines[window_start:call_index]
        pending_addi: int | None = None

        for line in reversed(window):
            comment_address = self._extract_comment_address(line)
            if comment_address is not None and self._looks_like_a0_setup(line):
                return comment_address

            addi = self._parse_addi_a0(line)
            if addi is not None:
                pending_addi = addi
                continue

            auipc = self._parse_auipc_a0(line)
            if auipc is not None:
                line_address = self._extract_line_address(line)
                if line_address is None:
                    continue
                base = line_address + (auipc << 12)
                if pending_addi is not None:
                    return base + pending_addi
                return base

            lui = self._parse_lui_a0(line)
            if lui is not None:
                base = lui << 12
                if pending_addi is not None:
                    return base + pending_addi
                return base

            immediate = self._parse_direct_a0_immediate(line)
            if immediate is not None:
                return immediate

        return None

    def _extract_line_address(self, line: str) -> int | None:
        match = _LINE_ADDRESS_RE.match(line)
        if not match:
            return None
        return int(match.group(1), 16)

    def _extract_comment_address(self, line: str) -> int | None:
        match = _COMMENT_HEX_RE.search(line)
        if not match:
            return None
        return int(match.group(1), 16)

    def _extract_numeric_literals(self, line: str) -> list[int]:
        values: list[int] = []
        for token in re.findall(r"0x[0-9a-fA-F]+|[0-9]+|[0-9a-fA-F]{5,}", line):
            try:
                if token.startswith("0x"):
                    values.append(int(token, 16))
                elif token.isdigit():
                    values.append(int(token, 10))
                else:
                    values.append(int(token, 16))
            except ValueError:
                continue
        return values

    def _parse_immediate(self, token: str) -> int | None:
        cleaned = token.strip().rstrip(",)")
        if not cleaned:
            return None
        try:
            if cleaned.startswith("-0x"):
                return -int(cleaned[3:], 16)
            if cleaned.startswith("0x"):
                return int(cleaned, 16)
            if re.fullmatch(r"-?\d+", cleaned):
                return int(cleaned, 10)
        except ValueError:
            return None
        return None

    def _parse_addi_a0(self, line: str) -> int | None:
        lower = line.lower()
        match = re.search(
            r"\baddi\s+(a0|x10)\s*,\s*(a0|x10)\s*,\s*([^\s#]+)",
            lower,
        )
        if not match:
            return None
        return self._parse_immediate(match.group(3))

    def _parse_auipc_a0(self, line: str) -> int | None:
        lower = line.lower()
        match = re.search(r"\bauipc\s+(a0|x10)\s*,\s*([^\s#]+)", lower)
        if not match:
            return None
        return self._parse_immediate(match.group(2))

    def _parse_lui_a0(self, line: str) -> int | None:
        lower = line.lower()
        match = re.search(r"\blui\s+(a0|x10)\s*,\s*([^\s#]+)", lower)
        if not match:
            return None
        return self._parse_immediate(match.group(2))

    def _parse_direct_a0_immediate(self, line: str) -> int | None:
        lower = line.lower()
        for mnemonic in ("li", "la"):
            match = re.search(rf"\b{mnemonic}\s+(a0|x10)\s*,\s*([^\s#]+)", lower)
            if match:
                value = self._parse_immediate(match.group(2))
                if value is not None:
                    return value
        return None

    def _looks_like_a0_setup(self, line: str) -> bool:
        lower = line.lower()
        if "0x" not in lower:
            return False

        # RV32I ABI: argument 0 is carried in a0/x10.
        return any(marker in lower for marker in _A0_REGISTER_MARKERS) and any(
            marker in lower for marker in _A0_ASSIGNMENT_MARKERS
        )

    def _find_libc_start_main_targets(self) -> set[int]:
        symbol_sources = []
        for source_name in ("symbols", "plt", "got"):
            source = getattr(self._elf, source_name, {})
            if isinstance(source, dict):
                symbol_sources.append(source.items())

        targets: set[int] = set()
        for source in symbol_sources:
            for name, value in source:
                lowered = str(name).lower()
                if (
                    _LIBC_START_MAIN_TOKEN not in lowered
                    and "libc_start_main" not in lowered
                ):
                    continue
                if isinstance(value, int) and value != 0:
                    targets.add(value)
        return targets

    def _resolve_from_symbol_table(self) -> int | None:
        symbols = getattr(self._elf, "symbols", {})
        if not isinstance(symbols, dict):
            return None

        value = symbols.get("main")
        if isinstance(value, int) and value != 0:
            return value
        return None
