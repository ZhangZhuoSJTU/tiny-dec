# Stage Contract: `post_00_loader`

## Summary

- Stage name: `post_00_loader`
- Owner directory: `tiny_dec/loader/`
- Immediate predecessor: ELF file path input
- Immediate successor: `post_01_decode`

## Purpose

Load ELF metadata into a stable in-memory view that downstream stages can query by
virtual address. This stage also resolves a best-effort `main` entry address and
provides deterministic loader snapshots for tests and CLI inspection.

## Inputs

- `binary_path: str | Path` to a Linux ELF.
- Loader backend: `pwn.ELF`.
- Optional policy flags:
  - `checksec` forwarded to `pwn.ELF`.
  - `enforce_rv32i` to enforce RV32I-compatible architecture.

Required assumptions:

- Binary is readable from disk.
- For strict RV32I mode, ELF is little-endian 32-bit RISC-V.

## Outputs

- `ProgramView` with:
  - architecture metadata (`arch`, `bits`, `endian`, `entrypoint`)
  - section layout list
  - symbol/external lookups
  - byte readers by virtual address
  - best-effort `main` resolution as `MainResolution`
- Function-style APIs:
  - `identify_main(binary_path, ...) -> MainResolution`
  - `read_bytes(binary_path, address, size, ...) -> bytes`

## Non-goals

- Full call-graph recovery.
- DWARF/debug-symbol parsing.
- Dynamic loader emulation.
- Guaranteed `main` recovery for all startup stubs/toolchains.

## Algorithm Sketch

1. Open ELF through `pwn.ELF`.
2. Validate architecture policy (`_is_rv32i`) when `enforce_rv32i=True`.
3. For `find_main()`:
   - Prefer `symbols["main"]` when non-zero integer.
   - Else disassemble startup bytes from `entrypoint`.
   - Detect control transfer to `__libc_start_main` via symbol names or numeric targets.
   - Reverse-scan nearby setup lines for `a0` value construction (`li/la/lui/auipc+addi`)
     and return the resolved candidate address.
   - If unresolved, return `MainResolution(address=None, source="unresolved", ...)`.
4. For `read_bytes(address, size)`:
   - Reject negative size.
   - Return empty bytes for size `0`.
   - Read exact count from ELF mapping.
   - Raise `AddressNotMappedError` when read fails or short-reads.

## Data Structures

- `SectionLayout` (`tiny_dec/loader/models.py`)
  - fields: `name`, `virtual_address`, `size`
  - invariant: `end_address == virtual_address + size`
  - pretty-print unit: `name vaddr size end`
- `ExternalFunction` (`tiny_dec/loader/models.py`)
  - fields: `name`, `plt_address`, `got_address`, `symbol_address`
  - invariant: addresses are `int | None`, sorted deterministically by `name`
- `MainResolution` (`tiny_dec/loader/models.py`)
  - fields: `address`, `source`, `entrypoint`
  - invariant: `source` explains why `address` is known or unresolved

## Edge Cases

- Symbol table exists but `main == 0` or non-integer.
- Disassembly unavailable or malformed.
- Startup flow without `__libc_start_main`.
- `a0` setup occurs outside reverse scan window before startup call.
- Reads crossing unmapped regions.
- Zero-length byte reads.

## Pretty-Print Contract

Loader snapshot text is line-oriented and deterministic:

1. `binary: <path>`
2. `arch: <arch> (<bits>-bit, <endian>-endian)`
3. `entrypoint: 0x...`
4. `main: 0x...` or `main: <unresolved>`
5. `main_source: <source>`
6. `sections:` block sorted by requested order
7. optional `external_functions:` block sorted by function name

This is the canonical debugging surface for stage-0 fixtures.

## End-to-End Harness Exposure

The stage e2e harness must run all fixture ELFs and assert deterministic loader
snapshot output containing entrypoint, main resolution, and section summaries.

## Validation Commands

- stage tests:
  - `poetry run pytest -q tests/posts/post_00_loader`
- e2e harness:
  - `poetry run pytest -q tests/posts/post_00_loader/test_loader_e2e_harness.py`
- ruff:
  - `poetry run ruff check tiny_dec/loader tests/posts/post_00_loader`
- mypy:
  - `poetry run mypy tiny_dec/loader tests/posts/post_00_loader`

## Open Questions

- Keep current disassembly-token heuristics as-is or move to decoded instruction
  modeling when post-01 and post-02 mature.
