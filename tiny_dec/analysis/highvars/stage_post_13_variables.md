# Stage Contract: `post_13_variables`

## Summary

- Stage name: `post_13_variables`
- Owner directory: `tiny_dec/analysis/highvars/`
- Immediate predecessor: `post_12_aggregate_types`
- Immediate successor: `post_14_range`

## Purpose

Recover a small, deterministic source-level variable layer on top of stage-12
aggregate facts.

This stage turns the current low-level memory, scalar, and aggregate evidence
into stable variable groups that later range, interprocedural, and structuring
work can consume directly:

- keep stack-backed parameters and locals as durable variable anchors
- attach recovered aggregate layouts to the parameter or local variable that
  appears to own them
- preserve absolute-address globals as explicit variables
- keep leftover non-stack dereferences visible as indirect variable groups

The goal is to expose plausible source-level variable groupings honestly, not to
invent names, eliminate SSA temporaries wholesale, or claim full alias-aware
high-variable recovery.

## Inputs

- `FunctionAggregateTypeFacts` from
  `tiny_dec.analysis.types.aggregate_models`
- `ProgramAggregateTypeFacts` from
  `tiny_dec.analysis.types.aggregate_models`
- embedded `FunctionScalarTypeFacts`, `FunctionMemoryFacts`,
  `FunctionStackFacts`, `FunctionCallFacts`, and `SSAFunctionIR` preserved
  through stage 12
- preserved upstream `pending_entries`, `invalidated_entries`, externals, and
  call graph metadata carried through stage 12

Assumptions:

- stage-12 aggregate layouts are already deterministic and preserve the stage-11
  scalar and stage-10 memory artifacts exactly
- stage-9 stack slot roles are truthful enough to distinguish parameter homes,
  ordinary locals, and saved-register bookkeeping
- stage-7 SSA live-ins are stable and deterministic
- this stage may omit evidence that does not map cleanly to a durable variable
  anchor rather than inventing a stronger variable identity
- this stage does not rewrite SSA, mutate type facts, or change scheduler state

## Outputs

- `VariableKind`
  - distinguishes recovered parameters, locals, globals, and residual indirect
    dereference groups
- `VariableBindingKind`
  - distinguishes whether a variable is anchored by a stack slot, live-in/root
    SSA value, absolute address, or raw memory partition
- `VariableBinding`
  - one deterministic anchor that explains why the variable exists
- `RecoveredVariable`
  - one variable group plus its typed partitions and optional aggregate layout
- `FunctionVariableFacts`
  - one function-level variable snapshot
- `ProgramVariableFacts`
  - one program-level variable snapshot preserving scheduler state

Output invariants:

- `ProgramVariableFacts.functions` covers the stage-12 program functions exactly
- `ProgramVariableFacts.pending_entries` and `invalidated_entries` preserve the
  stage-12 values unchanged
- variable ordering is deterministic and diff-friendly
- variable names are stable synthetic hints, not claimed source names
- saved-register stack slots do not become source-level variables
- every referenced partition comes from the wrapped stage-12 memory surface
- aggregate-backed variables retain the exact stage-12 layout object unchanged

## Re-trigger and invalidation rules

- This stage is read-only with respect to earlier stages.
- It does not discover new functions, blocks, edges, or call targets.
- It does not emit new `pending_entries` or `invalidated_entries`.
- It preserves the stage-12 scheduler state unchanged so later stages can still
  observe the current queue suggestions.

## Non-goals

- recovering true source variable names
- full alias-aware high-variable merging
- promoting every SSA temporary into a variable
- splitting or merging aggregate layouts across functions
- prototype inference
- stack-frame rewriting
- eliminating saved-register traffic from upstream stages
- rewriting stage-10 memory partitions, stage-11 scalar facts, or stage-12
  layouts

## Algorithm sketch

### supporting indexes

1. Start from one `FunctionAggregateTypeFacts`.
2. Build deterministic maps for:
   - typed partitions by `MemoryPartition`
   - typed values by `SSAValue`
   - aggregate layouts by root pointer value
   - the set of partitions already consumed by aggregate layouts

### aggregate-backed variables

1. For each aggregate layout, choose one durable anchor in priority order:
   - matching argument-home stack slot for the same ABI register root
   - matching non-saved stack slot whose accesses explicitly carry the same root
   - live-in ABI argument register value
   - the aggregate root SSA value itself
2. Classify the variable kind from that anchor:
   - argument-home slot or ABI live-in register -> `parameter`
   - ordinary stack slot -> `local`
   - fallback root-only anchor -> `indirect`
3. Emit one `RecoveredVariable` that keeps:
   - a stable synthetic name
   - the anchor binding
   - the root scalar type when available
   - the exact stage-12 `AggregateLayout`
   - the union of the anchor partition, if any, and all aggregate field
     partitions

### stack-backed scalar variables

1. Visit stage-10 stack-slot partitions in deterministic order.
2. Skip slots already consumed by an aggregate-backed variable.
3. Skip saved-register slots entirely.
4. Emit:
   - `parameter` variables for argument-home slots
   - `local` variables for local or unknown slots
5. Keep the stage-11 scalar type when available.

### absolute and residual dereference variables

1. Visit remaining typed and untyped partitions not already consumed by an
   aggregate-backed or stack-backed variable.
