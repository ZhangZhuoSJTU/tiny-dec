# Stage Contract: `post_14_range`

## Summary

- Stage name: `post_14_range`
- Owner directory: `tiny_dec/analysis/range/`
- Immediate predecessor: `post_13_variables`
- Immediate successor: `post_15_interproc`

## Purpose

Recover a small, deterministic value-range and branch-predicate refinement layer
on top of stage-13 variable facts.

This stage turns the current SSA, scalar, and recovered-variable evidence into
stable integer-interval facts that later interprocedural and structuring stages
can consume directly:

- recover conservative integer ranges for SSA values
- project those ranges onto recovered variables
- recover edge-specific branch refinements for a small comparison subset
- preserve the current scheduler state unchanged

The goal is to expose plausible numeric constraints honestly, not to introduce a
heavy abstract-interpretation framework, prove exact loop bounds, or normalize
the whole program into symbolic expressions.

## Inputs

- `FunctionVariableFacts` from `tiny_dec.analysis.highvars.models`
- `ProgramVariableFacts` from `tiny_dec.analysis.highvars.models`
- embedded `FunctionAggregateTypeFacts`, `FunctionScalarTypeFacts`,
  `FunctionMemoryFacts`, `FunctionStackFacts`, `FunctionCallFacts`, and
  `SSAFunctionIR` preserved through stage 13
- preserved upstream `pending_entries`, `invalidated_entries`, externals, and
  call graph metadata carried through stage 13

Assumptions:

- stage-13 variables are already deterministic and preserve the stage-12
  aggregates, stage-11 scalar facts, and stage-10 memory partitions exactly
- stage-7 SSA naming is stable and deterministic
- ranges are currently modeled as signed closed intervals with optional lower
  and upper bounds
- unsupported arithmetic or mixed-width reasoning should stay absent rather than
  be guessed into a stronger range fact
- this stage does not rewrite SSA, mutate variables, or change scheduler state

## Outputs

- `IntegerRange`
  - one conservative signed interval with optional bounds
- `ValueRangeFact`
  - one SSA value plus its recovered interval
- `VariableRangeFact`
  - one recovered variable plus its recovered interval
- `BranchRangeRefinement`
  - one branch edge plus an interval refinement implied for one value on that
    edge
- `FunctionRangeFacts`
  - one function-level range snapshot
- `ProgramRangeFacts`
  - one program-level range snapshot preserving scheduler state

Output invariants:

- `ProgramRangeFacts.functions` covers the stage-13 program functions exactly
- `ProgramRangeFacts.pending_entries` and `invalidated_entries` preserve the
  stage-13 values unchanged
- value-range facts are unique by SSA value and ordered deterministically
- variable-range facts are unique by variable name and ordered deterministically
- branch refinements are unique by `(block_start, successor, value, sense)` and
  ordered deterministically
- branch refinements only record intervals that are actually implied by one
  supported predicate form

## Re-trigger and invalidation rules

- This stage is read-only with respect to earlier stages.
- It does not discover new functions, blocks, edges, or call targets.
- It does not emit new `pending_entries` or `invalidated_entries`.
- It preserves the stage-13 scheduler state unchanged so later stages can still
  observe the current queue suggestions.

## Non-goals

- full symbolic simplification
- relational range domains across multiple values
- alias-aware numeric reasoning
- memory-state abstract interpretation
- exact loop-trip-count inference
- proving exclusion sets such as “all values except N”
- rewriting branch structure or stage-13 variable groups

## Algorithm sketch

### supporting indexes

1. Start from one `FunctionVariableFacts`.
2. Build deterministic maps for:
   - scalar types by SSA value
   - recovered variables by name and by root SSA value
   - the current function's SSA blocks in deterministic order
   - compare-output metadata for supported predicate-producing ops

### SSA value ranges

1. Seed initial ranges from:
   - constants -> exact intervals
   - bool-typed SSA values -> `[0, 1]`
   - compare and boolean-negate outputs -> `[0, 1]`
2. Iterate to a fixpoint over SSA blocks in deterministic order.
3. Support a small arithmetic subset:
   - `COPY`
   - phi nodes by interval union over currently-known inputs, with widening on
     repeatedly-growing loop-carried bounds
   - `INT_ADD` with either two known intervals or one known interval and one
     exact constant
   - `INT_SUB` with one known interval and one exact constant
   - `INT_AND` with a non-negative constant mask
   - partition-local load propagation from stage-10 memory partitions once a
     partition already has known access-value ranges
4. Leave unsupported operations absent rather than widening them into fake
   precision.

### variable ranges

1. For each recovered variable, gather candidate ranges from:
   - the variable root SSA value, when one exists and has a value-range fact
   - memory access values on the variable's supporting partitions
   - bool scalar types, which imply `[0, 1]`
2. Union those candidate intervals into one deterministic variable interval.
3. Omit the variable range entirely when no truthful interval can be recovered.

### branch refinements

1. Record supported compare outputs while scanning SSA:
   - `INT_SLESS`
   - `INT_LESS`
   - `INT_EQUAL`
   - `INT_NOTEQUAL`
2. When a `CBRANCH` consumes one recorded compare output, inspect the owning
   block successors.
