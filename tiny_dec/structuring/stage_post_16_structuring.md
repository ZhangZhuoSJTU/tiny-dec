# Stage Contract: `post_16_structuring`

## Summary

- Stage name: `post_16_structuring`
- Owner directory: `tiny_dec/structuring/`
- Immediate predecessor: `post_15_interproc`
- Immediate successor: `post_17_c_lowering`

## Purpose

Recover a small, deterministic structured-control IR on top of stage-15
interprocedural facts.

This stage turns the current CFG, SSA, range, and interprocedural evidence into
an explicit control tree that later C lowering can consume directly:

- preserve straight-line blocks as ordered structured leaves
- recover nested `if` and `if-else` regions where branch paths reconverge
- recover small constant-equality dispatch ladders as one `switch`-like node
- elide jump-only trampoline blocks when they only forward one structured
  branch arm to its next meaningful node
- recover small pretested `while` loops from natural loop headers
- make residual unstructured edges explicit as `goto`, `break`, or `continue`
  leaves
- preserve the current scheduler state unchanged

The goal is to expose the current control shape honestly, not to solve every
reducibility problem, infer source expressions perfectly, or hide unsupported
CFG edges behind a fake high-level structure.

## Inputs

- `FunctionInterprocFacts` from `tiny_dec.analysis.interproc.models`
- `ProgramInterprocFacts` from `tiny_dec.analysis.interproc.models`
- embedded `FunctionRangeFacts`, `FunctionVariableFacts`, `FunctionCallFacts`,
  `SSAFunctionIR`, and the preserved canonical CFG through stage 15
- preserved upstream `pending_entries`, `invalidated_entries`, call graph, and
  scheduler invalidations carried through stage 15

Assumptions:

- stage-15 function order, call graph order, and pretty-print stability are
  already deterministic
- the current CFG is the reachable SSA CFG from stage 7; this stage does not
  rebuild or mutate it
- simple natural loops can be recognized from backedges whose target dominates
  the source
- unsupported irreducible or ambiguous regions should fall back to explicit
  control-transfer leaves instead of guessed higher-level regions
- this stage is read-only with respect to earlier analyses and does not invent
  new program facts outside the structured-control surface

## Outputs

- `StructuredBlock`
  - one leaf that owns one existing CFG block
- `StructuredIf`
  - one conditional region with structured `then` and `else` bodies
- `StructuredSwitchCase`
  - one constant case body inside one recovered structured switch
- `StructuredSwitch`
  - one constant-equality dispatch region with ordered cases and one default
    body
- `StructuredWhile`
  - one pretested loop region with a structured body
- `StructuredGoto`
  - one explicit unstructured branch fallback
- `StructuredBreak`
  - one explicit loop-exit fallback
- `StructuredContinue`
  - one explicit loop-header fallback
- `StructuredSequence`
  - one ordered statement list
- `FunctionStructuredFacts`
  - one function-level structured-control snapshot
- `ProgramStructuredFacts`
  - one program-level structured-control snapshot preserving scheduler state

Output invariants:

- `ProgramStructuredFacts.functions` covers the stage-15 program functions
  exactly
- `ProgramStructuredFacts.pending_entries`, `invalidated_entries`, and
  `scheduler_invalidations` preserve the stage-15 values unchanged
- structured statement order is deterministic and follows CFG traversal order
  under the documented algorithm
- `StructuredIf` and `StructuredWhile` headers always reference real CFG block
  starts in the owned function
- `StructuredSwitch.header` references the first branch header in the recovered
  dispatch chain
- `StructuredSwitchCase.value` order is deterministic and unique inside one
  recovered switch
- `StructuredIf.true_target`, `StructuredIf.false_target`, and
  `StructuredWhile.body_entry` preserve the original CFG successor metadata
  even when the structured body elides a jump-only trampoline leaf
- `StructuredGoto`, `StructuredBreak`, and `StructuredContinue` targets are
  non-negative and explicit
- unsupported edges remain explicit; they are never silently discarded

## Re-trigger and invalidation rules

- This stage is read-only with respect to earlier CFG, SSA, variable, range,
  and interprocedural artifacts.
- It does not discover new functions, blocks, edges, or call targets.
- It does not emit new `pending_entries`, `invalidated_entries`, or scheduler
  invalidations.
- It preserves stage-15 `pending_entries`, `invalidated_entries`, and
  scheduler invalidations unchanged.
