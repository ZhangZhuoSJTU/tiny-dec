# Stage Contract: `post_09_stack`

## Summary

- Stage name: `post_09_stack`
- Owner directory: `tiny_dec/analysis/stack/`
- Immediate predecessor: `post_08_calls`
- Immediate successor: `post_10_memory`

## Purpose

Recover a small, deterministic stack-frame view on top of stage-8 call facts.

This stage turns repeated `sp` and `fp` address arithmetic into a function-local
frame model that later memory work can consume directly:

- recover constant stack-pointer deltas relative to the entry stack top
- detect a conventional frame-pointer base when the function establishes one
- group stack-relative loads and stores into stable frame slots
- classify a few common slot roles such as saved registers and argument homes

The goal is to expose the current stack layout honestly, not to pretend full
memory modeling already exists.

## Inputs

- `FunctionCallFacts` from `tiny_dec.analysis.calls.models`
- `ProgramCallFacts` from `tiny_dec.analysis.calls.models`
- embedded `SSAFunctionIR` and `SSAProgramIR` from stage 7
- preserved upstream `pending_entries`, `invalidated_entries`, externals, and
  refined call graph metadata carried through stage 8

Assumptions:

- stage-7 SSA naming is stable and deterministic
- stack addresses are currently recognized only when they are built from a
  known stack base plus a constant offset
- `x2` is the RV32I stack pointer and `x8` is the conventional frame pointer
  candidate
- stack pointer adjustment is treated conservatively; unsupported or
  non-constant arithmetic does not become a recovered stack slot
- this stage does not rewrite memory operations, infer types, or replace the
  stage-8 call ABI model

## Outputs

- `StackBaseKind`
  - distinguishes recovered frame-top-relative bases such as the entry stack
    top, current stack pointer, and frame pointer
- `StackFrameBase`
  - one recovered register value whose meaning is a known frame-top delta
- `StackAccessKind`
  - distinguishes stack loads from stack stores
- `StackSlotRole`
  - classifies stack slots as saved-register, argument-home, local, or unknown
- `StackAccess`
  - one deterministic stack load/store observation at one instruction
- `StackSlot`
  - one grouped frame slot with stable role and ordered accesses
- `FunctionStackFacts`
  - one function-level stack recovery snapshot
- `ProgramStackFacts`
  - one program-level stack recovery snapshot that preserves scheduler state

Output invariants:

- `ProgramStackFacts.functions` covers the stage-8 program functions exactly
- `ProgramStackFacts.pending_entries` and `invalidated_entries` preserve the
  stage-8 values unchanged
- recovered stack addresses are expressed as signed offsets from the function's
  entry stack top
- frame slots are unique by `(frame_offset, size)` and ordered by offset, then
  size
- slot access ordering is deterministic by block and instruction order
- saved-register and argument-home classifications are only emitted when the
  required register identity is actually known

## Re-trigger and invalidation rules

- This stage is read-only with respect to earlier stages.
- It does not discover new functions, blocks, edges, or callees.
- It does not emit new `pending_entries` or `invalidated_entries`.
- It preserves the stage-8 scheduler state unchanged so later stages can still
  observe the current queue suggestions.

## Non-goals

- stack-variable naming
- stack argument replacement in call signatures
- alias analysis
- heap or global memory modeling
- memory SSA
- dynamic `alloca` recovery
- non-constant stack-pointer arithmetic beyond conservative rejection
- rewriting stage-8 call facts or the stage-7 SSA graph

## Algorithm sketch

### symbolic stack-base tracking

1. Start from one `SSAFunctionIR` embedded in `FunctionCallFacts`.
2. Seed the traversal with the entry stack-top value `x2_0` at frame delta `0`.
3. Walk reachable SSA blocks in dominator-tree order:
   - apply phi outputs first
   - process instructions in address order
   - track register and `unique` outputs that are known to equal
     `frame_top + constant`
4. Recognize new symbolic stack bases through:
   - `COPY` of a known stack base
   - `INT_ADD` of a known stack base and a constant
5. Treat `x2` definitions as current-stack-pointer candidates and `x8`
   definitions as frame-pointer candidates when they resolve to a known
   frame-top delta.

### stack access recovery

1. When a `LOAD` or `STORE` uses an address that resolves to a known stack base
   plus constant offset, emit a `StackAccess`.
2. Normalize the address to a signed `frame_offset` from the entry stack top.
3. Group accesses by `(frame_offset, size)` into `StackSlot` records.

### slot role classification

1. Classify a slot as `saved_register` when its first stack store in the entry
   block writes a live-in register value and later accesses are consistent with
   restoring that register.
2. Classify a slot as `argument_home` when its first stack store in the entry
   block writes a live-in ABI argument register value.
3. Otherwise classify the slot as `local` when it has ordinary stack accesses,
   or `unknown` when the evidence is too weak to say more.

### frame summary

1. Derive `frame_size` from the most-negative recovered `x2` delta when one is
   available.
2. Record the recovered frame-pointer register base, if any.
3. Mark `dynamic_stack_pointer=yes` when `x2` receives a non-constant or
   unsupported update that prevents complete reasoning.

### program aggregation

