# Stage Contract: `post_17_c_lowering`

## Summary

- Stage name: `post_17_c_lowering`
- Owner directory: `tiny_dec/c_emit/`
- Immediate predecessor: `post_16_structuring`
- Immediate successor: `post_18_c_printer_pipeline`

## Purpose

Lower the current structured-control tree into a small, deterministic C-like IR.

This stage is the first point where the decompiler stops talking in CFG and SSA
terms and starts talking in source-shaped statements and expressions:

- recover typed parameter and local declaration surfaces from stage-13 variables
  plus stage-15 prototypes
- lower structured `if` and `while` regions into explicit C-like statement
  nodes
- lower one recovered stage-16 `switch` region into one explicit C-like switch
  statement
- lower supported SSA arithmetic, comparisons, loads, and stores into explicit
  expressions and assignments
- project aggregate layouts into synthetic field references such as
  `arg_x10_4[idx].field_4`
- preserve residual low-level uncertainty explicitly through raw expressions,
  raw call targets, explicit `goto`, `break`, and `continue`, and explicit
  register-carried return lists

The goal is not to print final polished C yet. The goal is to expose a stable,
typed, diff-friendly intermediate representation that stage 18 can print
without needing to rediscover control flow, variables, or aggregate layout.

## Inputs

- `FunctionStructuredFacts` from `tiny_dec.structuring.models`
- `ProgramStructuredFacts` from `tiny_dec.structuring.models`
- embedded stage-15 prototypes and effects through
  `FunctionStructuredFacts.interproc`
- embedded stage-14 branch refinements and stage-13 variables through
  `FunctionStructuredFacts.interproc.ranges`
- embedded stage-12 aggregate layouts, stage-11 scalar types, stage-10 memory
  partitions, stage-9 stack slots, stage-8 callsites, and stage-7 SSA through
  the existing upstream chain
- preserved upstream `pending_entries`, `invalidated_entries`, and scheduler
  invalidations carried through stage 16

Assumptions:

- stage-16 structured regions are already deterministic and are the only
  control surface this stage lowers
- stage-13 variable names, stage-12 field ordering, and stage-15 prototype
  ordering are deterministic and stable enough to become printed declarations
- when one direct internal callee has a stage-15 prototype, its lowered call
  arguments should follow that prototype's parameter order for the subset of
  carriers whose current SSA values are known
- when one named external callsite carries a stage-8 known external signature
  hint, its lowered call arguments should follow that signature's register and
  stack order for the subset of carrier values known at the callsite, and its
  unsupported secondary return carriers should stay absent
- unresolved or unspecialized external calls still fall back to the raw stage-8
  callsite register-plus-stack carrier order
- unresolved indirect calls may also carry one explicit stage-8 indirect target
  value, which this stage lowers as the leading `call_indirect(target, ...)`
  argument while leaving the remaining carrier order otherwise honest
- low-level prologue and epilogue stack traffic can be filtered conservatively
  from saved-register slots and parameter-home self-copies
- not every SSA value can be rendered as a clean source expression; unsupported
  values must fall back to explicit raw nodes instead of guessed source syntax
- when one lowered value is exactly the entry-stack-relative address of one
  recovered stack-slot variable, this stage may spell it as `&name` instead of
  preserving the raw stack-pointer arithmetic
- stage-7 SSA now creates explicit `CALL_RETURN` defs and stage-8 callsites
  preserve those return-carrier bindings
- this stage may fold a supported primary return (`x10`) directly into one
  clean assignment when the value is immediately stored to a recovered lvalue
- this stage may also materialize one directly consumed call-return carrier
  into one synthetic local so later calls, conditions, or return bindings can
  use a stable name instead of repeating a raw SSA carrier
- stage 18 may also collapse one supported direct multi-register call
  forwarder into one rendered-only temporary of the callee return type when
  the lowered body is already just one call plus one direct carrier return
  mapping
- stage 18 may also render one supported direct single-register internal call
  forwarder through one scalar temporary of the callee return type instead of
  boxing that call into a rendered-only `{ x10; }` helper struct