- If later stages decide that a structured region implies CFG cleanup or
  no-return pruning, that later stage must emit its own invalidation requests.
  Post 16 itself does not.

## Non-goals

- irreducible CFG normalization
- switch-table recognition as a dedicated node kind
- source-level boolean expression lowering
- expression sequencing or statement simplification
- exception handling, setjmp/longjmp, or non-local control flow
- interprocedural restructuring
- CFG rewriting or dead-block deletion
- hiding unsupported edges behind guessed `if` or loop forms

## Algorithm sketch

### supporting CFG indexes

1. Start from one `FunctionInterprocFacts`.
2. Build deterministic indexes for:
   - reachable SSA blocks in function order
   - CFG predecessors and successors
   - dominance and natural-loop candidates from stage-7 dominator data
   - postdominators and immediate postdominators over the reachable CFG plus a
     synthetic exit

### loop recognition

1. Identify backedges where the successor dominates the source.
2. For each candidate loop header, build the natural loop node set by walking
   backward through predecessors from each backedge source.
3. Recover a `StructuredWhile` only when:
   - the header has exactly two successors
   - exactly one successor remains inside the loop
   - exactly one successor exits the loop
4. Structure the loop body recursively, using explicit `continue` or `break`
   leaves whenever the body reaches the loop header or loop exit through edges
   that are not absorbed by a cleaner nested region.

### branch structuring

1. For non-loop branch headers with exactly two successors, inspect the
   immediate postdominator as the reconvergence target.
2. Recover a `StructuredIf` when both successors can be structured
   independently up to that merge point.
3. Before recursively structuring one branch body, skip any leading block whose
   only effect is one unconditional jump to another block inside the same
   region.
4. Represent else-if ladders naturally as nested `StructuredIf` nodes inside
   the `else` branch.

### limited switch recovery

1. After building nested `StructuredIf` ladders, inspect whether one chain is
   really one constant-equality dispatch over one stable selector.
2. Recover one `StructuredSwitch` only when:
   - every header compares one semantically-stable selector against one exact
     constant
   - every true arm is one case body
   - every false arm either continues to the next equality test or becomes the
     one default body
   - every branch in the chain shares one merge target
3. Keep the selector implicit in the stage-16 model and preserve only the
   ordered case values, original case targets, default target, and structured
   bodies.
4. Bail out back to nested `StructuredIf` nodes when the selector identity,
   case constants, or common merge target stop being clear.

### linear fallback and termination

1. Blocks with one normal successor become a `StructuredBlock` followed by the
   recursive structure of that successor.
2. One unconditional-jump trampoline block with no phis and no non-branch ops
   may be elided by advancing directly to its successor when that keeps the
   current structured region honest.
3. Return or stop blocks become terminal `StructuredBlock` leaves.
4. Edges that revisit an active region, jump to an unsupported target, or cross
   a boundary that cannot be absorbed by the current pattern become explicit
   `goto`, `break`, or `continue` leaves.

Failure and bailout rules:

- unsupported or irreducible regions stay explicit through fallback leaves
  rather than causing the whole function to fail
- ambiguous loop headers that do not have one in-loop successor and one exit
  successor are not forced into `while`
- malformed upstream invariants fail through model validation rather than
  silent normalization

## Data structures

- `StructuredBlock`
  - owner: `tiny_dec/structuring/models.py`
  - fields:
    - `block_start`
  - invariants:
    - block start is non-negative
  - pretty:
    - `block 0x110fc`
- `StructuredIf`
  - owner: `tiny_dec/structuring/models.py`
  - fields:
    - `header`
    - `true_target`
    - `false_target`
    - `merge_target`
    - `then_body`
    - `else_body`
  - invariants:
    - header and branch targets are non-negative
    - merge target is non-negative when present
  - pretty:
    - `if header=0x11100 true=0x11158 false=0x11124 merge=0x111a4`
- `StructuredSwitchCase`
  - owner: `tiny_dec/structuring/models.py`
  - fields:
    - `value`
    - `target`
    - `body`
  - invariants:
    - target is non-negative
    - case values are unique inside one `StructuredSwitch`
  - pretty:
    - `case 0 -> 0x11158`
- `StructuredSwitch`
  - owner: `tiny_dec/structuring/models.py`
  - fields:
    - `header`
    - `merge_target`
    - `cases`
    - `default_target`
    - `default_body`
  - invariants:
    - header is non-negative
    - default target is non-negative when present
    - case order is preserved exactly as recovered
  - pretty:
    - `switch header=0x11100 cases=4 default=0x11198 merge=0x111a4`