1. Analyze functions in stage-8 program discovery order.
2. Preserve externals, call graph, `pending_entries`, and `invalidated_entries`
   from stage 8 unchanged.
3. Emit `ProgramStackFacts`.

Failure and bailout rules:

- unsupported stack arithmetic becomes `dynamic_stack_pointer=yes` rather than a
  guessed slot
- non-stack addresses remain absent from the recovered slot list
- malformed upstream invariants fail through model validation rather than
  silent normalization

## Data structures

- `StackBaseKind`
  - owner: `tiny_dec/analysis/stack/models.py`
  - values:
    - `entry_sp`
    - `stack_pointer`
    - `frame_pointer`
- `StackFrameBase`
  - owner: `tiny_dec/analysis/stack/models.py`
  - fields:
    - `kind`
    - `register`
    - `value`
    - `frame_top_delta`
  - invariants:
    - register index is non-negative
    - `value` is a register SSA name for the same architectural register
  - pretty:
    - `frame_pointer x8=x8_1:4 delta=+0`
- `StackAccessKind`
  - owner: `tiny_dec/analysis/stack/models.py`
  - values:
    - `load`
    - `store`
- `StackSlotRole`
  - owner: `tiny_dec/analysis/stack/models.py`
  - values:
    - `saved_register`
    - `argument_home`
    - `local`
    - `unknown`
- `StackAccess`
  - owner: `tiny_dec/analysis/stack/models.py`
  - fields:
    - `instruction_address`
    - `block_start`
    - `kind`
    - `frame_offset`
    - `size`
    - `base_kind`
    - `base_register`
    - `value`
  - invariants:
    - addresses are non-negative
    - size is positive
    - base register is non-negative
  - pretty:
    - `store 0x110f8 block=0x110e4 slot=-12 size=4 via=frame_pointer(x8) value=x10_1:4`
- `StackSlot`
  - owner: `tiny_dec/analysis/stack/models.py`
  - fields:
    - `frame_offset`
    - `size`
    - `role`
    - `saved_register`
    - `argument_register`
    - `accesses`
  - invariants:
    - accesses all share the same `(frame_offset, size)`
    - accesses are deterministic and ordered
    - saved-register and argument-home detail fields match the role
  - pretty:
    - `slot -12 size=4 role=argument_home(x10) accesses=1`
- `FunctionStackFacts`
  - owner: `tiny_dec/analysis/stack/models.py`
  - fields:
    - `calls`
    - `frame_size`
    - `frame_pointer`
    - `dynamic_stack_pointer`
    - `slots`
  - invariants:
    - slot order is deterministic
    - frame pointer, when present, belongs to the owning function
  - pretty:
    - summary line with frame size, frame pointer, dynamic-stack marker, slot
      count, and preserved per-function pending entries
- `ProgramStackFacts`
  - owner: `tiny_dec/analysis/stack/models.py`
  - fields:
    - `calls`
    - `functions`
    - `pending_entries`
    - `invalidated_entries`
  - invariants:
    - function coverage matches stage 8 exactly
    - scheduler state matches stage 8 exactly
  - pretty:
    - preserved program header, queue state, call graph, and nested stack facts

## Edge cases

- stackless leaf functions with no `x2` live-in
- frame-pointer functions that access locals through `x8`
- stack-pointer-only functions that access locals through adjusted `x2`
- saved-register slots for `x1` and `x8`
- argument homes written in the entry block before any control-flow split
- loops that repeatedly access the same slot
- non-constant or unsupported `x2` arithmetic, which must set
  `dynamic_stack_pointer=yes`
- ordinary RAM accesses that must not be mislabeled as stack slots

## Pretty-print contract

### `FunctionStackFacts`

- summary line:
  - `function 0xADDR name=<name-or-?> frame_size=<n-or-?> fp=<base-or-none> dynamic_sp=<yes|no> slots=<n> pending=[...]`
- `slots:` section
  - one deterministic line per recovered slot in `(frame_offset, size)` order
  - optional indented access lines in instruction order

### `ProgramStackFacts`

- header lines:
  - `root: 0xADDR`
  - `order: ...`
  - `pending: ...`
  - `invalidated: ...`
- `call_graph:` section
  - preserved stage-8 call graph lines
- `functions:` section
  - nested `FunctionStackFacts` output

## End-to-end harness exposure

The persistent fixture harness should render `stack:` for every fixture binary.
Plausible output should show:

- empty slot lists for optimized stackless functions
- recovered frame sizes for ordinary `O0` functions with classic prologues
- stable negative frame offsets for locals and saved registers
- unchanged `pending` and `invalidated` program queue lines

## Validation commands

Record the commands that should be used while iterating:

- stage tests: `poetry run pytest -q tests/posts/post_09_stack`
- e2e harness: `poetry run pytest -q tests/posts/post_09_stack/test_stack_e2e_harness.py`
- ruff: `poetry run ruff check tiny_dec/analysis/stack tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_09_stack`
- mypy: `poetry run mypy tiny_dec/analysis/stack tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_09_stack`

## Open questions

- Whether a later memory stage should canonicalize outgoing stack arguments into
  a distinct role once call-argument stores become relevant in fixtures.
