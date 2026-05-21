# Stage Contract: `post_11_scalar_types`

## Summary

- Stage name: `post_11_scalar_types`
- Owner directory: `tiny_dec/analysis/types/`
- Immediate predecessor: `post_10_memory`
- Immediate successor: `post_12_aggregate_types`

## Purpose

Recover a small, deterministic scalar-type layer on top of stage-10 memory
facts.

This stage does not attempt full type inference. Its job is to expose the
current low-level scalar surface in a form later stages can build on:

- classify scalar values and memory partitions conservatively as
  `bool`, `int`, `pointer`, or fallback `word`
- keep widths explicit and deterministic
- propagate obvious scalar identity through copies and memory traffic
- preserve the current queue and invalidation state unchanged

The goal is to make later aggregate-type and variable-recovery stages consume a
typed surface that is honest about what is known today, not to guess C source
types prematurely.

## Inputs

- `FunctionMemoryFacts` from `tiny_dec.analysis.memory.models`
- `ProgramMemoryFacts` from `tiny_dec.analysis.memory.models`
- embedded `FunctionStackFacts`, `FunctionCallFacts`, `SSAFunctionIR`, and
  earlier wrapped artifacts preserved through stage 10
- preserved upstream `pending_entries`, `invalidated_entries`, externals, and
  call graph metadata carried through stage 10

Assumptions:

- stage-10 memory partitions are already deterministic and preserve the current
  memory-access grouping
- stage-7 SSA naming is stable and deterministic
- scalar recovery is limited to stage-local evidence from SSA operations and
  stage-10 memory partitions
- unsupported or conflicting evidence must degrade to the weaker `word`
  category rather than inventing a stronger type
- this stage does not rewrite SSA, mutate memory partitions, or infer
  aggregate layout

## Outputs

- `ScalarTypeKind`
  - distinguishes the currently recoverable scalar classes
- `ScalarType`
  - one recovered scalar class plus explicit byte width
- `PartitionScalarTypeFact`
  - one typed stage-10 memory partition
- `ValueScalarTypeFact`
  - one typed SSA or p-code value
- `FunctionScalarTypeFacts`
  - one function-level scalar-typing snapshot
- `ProgramScalarTypeFacts`
  - one program-level scalar-typing snapshot preserving scheduler state

Output invariants:

- `ProgramScalarTypeFacts.functions` covers the stage-10 program functions
  exactly
- `ProgramScalarTypeFacts.pending_entries` and `invalidated_entries` preserve
  the stage-10 values unchanged
- typed partition facts reference only stage-10 partitions from the owning
  function
- typed value facts are unique per value and ordered deterministically
- `ScalarType.size` matches the typed partition or value width exactly
- omitted partitions and values are intentionally unknown rather than silently
  normalized into a fake fallback fact

## Re-trigger and invalidation rules

- This stage is read-only with respect to earlier stages.
- It does not discover new functions, blocks, edges, or call targets.
- It does not emit new `pending_entries` or `invalidated_entries`.
- It preserves the stage-10 scheduler state unchanged so later stages can still
  observe the current queue suggestions.

## Non-goals

- aggregate or field layout recovery
- struct, array, or union inference
- prototype inference
- signed-versus-unsigned source-level distinctions
- memory SSA
- alias analysis
- value-range reasoning
- interprocedural type propagation
- rewriting stage-7 SSA values or stage-10 memory partitions

## Algorithm sketch

### scalar classes

This stage currently recognizes four scalar classes:

- `bool`
  - comparison and boolean-condition values
- `int`
  - ordinary arithmetic or signed-comparison operands/results
- `pointer`
  - values demonstrably used as memory addresses or pointer-derived addresses
- `word`
  - sized scalar fallback when evidence says a value is scalar but not whether
    it is `bool`, `int`, or `pointer`

Unknown values and partitions are omitted from the typed-fact lists.

### equivalence groups

1. Start from one `SSAFunctionIR` embedded in `FunctionMemoryFacts`.
2. Build scalar-identity groups for non-constant values and partitions through:
   - `COPY`
   - stage-10 `LOAD` outputs and `STORE` inputs
   - the owning stage-10 partition for each memory access
3. Keep groups deterministic by visiting functions and blocks in upstream
   discovery order.

### evidence seeding

Seed scalar facts conservatively from local evidence:

- comparison outputs and branch conditions produce `bool`
- signed compare operands produce `int`
- equality and bitwise operands produce weak `word` hints
- constant copies produce `int`
- absolute partitions start as weak `word` facts until stronger arithmetic or
  comparison evidence promotes them
- value-partition base values produce `pointer`
- argument-home groups that participate in constant-offset add/sub address
  shaping become pointer candidates
- pointer-preserving `INT_ADD` and `INT_SUB` produce `pointer`
- `INT_ADD` and `INT_SUB` produce `int` when existing non-pointer scalar
  evidence already justifies that relation
- shift and extend outputs produce `int`
- one local stack-slot identity group tied to a stored `CALL_RETURN` chain can
  inherit `int` when it later participates in `INT_ADD` or `INT_SUB` with a
  constant and no pointer evidence is present

### merge rules

