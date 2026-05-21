# Stage Contract: `post_06_dataflow`

## Summary

- Stage name: `post_06_dataflow`
- Owner directory: `tiny_dec/analysis/dataflow/`
- Immediate predecessor: `post_05_simplify`
- Immediate successor: `post_07_ssa`

## Purpose

Provide the first reusable intraprocedural dataflow facts on top of canonical
IR, and recover indirect branch or call targets when they reduce to constants.

This stage deliberately does **not** introduce a generic heavyweight framework.
It uses:

- an explicit monotone forward worklist over canonical basic blocks
- a tiny constant lattice for register state
- per-instruction temporary evaluation only inside one instruction

This matches the current repository need: teach dataflow foundations and expose
target-recovery facts without pretending memory modeling, SSA, or interprocedural
reasoning already exist.

## Inputs

- `CanonicalProgramIR` from `tiny_dec.analysis.simplify.models`
- `CanonicalFunctionIR` from `tiny_dec.analysis.simplify.models`
- deterministic canonical block order, successor edges, and program-level call
  graph metadata

Assumptions:

- stage-5 canonical IR is already deterministic
- canonical block topology is the current CFG source of truth
- indirect target recovery is currently limited to values derivable from local
  register and per-instruction `unique` facts
- memory loads and stores are not modeled yet

## Outputs

- `RegisterState`
  - block-entry or block-exit constant facts for non-`x0` registers
- `RecoveredTarget`
  - one constant indirect branch or indirect call target discovered by dataflow
- `BlockDataflowFacts`
  - one block plus its `in` and `out` states and recovered targets
- `FunctionDataflowFacts`
  - one canonical function plus all block facts and recovered targets
- `ProgramDataflowFacts`
  - one canonical program plus per-function facts and queue suggestions for
    earlier-stage reanalysis

Output invariants:

- block order mirrors the upstream canonical function exactly
- block `in` and `out` states are the fixpoint result of the monotone merge
  operator for the current lattice
- `x0` is treated as an implicit constant zero and is never materialized in
  stored register maps
- recovered targets only come from `BRANCHIND` or `CALLIND` whose resolved input
  value is constant after local instruction evaluation
- `pending_entries` only contains new indirect call targets not already known as
  discovered functions or externals
- `invalidated_entries` only contains functions whose recovered branch targets
  require a CFG rebuild

## Non-goals

- a generic multi-analysis framework
- interprocedural fixpoint iteration
- memory-state abstraction
- stack-slot, alias, or heap reasoning
- SSA construction
- path-sensitive branch refinement
- actually reopening disassembly or mutating the CFG in this stage

## Algorithm sketch

### lattice and merge

- domain per register:
  - unknown
  - constant 32-bit value
- block reachability:
  - unreachable
  - reachable with a register-state map

Merge rule:

1. unreachable merged with reachable yields the reachable side
2. reachable merged with reachable keeps only registers whose constant value
   agrees on both sides
3. disagreement drops the register fact to unknown

### per-instruction transfer

1. Start from the block input register state.
2. For each instruction:
   - start a fresh local map for `unique` varnodes
   - evaluate p-code ops in order
   - propagate constant facts through:
     - `COPY`
     - integer arithmetic and logic ops
     - comparisons
     - extensions and `SUBPIECE`
   - treat `LOAD` results as unknown
   - ignore `STORE` for state propagation
   - treat `CALL`, `CALLIND`, and `CALLOTHER` as killing non-`x0` register facts
3. When encountering `BRANCHIND` or `CALLIND`, try to evaluate the target input:
   - if constant, emit a `RecoveredTarget`
   - otherwise emit no recovery fact
4. Finish with the block output register state.

### function analysis

1. Seed entry-block `in` state as reachable with an empty explicit register map.
2. Run a forward worklist over canonical block successors.
3. Recompute block output facts until no block `out` state changes.
4. Materialize deterministic block facts in canonical discovery order.
5. Aggregate recovered targets in block order, then instruction order.

### program analysis

1. Analyze each discovered canonical function independently.
2. Preserve program discovery order, externals, and direct call graph metadata.
3. Derive queue suggestions:
   - recovered indirect call target not already known:
     - add to `pending_entries`
   - recovered indirect branch target not already a known block start:
     - add the owning function entry to `invalidated_entries`
4. Materialize `ProgramDataflowFacts`.

Failure and bailout rules:

- unsupported p-code opcodes become unknown facts rather than hard failures
- unresolved indirect targets stay absent from `RecoveredTarget`
- this stage records queue suggestions; it does not mutate upstream IR

## Data structures