- stage 18 may also project one supported direct multi-register call result
  through one rendered-only temporary when the lowered suffix already contains
  one folded primary call assignment or direct call expression, zero or more
  direct materialized secondary carriers from that same callsite, and one
  direct return mapping
- stage 18 may also group one supported call expression plus one immediate run
  of direct materialized call-return carrier locals into one rendered-only
  temporary when later uses stay in rvalue positions inside the same rendered
  statement tree
- secondary return carriers remain explicit when no equally clean source
  assignment or synthetic local materialization is available

## Outputs

- `CLoweredType`
  - one stable printed type spelling used by declarations and return carriers
- `CLoweredVariable`
  - one typed parameter or local declaration, including one register-carried or
    stack-carried parameter location
- `CLoweredReturn`
  - one explicit register-carried return carrier for one lowered function
- `CReturnBinding`
  - one register-to-expression binding inside one lowered `return` statement
- `CNameExpr`
  - one named variable-like expression
- `CFieldExpr`
  - one synthetic aggregate field expression rooted in one recovered variable
- `CGlobalExpr`
  - one named absolute global expression
- `CRawExpr`
  - one explicit fallback expression when cleaner lowering is not supported
- `CConstExpr`
  - one constant expression
- `CUnaryExpr`
  - one unary expression
- `CBinaryExpr`
  - one binary expression
- `CCallExpr`
  - one call expression with a modeled callee target and lowered arguments
- `CAssignStmt`
  - one assignment statement
- `CExprStmt`
  - one side-effecting expression statement, usually a call
- `CReturnStmt`
  - one explicit register-carried return statement
- `CIfStmt`
  - one lowered structured branch
- `CSwitchCase`
  - one lowered constant case body inside one C-like switch
- `CSwitchStmt`
  - one lowered switch statement over one selector expression
- `CWhileStmt`
  - one lowered structured loop
- `CGotoStmt`
  - one explicit unstructured jump fallback
- `CBreakStmt`
  - one explicit loop-exit fallback
- `CContinueStmt`
  - one explicit loop-header fallback
- `CStmtSequence`
  - one ordered statement list
- `FunctionCLowered`
  - one function-level C-like IR snapshot
- `ProgramCLowered`
  - one program-level C-like IR snapshot preserving scheduler state

Output invariants:

- `ProgramCLowered.functions` covers the stage-16 program functions exactly
- `ProgramCLowered.pending_entries`, `invalidated_entries`, and
  `scheduler_invalidations` preserve the stage-16 values unchanged
- parameter declarations follow stage-15 prototype order
- local declarations follow stage-13 variable order for non-promoted local
  variables
- synthetic locals introduced for directly consumed call-return carriers appear
  after recovered locals in deterministic callsite and register order
- statement order is deterministic and follows the lowered stage-16 structure
- direct internal call arguments follow the stage-15 callee prototype order for
  the subset of carrier values known at the callsite
- direct named external call arguments follow the attached stage-8 known
  external signature order for the subset of carrier values known at the
  callsite
- unresolved or unspecialized external calls preserve the raw stage-8 callsite
  register-plus-stack carrier order
- unresolved indirect calls prepend the explicit stage-8 indirect target value
  to the lowered `call_indirect(...)` helper arguments and omit that target
  carrier from the ordinary ABI register-argument list when stage 8 already
  separated it
- aggregate field expressions use one owning recovered variable plus one
  deterministic synthetic field name of the form `field_<offset>`
- exact entry-stack-relative addresses of recovered stack-slot variables lower
  to unary address-of expressions over the recovered variable name
- unsupported values remain explicit through `CRawExpr` or residual control
  statements; they are never silently dropped

## Re-trigger and invalidation rules

- This stage is read-only with respect to stage-16 structure and all earlier
  analyses.
- It does not discover new functions, edges, blocks, call targets, source
  variables, or aggregate layouts.
