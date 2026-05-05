# Stage Contract: `post_08_calls`

## Summary

- Stage name: `post_08_calls`
- Owner directory: `tiny_dec/analysis/calls/`
- Immediate predecessor: `post_07_ssa`
- Immediate successor: `post_09_stack`

## Purpose

Turn raw call instructions plus stage-6 and stage-7 facts into a deterministic
call model that downstream stages can consume.

This stage is the first place where a call boundary gets semantic shape:

- classify callsites as internal, external, or unresolved
- preserve whether the call was direct or indirect
- preserve one explicit indirect callee carrier value when a `CALLIND` input
  can be traced through trivial same-instruction forwarding ops
- attach fixed RV32I ABI carrier sets
- snapshot currently-known SSA argument carrier values at the callsite
- snapshot currently-known outgoing stack argument values at the callsite
- snapshot the coarse low-level memory version before and after the callsite
- snapshot currently-known SSA return carrier defs after the callsite
- attach optional known external-signature hints for a small curated libc subset
- expose conservative return and clobber assumptions
- refine the program-level call graph and pending-function queue

This stage should stay small and explicit. It is not prototype inference,
summary generation, or interprocedural fixed-point analysis.

## Inputs

- `SSAFunctionIR` from `tiny_dec.analysis.ssa.models`
- `SSAProgramIR` from `tiny_dec.analysis.ssa.models`
- preserved stage-4 raw callsites and direct call graph through the embedded
  canonical/dataflow/SSA wrappers
- preserved stage-6 `pending_entries`, `invalidated_entries`, and recovered
  `CALLIND` targets through the embedded dataflow facts

Assumptions:

- SSA renaming is already stable and deterministic
- stage-7 trivial-phi and identity-copy normalization has already run, so this
  stage consumes the surviving SSA carrier values rather than pre-normalized
  aliases
- stage-7 may also rewrite later uses of trivial register-forwarding copies to
  the forwarded SSA value while preserving the explicit register copy op, so
  carrier snapshots may point at the forwarded SSA value instead of the
  transient copied register name
- stage-6 recovered indirect call targets are the only new callee facts
  available at this point
- RV32I ILP32 call carriers are modeled conservatively with a fixed ABI in this
  stage
- when stage 4 can only identify a direct self-targeting unresolved call and
  the loader still exposes ordered undefined external names, that direct edge
  may already arrive here as a deterministic named external
- this stage may enqueue newly discovered candidate callees, but it does not
  itself reopen posts 01-04 or mutate the caller CFG

## Outputs

- `CallABI`
  - fixed ABI carrier model used by this stage
- `CallRegisterValue`
  - one currently-known SSA value bound to one ABI register at one callsite
- `CallStackValue`
  - one currently-known SSA value stored at one outgoing stack-argument offset
    at one callsite
- `KnownExternalSignature`
  - one curated external signature hint attached to a named external callee
- `ModeledCallSite`
  - one typed callsite with target classification, carrier snapshot, and
    coarse memory snapshot
- `FunctionCallFacts`
  - one function-level call analysis snapshot
- `ProgramCallFacts`
  - one program-level call analysis snapshot with refined call graph and queue
    suggestions

Output invariants:

- callsite order matches upstream `FunctionIR.callsites` instruction order
- direct callsite identity is preserved from stage 4
- indirect callsites only become target-resolved when stage 6 recovered a
  constant `CALLIND` target at the same instruction
- indirect callsites may preserve one explicit `indirect_target_value` when
  the `CALLIND` input can be traced through trivial same-instruction
  forwarding such as `COPY`, add-zero, or the low-bit-clearing mask emitted
  for `jalr`
- when that explicit indirect callee carrier is present, the same SSA value is
  omitted from the ordinary ABI register-argument snapshot rather than being
  counted as both callee and argument
- argument carrier values are ordered by ABI register number and only include
  registers whose current SSA value is known in this stage
