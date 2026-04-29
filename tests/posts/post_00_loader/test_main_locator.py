from __future__ import annotations

from pwn import ELF

from tiny_dec.loader.main_locator import MainLocator


class FakeELF(ELF):
    def __init__(
        self,
        disassembly: str = "",
        *,
        symbols: dict[str, int | object] | object | None = None,
        plt: dict[str, int | object] | object | None = None,
        got: dict[str, int | object] | object | None = None,
        disasm_raises: bool = False,
    ) -> None:
        self._disassembly = disassembly
        self._disasm_raises = disasm_raises
        self.symbols = {} if symbols is None else symbols
        self.plt = {} if plt is None else plt
        self.got = {} if got is None else got

    def disasm(self, address: int, n_bytes: int) -> str:
        if self._disasm_raises:
            raise RuntimeError("disasm failed")
        return self._disassembly


def test_resolve_prefers_symbol_table_main_when_present() -> None:
    elf = FakeELF(
        disassembly="\n".join(
            [
                "000100f0: auipc a0, 0x0",
                "000100f4: addi a0, a0, 0x40 # 0x10130",
                "000100f8: jal ra, 0x10020",
            ]
        ),
        symbols={"main": 0x20000, "__libc_start_main@GLIBC_2.34": 0x0},
        plt={"__libc_start_main": 0x10020},
    )

    resolution = MainLocator(elf, 0x100F0).resolve()

    assert resolution.address == 0x20000
    assert resolution.source == "symbol_table"
    assert resolution.entrypoint == 0x100F0


def test_resolve_uses_entrypoint_when_main_symbol_missing() -> None:
    elf = FakeELF(
        disassembly="\n".join(
            [
                "000100f0: auipc a0, 0x0",
                "000100f4: addi a0, a0, 0x38 # 0x10128",
                "000100f8: jal ra, 0x10020",
            ]
        ),
        symbols={"__libc_start_main@GLIBC_2.34": 0x0},
        plt={"__libc_start_main": 0x10020},
    )

    resolution = MainLocator(elf, 0x100F0).resolve()

    assert resolution.address == 0x10128
    assert resolution.source == "entrypoint_libc_start_main"


def test_resolve_unresolved_when_no_symbol_or_entrypoint_pattern() -> None:
    elf = FakeELF(disassembly="00010000: nop")

    resolution = MainLocator(elf, 0x10000).resolve()

    assert resolution.address is None
    assert resolution.source == "unresolved"


def test_resolve_unresolved_when_disasm_raises_and_no_symbol_main() -> None:
    elf = FakeELF(symbols={"puts": 0x1234}, disasm_raises=True)

    resolution = MainLocator(elf, 0x10000).resolve()

    assert resolution.address is None
    assert resolution.source == "unresolved"


def test_resolve_from_symbol_call_text_when_targets_not_available() -> None:
    elf = FakeELF(
        disassembly="\n".join(
            [
                "00011000: li a0, 0x23000",
                "00011004: call __libc_start_main",
            ]
        )
    )

    resolution = MainLocator(elf, 0x11000).resolve()

    assert resolution.address == 0x23000
    assert resolution.source == "entrypoint_libc_start_main"


def test_resolve_does_not_match_non_control_transfer_lines() -> None:
    elf = FakeELF(
        disassembly="\n".join(
            [
                "00012000: li a0, 0x33000",
                "00012004: addi t0, t1, __libc_start_main",
            ]
        )
    )

    resolution = MainLocator(elf, 0x12000).resolve()

    assert resolution.address is None
    assert resolution.source == "unresolved"


def test_extract_main_from_auipc_addi_without_comment() -> None:
    elf = FakeELF(
        disassembly="\n".join(
            [
                "00020000: auipc a0, 0x1",
                "00020004: addi a0, a0, 0x24",
                "00020008: jal ra, 0x10020",
            ]
        ),
        plt={"__libc_start_main": 0x10020},
    )

    resolution = MainLocator(elf, 0x20000).resolve()

    assert resolution.address == 0x21024
    assert resolution.source == "entrypoint_libc_start_main"


def test_extract_main_from_lui_addi_sequence() -> None:
    elf = FakeELF(
        disassembly="\n".join(
            [
                "00030000: lui a0, 0x12",
                "00030004: addi a0, a0, 0x34",
                "00030008: jal ra, 0x10020",
            ]
        ),
        plt={"__libc_start_main": 0x10020},
    )

    resolution = MainLocator(elf, 0x30000).resolve()

    assert resolution.address == 0x12034
    assert resolution.source == "entrypoint_libc_start_main"


def test_extract_main_from_direct_li_or_la() -> None:
    elf = FakeELF(
        disassembly="\n".join(
            [
                "00040000: la a0, 0x44044",
                "00040004: jal ra, 0x10020",
            ]
        ),
        plt={"__libc_start_main": 0x10020},
    )

    resolution = MainLocator(elf, 0x40000).resolve()

    assert resolution.address == 0x44044
    assert resolution.source == "entrypoint_libc_start_main"


def test_ignores_a0_setup_outside_reverse_scan_window() -> None:
    far_setup = [f"000500{index:02x}: nop" for index in range(21)]
    disassembly_lines = (
        ["00050000: li a0, 0x55055"] + far_setup + ["00050080: jal ra, 0x10020"]
    )
    elf = FakeELF(
        disassembly="\n".join(disassembly_lines),
        plt={"__libc_start_main": 0x10020},
    )

    resolution = MainLocator(elf, 0x50000).resolve()

    assert resolution.address is None
    assert resolution.source == "unresolved"


def test_main_zero_or_non_dict_symbols_do_not_short_circuit() -> None:
    elf_zero = FakeELF(
        disassembly="\n".join(
            [
                "00060000: li a0, 0x66066",
                "00060004: jal ra, 0x10020",
            ]
        ),
        symbols={"main": 0},
        plt={"__libc_start_main": 0x10020},
    )
    elf_nondict = FakeELF(
        disassembly="\n".join(
            [
                "00070000: li a0, 0x77077",
                "00070004: jal ra, 0x10020",
            ]
        ),
        symbols=[],
        plt={"__libc_start_main": 0x10020},
    )

    resolution_zero = MainLocator(elf_zero, 0x60000).resolve()
    resolution_nondict = MainLocator(elf_nondict, 0x70000).resolve()

    assert resolution_zero.address == 0x66066
    assert resolution_zero.source == "entrypoint_libc_start_main"
    assert resolution_nondict.address == 0x77077
    assert resolution_nondict.source == "entrypoint_libc_start_main"