- `StructuredWhile`
  - owner: `tiny_dec/structuring/models.py`
  - fields:
    - `header`
    - `body_entry`
    - `exit_target`
    - `body`
  - invariants:
    - header, body entry, and exit target are non-negative
  - pretty:
    - `while header=0x11120 body=0x1112c exit=0x11154`
- `StructuredGoto`
  - owner: `tiny_dec/structuring/models.py`
  - fields:
    - `target`
  - invariants:
    - target is non-negative
  - pretty:
    - `goto 0x11198`
- `StructuredBreak`
  - owner: `tiny_dec/structuring/models.py`
  - fields:
    - `target`
  - invariants:
    - target is non-negative
  - pretty:
    - `break 0x11154`
- `StructuredContinue`
  - owner: `tiny_dec/structuring/models.py`
  - fields:
    - `target`
  - invariants:
    - target is non-negative
  - pretty:
    - `continue 0x11120`
- `StructuredSequence`
  - owner: `tiny_dec/structuring/models.py`
  - fields:
    - `items`
  - invariants:
    - item order is preserved exactly as structured
  - pretty:
    - nested indented statement list
- `FunctionStructuredFacts`
  - owner: `tiny_dec/structuring/models.py`
  - fields:
    - `interproc`
    - `body`
  - invariants:
    - summary counts are derivable from the body tree
  - pretty:
    - summary line plus nested `body:` section
- `ProgramStructuredFacts`
  - owner: `tiny_dec/structuring/models.py`
  - fields:
    - `interproc`
    - `functions`
    - `pending_entries`
    - `invalidated_entries`
    - `scheduler_invalidations`
  - invariants:
    - function coverage matches stage 15 exactly
    - scheduler state matches stage 15 exactly
  - pretty:
    - preserved program header, queue state, externals, call graph, scheduler
      invalidations, and nested structured functions

## Edge cases

- single-block straight-line return function
- nested if / else-if ladder with one shared return block
- one constant-equality dispatch ladder that should collapse to one switch
- jump-only dispatcher trampoline blocks inside an else-if ladder or default arm
- pretested loop with a backedge into the header
- one-successor jump chain that should stay linear
- loop bodies that need explicit `continue`
- unsupported cross-region edges that must fall back to `goto`
- functions whose CFG stays too awkward to recover beyond a block list plus
  explicit fallback leaves
- stage-15 no-return summaries that should remain visible but not change the
  structured CFG on their own

## Pretty-print contract

### `FunctionStructuredFacts`

- summary line:
  - `function 0xADDR name=<name-or-?> frame_size=<n-or-?> dynamic_sp=<yes|no> stmts=<n> loops=<n> ifs=<n> switches=<n> gotos=<n> pending=[...]`
- `body:` section
  - nested deterministic statement lines with two-space indentation per level

### `ProgramStructuredFacts`

- header lines:
  - `root: 0xADDR`
  - `order: ...`
  - `pending: ...`
  - `invalidated: ...`
- `externals:` section
- `call_graph:` section
- `scheduler_invalidations:` section
- `functions:` section
  - nested `FunctionStructuredFacts` output

## End-to-end harness exposure

The persistent e2e harness should render every fixture binary through
`ProgramStructuredFacts` and the structuring pretty-printer.

Plausible output should show:

- one `block ...` leaf for straight-line optimized functions
- one `while ...` node on the loop fixture
- one `switch ...` node on the switch fixture, or nested `if ...` nodes when
  the dispatch chain does not meet the documented recovery limits
- explicit `goto`, `break`, or `continue` fallbacks only when the CFG shape
  cannot be absorbed more cleanly

## Validation commands

Record the commands that should be used while iterating:

- stage tests:
  `poetry run pytest -q tests/posts/post_16_structuring`
- e2e harness:
  `poetry run pytest -q tests/posts/post_16_structuring/test_structuring_e2e_harness.py`
- cli:
  `poetry run tiny-dec decompile tests/fixtures/bin/fixture_loop_O0_nopie.elf --func main --stage structuring`
- ruff:
  `poetry run ruff check tiny_dec/structuring tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_16_structuring`
- mypy:
  `poetry run mypy tiny_dec/structuring tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_16_structuring`

## Open questions

- whether a dedicated `switch` node should exist later or whether nested `if`
  nodes remain the intended stage-16 surface
- whether later C lowering will want branch-header expression metadata on the
  structured nodes rather than only block references