3. Recover edge-specific refinements only when one compare operand is a tracked
   SSA value and the other is a constant:
   - `x < c` true edge -> `x <= c - 1`
   - `x < c` false edge -> `x >= c`
   - `x == c` true edge -> `x == c`
   - `x != 0` over bool-like values may refine to `[1, 1]` / `[0, 0]`
4. Omit predicate forms that do not map cleanly to one interval.

Failure and bailout rules:

- unsupported arithmetic leaves no new fact instead of a guessed interval
- phis with no currently-known inputs stay absent until some incoming evidence
  exists
- branch refinements are omitted when the compare cannot be reduced to one
  tracked value plus one constant
- malformed upstream invariants fail through model validation rather than silent
  normalization

## Data structures

- `IntegerRange`
  - owner: `tiny_dec/analysis/range/models.py`
  - fields:
    - `lower`
    - `upper`
  - invariants:
    - at least one bound is present
    - `lower <= upper` when both are present
  - pretty:
    - `[0, 1]`
    - `[-inf, 9]`
    - `[4, +inf]`
- `ValueRangeFact`
  - owner: `tiny_dec/analysis/range/models.py`
  - fields:
    - `value`
    - `value_range`
  - invariants:
    - facts are unique by value inside one function
  - pretty:
    - `value x10_0:4 range=[0, 10]`
- `VariableRangeFact`
  - owner: `tiny_dec/analysis/range/models.py`
  - fields:
    - `variable`
    - `value_range`
  - invariants:
    - facts are unique by variable name inside one function
  - pretty:
    - `variable arg_x10_4 range=[0, 10]`
- `BranchRangeRefinement`
  - owner: `tiny_dec/analysis/range/models.py`
  - fields:
    - `block_start`
    - `successor`
    - `sense`
    - `source_opcode`
    - `value`
    - `value_range`
  - invariants:
    - addresses are non-negative
    - refinements are unique by branch edge, value, and sense
  - pretty:
    - `branch 0x1000 -> 0x1008 sense=true source=INT_SLESS value=x10_0:4 range=[-inf, 9]`
- `FunctionRangeFacts`
  - owner: `tiny_dec/analysis/range/models.py`
  - fields:
    - `variables`
    - `value_ranges`
    - `variable_ranges`
    - `branch_refinements`
  - invariants:
    - ordering is deterministic across all nested facts
  - pretty:
    - summary line with frame size, dynamic-stack marker, value-range count,
      variable-range count, branch-refinement count, and preserved per-function
      pending entries
- `ProgramRangeFacts`
  - owner: `tiny_dec/analysis/range/models.py`
  - fields:
    - `variables`
    - `functions`
    - `pending_entries`
    - `invalidated_entries`
  - invariants:
    - function coverage matches stage 13 exactly
    - scheduler state matches stage 13 exactly
  - pretty:
    - preserved program header, queue state, externals, call graph, and nested
      range facts

## Edge cases

- bool-typed values that never receive explicit compare outputs
- phi nodes that merge exact constants into a wider interval
- stack variables whose accesses carry multiple SSA versions
- loops that force interval union at phi nodes
- comparisons against constants on both taken and fallthrough edges
- unsupported predicates that should stay absent
- functions with zero recoverable range facts

## Pretty-print contract

### `FunctionRangeFacts`

- summary line:
  - `function 0xADDR name=<name-or-?> frame_size=<n-or-?> dynamic_sp=<yes|no> value_ranges=<n> variable_ranges=<n> branch_refinements=<n> pending=[...]`
- `variables:` section
  - one deterministic `variable ...` line per variable-range fact
- `values:` section
  - one deterministic `value ...` line per value-range fact
- `branches:` section
  - one deterministic `branch ...` line per branch refinement

### `ProgramRangeFacts`

- header lines:
  - `root: 0xADDR`
  - `order: ...`
  - `pending: ...`
  - `invalidated: ...`
- `externals:` section
- `call_graph:` section
- `functions:` section
  - nested `FunctionRangeFacts` output

## End-to-end harness exposure

The persistent e2e harness should render every fixture binary through
`ProgramRangeFacts` and the range pretty-printer.

Plausible output should show:

- `[0, 1]` style bool ranges where the current scalar surface already proves
  them
- branch refinement lines on compare-heavy fixtures such as loops
- stable variable-range lines for stack-backed locals and parameters when their
  access values stay numerically constrained
- deterministic output across repeated runs

## Validation commands

Record the commands that should be used while iterating:

- stage tests:
  `poetry run pytest -q tests/posts/post_14_range`
- e2e harness:
  `poetry run pytest -q tests/posts/post_14_range/test_range_e2e_harness.py`
- cli:
  `poetry run tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --func main --stage range`
- ruff:
  `poetry run ruff check tiny_dec/analysis/range tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_14_range`
- mypy:
  `poetry run mypy tiny_dec/analysis/range tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_14_range`

## Open questions

- whether later interprocedural work will want unsigned or wraparound-specific
  range domains in addition to the current signed interval view
- whether later stages should project branch refinements onto recovered
  variables more directly instead of keeping them keyed by SSA values
