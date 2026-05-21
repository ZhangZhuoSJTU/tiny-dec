# Stage Contract: `post_15_interproc`

## Summary

- Stage name: `post_15_interproc`
- Owner directory: `tiny_dec/analysis/interproc/`
- Immediate predecessor: `post_14_range`
- Immediate successor: `post_16_structuring`

## Purpose

Recover a small, deterministic interprocedural summary layer on top of stage-14
range facts.

This stage turns the current per-function range, variable, memory, and call
evidence into program-level function summaries that later structuring and C
lowering stages can consume directly:

- infer conservative register-carried and stack-carried input prototypes plus
  register-carried returns
- classify internal functions as returning or no-return
- summarize simple memory side effects that stay attributable to absolute or
  indirect partitions
- emit explicit caller invalidation suggestions when a no-return callee is
  inferred

The goal is to surface stable cross-function facts honestly, not to build a
whole-program optimizer, infer variadics, or mutate the current CFG in place.

## Inputs

- `FunctionRangeFacts` from `tiny_dec.analysis.range.models`
- `ProgramRangeFacts` from `tiny_dec.analysis.range.models`
- embedded `FunctionVariableFacts`, `FunctionAggregateTypeFacts`,
  `FunctionScalarTypeFacts`, `FunctionMemoryFacts`, `FunctionStackFacts`,
  `FunctionCallFacts`, and `SSAFunctionIR` preserved through stage 14
- preserved upstream `pending_entries`, `invalidated_entries`, externals, and
  call graph metadata carried through stage 14

Assumptions:

- stage-14 function ordering, call graph ordering, and pretty-print stability
  are already deterministic
- stage-8 modeled callsites already classify targets as internal, external, or
  unresolved
- stage-13 parameter variables and stage-7 SSA live-ins are the current best
  local evidence for register-carried inputs
- non-negative stage-9 stack slots plus stage-13 stack-slot variables are the
  current best local evidence for internal stack-carried inputs
- observed internal call carriers may refine the shape, type, or name of one
  locally supported register-carried parameter, but they do not create a new
  parameter carrier on their own when the callee lacks local evidence for that
  register
- observed internal stack-argument offsets may refine one locally supported
  non-negative stack slot, but they do not create a new stack parameter on
  their own when the callee lacks local stack-slot evidence for that offset
- for internal functions with observed internal callers, root-value-only local
  parameter evidence may be pruned when no caller actually supplies that
  register carrier
- return carriers that are only compare-scratch register traffic, or that only
  forward an internal callee carrier the callee itself does not expose, should
  stay absent rather than being guessed into the prototype
- secondary internal return carriers may also be pruned when observed internal
  callers never consume the corresponding `CALL_RETURN` value outside plain
  return forwarding
- when a caller return carrier only forwards one single-register internal
  callee return carrier that the callee does expose, this stage may reuse the
  callee scalar type instead of leaving the caller carrier as an untyped word
- known stage-8 external signature hints may also suppress return carriers that
  only forward unsupported external `CALL_RETURN` registers through copies or
  phis
- unsupported prototype shapes such as variadics, calling convention changes,
  stack shapes without matching local slot evidence, and aggregate-by-value
  returns should stay absent rather than be guessed
- this stage does not rewrite blocks, split CFG edges, or rebuild earlier stage
  artifacts immediately; it only emits scheduler suggestions

## Outputs

- `PrototypeRegister`
  - one inferred register-carried parameter or return carrier
- `PrototypeStackParameter`
  - one inferred stack-carried parameter at one outgoing-call stack offset
- `InferredPrototype`
  - one conservative mixed input prototype plus register-carried returns for
    one function
- `FunctionEffectSummary`
  - one small memory-side-effect summary for one function
- `InterprocInvalidation`
  - one explicit caller reanalysis suggestion emitted by this stage
- `FunctionInterprocFacts`
  - one function-level interprocedural summary snapshot
- `ProgramInterprocFacts`
  - one program-level interprocedural summary snapshot

Output invariants:

- `ProgramInterprocFacts.functions` covers the stage-14 program functions exactly
- `ProgramInterprocFacts.pending_entries` preserves the stage-14 values unchanged
- `ProgramInterprocFacts.invalidated_entries` is deterministic, deduplicated,
  and contains at least the stage-14 invalidations
- `ProgramInterprocFacts.scheduler_invalidations` is unique by
  `(caller_entry, callee_entry, reason)` and ordered deterministically
- function parameter carriers are unique by register for register parameters,
  unique by stack offset for stack parameters, and ordered deterministically
- function return carriers are unique by register and ordered deterministically
- observed internal call carriers only refine already-supported parameter
  carriers; they do not invent new register-carried parameters without local
  evidence in the callee
- observed internal stack arguments only refine already-supported non-negative
  local stack slots; they do not invent stack parameters without local callee
  slot evidence
