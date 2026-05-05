# Stage Contract: `post_12_aggregate_types`

## Summary

- Stage name: `post_12_aggregate_types`
- Owner directory: `tiny_dec/analysis/types/`
- Immediate predecessor: `post_11_scalar_types`
- Immediate successor: `post_13_variables`

## Purpose

Recover a small, deterministic aggregate-layout layer on top of stage-11 scalar
type facts.

This stage does not try to produce source-level `struct` declarations. Its job
is to identify pointer-rooted memory layouts that now look stable enough to
describe as aggregates:

- group scalar-typed pointer dereferences by one canonical aggregate root
- recover constant field offsets within that root
- keep any repeated dynamic indexing stride explicit when it is recoverable
- preserve the current queue and invalidation state unchanged

The goal is to give later variable-recovery and structuring stages a truthful
layout surface without pretending that field names, nested aggregates, array
lengths, or full source types are already known.

## Inputs

- `FunctionScalarTypeFacts` from `tiny_dec.analysis.types.models`
- `ProgramScalarTypeFacts` from `tiny_dec.analysis.types.models`
- embedded `FunctionMemoryFacts`, `FunctionStackFacts`, `FunctionCallFacts`,
  `SSAFunctionIR`, and earlier wrapped artifacts preserved through stage 11
- preserved upstream `pending_entries`, `invalidated_entries`, externals, and
  call graph metadata carried through stage 11

Assumptions:

- stage-11 scalar type facts are already deterministic and preserve the stage-10
  memory partitions exactly
- stage-7 SSA naming is stable and deterministic
- aggregate recovery is limited to pointer-rooted field layouts that can still
  be expressed as `root + unknown_multiple_of(stride) + constant_field_offset`
- unsupported or conflicting field evidence must either degrade to weak `word`
  or be omitted instead of inventing a stronger layout
- this stage does not rewrite SSA, mutate scalar facts, or introduce new
  scheduler work

## Outputs

- `AggregateRootKind`
  - distinguishes pointer-rooted aggregate layouts from any future root forms
- `AggregateRoot`
  - one canonical aggregate root plus an optional recovered repeated stride
- `AggregateField`
  - one constant field offset within one aggregate root
- `AggregateLayout`
  - one aggregate root plus its deterministic field set
- `FunctionAggregateTypeFacts`
  - one function-level aggregate-layout snapshot
- `ProgramAggregateTypeFacts`
  - one program-level aggregate-layout snapshot preserving scheduler state

Output invariants:

- `ProgramAggregateTypeFacts.functions` covers the stage-11 program functions
  exactly
- `ProgramAggregateTypeFacts.pending_entries` and `invalidated_entries`
  preserve the stage-11 values unchanged
- aggregate roots are unique per function and ordered deterministically
- field offsets are unique within one aggregate layout and ordered
  deterministically
- each field width matches the owning scalar partition width exactly
- omitted roots and partitions are intentionally unrecoverable rather than
  silently normalized into fake aggregate facts

## Re-trigger and invalidation rules

- This stage is read-only with respect to earlier stages.
- It does not discover new functions, blocks, edges, or call targets.
- It does not emit new `pending_entries` or `invalidated_entries`.
- It preserves the stage-11 scheduler state unchanged so later stages can still
  observe the current queue suggestions.

## Non-goals

- source-level `struct`, `union`, or array declarations
- field naming
- nested aggregate recovery
- absolute/global aggregate recovery
- stack-frame slot reclassification
- bitfields
- interprocedural layout merging
- array length inference
- rewriting stage-7 SSA values or stage-11 scalar facts

## Algorithm sketch

### candidate roots

1. Start from one `SSAFunctionIR` embedded in `FunctionScalarTypeFacts`.
2. Rebuild deterministic pointer-identity groups across pointer-typed scalar
   values through:
   - `COPY`
   - phi nodes
   - pointer-typed stage-10 memory partitions and their load/store values
3. Choose one canonical pointer value per group as the aggregate root
   representative.

### integer stride hints

Track conservative integer stride facts for scalar integer values:

- `COPY` preserves a known stride hint
- left shifts by a constant multiply the known stride hint
- adding or subtracting a constant preserves the known stride hint
- unsupported arithmetic drops the hint

The stride hint means “unknown multiple of N bytes”, not a concrete value.

### pointer expressions

Track pointer-valued SSA outputs when they stay expressible as:

- `canonical_root + constant`
- `canonical_root + unknown_multiple_of(stride) + constant`

Rules:

- `COPY` preserves the pointer expression
- `INT_ADD` and `INT_SUB` with constants adjust the constant field offset
- `INT_ADD` with one tracked pointer expression and one tracked integer stride
  preserves the root and attaches the stride hint
- unsupported pointer arithmetic drops the expression

### aggregate field recovery

1. Inspect scalar-typed stage-10 `MemoryPartitionKind.VALUE` partitions only.
2. For each partition whose `base_value` still has a tracked pointer
   expression, recover:
   - canonical aggregate root
   - optional repeated stride
   - constant field offset = tracked constant offset + partition offset
   - field scalar type from the stage-11 typed partition
