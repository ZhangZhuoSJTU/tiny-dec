# Stage Contract: `post_07_ssa`

## Summary

- Stage name: `post_07_ssa`
- Owner directory: `tiny_dec/analysis/ssa/`
- Immediate predecessor: `post_06_dataflow`
- Immediate successor: `post_08_calls`

## Purpose

Convert reachable canonical p-code into a deterministic low-level SSA form that
later analyses can consume directly.

This stage should teach the core SSA ideas, not build a generic compiler
framework. The implementation should therefore stay small and explicit:

- compute dominators on the reachable CFG
- place phi nodes for registers with the standard dominance-frontier algorithm
- place one conservative memory phi for the single low-level memory state when
  needed
- rename registers into SSA versions
- rename instruction-local `unique` temporaries into function-wide SSA names
- thread one low-level memory-version state through `LOAD`, `STORE`, `CALL`,
  and `CALLIND`
- run one small post-rename normalization pass that drops same-base identity
  copies, rewrites later uses of trivial register-forwarding copies to the
  forwarded SSA value, and drops trivial register or memory phis
- synthesize explicit call-result and call-clobber defs for all RV32I ILP32
  caller-saved registers after low-level `CALL` and `CALLIND` ops

The result is still low-level p-code. Its memory SSA layer is intentionally
coarse: one function-local memory state, not stack-slot or partition-aware
memory identity, not high-level variable recovery, and not a general
expression IR.

## Inputs

- `ProgramDataflowFacts` from `tiny_dec.analysis.dataflow.models`
- `FunctionDataflowFacts` from `tiny_dec.analysis.dataflow.models`
- upstream canonical blocks, successors, and instruction ordering preserved in
  the embedded dataflow facts

Assumptions:

- stage-6 reachability is the current source of truth for which CFG blocks
  participate in SSA construction
- canonical blocks remain the CFG shape; this stage does not discover or mutate
  control-flow edges
- register varnodes are the only values that need phi insertion in this stage
- `unique` varnodes are local temporaries and never need cross-block phi nodes
- low-level memory SSA is modeled as one conservative memory-version stream for
  all memory traffic before stack slots, partitions, or alias classes exist
- call-result defs cover all RV32I ILP32 caller-saved registers: `CALL_RETURN`
  for the return carriers (`x10`, `x11`) and `CALL_CLOBBER` for the remaining
  caller-saved registers (`x1`, `x5`-`x7`, `x12`-`x17`, `x28`-`x31`) so
  downstream stages see every pre-call value as killed across the call

## Outputs

- `SSANameKind`
  - distinguishes SSA names for registers vs `unique` temporaries
- `SSAName`
  - one versioned SSA value name such as a register live-in or renamed def
- `SSAOp`
  - one renamed low-level p-code op using SSA inputs and outputs
- `SSAPhiInput`
  - one predecessor-labelled incoming phi argument
- `SSAPhiNode`
  - one phi node inserted at a reachable block header
- `SSAInstruction`
  - one canonical instruction plus its renamed SSA ops
- `MemoryVersion`
  - one versioned conservative low-level memory state
- `SSAMemoryPhiInput`
  - one predecessor-labelled incoming memory version
- `SSAMemoryPhiNode`
  - one memory phi node inserted at a reachable block header when multiple
    predecessor memory states meet
- `SSABlock`
  - one reachable canonical block plus register phis, one optional memory phi,
    and renamed instructions
- `SSAFunctionIR`
  - one function-level SSA snapshot plus dominator metadata and one optional
    memory live-in
- `SSAProgramIR`
  - one program-level SSA snapshot preserving stage-6 program metadata

Output invariants:

- SSA is only built for blocks whose stage-6 `in_state` is reachable
- `SSAFunctionIR.unreachable_blocks` records the remaining canonical blocks in
  deterministic order
- register phi nodes appear at the start of a block and are unique per register
- each block carries at most one memory phi for the coarse low-level memory
  state
- each SSA definition has exactly one output version
- `SSAName` version `0` is reserved for block-external register live-ins
- `MemoryVersion` version `0` is reserved for the block-external memory live-in
- later explicit definitions of the same register use increasing versions
- later explicit memory definitions use increasing memory versions
- each `CALL` or `CALLIND` op is followed by deterministic synthetic
  `CALL_RETURN` defs for the return carriers (`x10`, `x11`) and
  `CALL_CLOBBER` defs for every other caller-saved register
- `LOAD` consumes one current memory version; `STORE`, `CALL`, and `CALLIND`
  consume one current memory version and define one later version
- same-base identity copies such as `COPY x10_3 <- x10_2` may be elided from
  the final stage snapshot after normalization
- non-identity register-forwarding copies such as `COPY x12_1 <- x10_0` stay
  explicit so the written carrier remains visible, but later SSA uses may be
  rewritten to the forwarded value
- trivial register and memory phis may be elided when all non-self incoming
  values collapse to one rewritten input
- phi inputs are ordered by predecessor block address
- dominator and dominance-frontier maps cover the reachable blocks exactly
- `SSAProgramIR` preserves stage-6 pending and invalidation suggestions through
  its embedded dataflow facts; it does not act on them