- It does not emit new `pending_entries`, `invalidated_entries`, or scheduler
  invalidations.
- It preserves stage-16 `pending_entries`, `invalidated_entries`, and
  scheduler invalidations unchanged.
- If a later printing or cleanup stage wants to normalize returns, split raw
  expressions, or polish rendered syntax further, that later stage must own
  those decisions. Post 17 itself does not.

## Non-goals

- final user-facing C pretty-printing
- source-level naming recovery beyond existing synthetic names
- aggressive expression simplification or global constant folding
- semantic rewrites that require upstream proof, such as removing `raw<...>`
  evidence or inventing stronger condition operators than the current lowered
  compare tree supports
- broader pointer cleanup when the current function still lacks the aggregate,
  alias, or type facts needed to name the pointed-to object directly
- general multi-carrier call-result reconstruction beyond supported
  primary-return-to-lvalue folds and selected synthetic-local materializations
- general switch reconstruction beyond one already-recovered stage-16 switch
  surface
- alias analysis, heap-object recovery, or pointer provenance beyond the
  current variable and aggregate evidence
- full validity as compilable ISO C text; the artifact is C-like IR, not the
  final printer output

## Algorithm sketch

### declaration recovery

1. Start from one `FunctionStructuredFacts`.
2. Recover parameter declarations from the stage-15 prototype in mixed
   register-then-stack order.
3. Bind parameter carriers to stage-13 variables where names and types already
   exist.
4. Recover local declarations from stage-13 local variables in their existing
   deterministic order, skipping local stack-slot variables already promoted
   into stack-carried parameter declarations by stage 15.
5. Derive printed type spellings from scalar types and aggregate layouts:
   - `bool`
   - `int<size>_t`
   - `word<size>_t`
   - `void*`
   - synthetic aggregate pointer spellings such as `agg_8*`

### statement lowering

1. Build per-function lookup tables for:
   - SSA definitions and phi nodes
   - stage-8 callsites by instruction address
   - stage-15 internal callee prototypes by entry address
   - memory partitions by memory-access instruction
   - recovered variables by root value, stack slot, partition, and aggregate
     field partition
2. Lower each stage-16 node recursively.
3. For `StructuredBlock`, emit only side-effecting statements:
   - local/global/aggregate/indirect assignments from supported stores
   - call expression statements
   - supported primary-return call assignments when one immediate store writes
     the stage-7 `CALL_RETURN x10_*` value into one clean recovered lvalue
   - selected synthetic-local assignments for directly consumed `CALL_RETURN`
     carriers after the owning call
   - selected synthetic-local assignments for simple `if`-merge phis when one
     later use would otherwise fall back to a raw call-return carrier through
     the merge block
   - explicit return statements for return blocks
4. Do not emit standalone statements for pure SSA operations such as copies,
   arithmetic, loads, and compare temporaries; instead lower them on demand
   into expressions.
5. For `StructuredSwitch`, lower one selector expression from the first switch
   header compare, then lower ordered case and default bodies recursively.

### condition lowering

1. Recover the terminal `CBRANCH` input from each structured header block.
2. Lower the condition value recursively through compare-producing SSA ops.
3. For `StructuredIf`, use the condition sense that leads to `true_target`.
4. For `StructuredWhile`, use the condition sense that leads to `body_entry`,
   inverting the recovered branch condition when the taken edge is the loop
   exit.

### lvalue lowering

1. For stack-slot or partition accesses that map cleanly to one recovered
   variable, emit a named variable expression.
2. For aggregate-backed partitions, match the lowered address against one owning
   aggregate variable plus one optional scaled index plus one field offset.
3. Emit:
   - `arg_x10_4->field_0` when the access is one direct field reference
   - `arg_x10_4[idx].field_4` when the address matches one stride-scaled index
     plus one field offset
4. For absolute partitions without a recovered variable, emit a synthetic
   `global_0xADDR_<size>` expression.
5. For unsupported value-backed memory accesses, fall back to `CRawExpr`.

### address-of lowering

