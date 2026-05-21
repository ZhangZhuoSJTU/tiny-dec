# Stage Contract: `post_01_decode`

## Summary

- Stage name: `post_01_decode`
- Owner directory: `tiny_dec/decode/`
- Immediate predecessor: `post_00_loader`
- Immediate successor: `post_02_lift_pcode`

## Purpose

Decode raw 32-bit instruction words into deterministic RV32I instruction
objects that downstream stages can consume without re-parsing bitfields.

This stage is RV32I-only and decodes 32-bit instruction words.

## Inputs

- `word: int` (fetched 32-bit little-endian instruction word)
- `address: int` (virtual address / program counter of the instruction)

Assumptions:

- `(word & 0x3) == 0x3` for RV32I instruction length.
- Caller provides instruction bytes from a valid mapped executable region.

## Outputs

- `RV32IInstruction` with:
  - stable `mnemonic`, `format`, and `size`
  - decoded register operands (`rd`, `rs1`, `rs2`)
  - decoded immediate (`imm`) and control-flow `target` when applicable
  - raw selector fields (`opcode`, `funct3`, `funct7`) for debugging

## Non-goals

- RISC-V extensions outside RV32I baseline.
- Control-flow graph construction or recursive traversal.

## Algorithm Sketch

1. Mask input to 32-bit.
2. Validate low bits for 32-bit instruction form.
3. Extract common fields (`opcode`, `rd`, `rs1`, `rs2`, `funct3`, `funct7`).
4. Reconstruct all immediate families (`I`, `S`, `B`, `U`, `J`) with sign
   extension where required.
5. Dispatch by opcode + selector tables:
   - `LUI/AUIPC/JAL/JALR`
   - branches, loads, stores
   - OP-IMM and OP register ALU
   - `FENCE`, `ECALL`, `EBREAK`
6. Construct `RV32IInstruction` with deterministic formatting fields.
7. Emit `illegal` RV32I instructions for unsupported/reserved selectors.
8. Raise `DecodeError` when a non-RV32I-length encoding is passed to RV32I
   decode entrypoints.

## Data Structures

- `RV32IInstruction` (`tiny_dec/decode/decoder.py`)
  - fields:
    - `address`, `word`, `mnemonic`, `format`, `size`
    - `opcode`, `funct3`, `funct7`
    - `rd`, `rs1`, `rs2`
    - `imm`, `target`
  - invariants:
    - `size == 4`
    - `opcode` always present for decoded RV32I words
    - `target` only set for PC-relative control transfer with concrete target
  - pretty-print format:
    - instruction text: canonical `mnemonic operands` string
    - snapshot line: `0xADDR: 0xWORD  <text>`

## Edge Cases

- Immediate sign-extension boundaries (e.g., `-2048`, `+2047`).
- Shift-immediate selector constraints (`slli/srli/srai` high bits).
- Reserved `system` encodings beyond `ecall`/`ebreak`.
- Unsupported opcode selector combinations.
- Words that do not encode a 32-bit RV32I instruction length.

## Pretty-Print Contract

Per-instruction output is deterministic and stable:

- no register aliases (`x0..x31` only)
- lowercase mnemonic
- fixed address/word prefix in decode snapshots
- no nondeterministic ordering

## End-to-End Harness Exposure

The stage e2e harness iterates all fixture binaries, chooses
`main` (or entrypoint fallback), decodes a bounded linear window of RV32I
words, and renders deterministic text snapshots.

## CLI Exposure

Decode stage inspection is exposed through:

- `tiny-dec decompile <binary> --stage decode [--func <selector>]`
  - resolves a function start address (`main`, symbol, hex, decimal)
  - decodes one deterministic linear window with stable line formatting
  - returns non-zero when the function selector cannot be resolved

## Validation Commands

- stage tests:
  - `poetry run pytest -q tests/posts/post_01_decode`
- cli tests:
  - `poetry run pytest -q tests/posts/post_01_decode/test_cli_decode.py`
- e2e harness:
  - `poetry run pytest -q tests/posts/post_01_decode/test_decode_e2e_harness.py`
- ruff:
  - `poetry run ruff check tiny_dec/decode tests/posts/post_01_decode`
- mypy:
  - `poetry run mypy tiny_dec/decode tests/posts/post_01_decode`

## Open Questions

- Whether to represent `fence` operand masks as structured fields now or
  postpone until a later memory-ordering stage needs them.