2. Emit:
   - `global` variables for absolute partitions
   - `indirect` variables for value-based partitions that remain outside any
     recovered aggregate layout
3. Keep the partition itself as the binding anchor so the evidence stays
   inspectable.

### register-only parameters

1. Inspect stage-7 live-in SSA names.
2. For ABI argument registers that have a scalar type but no existing variable
   anchor, emit one `parameter` variable anchored by the live-in SSA value.
3. Do not emit generic non-argument register variables in this first
   implementation.

Failure and bailout rules:

- ambiguous anchors prefer omission over guessed merging
- aggregate layouts are never rewritten to fit a chosen variable anchor
- unsupported value-root provenance remains an `indirect` variable rather than
  a false local or parameter claim
- malformed upstream invariants fail through model validation rather than silent
  normalization

## Data structures

- `VariableKind`
  - owner: `tiny_dec/analysis/highvars/models.py`
  - values:
    - `parameter`
    - `local`
    - `global`
    - `indirect`
- `VariableBindingKind`
  - owner: `tiny_dec/analysis/highvars/models.py`
  - values:
    - `stack_slot`
    - `root_value`
    - `absolute`
    - `partition`
- `VariableBinding`
  - owner: `tiny_dec/analysis/highvars/models.py`
  - fields:
    - `kind`
    - `stack_slot`
    - `root_value`
    - `absolute_address`
    - `partition`
  - invariants:
    - exactly the detail field for the chosen binding kind is populated
    - stack-slot and partition bindings preserve size through the owning
      variable
  - pretty:
    - `stack_slot -12 size=4 role=argument_home(x10)`
    - `root_value x10_0:4`
    - `absolute 0x2000`
    - `partition value u0_14:4 offset=+0 size=4`
- `RecoveredVariable`
  - owner: `tiny_dec/analysis/highvars/models.py`
  - fields:
    - `name`
    - `kind`
    - `size`
    - `binding`
    - `scalar_type`
    - `root_value`
    - `aggregate_layout`
    - `partitions`
  - invariants:
    - name is non-empty
    - size is positive
    - partitions are deterministic and unique
    - aggregate-backed variables keep the exact stage-12 layout root
  - pretty:
    - `variable arg_x10_4 kind=parameter size=4 binding=stack_slot -12 size=4 role=argument_home(x10) type=pointer:4 root=x10_0:4 aggregate_fields=2 partitions=3`
- `FunctionVariableFacts`
  - owner: `tiny_dec/analysis/highvars/models.py`
  - fields:
    - `aggregate_types`
    - `variables`
  - invariants:
    - variable ordering is deterministic
    - names are unique within a function
  - pretty:
    - summary line with frame size, dynamic-stack marker, variable count, and
      preserved per-function pending entries
- `ProgramVariableFacts`
  - owner: `tiny_dec/analysis/highvars/models.py`
  - fields:
    - `aggregate_types`
    - `functions`
    - `pending_entries`
    - `invalidated_entries`
  - invariants:
    - function coverage matches stage 12 exactly
    - scheduler state matches stage 12 exactly
  - pretty:
    - preserved program header, queue state, externals, call graph, and nested
      variable facts

## Edge cases

- aggregate layouts rooted in a parameter register that was also spilled to an
  argument-home slot
- local stack slots with no recovered scalar type
- saved-register slots that must stay absent from the source-level variable set
- absolute partitions with no stronger type than `word`
- leftover value partitions that stay as raw dereference variables
- optimized register-only parameters with no stack home
- aggregate roots that cannot be matched to a durable stack slot
- functions with zero recovered variables

## Pretty-print contract

### `FunctionVariableFacts`

- summary line:
  - `function 0xADDR name=<name-or-?> frame_size=<n-or-?> dynamic_sp=<yes|no> variables=<n> pending=[...]`
- `variables:` section
  - one deterministic `variable ...` header per recovered variable
  - aggregate-backed variables render nested `aggregate ...` and `field ...`
    lines using the stage-12 pretty contract

### `ProgramVariableFacts`

- header lines:
  - `root: 0xADDR`
  - `order: ...`
  - `pending: ...`
  - `invalidated: ...`
- `externals:` section
- `call_graph:` section
- `functions:` section
  - nested `FunctionVariableFacts` output

## End-to-end harness exposure

The persistent e2e harness should render every fixture binary through
`ProgramVariableFacts` and the variable pretty-printer.

Plausible output should show:

- stable parameter and local variables for stack-heavy `-O0` fixtures
- aggregate-backed parameter variables on the struct fixture
- no saved-register-only variables
- deterministic output across repeated runs

## Validation commands

Record the commands that should be used while iterating:

- stage tests:
  `poetry run pytest -q tests/posts/post_13_variables`
- e2e harness:
  `poetry run pytest -q tests/posts/post_13_variables/test_variables_e2e_harness.py`
- cli:
  `poetry run tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --func main --stage variables`
- ruff:
  `poetry run ruff check tiny_dec/analysis/highvars tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_13_variables`
- mypy:
  `poetry run mypy tiny_dec/analysis/highvars tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_13_variables`

## Resolved design decisions

- Range and interprocedural stages (14-15) operate on individual SSA values
  rather than requiring additional variable grouping across pointer aliases.
- The `indirect` bucket remains unsplit; no downstream stage required finer
  heap or pointer-member categories for the current pipeline scope.