## Non-goals

- stack-slot or partition-aware memory SSA
- alias analysis
- aggressive phi simplification, dead phi elimination, or general copy
  coalescing beyond same-base identity copies, later-use rewriting of trivial
  register-forwarding copies, and trivial self or same-value phis
- sparse conditional constant propagation
- use-def or def-use side tables beyond what is needed for renaming
- interprocedural SSA
- calling-convention inference beyond the fixed RV32I ILP32 clobber set
- any CFG rewrite or scheduler invalidation in this stage

## Algorithm sketch

### reachable CFG and dominators

1. Start from `FunctionDataflowFacts`.
2. Keep only blocks whose `in_state` is reachable; record the others in
   `unreachable_blocks`.
3. Build reachable predecessor lists from canonical successors.
4. Compute dominator sets with the standard iterative intersection algorithm:
   - entry dominates only itself
   - every other reachable block starts dominated by all reachable blocks
   - iterate until the sets stabilize
5. Derive immediate dominators and the dominator tree from those sets.
6. Compute dominance frontiers from the dominator tree and reachable CFG edges.

### phi placement

1. Collect register definition blocks from reachable instructions.
2. For each register, place phi nodes with the Cytron-style
   dominance-frontier worklist.
3. Insert at most one phi per register per reachable block.
4. Do not place phi nodes for `unique` temporaries.
5. Treat the coarse low-level memory state as one additional SSA variable and
   place at most one memory phi per reachable block.

### renaming

1. Traverse the dominator tree from the entry block.
2. Maintain per-register stacks of current SSA names.
3. Seed register live-ins lazily as version `0` when a reachable use appears
   before any explicit definition.
4. Rename phi outputs first, then instruction ops in order.
5. For instruction-local `unique` temporaries:
   - keep a local map per instruction
   - assign function-wide SSA versions to each explicit `unique` definition
   - reuse those names for later uses inside the same instruction
6. Thread one current memory version through instructions:
   - `LOAD` records the current memory version as a use
   - `STORE`, `CALL`, and `CALLIND` record the current memory version as a use
     and define the next memory version
7. After renaming one `CALL` or `CALLIND` op, append synthetic defs for all
   RV32I ILP32 caller-saved registers: `CALL_RETURN` for `x10` and `x11`,
   `CALL_CLOBBER` for every other caller-saved register, so downstream stages
   see pre-call values as killed.
8. After processing a block, add the current register names and current memory
   version as phi inputs to
   each reachable successor.
9. Pop definitions when unwinding the dominator-tree recursion.
10. Run one small normalization pass over the renamed SSA:
   - drop same-base identity copies such as `COPY x10_3 <- x10_2`
   - rewrite later uses of trivial register-forwarding copies such as
     `COPY x12_1 <- x10_0` to the forwarded SSA value while keeping the
     explicit register copy op in place
   - rewrite later uses to the surviving carrier value
   - remove register or memory phis whose non-self rewritten inputs agree on
     one value

Failure and bailout rules:

- malformed dominator input should fail through model invariants rather than
  being silently normalized
- unsupported value spaces remain as raw non-SSA varnodes in inputs
- unreachable blocks stay outside renamed SSA blocks rather than receiving
  synthetic phi nodes

## Data structures

- `SSANameKind`
  - owner: `tiny_dec/analysis/ssa/models.py`
  - values:
    - `register`
    - `unique`
- `SSAName`
  - owner: `tiny_dec/analysis/ssa/models.py`
  - fields:
    - `kind`
    - `base`
    - `version`
    - `size`
  - invariants:
    - `base` is non-negative
    - `version` is non-negative
    - version `0` for registers is a live-in, not a redefinition
  - pretty:
    - register: `x10_3:4`
    - unique: `u0_2:4`
- `MemoryVersion`
  - owner: `tiny_dec/analysis/ssa/models.py`
  - fields:
    - `version`
  - invariants:
    - version is non-negative
  - pretty:
    - `m0`
- `SSAOp`
  - owner: `tiny_dec/analysis/ssa/models.py`
  - fields:
    - `opcode`
    - `inputs`
    - `output`
    - `memory_before`
    - `memory_after`
  - pretty:
    - `INT_ADD x10_2:4 <- x10_1:4, const[0x1:4]`
    - load with memory use:
      `LOAD x10_3:4 <- u0_1:4 [m0]`
    - store with memory def:
      `STORE u0_1:4, x10_2:4 [m0 -> m1]`
    - synthetic call result:
      `CALL_RETURN x10_3:4 <- const[0x1004:4]`
    - synthetic call clobber:
      `CALL_CLOBBER x5_2:4 <- const[0x1004:4]`
- `SSAMemoryPhiInput`
  - owner: `tiny_dec/analysis/ssa/models.py`
  - fields:
    - `predecessor`
    - `value`
  - pretty:
    - `0x1010:m0`
- `SSAMemoryPhiNode`
  - owner: `tiny_dec/analysis/ssa/models.py`
  - fields:
    - `output`
    - `inputs`
  - invariants:
    - predecessor inputs are unique and sorted
  - pretty:
    - `MEM_PHI m2 <- 0x1010:m0, 0x1020:m1`