- when one register is only forwarding another SSA register through a trivial
  surviving `COPY`, the snapshot may bind the written carrier to the forwarded
  SSA value rather than the transient copy output
- outgoing stack argument values are ordered by non-negative byte offset from
  the call-time stack pointer and only include stores whose address is a known
  constant `sp`-relative slot at the callsite and whose slot is not later
  reloaded by the caller into the same register base that was originally saved
  there
- coarse memory snapshots come from the stage-7 low-level memory SSA state, not
  from stack slots, partitions, or effect summaries
- return carrier values are ordered by ABI register number and only include
  registers whose current SSA value is known after synthetic stage-7
  `CALL_RETURN` defs
- known external signatures only appear for named external callees that match
  the curated stage-8 signature table; unknown externals remain unspecialized
- program-level call graph order matches function discovery order, then modeled
  callsite order for the subset of callsites with a concrete target address
- `ProgramCallFacts.pending_entries` is deterministic and deduplicated
- `ProgramCallFacts.invalidated_entries` preserves upstream invalidation
  suggestions; this stage does not introduce CFG invalidation on its own

## Re-trigger and invalidation rules

- If this stage classifies a callsite as an internal callee whose entry address
  is not already present in the program and is not known external metadata, it
  emits that entry in `pending_entries`.
- Those `pending_entries` mean: rerun posts 01-04 for that callee entry, then
  rebuild later stage artifacts for the affected program view.
- This stage does not reopen the caller function's stage-3 CFG.
- This stage does not emit new `invalidated_entries`; it preserves stage-6
  invalidation suggestions unchanged.
- If a later stage such as interprocedural summary inference changes call
  prototypes or no-return status, that later stage should rerun call modeling.
  That is outside post 08 itself.

## Non-goals

- parameter count inference
- no-return inference
- calling-convention inference
- memory-side-effect modeling
- indirect call solving beyond preserved stage-6 recovered constant targets
- interprocedural fixed-point iteration
- incoming stack-parameter declaration recovery for internal callees
- mutation of upstream IR, CFGs, or the function-discovery worklist scheduler

## Algorithm sketch

### ABI model

1. Use one fixed RV32I ILP32 ABI model:
   - argument carriers: `x10` through `x17`
   - return carriers: `x10`, `x11`
   - clobbered registers: `x1`, `x5`-`x7`, `x10`-`x17`, `x28`-`x31`
2. Do not infer prototypes yet; the ABI is a conservative surface contract only.

### Function-local call modeling

1. Start from one `SSAFunctionIR`.
2. Build a direct call-edge map from the preserved stage-4 program call graph
   using `(caller, callsite_address)` as the key.
3. Build a recovered indirect-call target map from stage-6 recovered targets
   using instruction address as the key.
4. Traverse SSA blocks in dominator-tree order while maintaining the current SSA
   register binding map plus the current coarse memory version:
   - seed the traversal with version-0 `live_ins`
   - apply surviving block phi outputs first
   - walk instructions in address order
   - update the current register binding after each SSA register definition
   - for a trivial surviving register `COPY` whose input is already an SSA
     value, bind the written carrier to that forwarded value so downstream
     snapshots do not keep a needless alias
5. When a `CALL` or `CALLIND` op is encountered:
   - identify the callsite
   - classify the target as `internal`, `external`, or `unresolved`
   - for `CALLIND`, preserve one explicit indirect callee carrier value when
     the target input can be traced through trivial same-instruction
     forwarding such as `COPY`, add-zero, or the `jalr` low-bit-clearing mask
   - snapshot currently-known argument carrier values from the current register
     map for `x10`-`x17`
   - when that explicit indirect callee carrier value is present, omit the
     same SSA value from the ordinary ABI register-argument snapshot
   - snapshot currently-known outgoing stack argument values from the current
     stack-relative store map for non-negative `sp` offsets, excluding slots
     later reloaded by the caller into the same register base that was stored
     there
   - snapshot the current coarse memory version before the call op
   - continue applying SSA register defs for the rest of the instruction so the
     synthetic stage-7 `CALL_RETURN` and `CALL_CLOBBER` defs become current and
     the low-level call op exposes its later memory version
   - snapshot currently-known return carrier values from the current register
     map for `x10` and `x11`
   - snapshot the current coarse memory version after the call op
   - if the callee is a named external in the curated signature table, attach
     that signature hint
   - attach the fixed ABI return and clobber sets
