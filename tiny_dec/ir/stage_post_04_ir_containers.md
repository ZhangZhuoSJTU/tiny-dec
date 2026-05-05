# Stage Contract: `post_04_ir_containers`

## Summary

- Stage name: `post_04_ir_containers`
- Owner directory: `tiny_dec/ir/`
- Immediate predecessor: `post_03_disasm`
- Immediate successor: `post_05_simplify`

## Purpose

Turn stage-3 disassembly results into durable, typed containers that later
stages can consume without needing to rediscover function-level structure from
raw bytes.

This stage introduces:

- `FunctionIR` as the stable per-function container
- `ProgramIR` as the stable program-level container rooted at one function

At this stage the containers are still intentionally raw. They preserve stage-3
disassembly and direct call discovery, but they do not perform normalization,
SSA, stack recovery, or type inference.

## Inputs

- `ProgramView` from `tiny_dec.loader`
  - must provide loader-backed bytes, symbol lookup, and external function
    metadata
- `DisasmFunction` from `tiny_dec.disasm`
  - contains ordered basic blocks, block terminators, and direct call targets
- one root function entry address
  - usually resolved from `main`

Assumptions:

- stage-3 disassembly is deterministic
- stage-3 direct call targets are precise for direct calls
- when one unresolved direct call is encoded as a self-targeting `jal` and the
  loader still exposes ordered undefined external names, stage 4 may use that
  ordered loader fallback to attach one named external edge
- indirect calls and indirect jumps remain unresolved at this stage

## Outputs

- `FunctionIR`
  - one entry address
  - one owned `DisasmFunction`
  - deterministic instruction index
  - typed callsite list
  - return-block list
  - direct-callee list
- `ProgramIR`
  - one root entry
  - discovered functions keyed by entry
  - deterministic function discovery order
  - loader external-function metadata
  - direct call-graph edges
  - explicit empty `pending_entries` and `invalidated_entries` queues

Output invariants:

- every `FunctionIR.entry` matches `FunctionIR.disasm.entry`
- `FunctionIR.instruction_index` covers every distinct instruction address in
  first-seen block order, even when stage-3 blocks overlap
- `FunctionIR.direct_callees` is deduplicated and stable
- `ProgramIR.discovery_order` references exactly the discovered functions
- `ProgramIR.root_entry` is always present in `ProgramIR.functions`
- `ProgramIR.call_graph` is deterministic and ordered by function discovery,
  then callsite order

## Non-goals

- dataflow or target recovery for indirect edges
- call-convention modeling
- prototype inference
- stack, memory, or type recovery
- CFG rewriting or normalization
- interprocedural fixpoint scheduling beyond recording initial queue state
  (consumed by the stage-18 pipeline scheduler)

## Algorithm sketch

### `build_function_ir`

1. Accept a `ProgramView` and function entry, or an already-built
   `DisasmFunction`.
2. Build a deterministic instruction index by iterating blocks in disassembly
   order and keeping the first-seen instance of each instruction address.
3. Derive callsites by scanning each instruction's lifted p-code for `CALL` and
   `CALLIND`.
4. Derive direct callees from direct callsites in first-seen order.
5. Derive return blocks from blocks whose terminator is `RETURN`.
6. Attach the best available symbol name for the entry address.
7. Materialize `FunctionIR`.

### `build_program_ir`

1. Seed a worklist with the chosen root function entry.
2. Materialize `FunctionIR` for each scheduled entry.
3. Record each function in deterministic discovery order.
4. For every direct callsite:
   - classify it as internal, external, or unresolved
   - record a direct call-graph edge
   - schedule newly discovered internal callees
5. Initialize empty `pending_entries` and `invalidated_entries` as the initial
   scheduler state (consumed by the stage-18 pipeline scheduler).
6. Materialize `ProgramIR`.

Traversal and bailout rules:

- direct internal calls recurse through post 03 and post 04 only
- external calls are recorded but not disassembled
- one self-targeting unresolved direct call may still become a named external
  when the loader only exposes ordered undefined externals and no concrete
  PLT/GOT/symbol address
- indirect calls remain in `FunctionIR.callsites` but do not create call-graph
  edges yet
- unmapped direct targets are recorded as unresolved direct edges instead of
  crashing later stages

## Data structures

- `CallSite`
  - owner: `tiny_dec/ir/function_ir.py`
  - fields:
    - `instruction_address`
    - `block_start`
    - `target`
    - `target_name`
    - `is_indirect`
  - invariants:
    - addresses are non-negative
    - indirect callsites do not claim a resolved direct target
  - pretty:
    - direct: `call 0xADDR block=0xBLOCK -> 0xTARGET [name=...]`
    - indirect: `call 0xADDR block=0xBLOCK -> <indirect>`
