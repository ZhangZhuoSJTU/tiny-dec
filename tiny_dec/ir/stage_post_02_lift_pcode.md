# Stage Contract: `post_02_lift_pcode`

## Summary

- Stage name: `post_02_lift_pcode`
- Owner directory: `tiny_dec/ir/`
- Immediate predecessor: `post_01_decode`
- Immediate successor: `post_03_disasm`

## Purpose

Lift decoded RV32I instructions into deterministic low-level pcode operations.

This stage produces direct instruction semantics only. It does not perform SSA
renaming or dataflow normalization.

## Inputs

- `Instruction` / `RV32IInstruction` from `tiny_dec.decode`:
  - `address`, `word`, `mnemonic`
  - decoded operand fields (`rd`, `rs1`, `rs2`, `imm`, `target`)

Assumptions:

- Input instructions are already validated by the RV32I decoder.
- Lifter only needs RV32I mnemonics produced by stage-1 decode.

## Outputs

- `list[PcodeOp]` representing low-level pcode for exactly one instruction.
- Optional pretty-print snapshot lines for deterministic debugging and e2e tests.

Output invariants:

- Deterministic op order.
- Deterministic temporary varnode allocation within one instruction lift.
- Varnode sizes are explicit.

## Non-goals

- SSA form or phi insertion (handled in `post_07_ssa`).
- Global control-flow graph construction (handled in `post_03_disasm`).
- Aggressive simplification/canonicalization (handled in later analysis posts).

## Algorithm Sketch

1. Normalize instruction mnemonic text.
2. Build register/constant varnodes for operands.
3. Dispatch mnemonic to an RV32I lift routine.
4. Emit low-level pcode ops in execution order.
5. Allocate deterministic `unique` temporaries as needed.
6. Return emitted op list; never mutate upstream instruction objects.

## Data Structures

- `PcodeSpace` (`tiny_dec/ir/pcode.py`)
  - enumerates varnode spaces: `register`, `const`, `ram`, `unique`
- `PcodeOpcode` (`tiny_dec/ir/pcode.py`)
  - enumerates low-level opcodes used by this stage
- `Varnode` (`tiny_dec/ir/pcode.py`)
  - fields: `space`, `offset`, `size`
  - pretty: `space[offset:size]`
- `PcodeOp` (`tiny_dec/ir/pcode.py`)
  - fields: `opcode`, `inputs`, `output`
  - pretty: `OP out <- in0, in1` (or `OP in0, in1` when no output)

## Edge Cases

- `x0` reads are lifted as `const 0`.
- Side-effect-free writes to `x0` are dropped during lift.
- Side-effecting instructions targeting `x0` still emit pcode for effects.
- Signed vs unsigned comparisons and load-extension behavior.
- `jalr` target alignment mask (`& ~1`) in lifted semantics.
- Decoder-emitted illegal instructions map to explicit trap-like pcode.

## Pretty-Print Contract

- Varnode text is lowercase and fully explicit.
- Pcode op text is one line per op.
- Per-instruction dump header format:
  - `0xADDR: 0xWORD  <mnemonic ...>`
  - followed by indented pcode op lines in lift order.

## End-to-End Harness Exposure

Stage e2e harness iterates all fixture binaries, decodes a small linear window
from `main` (entrypoint fallback), lifts each decoded instruction to pcode, and
renders deterministic snapshots.

## CLI Exposure

Pcode stage inspection is exposed through:

- `tiny-dec decompile <binary> --stage pcode [--func <selector>]`
  - prints a deterministic lifted pcode window rooted at the selected function
  - returns non-zero on unresolved function selectors

## Validation Commands

- stage tests:
  - `poetry run pytest -q tests/posts/post_02_lift_pcode`
- e2e harness:
  - `poetry run pytest -q tests/posts/post_02_lift_pcode/test_pcode_e2e_harness.py`
- ruff:
  - `poetry run ruff check tiny_dec/ir tiny_dec/cli.py tests/posts/post_02_lift_pcode`
- mypy:
  - `poetry run mypy tiny_dec/ir tiny_dec/cli.py tests/posts/post_02_lift_pcode`

## Open Questions

- Whether to later model pcode op sequence numbers explicitly once CFG assembly
  starts in `post_03_disasm`.