- internal-call observations can prune root-value-only local parameters when
  no observed caller supplies that register carrier
- return carriers are omitted when the only surviving evidence is compare
  scratch traffic, an unsupported internal-callee carrier, or an unsupported
  known external-callee carrier
- secondary internal return carriers are also omitted when observed internal
  callers never consume the corresponding call-return SSA value outside plain
  return forwarding
- directly forwarded single-register internal-callee return carriers may reuse
  the exposed callee scalar type when that is the only surviving source for
  the caller carrier
- function effect summaries only record absolute addresses or boolean indirect
  load/store markers; unsupported alias shapes stay absent

## Re-trigger and invalidation rules

- This stage is read-only with respect to earlier CFG, SSA, variable, and range
  artifacts.
- It does not discover new functions or emit new `pending_entries`.
- It preserves upstream `pending_entries` unchanged.
- If an internal callee is inferred as no-return, this stage emits one
  `InterprocInvalidation` per internal caller so a later scheduler pass can
  rebuild call modeling and downstream facts for that caller.
- `ProgramInterprocFacts.invalidated_entries` is the union of:
  - preserved stage-14 `invalidated_entries`
  - callers named in the stage-15 scheduler invalidations
- Prototype narrowing on its own does not currently emit invalidations; the
  stage records the prototype fact but leaves future callsite re-specialization
  to later work.

## Non-goals

- variadic prototype inference
- calling-convention inference
- aggregate-by-value parameter or return recovery
- transitive summary composition across the whole call graph
- interprocedural constant propagation
- alias-sensitive memory-effect summaries
- CFG rewriting for no-return callees inside this stage
- external-library signature databases

## Algorithm sketch

### program indexes

1. Start from one `ProgramRangeFacts`.
2. Build deterministic indexes for:
   - incoming internal callers by callee entry
   - internal callsites grouped by callee entry
   - stage-14 functions in discovery order

### function-local evidence

1. For each `FunctionRangeFacts`, gather local prototype evidence from:
   - stage-13 recovered parameter variables
   - stage-13 recovered stack-slot variables whose owning stage-9 slots sit at
     non-negative frame offsets
   - stage-7 ABI argument live-ins that are actually used by SSA operations,
     phi inputs, or memory-access values
   - stage-10 memory partitions and accesses for simple global/indirect effects
2. Capture return-register snapshots by walking SSA blocks in dominator-tree
   order and recording the current ABI return-register bindings at return
   blocks.
3. Suppress return carriers whose snapshots are only:
   - same-register live-ins mixed with compare-scratch constants or phis
   - internal call-return carriers for registers the inferred callee prototype
     does not expose
   - known external call-return carriers for registers the attached stage-8
     external signature does not expose
3. Infer `no_return=yes` when the upstream function has zero return blocks.

### interprocedural refinement

1. For each internal callee, gather observed incoming argument carriers from all
   modeled internal callsites that target that entry.
2. Combine local and incoming evidence conservatively:
   - parameter carriers start from local parameter evidence only
   - observed incoming carriers may refine size, scalar-type, or variable-name
     hints for registers that already have local support
   - observed incoming stack arguments may refine size, scalar-type, or
     variable-name hints for non-negative stack slots that already have local
     support
   - for internal functions with at least one observed incoming carrier,
     root-value-only local parameters are pruned if no caller supplies that
     register
   - return carriers come from return-block snapshots only, are pruned by the
     compare-scratch, unconsumed-secondary-internal-return, and
     unsupported-internal-callee checks, and become empty when `no_return=yes`
3. Attach scalar-type and variable-name hints only when they are already
   available from upstream facts, except that one directly forwarded
   single-register internal callee return may lend its already-inferred scalar
   type to the caller carrier.

### scheduler effects

1. For each internal function inferred as no-return, inspect the incoming
   internal-call map.
2. Emit one deterministic `InterprocInvalidation` per caller with reason
   `noreturn_callee`.
3. Preserve upstream `pending_entries`.
4. Build `invalidated_entries` as the deterministic union of upstream
   invalidations and the emitted caller invalidations.

Failure and bailout rules:

- unsupported prototype shapes stay absent rather than widened into fake
  carriers
- return carriers are omitted when no truthful SSA return snapshot exists
- malformed upstream invariants fail through model validation rather than silent
  normalization
- memory effects from non-absolute aliased partitions stay summarized only as
  indirect read/write booleans

## Data structures

- `PrototypeRegister`
  - owner: `tiny_dec/analysis/interproc/models.py`
  - fields:
    - `register`
    - `size`
    - `scalar_type`
    - `variable_name`
  - invariants:
    - register is non-negative
    - size is positive
    - scalar type size matches the carrier size when present
  - pretty:
    - `x10:4 type=int:4 name=arg_x10_4`