- `FunctionIR`
  - owner: `tiny_dec/ir/function_ir.py`
  - fields:
    - `entry`
    - `name`
    - `disasm`
    - `instruction_index`
    - `callsites`
    - `return_blocks`
    - `direct_callees`
  - invariants:
    - `entry == disasm.entry`
    - instruction index matches the owned disassembly after first-seen address
      deduplication
    - direct callees are deduplicated
  - pretty:
    - one summary line
    - `callsites:` section
    - `instructions:` index line
    - nested `disasm:` snapshot
- `CallGraphEdgeKind`
  - owner: `tiny_dec/ir/program_ir.py`
  - values:
    - `internal`
    - `external`
    - `unresolved`
- `CallGraphEdge`
  - owner: `tiny_dec/ir/program_ir.py`
  - fields:
    - `caller`
    - `callsite_address`
    - `kind`
    - `callee_address`
    - `callee_name`
  - pretty:
    - `0xCALLER@0xSITE -> <kind> ...`
- `ProgramIR`
  - owner: `tiny_dec/ir/program_ir.py`
  - fields:
    - `root_entry`
    - `functions`
    - `discovery_order`
    - `externals`
    - `call_graph`
    - `pending_entries`
    - `invalidated_entries`
  - invariants:
    - root entry exists in functions
    - discovery order references known functions only
    - queues are deterministic snapshots
  - pretty:
    - program header
    - discovery order
    - queue state
    - external list
    - call-graph section
    - nested function IR sections

## Edge cases

- root function with no calls
- direct self-recursion
- direct self-targeting unresolved call that falls back to one ordered
  undefined external name
- multiple callsites to the same callee
- indirect calls mixed with direct calls in one block
- direct call target that is external via loader metadata
- direct call target that is not disassemblable from the current loader mapping
- function with multiple return blocks
- overlapping stage-3 blocks that share tail instructions
- symbol-less internal helper functions

## Pretty-print contract

### `FunctionIR`

- summary line:
  - `function 0xADDR name=<name-or-?> blocks=<n> instructions=<n> returns=[...] callees=[...]`
- `callsites:` section
  - one line per callsite in instruction order
- `instructions:` line
  - ordered address index
- `disasm:` section
  - nested stage-3 snapshot, indented by two spaces

### `ProgramIR`

- header lines:
  - `root: 0xADDR`
  - `order: 0xADDR, ...`
  - `pending: ...`
  - `invalidated: ...`
- `externals:` section
  - one line per loader external
- `call_graph:` section
  - one line per direct call edge
- `functions:` section
  - nested `FunctionIR` snapshots in discovery order

Pretty output must be deterministic across repeated runs over the same fixture.

## End-to-end harness exposure

The post-04 e2e harness should iterate all fixture binaries, resolve the root
function (`main`, with entrypoint fallback), build `ProgramIR`, and render the
deterministic program snapshot.

The snapshot should make it obvious:

- which internal functions were discovered from the root
- which calls were classified as internal or external
- which direct callees remain unresolved
- that initial scheduler queues (`pending_entries`, `invalidated_entries`) are empty

## CLI exposure

Post 04 adds an `ir` debug surface:

- `tiny-dec decompile <binary> --stage ir [--func <selector>]`
  - renders `ProgramIR` rooted at the selected function

## Validation commands

- stage tests:
  - `poetry run pytest -q tests/posts/post_04_ir_containers`
- e2e harness:
  - `poetry run pytest -q tests/posts/post_04_ir_containers/test_ir_containers_e2e_harness.py`
- ruff:
  - `poetry run ruff check tiny_dec/ir tiny_dec/cli.py tiny_dec/pipeline tests/posts/post_04_ir_containers`
- mypy:
  - `poetry run mypy tiny_dec/ir tiny_dec/cli.py tiny_dec/pipeline tests/posts/post_04_ir_containers`
- cli smoke:
  - `poetry run tiny-dec decompile tests/fixtures/bin/fixture_basic_O0_nopie.elf --func main --stage ir`

## Resolved design decisions

- Scheduler queues are stored in wrapper state objects at each stage level
  rather than directly inside `ProgramIR`.
- Stage 08 introduced a separate `ModeledCallSite` type rather than extending
  the raw post-04 `CallSite`, preserving the original view at each layer.
