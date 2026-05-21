# Stage Contract: `post_10_memory`

## Summary

- Stage name: `post_10_memory`
- Owner directory: `tiny_dec/analysis/memory/`
- Immediate predecessor: `post_09_stack`
- Immediate successor: `post_11_scalar_types`

## Purpose

Recover a small, deterministic memory-access model on top of stage-9 stack
facts.

This stage turns raw `LOAD` and `STORE` operations into stable memory
partitions that later typing and variable-recovery stages can consume:

- reuse recovered stack slots as concrete stack memory partitions
- recognize absolute-address memory accesses
- preserve non-stack pointer dereferences as explicit value-based partitions
- preserve the coarse stage-7 memory version seen at each `LOAD` or `STORE`
- keep per-partition access order stable and diff-friendly

The goal is to expose the current memory surface honestly, not to introduce a
full alias framework, partition-local memory SSA, or heap modeling.

## Inputs

- `FunctionStackFacts` from `tiny_dec.analysis.stack.models`
- `ProgramStackFacts` from `tiny_dec.analysis.stack.models`
- embedded `FunctionCallFacts`, `SSAFunctionIR`, and earlier wrapped artifacts
  preserved through stage 9
- preserved upstream `pending_entries`, `invalidated_entries`, externals, and
  call graph metadata carried through stage 9

Assumptions:

- stage-9 stack slots are already deterministic and preserve all currently
  recognized stack-relative accesses
- stage-7 SSA naming is stable and deterministic
- stage-7 low-level memory SSA is already present on `LOAD`, `STORE`, `CALL`,
  and `CALLIND`
- address expressions are only modeled when they reduce to one of:
  - a stage-9 stack slot
  - an absolute constant address plus constant offset
  - a value-based pointer root plus constant offset
- value-based pointer roots may additionally carry one scaled dynamic index of
  the form `root + index * stride + constant`; the index stays in the tracked
  address fact but is intentionally dropped from the exposed partition identity
- compatible SSA phi joins may preserve a tracked address when every incoming
  value resolves to the same tracked form
- variable or unsupported address arithmetic remains explicit as a value-based
  partition keyed by the exact SSA address value seen at the access site
- this stage does not rewrite memory operations, mutate stack facts, or infer
  types

## Outputs

- `MemoryPartitionKind`
  - distinguishes stack-slot, absolute-address, and value-based partitions
- `MemoryAccessKind`
  - distinguishes memory loads from memory stores
- `MemoryAccess`
  - one deterministic `LOAD` or `STORE` observation at one instruction, plus
    the coarse stage-7 memory version it used or defined
- `MemoryPartition`
  - one grouped memory partition plus its ordered accesses
- `FunctionMemoryFacts`
  - one function-level memory snapshot
- `ProgramMemoryFacts`
  - one program-level memory snapshot preserving scheduler state

Output invariants:

- `ProgramMemoryFacts.functions` covers the stage-9 program functions exactly
- `ProgramMemoryFacts.pending_entries` and `invalidated_entries` preserve the
  stage-9 values unchanged
- partitions are unique and deterministic by partition identity and access size
- stack-slot partitions reference the exact upstream `StackSlot`
- absolute partitions carry a concrete absolute address
- value-based partitions carry an explicit SSA or p-code value root and signed
  constant offset
- partition access ordering is deterministic by block and instruction order
- `LOAD` accesses preserve one coarse `memory_before` version when the
  upstream stage-7 op carried one
- `STORE` accesses preserve both coarse `memory_before` and `memory_after`
  versions when the upstream stage-7 op carried them

## Re-trigger and invalidation rules

- This stage is read-only with respect to earlier stages.
- It does not discover new functions, blocks, edges, or call targets.
- It does not emit new `pending_entries` or `invalidated_entries`.
- It preserves the stage-9 scheduler state unchanged so later stages can still
  observe the current queue suggestions.

## Non-goals

- full heap or global alias analysis
- partition-local memory SSA
- load/store reordering or dead-store elimination
- effect summaries for calls
- stack-argument promotion into the call ABI model
- element identity or per-index alias separation for variable-offset pointer
  walks
- type recovery
- rewriting the stage-7 SSA graph or stage-9 stack slots

## Algorithm sketch

### tracked address expressions

1. Start from one `SSAFunctionIR` embedded in `FunctionStackFacts`.
2. Seed tracked values with:
   - `x2` live-in as the entry stack-top address expression
   - other register live-ins as value-root expressions keyed by their SSA name
3. Iterate over reachable SSA phi nodes and instruction defs until tracked
   address facts stabilize.
4. Preserve one phi output only when every incoming phi value resolves to the
   same tracked address form.
5. Track address expressions through:
   - `COPY`
   - `INT_ADD` with one tracked input and one constant input
   - `INT_SUB` with one tracked input and one constant input
   - `INT_LEFT` when it produces one scaled dynamic index consumed by a
     value-root address
6. When loading from an argument-home stack slot, allow the output to inherit
   the corresponding live-in register root so spilled pointer arguments remain
   recognizable later in the function.

### partition recovery

1. For every `LOAD` and `STORE`, inspect the address input.
2. Preserve the coarse stage-7 memory version carried by that `LOAD` or
   `STORE`:
   - `LOAD` keeps its `memory_before`
   - `STORE` keeps both `memory_before` and `memory_after`
3. If the address expression resolves to a stage-9 stack offset and the access
   size matches an upstream slot, emit a `stack_slot` partition.
4. If the address expression resolves to an absolute constant address, emit an
   `absolute` partition.
5. If the address expression resolves to a value root plus constant offset, or
   to one value root plus one scaled dynamic index plus constant offset, emit a
   `value` partition keyed by the root and the constant field offset.
