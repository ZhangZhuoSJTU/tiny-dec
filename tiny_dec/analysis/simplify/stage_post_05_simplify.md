# Stage Contract: `post_05_simplify`

## Summary

- Stage name: `post_05_simplify`
- Owner directory: `tiny_dec/analysis/simplify/`
- Immediate predecessor: `post_04_ir_containers`
- Immediate successor: `post_06_dataflow`

## Purpose

Canonicalize the raw stage-4 IR into a more analysis-friendly function and
program form without changing control flow or call discovery.

This stage exists to remove mechanical p-code noise that comes directly from
instruction lifting, such as:

- constant-only arithmetic that can already be folded
- identity operations that can already collapse to `COPY`
- `op temp <- ...` followed by `COPY out <- temp` when the temp is single-use
- sparse per-instruction `unique` numbering after earlier rewrites

The output is still low-level and block-structured. It is not SSA and it does
not perform inter-instruction propagation.

## Inputs

- `ProgramIR` from `tiny_dec.ir.program_ir`
- `FunctionIR` from `tiny_dec.ir.function_ir`
- stage-4 block/instruction order, callsites, and call graph metadata

Assumptions:

- stage-4 output is already deterministic
- block topology, callsites, and direct call graph are already correct enough to
  preserve as-is
- stage-2 p-code op semantics are the source of truth for local rewrites

## Outputs

- `CanonicalInstruction`
  - one decoded instruction
  - one deterministic tuple of locally simplified p-code ops
- `CanonicalBlock`
  - preserved block topology and metadata with canonicalized instructions
- `CanonicalFunctionIR`
  - preserved function-level metadata with canonicalized blocks
  - preserved deterministic instruction index
- `CanonicalProgramIR`
  - preserved program-level metadata with canonicalized functions

Output invariants:

- instruction addresses and block starts are preserved exactly
- block discovery order and successor edges are preserved exactly
- callsites, return blocks, direct callees, externals, and call-graph edges are
  preserved exactly
- canonicalization only rewrites p-code within one instruction at a time
- remaining `unique` temporaries are renumbered densely in first-use order per
  instruction

## Non-goals

- inter-instruction copy propagation
- CFG rewriting, block merging, or dead-block elimination
- alias analysis, dataflow, or SSA
- stack, memory, or type recovery
- call graph refinement beyond preserving stage-4 results

## Algorithm sketch

### `canonicalize_instruction`

1. Start from one stage-3 `BlockInstruction`.
2. Copy the instruction metadata unchanged.
3. Repeatedly apply local rewrite rules to that instruction's p-code tuple until
   it reaches a fixpoint:
   - fold pure operations with constant inputs into `COPY const`
   - collapse identity operations such as add-zero, or-zero, xor-zero,
     shift-zero, and and-all-ones
   - rewrite `producer temp` + `COPY out <- temp` into `producer out` when:
     - the temp is `unique`
     - the producer is pure
     - the temp has exactly one use
     - the producer output size matches the copy destination size
4. Renumber the remaining `unique` varnodes densely in first-appearance order.
5. Materialize `CanonicalInstruction`.

Unsupported or non-matching patterns are left unchanged.

### `canonicalize_function_ir`

1. Iterate blocks in stage-4 discovery order.
2. Canonicalize each lifted instruction independently.
3. Rebuild `CanonicalBlock` values while preserving:
   - `start`
   - `successors`
   - `terminator`
   - `call_targets`
   - `has_indirect_call`
4. Rebuild `CanonicalFunctionIR` while preserving:
   - `entry`
   - `name`
   - `discovery_order`
   - `callsites`
   - `return_blocks`
   - `direct_callees`

### `canonicalize_program_ir`

1. Iterate functions in stage-4 discovery order.
2. Canonicalize each function independently.
3. Rebuild `CanonicalProgramIR` while preserving:
   - `root_entry`
   - `discovery_order`
   - `externals`
   - `call_graph`
   - `pending_entries`
   - `invalidated_entries`

### loader-backed builders

- `build_canonical_function_ir(view, entry)` first builds `FunctionIR`, then
  canonicalizes it
- `build_canonical_program_ir(view, root_entry)` first builds `ProgramIR`, then
  canonicalizes it

Failure and bailout rules:

- malformed stage-4 objects should fail through type invariants instead of being
  silently accepted