6. Record per-function pending internal callees not already present in the
   program or external metadata.

### Program aggregation

1. Analyze functions in program discovery order.
2. Build the refined program call graph from the modeled callsites.
3. Compute `pending_entries` as the union of:
   - preserved stage-6 pending entries
   - newly modeled internal callees not already known in the program or loader
     external metadata
4. Preserve stage-6 `invalidated_entries` unchanged.
5. Emit program call-graph edges only for modeled callsites with a concrete
   target address.

Failure and bailout rules:

- if SSA invariants are malformed, fail through model validation rather than
  silently normalizing
- if a callsite cannot be matched to a concrete target, keep it `unresolved`
- if an argument carrier does not have a current SSA binding, omit it from the
  captured callsite snapshot rather than fabricating a value
- if a store address cannot be proven to be a constant current-`sp` offset,
  omit it from the outgoing stack-argument snapshot rather than guessing
- if a stack slot is later reloaded by the caller after the callsite, omit it
  from the outgoing stack-argument snapshot when that reload restores the same
  register base that was stored there, rather than guessing that it is an
  outgoing argument instead of saved frame state

## Data structures

- `CallABI`
  - owner: `tiny_dec/analysis/calls/models.py`
  - fields:
    - `name`
    - `argument_registers`
    - `return_registers`
    - `clobbered_registers`
  - invariants:
    - register lists are unique and sorted
  - pretty:
    - `rv32i_ilp32 args=[x10, x11, ...] returns=[x10, x11] clobbers=[...]`
- `CallRegisterValue`
  - owner: `tiny_dec/analysis/calls/models.py`
  - fields:
    - `register`
    - `value`
  - invariants:
    - one register appears at most once per callsite snapshot
  - pretty:
    - `x10=x10_4:4`
- `CallStackValue`
  - owner: `tiny_dec/analysis/calls/models.py`
  - fields:
    - `stack_offset`
    - `value`
  - invariants:
    - stack offsets are non-negative and unique per callsite snapshot
  - pretty:
    - `stack+0=x18_1:4`
- `KnownExternalSignature`
  - owner: `tiny_dec/analysis/calls/models.py`
  - fields:
    - `name`
    - `parameter_registers`
    - `parameter_stack_offsets`
    - `return_registers`
    - `no_return`
  - invariants:
    - register and stack-offset lists are deterministic and unique
  - pretty:
    - `malloc regs=[x10] stack=[] returns=[x10] no_return=no`
- `ModeledCallSite`
  - owner: `tiny_dec/analysis/calls/models.py`
  - fields:
    - `instruction_address`
    - `block_start`
    - `target_kind`
    - `target_address`
    - `callee_name`
    - `is_indirect`
    - `resolved_from_recovered_target`
    - `indirect_target_value`
    - `argument_values`
    - `stack_argument_values`
    - `memory_before`
    - `memory_after`
    - `return_values`
    - `external_signature`
  - invariants:
    - instruction and block addresses are non-negative
    - argument values are unique by register and sorted
    - stack argument values are unique by offset and sorted
    - return values are unique by register and sorted
    - when `memory_after` is present, `memory_before` is present
    - `resolved_from_recovered_target` only applies to indirect calls
    - `indirect_target_value` only appears on indirect callsites
  - pretty:
    - `call 0x1112c block=0x1111c via=direct -> internal 0x1100 name=helper args=[x10=x10_5:4] stack_args=[stack+0=x18_1:4] mem=[m1 -> m2] returns=[x10=x10_6:4, x11=x11_2:4]`
    - `call 0x11108 block=0x110d4 via=indirect -> unresolved target_value=x12_1:4 args=[x10=x10_5:4, x11=x11_2:4] stack_args=[stack+0=x10_3:4] mem=[m5 -> m6] returns=[x10=x10_6:4, x11=x11_3:4]`