1. Lower one SSA value recursively as usual.
2. If the resulting expression is exactly one additive entry-stack-relative
   address of the form `x2_0 + constant` and that constant matches one
   recovered stack-slot variable binding in the current function, rewrite it to
   `&variable_name`.
3. Keep this rewrite local to exact stack-slot bindings only; do not invent
   aggregate array locals, pointer casts, or broader pointer provenance.

### return lowering

1. Use the stage-15 prototype return carriers in register order.
2. Reconstruct the current register binding at each return block from the
   block's phis plus register-defining SSA ops.
3. Lower each return carrier to one `CLoweredReturn`.
4. Emit one `CReturnStmt` with an explicit list of register-value bindings such
   as `return [x10=local_16_4, x11=arg_x11_4];`
5. When one return carrier comes from a supported simple merge phi that has
   already been materialized into one local on each `if` arm, return that
   named local instead of the raw phi SSA value.

Failure and bailout rules:

- if one memory access cannot be matched to a clean variable or field, keep it
  explicit as a raw expression rather than inventing an lvalue
- if one condition cannot be reconstructed as a supported compare tree, keep it
  explicit as a raw boolean expression
- if one call target stays unresolved, print a deterministic synthetic target
  rather than guessing a symbol name
- if one call result cannot be attached to one immediate clean lvalue or one
  supported synthetic local, keep the call as a plain expression statement and
  keep later uses explicit
- if one merge phi is not one supported two-arm `if` merge, keep it explicit
  rather than inventing source-level control-dependent assignments
- if one return carrier cannot be expressed cleanly, print its raw SSA value
- if one pointer-like value does not match one exact recovered stack-slot
  address, keep it explicit rather than guessing an address-of expression

## Data structures

- `CLoweredType`
  - owner: `tiny_dec/c_emit/models.py`
  - fields:
    - `spelling`
    - `size`
  - invariants:
    - spelling is non-empty
    - size is positive when present
  - pretty:
    - `int32_t`
- `CLoweredVariable`
  - owner: `tiny_dec/c_emit/models.py`
  - fields:
    - `name`
    - `kind`
    - `ctype`
    - `register`
  - invariants:
    - declaration order is deterministic at the function level
  - pretty:
    - `local int32_t local_16_4`
- `CLoweredReturn`
  - owner: `tiny_dec/c_emit/models.py`
  - fields:
    - `register`
    - `ctype`
  - invariants:
    - register is non-negative
  - pretty:
    - `return x10 int32_t`
- `CReturnBinding`
  - owner: `tiny_dec/c_emit/models.py`
  - fields:
    - `register`
    - `value`
  - invariants:
    - register is non-negative
  - pretty:
    - `x10=local_16_4`
- expression nodes
  - owner: `tiny_dec/c_emit/models.py`
  - kinds:
    - `CNameExpr`
    - `CFieldExpr`
    - `CGlobalExpr`
    - `CRawExpr`
    - `CConstExpr`
    - `CUnaryExpr`
    - `CBinaryExpr`
    - `CCallExpr`
  - invariants:
    - all printed names are non-empty
    - call arguments preserve the lowering-selected argument order
    - field offsets are non-negative
  - pretty:
    - `local_20_4`
    - `&local_12_4`
    - `arg_x10_4[i].field_4`
    - `global_0x2000_4`
    - `raw<x10_6:4>`
    - `(local_16_4 + local_20_4)`
    - `memset(local_16_4, 0, 32)`
- statement nodes
  - owner: `tiny_dec/c_emit/models.py`
  - kinds:
    - `CAssignStmt`
    - `CExprStmt`
    - `CReturnStmt`
    - `CIfStmt`
    - `CWhileStmt`
    - `CGotoStmt`
    - `CBreakStmt`
    - `CContinueStmt`
    - `CStmtSequence`
  - invariants:
    - nested statement order is preserved exactly
    - `goto`, `break`, and `continue` targets are explicit and non-negative
  - pretty:
    - `local_16_4 = 0;`
    - `if (local_16_4 != 0)`
    - `while (local_24_4 < arg_x11_4)`
    - `return [x10=local_20_4, x11=arg_x11_4];`