- unsupported p-code opcodes are preserved unchanged
- no rewrite may change call, branch, or return targets

## Data structures

- `CanonicalInstruction`
  - owner: `tiny_dec/analysis/simplify/models.py`
  - fields:
    - `instruction`
    - `ops`
  - invariants:
    - rendered instruction address matches `instruction.address`
    - `ops` ordering is deterministic
    - surviving `unique` varnodes use dense offsets per instruction
  - pretty:
    - instruction line followed by indented canonical p-code lines
- `CanonicalBlock`
  - owner: `tiny_dec/analysis/simplify/models.py`
  - fields:
    - `start`
    - `instructions`
    - `successors`
    - `terminator`
    - `call_targets`
    - `has_indirect_call`
  - invariants:
    - `start` matches the first instruction address
    - successor and call-target ordering stays deterministic
  - pretty:
    - same block header shape as stage 3 and 4, but rendered with canonical
      instructions
- `CanonicalFunctionIR`
  - owner: `tiny_dec/analysis/simplify/models.py`
  - fields:
    - `entry`
    - `name`
    - `blocks`
    - `discovery_order`
    - `instruction_index`
    - `callsites`
    - `return_blocks`
    - `direct_callees`
  - invariants:
    - metadata mirrors the upstream `FunctionIR`
    - block order references known blocks only
  - pretty:
    - function summary
    - `callsites:` section
    - `blocks:` section
- `CanonicalProgramIR`
  - owner: `tiny_dec/analysis/simplify/models.py`
  - fields:
    - `root_entry`
    - `functions`
    - `discovery_order`
    - `externals`
    - `call_graph`
    - `pending_entries`
    - `invalidated_entries`
  - invariants:
    - metadata mirrors the upstream `ProgramIR`
    - discovery order references known functions only
  - pretty:
    - program header
    - queue state
    - external list
    - call graph
    - nested canonical functions

## Edge cases

- instructions whose p-code is already canonical and should remain unchanged
- instructions with empty p-code tuples
- constant folding that changes sign or boolean width
- single-use temp forwarding that must not cross size mismatches
- call, branch, or return operations that must remain semantically unchanged
- repeated rewrite passes that expose a second rewrite opportunity in the same
  instruction
- instructions with no surviving `unique` temps after simplification

## Pretty-print contract

### `CanonicalFunctionIR`

- summary line:
  - `function 0xADDR name=<name-or-?> blocks=<n> instructions=<n> ops=<n> returns=[...] callees=[...]`
- `callsites:` section
  - one line per preserved callsite in instruction order
- `blocks:` section
  - block header lines in discovery order
  - instruction pretty lines followed by canonical p-code lines
  - instructions with no ops print `    <none>`

### `CanonicalProgramIR`

- header lines:
  - `root: 0xADDR`
  - `order: 0xADDR, ...`
  - `pending: ...`
  - `invalidated: ...`
- `externals:` section
- `call_graph:` section
- `functions:` section
  - nested `CanonicalFunctionIR` snapshots in discovery order

Pretty output must be deterministic across repeated runs over the same fixture.

## End-to-end harness exposure

The post-05 e2e harness should iterate all fixture binaries, resolve the root
function (`main`, with entrypoint fallback), build `CanonicalProgramIR`, and
render the deterministic snapshot.

The snapshot should make it obvious:

- which functions were discovered
- that block and call-graph structure still matches stage 4
- that local p-code is now less mechanical and more canonical
- that later analyses still start from preserved queue state

## CLI exposure

Post 05 adds a `simplify` debug surface:

- `tiny-dec decompile <binary> --stage simplify [--func <selector>]`
  - renders the canonical program rooted at the selected function

## Validation commands

- stage tests:
  - `poetry run pytest -q tests/posts/post_05_simplify`
- e2e harness:
  - `poetry run pytest -q tests/posts/post_05_simplify/test_simplify_e2e_harness.py`
- ruff:
  - `poetry run ruff check tiny_dec/analysis/simplify tiny_dec/cli.py tiny_dec/pipeline tests/posts/post_05_simplify`
- mypy:
  - `poetry run mypy tiny_dec/analysis/simplify tiny_dec/cli.py tiny_dec/pipeline tests/posts/post_05_simplify`

## Open questions

- Whether a later pass should introduce explicit expression trees instead of
  continuing to represent canonicalized statements as simplified p-code.