3. Group recovered fields by aggregate root.
4. Merge multiple partitions that land on the same root and constant offset:
   - identical scalar types stay precise
   - conflicting precise scalar classes degrade to weak `word`
   - conflicting widths are malformed upstream state and should fail through
     model validation rather than silent coercion
5. Emit one deterministic `AggregateLayout` per recovered root.

Failure and bailout rules:

- if a pointer root cannot be canonicalized, skip the candidate
- if the partition address no longer fits the tracked expression forms, skip it
- if a root has no recovered fields, omit it entirely
- this stage records layout facts only; it does not mutate upstream state

## Data structures

- `AggregateRootKind`
  - owner: `tiny_dec/analysis/types/aggregate_models.py`
  - values:
    - `pointer`
- `AggregateRoot`
  - owner: `tiny_dec/analysis/types/aggregate_models.py`
  - fields:
    - `kind`
    - `pointer_value`
    - `stride`
  - invariants:
    - pointer roots must carry a pointer SSA value
    - stride, when present, is positive
  - pretty:
    - `pointer x10_0:4 stride=8`
    - `pointer x10_0:4 stride=?`
- `AggregateField`
  - owner: `tiny_dec/analysis/types/aggregate_models.py`
  - fields:
    - `offset`
    - `scalar_type`
    - `partitions`
  - invariants:
    - offset is non-negative
    - partitions are non-empty
    - every partition width matches `scalar_type.size`
    - partition ordering is deterministic
  - pretty:
    - `field +0 size=4 type=int:4 partitions=[value u0_14:4 offset=+0 size=4]`
- `AggregateLayout`
  - owner: `tiny_dec/analysis/types/aggregate_models.py`
  - fields:
    - `root`
    - `fields`
  - invariants:
    - fields are ordered by offset
    - field offsets are unique
  - pretty:
    - `aggregate pointer x10_0:4 stride=8 fields=2`
- `FunctionAggregateTypeFacts`
  - owner: `tiny_dec/analysis/types/aggregate_models.py`
  - fields:
    - `scalar_types`
    - `layouts`
  - invariants:
    - layout ordering is deterministic
    - embedded stage-11 facts remain the upstream source of truth for frame size
      and scheduler state
  - pretty:
    - summary line with frame size, dynamic-stack marker, aggregate count, and
      preserved per-function pending entries
- `ProgramAggregateTypeFacts`
  - owner: `tiny_dec/analysis/types/aggregate_models.py`
  - fields:
    - `scalar_types`
    - `functions`
    - `pending_entries`
    - `invalidated_entries`
  - invariants:
    - function coverage matches stage 11 exactly
    - scheduler state matches stage 11 exactly
  - pretty:
    - preserved program header, queue state, externals, call graph, and nested
      aggregate-layout facts

## Edge cases

- one-field aggregates with no recoverable repeated stride
- repeated dynamic indexing where the stride is known but the index value is not
- conflicting scalar evidence for the same field offset degrading to `word`
- pointer roots rebuilt through argument-home reloads and phi nodes
- saved-register, stack-slot, and absolute partitions that should not become
  aggregate facts
- optimized leaf functions with no pointer-rooted partitions
- malformed mixed-width field merges that must fail clearly

## Pretty-print contract

### `FunctionAggregateTypeFacts`

- summary line:
  - `function 0xADDR name=<name-or-?> frame_size=<n-or-?> dynamic_sp=<yes|no> aggregates=<n> pending=[...]`
- `aggregates:` section
  - one deterministic `aggregate ...` header per recovered layout
  - nested deterministic `field ...` lines under each aggregate

### `ProgramAggregateTypeFacts`

- header lines:
  - `root: 0xADDR`
  - `order: ...`
  - `pending: ...`
  - `invalidated: ...`
- `externals:` section
- `call_graph:` section
- `functions:` section
  - nested `FunctionAggregateTypeFacts` output

## End-to-end harness exposure

The persistent fixture harness should render `aggregate_types:` for every
fixture binary. Plausible output should show:

- one aggregate rooted at the `parse_record` pointer argument in
  `fixture_struct_O0_nopie`
- a recovered repeated stride of `8`
- two recovered integer fields at offsets `+0` and `+4`
- empty aggregate sections for fixtures whose current pipeline still exposes no
  honest pointer-rooted layout

## Validation commands

- stage tests: `poetry run pytest -q tests/posts/post_12_aggregate_types`
- e2e harness: `poetry run pytest -q tests/posts/post_12_aggregate_types/test_aggregate_types_e2e_harness.py`
- cli while iterating before wiring: `poetry run tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --func parse_record --stage scalar_types`
- final stage cli: `poetry run tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --func main --stage aggregate_types`
- ruff: `poetry run ruff check tiny_dec/analysis/types tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_12_aggregate_types`
- mypy: `poetry run mypy tiny_dec/analysis/types tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_12_aggregate_types`

## Open questions

- Whether a later refinement should model absolute/global aggregate roots in the
  same artifact or in a sibling stage-specific abstraction.