6. If the address expression cannot be tracked at all, emit a fallback `value`
   partition keyed by the raw SSA address value seen at the access site.

### partition grouping

1. Group accesses by partition identity:
   - stack slot `(frame_offset, size)`
   - absolute address `(address, size)`
   - value root plus constant offset `(value, offset, size)`
2. Keep accesses inside each partition in deterministic instruction order.
3. Materialize `MemoryPartition` objects in deterministic partition order.

### program aggregation

1. Analyze functions in stage-9 program discovery order.
2. Preserve externals, call graph, `pending_entries`, and `invalidated_entries`
   from stage 9 unchanged.
3. Emit `ProgramMemoryFacts`.

Failure and bailout rules:

- unsupported address arithmetic is preserved as a value-based partition keyed
  by the raw address value rather than being guessed into a stronger partition
- phi joins with mixed tracked roots, scaled-index shapes, or offsets bail out
  to the existing raw value-based fallback rather than inventing a merged alias
  class
- malformed upstream invariants fail through model validation rather than
  silent normalization
- this stage records memory facts only; it does not mutate upstream state

## Data structures

- `MemoryPartitionKind`
  - owner: `tiny_dec/analysis/memory/models.py`
  - values:
    - `stack_slot`
    - `absolute`
    - `value`
- `MemoryAccessKind`
  - owner: `tiny_dec/analysis/memory/models.py`
  - values:
    - `load`
    - `store`
- `MemoryAccess`
  - owner: `tiny_dec/analysis/memory/models.py`
  - fields:
    - `instruction_address`
    - `block_start`
    - `kind`
    - `size`
    - `value`
    - `memory_before`
    - `memory_after`
  - invariants:
    - addresses are non-negative
    - size is positive
    - `memory_after` requires `memory_before`
  - pretty:
    - `load 0x11174 block=0x11164 size=4 value=x11_5:4 [m6]`
    - `store 0x11180 block=0x11164 size=4 value=x10_8:4 [m9 -> m10]`
- `MemoryPartition`
  - owner: `tiny_dec/analysis/memory/models.py`
  - fields:
    - `kind`
    - `size`
    - `stack_slot`
    - `absolute_address`
    - `base_value`
    - `offset`
    - `accesses`
  - invariants:
    - exactly the detail fields for the chosen kind are populated
    - accesses are deterministic and match the partition size
    - stack-slot partitions reference an upstream slot with the same size
  - pretty:
    - `stack_slot -12 size=4 role=argument_home(x10) accesses=3`
    - `absolute 0x2000 size=4 accesses=1`
    - `value x10_0:4 offset=+4 size=4 accesses=1`
- `FunctionMemoryFacts`
  - owner: `tiny_dec/analysis/memory/models.py`
  - fields:
    - `stack`
    - `partitions`
  - invariants:
    - partition order is deterministic
    - embedded stack facts remain the upstream source of truth for frame size
      and scheduler state
  - pretty:
    - summary line with frame size, dynamic-stack marker, partition count,
      access count, and preserved per-function pending entries
- `ProgramMemoryFacts`
  - owner: `tiny_dec/analysis/memory/models.py`
  - fields:
    - `stack`
    - `functions`
    - `pending_entries`
    - `invalidated_entries`
  - invariants:
    - function coverage matches stage 9 exactly
    - scheduler state matches stage 9 exactly
  - pretty:
    - preserved program header, queue state, externals, call graph, and nested
      function memory facts

## Edge cases

- stack-only functions whose partitions are entirely recovered from stage-9
  slots
- stackless leaf functions with no memory accesses
- direct absolute-address memory accesses
- spilled pointer arguments reloaded from argument-home stack slots
- variable-offset pointer walks that must remain value-based rather than being
  guessed as typed fields
- unsupported pointer arithmetic that still needs a deterministic fallback
  partition
- repeated accesses to the same partition across loop iterations

## Pretty-print contract

### `FunctionMemoryFacts`

- summary line:
  - `function 0xADDR name=<name-or-?> frame_size=<n-or-?> dynamic_sp=<yes|no> partitions=<n> accesses=<n> pending=[...]`
- `partitions:` section
  - one deterministic line per partition
  - optional indented access lines in instruction order

### `ProgramMemoryFacts`

- header lines:
  - `root: 0xADDR`
  - `order: ...`
  - `pending: ...`
  - `invalidated: ...`
- `externals:` section
- `call_graph:` section
- `functions:` section
  - nested `FunctionMemoryFacts` output

## End-to-end harness exposure

The persistent fixture harness should render `memory:` for every fixture binary.
Plausible output should show:

- stack-slot partitions for ordinary `O0` functions with recovered frames
- value-based partitions for pointer dereferences the current tracker cannot
  reduce to stack or absolute memory
- stable root-plus-field partitions for simple scaled-index pointer walks such
  as `base + (index << k) + field_offset`
- stable partition ordering and access ordering
- unchanged `pending` and `invalidated` queue lines

## Validation commands

Record the commands that should be used while iterating:

- stage tests: `poetry run pytest -q tests/posts/post_10_memory`
- e2e harness: `poetry run pytest -q tests/posts/post_10_memory/test_memory_e2e_harness.py`
- cli: `poetry run tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --func main --stage memory`
- ruff: `poetry run ruff check tiny_dec/analysis/memory tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_10_memory`
- mypy: `poetry run mypy tiny_dec/analysis/memory tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_10_memory`

## Open questions

- Whether a later memory or aggregate stage should keep the tracked dynamic
  index visible instead of dropping it from the partition identity whenever one
  source-level array walk clearly owns the access path.