- `FunctionCallFacts`
  - owner: `tiny_dec/analysis/calls/models.py`
  - fields:
    - `ssa`
    - `abi`
    - `callsites`
    - `pending_entries`
  - invariants:
    - callsites follow upstream function callsite order exactly
    - `pending_entries` is unique and sorted
  - pretty:
    - function summary
    - ABI line
    - pending-entry line
    - modeled callsite list
- `ProgramCallFacts`
  - owner: `tiny_dec/analysis/calls/models.py`
  - fields:
    - `ssa`
    - `abi`
    - `functions`
    - `call_graph`
    - `pending_entries`
    - `invalidated_entries`
  - invariants:
    - functions cover the SSA program functions exactly
    - call graph order is deterministic
    - pending and invalidated entries are unique
  - pretty:
    - preserved program header
    - ABI line
    - refined call graph
    - pending and invalidated lines
    - nested function call facts

## Edge cases

- function with no callsites
- direct internal call to an already discovered function
- direct self-targeting unresolved call that must fall back to an ordered
  undefined external name
- direct call preserved as unresolved from stage 4
- indirect call with no recovered target
- indirect call with a recovered internal target not yet in the program
- indirect call with a recovered target that matches external loader metadata
- call passing a ninth-or-later argument through `sp+0`, `sp+4`, ...
- callsite at a block entered through phi nodes, where argument carriers come
  from phi outputs
- callsite at a block entered through a memory phi, where the coarse memory
  snapshot comes from the merged memory state
- multiple callsites in one block

## Pretty-print contract

### `FunctionCallFacts`

- summary line:
  - `function 0xADDR name=<name-or-?> callsites=<n> pending=[...]`
- ABI line:
  - `abi: rv32i_ilp32 args=[...] returns=[...] clobbers=[...]`
  - `callsites:` section
  - one deterministic line per modeled callsite in instruction order
  - each line includes:
    - instruction address
    - block start
    - direct or indirect marker
    - target classification
    - target address and name when known
    - explicit indirect callee carrier value when preserved
    - captured SSA argument carrier values
    - captured outgoing stack argument values
    - captured SSA return carrier values

### `ProgramCallFacts`

- header lines:
  - `root: 0xADDR`
  - `order: ...`
  - `pending: ...`
  - `invalidated: ...`
- ABI line
- `externals:` section
- `call_graph:` section
    - one `CallGraphEdge` line per modeled edge with a concrete target address
- `functions:` section
  - nested `FunctionCallFacts` output

## End-to-end harness exposure

The persistent fixture harness should render `calls:program:` for every fixture
binary. Plausible output should show:

- stable function order
- stable callsite order inside each function
- internal or named external calls where the current pipeline really knows them
- unresolved calls where the current pipeline still lacks enough information
- pending entries only when a new internal callee candidate was found

## Validation commands

Record the commands that should be used while iterating:

- stage tests: `poetry run pytest -q tests/posts/post_08_calls`
- e2e harness: `poetry run pytest -q tests/posts/post_08_calls/test_calls_e2e_harness.py`
- ruff: `poetry run ruff check tiny_dec/analysis/calls tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_08_calls`
- mypy: `poetry run mypy tiny_dec/analysis/calls tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_08_calls`

## Open questions

- Whether a later slice should turn outgoing stack-argument snapshots into
  durable incoming stack-parameter declarations for internal callees without
  inventing semantics in the printer.