- `FunctionCLowered`
  - owner: `tiny_dec/c_emit/models.py`
  - fields:
    - `structured`
    - `parameters`
    - `locals`
    - `body`
  - invariants:
    - parameters follow prototype order
    - locals follow deterministic variable order
  - pretty:
    - summary line plus `signature:`, `locals:`, and `body:` sections
- `ProgramCLowered`
  - owner: `tiny_dec/c_emit/models.py`
  - fields:
    - `structured`
    - `functions`
    - `pending_entries`
    - `invalidated_entries`
    - `scheduler_invalidations`
  - invariants:
    - function coverage matches stage 16 exactly
    - scheduler state matches stage 16 exactly
  - pretty:
    - preserved program header plus nested lowered functions

## Edge cases

- entry blocks that mix real side effects with prologue noise before one branch
- loop headers whose condition is the inverse of the branch-taken edge
- aggregate accesses with one scaled index and one field offset
- absolute globals without a named recovered variable
- unresolved direct or indirect call targets
- return blocks that carry multiple return registers
- saved-register stack traffic that must be suppressed instead of printed as
  fake locals
- unsupported SSA op trees that must fall back to `CRawExpr`

## Pretty-print contract

Program-level pretty-printing must stay deterministic and diff-friendly:

- preserve the current root, order, pending, invalidated, externals, call
  graph, and scheduler sections from stage 16
- print one lowered function in entry order
- each function renders:
  - one summary line with counts
  - `signature:` with ordered parameters then ordered return carriers
  - `locals:` with ordered local declarations
  - `body:` with an indented statement tree
- expressions print on one line with deterministic precedence-aware
  parentheses
- purely presentational rewrites are allowed when they preserve the same
  lowered expression tree, such as:
  - `x + -2` -> `x - 2`
  - `x - -2` -> `x + 2`
  - `!(a < b)` -> `a >= b`
- these rewrites must stay local to `tiny_dec/c_emit/` and must not invent
  facts that upstream stages did not prove
- `return` prints an explicit register list in brackets

## End-to-end harness exposure

The persistent e2e harness should render every fixture binary through
`build_program_c_lowered` and `format_program_c_lowered`.

The harness output should make the following easy to inspect:

- whether each function now has sensible parameter and local declarations
- whether loops and nested branches stayed structurally correct
- whether aggregate field references appear for the struct fixture
- whether unresolved calls remain explicit instead of disappearing
- whether directly consumed secondary call returns now use stable synthetic
  locals instead of raw SSA carriers where supported, including later branch
  and return uses
- whether one supported direct multi-register call forwarder now renders
  through one temporary plus one aggregate return mapping instead of raw
  per-register carrier locals
- whether one supported direct multi-register call result now renders through
  one temporary plus projected field uses in the final return expression
- whether one supported grouped call-result cluster in the call fixture now
  renders through one temporary instead of one call plus one raw carrier local
  per consumed register
- whether returns show the currently-carried ABI return registers

## Validation commands

Record the commands that should be used while iterating:

- stage tests:
  `poetry run pytest -q tests/posts/post_17_c_lowering`
- e2e harness:
  `poetry run pytest -q tests/posts/post_17_c_lowering/test_c_lowering_e2e_harness.py`
- cli:
  `poetry run tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --func main --stage c_lowering`
- ruff:
  `poetry run ruff check tiny_dec/c_emit tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_17_c_lowering`
- mypy:
  `poetry run mypy tiny_dec/c_emit tiny_dec/cli.py tiny_dec/pipeline/decompile.py tests/posts/post_17_c_lowering`

## Open questions

- Whether stage 18 should keep multi-register returns explicit or collapse them
  into one printed primary return plus comments.
- Whether later work should recover full tuple-style call expressions instead
  of the current synthetic-local bridge for selected secondary-return uses.