- `RegisterState`
  - owner: `tiny_dec/analysis/dataflow/models.py`
  - fields:
    - `reachable`
    - `known_registers`
  - invariants:
    - stored register keys are non-negative
    - `x0` is implicit and must not appear in `known_registers`
    - values are masked to 32 bits
  - pretty:
    - reachable empty state: `<empty>`
    - reachable facts: `xREG=0xVALUE, ...`
    - unreachable state: `<unreachable>`
- `RecoveredTargetKind`
  - owner: `tiny_dec/analysis/dataflow/models.py`
  - values:
    - `branch`
    - `call`
- `RecoveredTarget`
  - owner: `tiny_dec/analysis/dataflow/models.py`
  - fields:
    - `instruction_address`
    - `block_start`
    - `kind`
    - `target`
  - pretty:
    - `recover <kind> 0xINSN -> 0xTARGET`
- `BlockDataflowFacts`
  - owner: `tiny_dec/analysis/dataflow/models.py`
  - fields:
    - `start`
    - `in_state`
    - `out_state`
    - `recovered_targets`
  - invariants:
    - `start` references a known canonical block
    - recovered targets are deterministic and unique by
      `(instruction_address, kind, target)`
  - pretty:
    - canonical block header plus `in=` and `out=` state text
- `FunctionDataflowFacts`
  - owner: `tiny_dec/analysis/dataflow/models.py`
  - fields:
    - `function`
    - `blocks`
    - `recovered_targets`
  - invariants:
    - block facts cover the canonical function's blocks exactly
    - recovered target ordering matches canonical block/instruction order
  - pretty:
    - function summary
    - `recovered_targets:` section
    - `blocks:` section
- `ProgramDataflowFacts`
  - owner: `tiny_dec/analysis/dataflow/models.py`
  - fields:
    - `program`
    - `functions`
    - `pending_entries`
    - `invalidated_entries`
  - invariants:
    - function facts cover the canonical program's discovered functions exactly
    - queue suggestions are deterministic and unique
  - pretty:
    - program header
    - queue suggestions
    - preserved externals and call graph
    - nested function facts

## Edge cases

- unreachable blocks
- joins where constants agree vs disagree
- writes to `x0`
- `CALLIND` or `BRANCHIND` fed by local `unique` temporaries
- direct calls and direct branches, which must not be reported as recovered
  targets
- loads that erase otherwise known register facts
- call instructions that kill register facts
- recovered target equal to an existing block start or known function entry

## Pretty-print contract

### `FunctionDataflowFacts`

- summary line:
  - `function 0xADDR name=<name-or-?> blocks=<n> recovered=<n>`
- `recovered_targets:` section
  - one line per recovered target in deterministic order
- `blocks:` section
  - one line per canonical block:
    - `block 0xADDR term=<kind> succ=[...] in=[...] out=[...]`
  - optional indented recovered-target lines under the owning block

### `ProgramDataflowFacts`

- header lines:
  - `root: 0xADDR`
  - `order: 0xADDR, ...`
  - `pending: 0xADDR, ...`
  - `invalidated: 0xADDR, ...`
- `externals:` section
- `call_graph:` section
- `functions:` section
  - nested `FunctionDataflowFacts` snapshots in program discovery order

Pretty output must be deterministic across repeated runs over the same input.

## End-to-end harness exposure

The post-06 e2e harness should iterate all fixture binaries, resolve the root
function, build `ProgramDataflowFacts`, and render the deterministic snapshot.

The snapshot should make it obvious:

- which blocks are reachable
- what constant register facts survive into and out of each block
- whether any indirect targets were recovered
- which earlier-stage queue suggestions are now populated

## CLI exposure

Post 06 adds a `dataflow` debug surface:

- `tiny-dec decompile <binary> --stage dataflow [--func <selector>]`
  - renders the program-level dataflow facts rooted at the selected function

## Validation commands

- stage tests:
  - `poetry run pytest -q tests/posts/post_06_dataflow`
- e2e harness:
  - `poetry run pytest -q tests/posts/post_06_dataflow/test_dataflow_e2e_harness.py`
- ruff:
  - `poetry run ruff check tiny_dec/analysis/dataflow tiny_dec/cli.py tiny_dec/pipeline tests/posts/post_06_dataflow`
- mypy:
  - `poetry run mypy tiny_dec/analysis/dataflow tiny_dec/cli.py tiny_dec/pipeline tests/posts/post_06_dataflow`

## Open questions

- Whether a later stage should retain this constant-state analysis as a helper
  beneath richer range or memory abstractions, or replace it with a broader
  abstract-value lattice once those stages exist.