- `PrototypeStackParameter`
  - owner: `tiny_dec/analysis/interproc/models.py`
  - fields:
    - `stack_offset`
    - `size`
    - `scalar_type`
    - `variable_name`
  - invariants:
    - stack offset is non-negative
    - size is positive
    - scalar type size matches the carrier size when present
  - pretty:
    - `stack+0:4 type=int:4 name=local_0_4`
- `InferredPrototype`
  - owner: `tiny_dec/analysis/interproc/models.py`
  - fields:
    - `parameters`
    - `returns`
    - `no_return`
  - invariants:
    - register parameters are unique by register
    - stack parameters are unique by stack offset
    - parameter and return carriers are ordered deterministically
    - no-return prototypes have zero return carriers
  - pretty:
    - `prototype params=[x10:4 type=int:4, stack+0:4 type=int:4] returns=[x10:4 type=int:4] no_return=no`
- `FunctionEffectSummary`
  - owner: `tiny_dec/analysis/interproc/models.py`
  - fields:
    - `global_reads`
    - `global_writes`
    - `indirect_reads`
    - `indirect_writes`
  - invariants:
    - absolute-address lists are unique, sorted, and non-negative
  - pretty:
    - `effects reads=[0x2000] writes=[0x2004] indirect_reads=no indirect_writes=yes`
- `InterprocInvalidation`
  - owner: `tiny_dec/analysis/interproc/models.py`
  - fields:
    - `caller_entry`
    - `callee_entry`
    - `reason`
  - invariants:
    - entries are non-negative
    - reason is non-empty
  - pretty:
    - `invalidate caller=0x1000 callee=0x1100 reason=noreturn_callee`
- `FunctionInterprocFacts`
  - owner: `tiny_dec/analysis/interproc/models.py`
  - fields:
    - `ranges`
    - `prototype`
    - `effects`
  - invariants:
    - summary line stays derivable from the embedded stage-14 function facts
  - pretty:
    - one summary line plus prototype and effect sections
- `ProgramInterprocFacts`
  - owner: `tiny_dec/analysis/interproc/models.py`
  - fields:
    - `ranges`
    - `functions`
    - `scheduler_invalidations`
    - `pending_entries`
    - `invalidated_entries`
  - invariants:
    - function coverage matches stage 14 exactly
    - pending entries match stage 14 exactly
    - invalidated entries are the sorted union of upstream and scheduler-driven
      invalidations
  - pretty:
    - preserved program header, queue state, externals, call graph, scheduler
      invalidations, and nested function summaries

## Edge cases

- root-entry function with no internal callers
- internal callee with zero return blocks
- parameter register only visible through an argument-home stack slot
- return register passed through from a live-in instead of being freshly
  defined
- function that only touches absolute globals
- function that only touches indirect partitions
- external or unresolved callsites that should not create internal caller
  invalidations
- upstream invalidations that must remain visible after stage 15 adds its own

## Pretty-print contract

### `FunctionInterprocFacts`

- summary line:
  - `function 0xADDR name=<name-or-?> frame_size=<n-or-?> dynamic_sp=<yes|no> params=<n> returns=<n> no_return=<yes|no> globals_read=<n> globals_written=<n> pending=[...]`
- `prototype:` section
  - one deterministic `param ...` line per parameter carrier
  - one deterministic `return ...` line per return carrier
- `effects:` section
  - one `effects ...` line

### `ProgramInterprocFacts`

- header lines:
  - `root: 0xADDR`
  - `order: ...`
  - `pending: ...`
  - `invalidated: ...`
- `externals:` section
- `call_graph:` section
- `scheduler_invalidations:` section
- `functions:` section
  - nested `FunctionInterprocFacts` output

## End-to-end harness exposure

The persistent e2e harness should render every fixture binary through
`ProgramInterprocFacts` and the interproc pretty-printer.

Plausible output should show:

- stable inferred parameter carriers on simple helper functions
- explicit `no_return=yes` when a function lacks return blocks in the current
  IR
- deterministic global read/write summaries for fixtures with absolute data
  accesses
- deterministic caller invalidation lines whenever a no-return internal callee
  appears

## Validation commands

Record the commands that should be used while iterating:

- stage tests:
  `poetry run pytest -q tests/posts/post_15_interproc`
- e2e harness:
  `poetry run pytest -q tests/posts/post_15_interproc/test_interproc_e2e_harness.py`
- cli:
  `poetry run tiny-dec decompile tests/fixtures/bin/fixture_loop_O0_nopie.elf --func main --stage interproc`
- ruff:
  `poetry run ruff check tiny_dec/analysis/interproc tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_15_interproc`
- mypy:
  `poetry run mypy tiny_dec/analysis/interproc tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_15_interproc`

## Open questions

- whether later callsite re-specialization should invalidate callers for
  prototype narrowing as well as no-return
- whether external-only prototype inference should become a first-class output
  instead of staying implicit in modeled callsites