1. Merge evidence inside one scalar-identity group by byte width.
2. `word` is a weak hint:
   - `word + pointer -> pointer`
   - `word + int -> int`
   - `word + bool -> bool`
3. Conflicting precise classes degrade to `word` of the same width:
   - `pointer + int -> word`
   - `pointer + bool -> word`
   - `int + bool -> word`
4. Width mismatches are malformed upstream state and should fail through model
   validation rather than silent coercion.

### program aggregation

1. Analyze functions in stage-10 program discovery order.
2. Preserve externals, call graph, `pending_entries`, and `invalidated_entries`
   from stage 10 unchanged.
3. Emit `ProgramScalarTypeFacts`.

Failure and bailout rules:

- if the stage cannot justify a scalar class, it omits the fact instead of
  inventing `word`
- if evidence conflicts only weakly, the stage keeps the stronger precise class
- if evidence conflicts strongly, the stage degrades to `word`
- this stage records scalar facts only; it does not mutate upstream state

## Data structures

- `ScalarTypeKind`
  - owner: `tiny_dec/analysis/types/models.py`
  - values:
    - `bool`
    - `int`
    - `pointer`
    - `word`
- `ScalarType`
  - owner: `tiny_dec/analysis/types/models.py`
  - fields:
    - `kind`
    - `size`
  - invariants:
    - size is positive
  - pretty:
    - `pointer:4`
    - `int:4`
    - `bool:1`
- `PartitionScalarTypeFact`
  - owner: `tiny_dec/analysis/types/models.py`
  - fields:
    - `partition`
    - `scalar_type`
  - invariants:
    - typed width matches the owning partition width
  - pretty:
    - `stack_slot -12 size=4 role=argument_home(x10) type=pointer:4`
- `ValueScalarTypeFact`
  - owner: `tiny_dec/analysis/types/models.py`
  - fields:
    - `value`
    - `scalar_type`
  - invariants:
    - typed width matches the value width
  - pretty:
    - `x10_5:4 type=pointer:4`
    - `u0_0:1 type=bool:1`
- `FunctionScalarTypeFacts`
  - owner: `tiny_dec/analysis/types/models.py`
  - fields:
    - `memory`
    - `partition_facts`
    - `value_facts`
  - invariants:
    - fact ordering is deterministic
    - embedded memory facts remain the upstream source of truth for frame size
      and scheduler state
  - pretty:
    - summary line with frame size, dynamic-stack marker, typed partition
      count, typed value count, and preserved per-function pending entries
- `ProgramScalarTypeFacts`
  - owner: `tiny_dec/analysis/types/models.py`
  - fields:
    - `memory`
    - `functions`
    - `pending_entries`
    - `invalidated_entries`
  - invariants:
    - function coverage matches stage 10 exactly
    - scheduler state matches stage 10 exactly
  - pretty:
    - preserved program header, queue state, externals, call graph, and nested
      function scalar-type facts

## Edge cases

- functions whose only typed evidence is boolean branch conditions
- pointer arguments spilled to argument-home stack slots and later reloaded
- values compared only for equality, which should remain `word` unless other
  evidence makes them stronger
- arithmetic values that later feed memory partitions
- one stored call result that only becomes obviously scalar after one later
  `+/- const` use
- saved-register slots that remain untyped because the current stage sees no
  scalar evidence for them
- saved-register return-address traffic may still degrade to weak `word` facts
  when the low-level epilogue uses bitwise canonicalization
- conflicting evidence that must degrade to `word`
- stackless leaf functions with no typed partitions or typed values

## Pretty-print contract

### `FunctionScalarTypeFacts`

- summary line:
  - `function 0xADDR name=<name-or-?> frame_size=<n-or-?> dynamic_sp=<yes|no> typed_partitions=<n> typed_values=<n> pending=[...]`
- `partitions:` section
  - one deterministic line per typed partition fact
- `values:` section
  - one deterministic line per typed value fact

### `ProgramScalarTypeFacts`

- header lines:
  - `root: 0xADDR`
  - `order: ...`
  - `pending: ...`
  - `invalidated: ...`
- `externals:` section
- `call_graph:` section
- `functions:` section
  - nested `FunctionScalarTypeFacts` output

## End-to-end harness exposure

The persistent fixture harness should render `scalar_types:` for every fixture
binary. Plausible output should show:

- pointer typing on spilled pointer arguments such as `parse_record(records, ...)`
- integer typing on arithmetic loop counters and totals
- boolean typing on comparison results where those SSA values survive in the
  typed-value section
- empty typed sections for fixtures whose current pipeline still exposes no
  honest scalar evidence

## Validation commands

- stage tests: `poetry run pytest -q tests/posts/post_11_scalar_types`
- e2e harness: `poetry run pytest -q tests/posts/post_11_scalar_types/test_scalar_types_e2e_harness.py`
- iterate CLI until stage wiring exists: `poetry run tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --func parse_record --stage memory`
- final stage CLI: `poetry run tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --func main --stage scalar_types`
- ruff: `poetry run ruff check tiny_dec/analysis/types tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_11_scalar_types`
- mypy: `poetry run mypy tiny_dec/analysis/types tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_11_scalar_types`