- `SSAPhiInput`
  - owner: `tiny_dec/analysis/ssa/models.py`
  - fields:
    - `predecessor`
    - `value`
  - pretty:
    - `0x1010:x10_1:4`
- `SSAPhiNode`
  - owner: `tiny_dec/analysis/ssa/models.py`
  - fields:
    - `output`
    - `inputs`
  - invariants:
    - output is a register `SSAName`
    - predecessor inputs are unique and sorted
  - pretty:
    - `PHI x10_3:4 <- 0x1010:x10_1:4, 0x1020:x10_2:4`
- `SSAInstruction`
  - owner: `tiny_dec/analysis/ssa/models.py`
  - fields:
    - `instruction`
    - `ops`
  - pretty:
    - original instruction line followed by renamed SSA ops
- `SSABlock`
  - owner: `tiny_dec/analysis/ssa/models.py`
  - fields:
    - `start`
    - `phis`
    - `memory_phi`
    - `instructions`
    - `successors`
    - `terminator`
    - `call_targets`
    - `has_indirect_call`
  - invariants:
    - block is reachable
    - phi outputs are unique per register
  - pretty:
    - canonical block header
    - optional memory phi line
    - optional phi lines
    - renamed instruction dump
- `SSAFunctionIR`
  - owner: `tiny_dec/analysis/ssa/models.py`
  - fields:
    - `dataflow`
    - `blocks`
    - `immediate_dominators`
    - `dominance_frontiers`
    - `live_ins`
    - `memory_live_in`
    - `unreachable_blocks`
  - invariants:
    - reachable SSA blocks plus `unreachable_blocks` cover the canonical blocks
      exactly
    - dominator metadata covers reachable blocks exactly
  - pretty:
    - function summary
    - live-in list
    - optional memory live-in
    - unreachable block list
    - nested blocks with phi nodes and renamed ops
- `SSAProgramIR`
  - owner: `tiny_dec/analysis/ssa/models.py`
  - fields:
    - `dataflow`
    - `functions`
  - invariants:
    - functions cover the stage-6 discovered program functions exactly
  - pretty:
    - preserved program header, queue suggestions, externals, and call graph
    - nested `SSAFunctionIR` snapshots

## Edge cases

- straight-line functions with only live-ins and no phi nodes
- diamonds that require one phi at a join block
- loops that require a header phi from the entry path and backedge
- loops that require a header memory phi from a store-carrying backedge
- blocks reachable only through one predecessor, which must not get a phi
- entry uses of registers before any local definition
- entry loads before any local memory definition
- repeated instruction-local `unique` offsets across different instructions
- unreachable canonical blocks
- blocks with no register definitions at all
- call instructions whose return and clobber carriers feed later local SSA uses

## Pretty-print contract

### `SSAFunctionIR`

- summary line:
  - `function 0xADDR name=<name-or-?> reachable=<n> unreachable=<n> phis=<n>`
- `live_ins:` section
  - version-0 register names in deterministic register order
- `unreachable_blocks:` section
  - `0xADDR, ...` or `<none>`
- `blocks:` section
  - one reachable block in canonical discovery order
  - block header line:
    - `block 0xADDR term=<kind> succ=[...] idom=<entry|0xADDR> df=[...]`
  - optional phi lines before instructions
  - original instruction line followed by renamed SSA ops, including synthetic
    `CALL_RETURN` and `CALL_CLOBBER` ops after call instructions

### `SSAProgramIR`

- header lines:
  - `root: 0xADDR`
  - `order: 0xADDR, ...`
  - `pending: 0xADDR, ...`
  - `invalidated: 0xADDR, ...`
- `externals:` section
- `call_graph:` section
- `functions:` section
  - nested `SSAFunctionIR` snapshots in program discovery order

Pretty output must be deterministic across repeated runs over the same input.

## End-to-end harness exposure

The post-07 e2e harness should iterate all fixture binaries, resolve the root
function, build `SSAProgramIR`, and render the deterministic snapshot.

The snapshot should make it obvious:

- which blocks participated in SSA
- which blocks stayed unreachable
- where phi nodes were inserted
- which register names were treated as entry live-ins
- how instructions were renamed into SSA values

## CLI and iteration commands

Post 07 should add an `ssa` debug surface:

- `tiny-dec decompile <binary> --stage ssa [--func <selector>]`
  - renders the program-level SSA snapshot rooted at the selected function

After post 07 is implemented, `decompile` should default to `ssa`.

While iterating on this stage, use:

- tests:
  - `poetry run pytest -q tests/posts/post_07_ssa`
- e2e harness:
  - `poetry run pytest -q tests/posts/post_07_ssa/test_ssa_e2e_harness.py`
- ruff:
  - `poetry run ruff check tiny_dec/analysis/ssa tiny_dec/cli.py tiny_dec/pipeline tests/posts/post_07_ssa`
- mypy:
  - `poetry run mypy tiny_dec/analysis/ssa tiny_dec/cli.py tiny_dec/pipeline tests/posts/post_07_ssa`
