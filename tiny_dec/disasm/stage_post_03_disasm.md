## Stage Contract: `post_03_disasm`

## Summary

- Stage name: `post_03_disasm`
- Owner directory: `tiny_dec/disasm/`
- Immediate predecessor: `post_02_lift_pcode`
- Immediate successor: `post_04_ir_containers`

## Purpose

Build deterministic p-code basic blocks and an intra-procedural CFG for one
function entry point.

This stage is the repository's first round of recursive disassembly. Starting
from one function entry address, it repeatedly:

1. decodes RV32I instructions
2. lifts each decoded instruction to semantic p-code
3. groups lifted instructions into basic blocks
4. records direct CFG edges between reachable blocks
5. records direct call targets without recursing into callees

## Inputs

- `ProgramView` from `tiny_dec.loader`
  - must provide `read_u32(address)` over mapped executable bytes
- `entry: int`
  - the function entry address to analyze, typically resolved from `main`

Assumptions:

- Reachable instructions are RV32I words accepted by `post_01_decode`.
- Each reachable instruction can be lifted by `post_02_lift_pcode`.
- The current stage is intra-procedural only.
- Indirect jump and indirect call target recovery is deferred to later stages.

## Outputs

- `DisasmFunction`
  - `entry`: analyzed function entry address
  - `blocks`: deterministic mapping of block start to `BasicBlock`
  - `discovery_order`: stable recursive-disassembly visitation order

Output invariants:

- Every block is non-empty.
- Every block starts at the address of its first decoded instruction.
- Successor edges are direct and deterministic.
- All p-code inside a block is produced by the stage-2 lifter without mutation.
- Direct calls stay inside the current block and are recorded as metadata.

## Non-goals

- Resolving indirect jump targets.
- Interprocedural traversal into direct or indirect callees.
- SSA, dominators, dataflow, or prototype inference.
- Normalizing or simplifying p-code across instruction boundaries.

## Algorithm Sketch

1. Seed a recursive-disassembly worklist with the function entry address.
2. When a new block start is discovered, decode and lift instructions linearly.
3. Stop the current block when:
   - a conditional branch is reached
   - a direct jump is reached
   - a return is reached
   - an indirect jump is reached
   - a trap-like stop is reached
   - the next address is already known to start another block
4. For conditional branches, record both taken and fallthrough successors.
5. For direct jumps, record the target successor only.
6. For call-like instructions, keep decoding linearly in the same block and only
   record call metadata; do not recurse into the callee.
7. Treat unresolved indirect jumps as terminating edges with no successor.
8. Emit the final disassembly in deterministic discovery order.

## Data structures

- `BlockInstruction`
  - owner: `tiny_dec/disasm/models.py`
  - fields: `instruction`, `pcode_ops`
  - invariant: p-code ops correspond exactly to the decoded instruction
  - pretty: one decoded instruction line followed by indented p-code lines
- `BlockEdge`
  - owner: `tiny_dec/disasm/models.py`
  - fields: `kind`, `target`
  - invariant: `target` is a direct successor start address
  - pretty: `<kind>:0xADDR`
- `BasicBlock`
  - owner: `tiny_dec/disasm/models.py`
  - fields: `start`, `instructions`, `successors`, `terminator`,
    `call_targets`, `has_indirect_call`
  - invariants:
    - `instructions` is non-empty
    - `start` matches the first instruction address
    - `successors` are deterministic and deduplicated
  - pretty: block header line plus rendered instructions
- `DisasmFunction`
  - owner: `tiny_dec/disasm/models.py`
  - fields: `entry`, `blocks`, `discovery_order`
  - invariant: `entry` is present in `blocks` when the disassembly is non-empty
  - pretty: function header followed by blocks in discovery order

## Edge cases

- Direct calls inside a function body remain inline and do not spawn callee
  disassembly.
- `jalr x0, 0(x1)` is lifted as a return terminator.
- Other `jalr x0, ...` forms are treated as unresolved indirect jumps.
- `jalr` with link-register writes is lifted as an indirect call and kept inline.
- Self-targeting direct calls must not create infinite recursive traversal.
- Reachable decode or lift failures should fail clearly instead of silently
  truncating the disassembly.

## Pretty-print Contract

- Function header:
  - `entry: 0xADDR`
  - `order: 0xADDR, ...`
- One block per section:
  - `block 0xADDR term=<kind> succ=[kind:0xADDR, ...]`
  - optional `calls=[0xADDR, ...]`
  - optional `indirect_call=yes`
- Each instruction is rendered with the stage-1 pretty line.
- Each p-code op is rendered on its own indented line.

## End-to-End Harness Exposure

The stage e2e harness iterates all fixture binaries, resolves `main`, builds a
recursive disassembly from that address, and renders the deterministic snapshot
for each binary.

The snapshot should make it obvious which blocks were discovered, how they
connect, and where traversal stops at returns or unresolved indirect jumps.

## Validation Commands

- stage tests:
  - `poetry run pytest -q tests/posts/post_03_disasm`
- e2e harness:
  - `poetry run pytest -q tests/posts/post_03_disasm/test_disasm_e2e_harness.py`
- ruff:
  - `poetry run ruff check tiny_dec/disasm tiny_dec/cli.py tiny_dec/pipeline tests/posts/post_03_disasm`
- mypy:
  - `poetry run mypy tiny_dec/disasm tiny_dec/cli.py tiny_dec/pipeline tests/posts/post_03_disasm`
