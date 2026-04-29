# Current Architecture and Implementation

This document is the repository's present-tense implementation snapshot.

Update it after each completed stage. It should describe what is implemented
and wired now, not future roadmap items or development tasks.

## Current scope

`tiny_dec` is implemented through `post_18_c_printer_pipeline`.

Public stage stops and debug surfaces currently exist for:

- `loader`
- `decode`
- `pcode`
- `disasm`
- `ir`
- `simplify`
- `dataflow`
- `ssa`
- `calls`
- `stack`
- `memory`
- `scalar_types`
- `aggregate_types`
- `variables`
- `range`
- `interproc`
- `structuring`
- `c_lowering`
- `c`

The final rendered-C endpoint is now real. `tiny_dec/c_emit/` owns the stage-17
C-like IR plus the stage-18 rendered source surface, and `tiny_dec/pipeline/`
owns the final decompile driver behavior on top of that rendered output.

## Current pipeline

The implemented pipeline is:

`ELF path -> ProgramView -> RV32I decode -> semantic p-code -> recursive disassembly -> ProgramIR / FunctionIR -> CanonicalProgramIR / CanonicalFunctionIR -> ProgramDataflowFacts / FunctionDataflowFacts -> SSAProgramIR / SSAFunctionIR -> ProgramCallFacts / FunctionCallFacts -> ProgramStackFacts / FunctionStackFacts -> ProgramMemoryFacts / FunctionMemoryFacts -> ProgramScalarTypeFacts / FunctionScalarTypeFacts -> ProgramAggregateTypeFacts / FunctionAggregateTypeFacts -> ProgramVariableFacts / FunctionVariableFacts -> ProgramRangeFacts / FunctionRangeFacts -> ProgramInterprocFacts / FunctionInterprocFacts -> ProgramStructuredFacts / FunctionStructuredFacts -> ProgramCLowered / FunctionCLowered -> ProgramCRendered / FunctionCRendered`

The main entrypoints are:

- `tiny_dec.pipeline.decompile_function`
- `tiny-dec decompile <binary> [--func NAME_OR_HEX] [--stage STAGE] [--strict-func]`
  - `--stage` choices: `loader|decode|pcode|disasm|ir|simplify|dataflow|ssa|calls|stack|memory|scalar_types|aggregate_types|variables|range|interproc|structuring|c_lowering|c` (default: `c`)
  - `--func` selects the function by symbol name or hex address (default: `main`)
  - `--strict-func` exits non-zero when the function selector cannot be resolved
- `tiny-dec info <binary> [--scan-size N]`
  - `--scan-size` controls the main-locator scan window in bytes (default: 512)

Each implemented stage has a deterministic text renderer. Those pretty-printers
are the main debugging and test surface for the repository today.

## Current stage ownership

| Post | Stage | Owner | Stable artifact |
| --- | --- | --- | --- |
| `post_00_loader` | Loader | `tiny_dec/loader/` | `ProgramView` |
| `post_01_decode` | Decode | `tiny_dec/decode/` | `RV32IInstruction` |
| `post_02_lift_pcode` | Semantic p-code lift | `tiny_dec/ir/` | `list[PcodeOp]` per instruction |
| `post_03_disasm` | Recursive disassembly | `tiny_dec/disasm/` | `DisasmFunction` |
| `post_04_ir_containers` | IR containers | `tiny_dec/ir/` | `FunctionIR`, `ProgramIR` |
| `post_05_simplify` | Canonical simplification | `tiny_dec/analysis/simplify/` | `CanonicalFunctionIR`, `CanonicalProgramIR` |
| `post_06_dataflow` | Intraprocedural dataflow | `tiny_dec/analysis/dataflow/` | `FunctionDataflowFacts`, `ProgramDataflowFacts` |
| `post_07_ssa` | Low-level SSA | `tiny_dec/analysis/ssa/` | `SSAFunctionIR`, `SSAProgramIR` |
| `post_08_calls` | Call modeling | `tiny_dec/analysis/calls/` | `FunctionCallFacts`, `ProgramCallFacts` |
| `post_09_stack` | Stack and frame recovery | `tiny_dec/analysis/stack/` | `FunctionStackFacts`, `ProgramStackFacts` |
| `post_10_memory` | Memory modeling | `tiny_dec/analysis/memory/` | `FunctionMemoryFacts`, `ProgramMemoryFacts` |
| `post_11_scalar_types` | Scalar type recovery | `tiny_dec/analysis/types/` | `FunctionScalarTypeFacts`, `ProgramScalarTypeFacts` |
| `post_12_aggregate_types` | Aggregate type recovery | `tiny_dec/analysis/types/` | `FunctionAggregateTypeFacts`, `ProgramAggregateTypeFacts` |
| `post_13_variables` | Variable recovery | `tiny_dec/analysis/highvars/` | `FunctionVariableFacts`, `ProgramVariableFacts` |
| `post_14_range` | Range and predicate refinement | `tiny_dec/analysis/range/` | `FunctionRangeFacts`, `ProgramRangeFacts` |
| `post_15_interproc` | Interprocedural summaries and prototype inference | `tiny_dec/analysis/interproc/` | `FunctionInterprocFacts`, `ProgramInterprocFacts` |
| `post_16_structuring` | Control-structure recovery | `tiny_dec/structuring/` | `FunctionStructuredFacts`, `ProgramStructuredFacts` |
| `post_17_c_lowering` | C-like IR lowering | `tiny_dec/c_emit/` | `FunctionCLowered`, `ProgramCLowered` |
| `post_18_c_printer_pipeline` | Rendered C and final pipeline driver | `tiny_dec/c_emit/`, `tiny_dec/pipeline/` | `FunctionCRendered`, `ProgramCRendered` |

## Current architecture

### Loader

`tiny_dec/loader/` owns ELF-backed program access through `ProgramView`.

Current responsibilities:

- expose architecture metadata, section layout, and external function metadata
- read bytes by virtual address
- resolve a best-effort `main` entry through symbol lookup and startup-code
  heuristics
- render deterministic loader snapshots

This is the repository's current program identity layer. Downstream stages read
from `ProgramView`; they do not open ELFs themselves.

### Decode

`tiny_dec/decode/` owns deterministic RV32I instruction decoding.

Current responsibilities:

- parse one 32-bit RV32I instruction word at a time
- produce `RV32IInstruction` objects with explicit bitfield-derived operands
- provide stable per-instruction pretty-printing
- expose linear function-window decode helpers for CLI and harness use

The decode layer is RV32I-only and word-oriented. It does not build CFGs or
perform traversal.

### Semantic p-code

`tiny_dec/ir/` currently owns both the p-code layer and the post-04 IR
containers.

Current p-code responsibilities:

- lift decoded instructions into semantic low-level p-code
- model varnodes explicitly through `Varnode`
- model p-code operations explicitly through `PcodeOp`
- preserve control-flow semantics such as calls, returns, direct branches, and
  indirect branches in a stage-3-consumable form

P-code is deterministic per instruction. SSA construction and cross-instruction
analysis happen in later stages (stage 7 onward).

### Disassembly

`tiny_dec/disasm/` owns function-level recursive disassembly.

Current responsibilities:

- start from one function entry address
- decode and lift reachable instructions
- group instructions into p-code basic blocks
- record deterministic direct CFG edges
- record direct call targets while staying intra-procedural
- render `DisasmFunction` deterministically

This stage does not recurse into callees and does not recover indirect targets.

### IR containers

`tiny_dec/ir/` also owns the first durable whole-function and whole-program IR
containers.

Current responsibilities:

- wrap one `DisasmFunction` as `FunctionIR`
- build a deterministic instruction index and callsite list
- build a rooted `ProgramIR`
- classify direct call targets as internal, external through loader
  PLT/GOT/symbol metadata, or unresolved
- discover directly called internal functions
- record a deterministic direct call graph
- initialize scheduler state through empty `pending_entries` and
  `invalidated_entries` (consumed by stage-18 pipeline scheduler)

`ProgramIR` and `FunctionIR` are the current boundary between early pipeline
recovery and later analysis stages. They preserve stage-3 structure rather than
rewriting it.

### Simplify

`tiny_dec/analysis/simplify/` owns the first analysis-stage canonicalization
pass.

Current responsibilities:

- canonicalize one lifted instruction at a time without changing CFG topology
- fold constant-only p-code into simpler `COPY const` forms
- collapse identity operations such as add-zero and and-all-ones
- forward single-use `unique` temporaries into trailing copy targets
- renumber surviving `unique` temporaries densely per instruction
- rebuild canonical block, function, and program containers while preserving
  stage-4 metadata

This stage is still low-level and block-structured. It does not perform
inter-instruction propagation, SSA construction, or dataflow analysis.

### Dataflow

`tiny_dec/analysis/dataflow/` owns the first explicit dataflow pass on top of
canonical IR.

Current responsibilities:

- run a forward intraprocedural worklist over canonical blocks
- track a tiny constant lattice for non-`x0` register facts
- recompute deterministic block `in` and `out` states
- evaluate per-instruction `unique` temporaries locally inside one instruction
- recover constant indirect branch and indirect call targets from `BRANCHIND`
  and `CALLIND`
- derive program-level `pending_entries` and `invalidated_entries` suggestions
  without mutating upstream IR

This stage is intentionally conservative. Memory remains unknown, calls kill
explicit register facts, and the queue suggestions stay descriptive inside
dataflow itself even though the final pipeline now consumes them later during
scheduled rendered-C building.

### SSA

`tiny_dec/analysis/ssa/` owns low-level SSA construction on top of the reachable
stage-6 CFG.

Current responsibilities:

- restrict SSA construction to blocks whose stage-6 `in_state` is reachable
- compute dominators, immediate dominators, and dominance frontiers
- place register phi nodes with the dominance-frontier algorithm
- place one coarse low-level memory phi where the single memory-version stream
  merges
- rename registers into stable SSA versions with lazy version-0 live-ins
- rename instruction-local `unique` temporaries into function-wide SSA names
- thread one conservative low-level memory-version state through `LOAD`,
  `STORE`, `CALL`, and `CALLIND`
- run one small post-rename normalization pass that elides same-base identity
  copies and trivial register or memory phis
- synthesize fixed RV32I ILP32 `CALL_RETURN` defs for `x10` and `x11` after
  each low-level call instruction so downstream stages can refer to explicit
  post-call SSA values
- preserve stage-6 program metadata, queue suggestions, and canonical block
  ordering around the renamed SSA blocks

This is still a low-level p-code view. Its memory SSA layer is intentionally
coarse and function-local, not partition-aware. The normalization is still
deliberately small; it does not do aggressive copy propagation or recover
high-level variables.

### Calls

`tiny_dec/analysis/calls/` owns the first typed call-boundary model on top of
SSA.

Current responsibilities:

- classify callsites as internal, external, or unresolved
- preserve one stage-4 fallback that can map a self-targeting unresolved direct
  call to one ordered undefined external name when the loader lacks a concrete
  address
- preserve direct versus indirect call identity
- preserve one explicit unresolved indirect callee carrier value separately
  from ordinary ABI argument snapshots when it can be recovered from the
  low-level `CALLIND` input
- attach fixed RV32I ILP32 argument, return, and clobber carrier sets
- snapshot currently-known SSA argument carrier values at each callsite
- snapshot currently-known outgoing stack-argument values at each callsite
- omit contiguous `sp`-relative slots from that outgoing stack-argument surface
  when the caller later reloads the same slot back into the same register base
- snapshot the coarse stage-7 memory version before and after each low-level
  call
- snapshot SSA return-carrier values materialized by stage-7 `CALL_RETURN`
  defs at each callsite
- attach small curated known-external signature hints such as `malloc`,
  `memset`, `puts`, and `free` when stage 8 has a named external callee
- refine the program-level call graph for callsites with concrete target
  addresses
- emit pending function-entry suggestions for newly discovered internal
  callees without reopening the caller CFG

This stage is still intentionally conservative. It does not infer parameter
counts, full prototypes, no-return behavior, incoming stack-parameter
declarations, variadics, or partition-aware memory side effects.

### Stack

`tiny_dec/analysis/stack/` owns conservative stack and frame recovery on top of
stage-8 call facts.

Current responsibilities:

- treat the SSA live-in `x2` value as the entry stack top when it exists
- track symbolic values of the form `frame_top + constant` through `COPY`,
  `INT_ADD`, and `INT_SUB`
- recover constant stack-pointer deltas from `x2` updates
- recover a conventional frame-pointer base when `x8` is assigned a known
  frame-top-relative value
- recognize `LOAD` and `STORE` operations whose address resolves to a known
  stack offset
- group stack accesses into deterministic frame slots
- classify a few slot roles conservatively as saved-register, argument-home, or
  local
- preserve stage-8 call graph and scheduler metadata unchanged

This stage is still intentionally conservative. It only models stack addresses
that reduce to `frame_top + constant`, reports `dynamic_sp=yes` when `x2`
updates stop fitting that form, and does not yet replace call signatures with
stack-argument locations or perform general memory modeling.

### Memory

`tiny_dec/analysis/memory/` owns conservative memory partition recovery on top
of stage-9 stack facts.

Current responsibilities:

- project recovered stage-9 stack slots into explicit stack memory partitions
- carry the coarse stage-7 memory version seen by each recorded `LOAD` or
  `STORE`, including stack-slot accesses matched back to their SSA ops
- rebuild tracked address facts across SSA defs until they stabilize, so
  compatible phi joins can keep one shared stack, absolute, or value-root form
- preserve one scaled dynamic index on value-root addresses so simple
  `base + (index << k) + field_offset` walks still normalize onto one stable
  root plus field offset
- recognize address expressions that stay reducible to stack offsets, absolute
  addresses, or value roots plus constant offsets
- preserve reloaded pointer arguments from `argument_home` slots so later
  constant-offset dereferences can still point back to the original live-in
  root
- recover deterministic non-stack partitions for absolute addresses and
  value-based pointer accesses
- fall back to raw SSA address values when arithmetic stops fitting the tracked
  forms
- preserve stage-9 call-graph and scheduler metadata unchanged

This stage is still intentionally conservative. It does not perform alias
analysis, partition-local memory SSA, heap/global partitioning, field
inference, call-effect modeling, or stack-argument promotion into the call ABI
model.

### Scalar types

`tiny_dec/analysis/types/` currently owns conservative scalar-type recovery on
top of stage-10 memory facts.

Current responsibilities:

- build deterministic scalar-identity groups across SSA copies, phi nodes, and
  stage-10 memory partition traffic
- seed pointer facts from stage-10 value-partition bases and from
  address-style constant-offset arithmetic on argument-home reload groups
- seed boolean facts from compare outputs, branch conditions, and
  `BOOL_NEGATE`
- seed integer facts from signed comparisons, constant copies, shifts, and
  non-pointer arithmetic
- use `word` as a weak fallback for equality, bitwise operations, and absolute
  partitions until stronger evidence exists
- preserve stage-10 externals, call graph, `pending_entries`, and
  `invalidated_entries` unchanged

This stage is still intentionally conservative. It only recovers four scalar
classes (`bool`, `int`, `pointer`, `word`), it does not infer source-level C
scalar distinctions, and conflicting precise evidence degrades to `word`.

### Aggregate types

`tiny_dec/analysis/types/` also owns conservative aggregate-layout recovery on
top of stage-11 scalar facts.

Current responsibilities:

- rebuild deterministic pointer-root candidates across pointer copies, phis,
  and pointer-typed memory traffic
- track small integer stride hints from shifted non-constant values and
  constant-preserving arithmetic
- track pointer expressions of the form `root + unknown_multiple_of(stride) +
  constant`
- recover deterministic aggregate layouts from typed stage-10 value partitions
  whose address expressions stay attributable to one canonical root
- preserve stage-11 externals, call graph, `pending_entries`, and
  `invalidated_entries` unchanged

This stage is intentionally conservative. It only emits pointer-rooted layouts
with constant field offsets and an optional repeated stride, it does not infer
field names, nested aggregates, arrays, globals, or source-level `struct`
declarations, and conflicting precise field kinds degrade to `word`.

### Variables

`tiny_dec/analysis/highvars/` currently owns conservative variable recovery on
top of stage-12 aggregate facts.

Current responsibilities:

- choose deterministic durable anchors for aggregate-backed variables
- recover stack-backed parameters and locals from argument-home and local stack
  slots while omitting saved-register bookkeeping slots
- preserve absolute partitions as explicit globals
- preserve leftover value partitions as explicit indirect dereference variables
- recover register-only ABI parameters when they have scalar type facts but no
  stronger stack anchor
- preserve stage-12 externals, call graph, `pending_entries`, and
  `invalidated_entries` unchanged

This stage is intentionally conservative. It emits only synthetic variable
names, does not perform alias-aware merging, does not promote generic SSA
temporaries into variables, and falls back to explicit `indirect` groups when
pointer provenance does not map cleanly to a parameter or local anchor.

### Range

`tiny_dec/analysis/range/` currently owns conservative range and predicate
refinement on top of stage-13 variable facts.

Current responsibilities:

- seed exact ranges from literal constants and boolean surfaces from stage-11
  scalar facts and predicate-producing SSA ops
- propagate small signed intervals through copies, phi nodes, selected
  partition-local load/store identities, `INT_ADD`, `INT_SUB`, `INT_AND`, and
  `BOOL_NEGATE`
- use a deterministic widening rule so loop-carried interval growth converges
  to half-bounded facts instead of iterating forever
- project recovered SSA ranges onto stage-13 variables through roots, memory
  access values, and boolean variable types
- recover edge-local branch refinements for supported compare patterns that
  reduce to one tracked SSA value plus one exact constant
- preserve stage-13 externals, call graph, `pending_entries`, and
  `invalidated_entries` unchanged

This stage is intentionally conservative. It only emits one signed interval per
value or variable, only handles a small predicate subset, and omits unsupported
arithmetic or non-interval facts rather than inventing precision.

### Interproc

`tiny_dec/analysis/interproc/` currently owns conservative interprocedural
summaries and prototype inference on top of stage-14 range facts.

Current responsibilities:

- infer explicit register-carried parameter carriers from stage-13 parameter
  variables and stage-7 live-ins, then use internal caller observations only
  to refine already-supported carriers
- infer explicit stack-carried parameter carriers for internal callees when one
  non-negative stage-13 stack-slot local matches one observed internal
  stack-argument offset
- ignore duplicate trivially forwarded caller-carrier aliases at one internal
  callsite when refining observed parameter hints
- prune root-value-only local parameter carriers for internal functions when
  observed internal callers never supply that register
- infer conservative return carriers from return-block register snapshots
- suppress return carriers that are only compare-scratch register traffic,
  observed-unconsumed secondary internal call-return traffic, or unsupported
  forwarded internal-callee carriers
- reuse one exposed single-register internal-callee scalar return type when a
  caller return carrier is only forwarding that same callee carrier
- classify internal functions as returning or no-return
- summarize absolute-memory reads and writes plus value-partition indirect
  read/write behavior
- preserve stage-14 `pending_entries`
- add caller invalidation suggestions when an internal callee is inferred as
  no-return
- merge preserved and scheduler-driven caller invalidations into deterministic
  program-level `invalidated_entries` and `scheduler_invalidations`

This stage is intentionally conservative. It only models small mixed
register-plus-stack prototypes for supported internal callees, only emits small
memory-side-effect summaries, and does not yet rewrite caller callsites,
specialize the call ABI surface for variadics or aggregate-by-value cases, or
compose transitive summaries across the call graph.

### Structuring

`tiny_dec/structuring/` currently owns conservative control-structure recovery
on top of stage-15 interprocedural facts.

Current responsibilities:

- recover straight-line prefixes as ordered `StructuredBlock` leaves
- recover pretested natural loops as `StructuredWhile` nodes when the loop
  header has one in-loop successor and one exit successor
- recover nested two-way branches as `StructuredIf` nodes when both branch
  regions structure cleanly up to one immediate postdominator
- collapse one narrow constant-equality dispatch ladder with one shared merge
  into a dedicated `StructuredSwitch` node with explicit ordered cases plus a
  default body
- elide jump-only trampoline blocks inside structured branch legs when they
  only forward control to the next meaningful node in the same region
- preserve unsupported cross-region transfers explicitly as `goto`, `break`,
  or `continue` leaves instead of guessing a higher-level shape
- preserve stage-15 externals, call graph, `pending_entries`,
  `invalidated_entries`, and scheduler invalidations unchanged

This stage is intentionally conservative. It only recovers one small
constant-equality switch subset, and it still does not normalize irreducible
CFGs, lower source expressions, or rewrite the upstream CFG.

### C Lowering

`tiny_dec/c_emit/` currently owns conservative C-like IR lowering on top of
stage-16 structure.

Current responsibilities:

- recover typed parameter declarations from stage-15 prototypes plus stage-13
  variables, including promoted stack-carried parameter slots
- recover typed local declarations from stage-13 local variables that were not
  promoted into stack-carried parameters
- lower structured `if` and `while` nodes into explicit C-like statement trees
- lower recovered stage-16 `StructuredSwitch` nodes into explicit
  `CSwitchStmt` / `CSwitchCase` trees, reusing the first compare as the switch
  selector expression and inserting explicit case breaks when control rejoins
  one shared merge
- lower supported stores into assignments, supported callsites into call
  expression statements, and supported immediate `CALL_RETURN x10_*` store
  patterns into one folded call-result assignment
- render known direct internal call arguments in stage-15 callee prototype
  order for the subset of carrier values known at the callsite
- render named external call arguments in stage-8 known external-signature
  order when that signature exists, while leaving unresolved or unspecialized
  external callsites in raw stage-8 carrier order
- materialize selected directly consumed call-return carriers into
  deterministic synthetic locals so later calls, conditions, and return
  bindings can use stable names
- materialize selected simple `if`-merge phis for returned call carriers into
  deterministic synthetic locals so structured merge blocks can reuse one
  named value instead of falling straight back to raw carrier phis
- lower return blocks into explicit register-carried return lists
- lower supported SSA expressions lazily from copies, integer arithmetic,
  compares, loads, and small constant-only folds
- project stage-12 aggregate layouts into synthetic field expressions such as
  `arg_x10_4[idx].field_4`, using the aggregate-layout size as a fallback
  stride when the upstream layout omits an explicit repeated stride
- preserve stage-16 externals, call graph, `pending_entries`,
  `invalidated_entries`, and scheduler invalidations unchanged

This stage is intentionally conservative. It still keeps unresolved low-level
details explicit through raw expressions, explicit register-carried returns,
secondary call-return carriers that survive through wider or unsupported
control merges, and synthetic variable and field spellings so the final
printer does not need to guess missing source semantics.

### C Printing and Pipeline Driver

`tiny_dec/c_emit/` now also owns the final rendered-C artifact on top of
stage-17 lowering, while `tiny_dec/pipeline/` owns the final `decompile`
driver behavior plus the explicit rerun scheduler around the final stage-18
builder.

Current responsibilities:

- build one direct rendered-C function snapshot for internal API consumers and
  scheduled program assembly
- synthesize deterministic aggregate helper structs such as `agg_8`
- synthesize deterministic multi-register return helper structs such as
  `ret_x10_x11`
- map unknown `word<size>_t` carriers into concrete unsigned `<stdint.h>`
  spellings in the final source surface
- render stage-17 statements into braced `if` and `while` source text with
  stable two-space indentation, including `else if` chains when one `else`
  arm contains exactly one nested branch and braced `switch (...)` statements
  with deterministic case order and explicit `break;` lines for the current
  recovered-switch subset
- render stage-17 expressions and stage-18 final expressions through one
  shared precedence-aware formatter that keeps safe local rewrites such as
  `x + -2 -> x - 2`, `x - -2 -> x + 2`, and `!(a < b) -> a >= b`
- rewrite exact entry-stack-relative addresses of recovered stack-slot
  variables to `&local_*` style expressions instead of preserving raw
  stack-pointer arithmetic in the stage-17 and stage-18 surfaces
- preserve unresolved low-level evidence explicitly through residual
  `raw<...>` expressions instead of guessing source syntax
- run a deterministic final scheduler that:
  - starts from the selected root entry
  - schedules new root builds for preserved `pending_entries`
  - schedules one additional rerun per unique invalidation cause
  - merges the completed root renders into one translation unit
- render scheduled translation-unit output for `tiny-dec decompile --stage c`
  and default `tiny-dec decompile`, with leading `root`,
  `scheduled_roots`, queue-state, and scheduler-invalidation comments
  followed by helper declarations, forward declarations, and function
  definitions
- make `tiny-dec decompile` default to the final `c` stage while keeping
  `--stage c_lowering` available as the last debug-IR stop

This stage is intentionally conservative. The rendered output is readable and
stable, but it is still pseudo-C in places: raw expressions can survive,
call-result cleanup is still limited by earlier SSA surfaces plus the current
synthetic-local bridge for selected directly consumed carriers, one supported
direct single-register internal-call wrapper now renders through one scalar
temporary of the callee return type instead of a rendered-only `{ x10; }`
helper struct,
one supported
direct multi-register wrapper-forwarding case now renders through one typed
temporary plus one aggregate return mapping, one supported direct call-result
projection case now renders through one typed temporary plus projected field
uses in the final return, one supported grouped call-result cluster now
renders through rendered-only call temporaries instead of one raw carrier
local per consumed register, and function/field names remain synthetic unless
earlier stages already recovered better ones.

## Current user-facing surfaces

`tiny_dec/cli.py` currently exposes:

- `tiny-dec decompile`
- `tiny-dec info`

`tiny_dec/pipeline/decompile.py` is the current stage-stop driver used by
`tiny-dec decompile`. It can still render earlier debug stages, and now
defaults to the final rendered-C `c` stage.

## Current testing and harness structure

Implemented stages have dedicated post folders under `tests/posts/`:

- `tests/posts/post_00_loader`
- `tests/posts/post_01_decode`
- `tests/posts/post_02_lift_pcode`
- `tests/posts/post_03_disasm`
- `tests/posts/post_04_ir_containers`
- `tests/posts/post_05_simplify`
- `tests/posts/post_06_dataflow`
- `tests/posts/post_07_ssa`
- `tests/posts/post_08_calls`
- `tests/posts/post_09_stack`
- `tests/posts/post_10_memory`
- `tests/posts/post_11_scalar_types`
- `tests/posts/post_12_aggregate_types`
- `tests/posts/post_13_variables`
- `tests/posts/post_14_range`
- `tests/posts/post_15_interproc`
- `tests/posts/post_16_structuring`
- `tests/posts/post_17_c_lowering`
- `tests/posts/post_18_c_printer_pipeline`

Each implemented post includes stage-scoped tests, and the current stage keeps
an end-to-end harness that runs the fixture binaries and prints the latest real
pipeline artifact in a deterministic format.

Fixture binaries live under `tests/fixtures/`.

## Current limitations

- Input scope is Linux ELF, with RV32I-focused fixtures and decoding.
- The implemented public pipeline now ends at rendered `c`.
- All analysis packages under `tiny_dec/analysis/` are implemented through
  their current conservative scope as described above.
- Indirect target recovery is limited to intraprocedural constant results for
  `BRANCHIND` and `CALLIND`. `CALLIND` recovery can now feed call modeling and
  pending-callee suggestions, but it does not yet reopen disassembly or mutate
  the CFG automatically.
- SSA is still low-level and register-focused. Coarse memory SSA and a small
  normalization pass now exist for same-base identity copies, trivial
  register or memory phis, and later-use canonicalization of trivial
  register-forwarding copies, but broader SSA cleanup and source-level
  call/return modeling are still limited.
- The final rendered C still exposes residual pseudo-C where stage-17 lowering
  had to preserve `raw<...>` expressions or explicit low-level return carriers.
- Call modeling uses a fixed RV32I ABI surface. It does not infer prototypes,
  no-return behavior, or incoming stack-parameter locations by itself, but it
  now does capture outgoing stack-argument stores plus small curated named
  external signature hints, filters obvious saved-register restore slots from
  that outgoing stack-argument view, and can fall back to ordered undefined
  externals when stage 4 only sees self-targeting unresolved direct calls.
- Stack recovery only handles stack addresses that stay expressible as
  `frame_top + constant`. It does not model heap/global memory, dynamic
  allocation, aliasing, or stack argument integration with the call ABI model.
- Memory modeling only partitions addresses that remain reducible to stack
  slots, absolute constants, value roots plus constant offsets, or one
  value-root plus one scaled dynamic index plus constant field offset.
  Richer pointer walks, unknown aliasing, and multi-root arithmetic still fall
  back to raw SSA address partitions, and no type or field structure is
  inferred yet.
- Scalar-type recovery only recognizes `bool`, `int`, `pointer`, and `word`.
  It now also promotes one local stack-slot group tied to a stored call-result
  chain to `int` when later `+/- const` arithmetic proves scalar use, which is
  enough for `fixture_basic`-style helper results to propagate as `int`
  through variables and final C. It does not infer signed versus unsigned
  source types or interprocedural prototypes, and some saved-register traffic
  can still appear as weak `word` facts when the low-level p-code uses
  bitwise canonicalization.
- Aggregate-type recovery only models pointer-rooted layouts that stay
  expressible as one canonical root plus constant field offsets and, when
  recoverable, one repeated stride. It does not infer field names, nested
  aggregates, arrays, global layouts, or source-level declarations.
- Variable recovery only forms conservative parameter, local, global, and
  indirect groups from durable stack slots, aggregate roots, live-in ABI
  arguments, and remaining memory partitions. It does not recover true source
  names, merge aliases aggressively, or classify heap objects beyond explicit
  indirect dereference groups.
- Range refinement only recovers one interval per value or variable and a small
  branch-refinement subset. It does not model relational constraints, exact
  loop trip counts, exclusion sets, alias-aware numeric reasoning, or
  interprocedural constant propagation.
- Interprocedural summaries only recover conservative mixed register-plus-stack
  prototypes for supported internal callees, local no-return classification,
  and small memory-effect summaries. They do not yet rewrite caller callsites
  upstream, support variadics or aggregate-by-value prototypes, compose
  summaries transitively, or reopen earlier stage ownership beyond the final
  pipeline's scheduled rendered-C reruns.
- Structuring recovers straight-line blocks, nested two-way branches,
  pretested natural loops, and one narrow constant-equality ladder as a real
  `switch`. It does not normalize irreducible CFGs, perform general condition
  expression reconstruction, or recover broader `switch` families yet.
- C lowering only emits a conservative C-like IR. It does not yet print final
  C syntax, infer polished type names, recover call-result assignments without
  upstream SSA support, reconstruct full tuple-style call expressions, or
  normalize multi-register returns into source-level function signatures.
- `ProgramIR` already carries queue-like fields for iterative reanalysis,
  stage-6 reports CFG and call-target suggestions, stage-8 can add pending
  internal callees, stages 9 through 14 preserve that scheduler state
  unchanged, stage 15 can now add caller invalidations for no-return internal
  callees, stages 16 and 17 preserve that scheduler state unchanged while
  building the structured and lowered views, and `tiny_dec/pipeline/` now
  consumes that preserved state in the final `c` surface by scheduling extra
  root builds plus one-shot caller reruns. Earlier owners still do not reopen
  disassembly or CFG shape automatically from those suggestions.

## Current enhancement-plan alignment

- Checkpoint 1 is implemented: `tiny_dec/pipeline/` owns an explicit rerun
  scheduler through `scheduler.py` and `passes.py`, and the final `c` surface
  consumes preserved pending-entry and invalidation state.
- Checkpoint 2 is partially implemented: `tiny_dec/analysis/ssa/` now
  synthesizes `CALL_RETURN` carriers for `x10` and `x11`, threads one coarse
  low-level memory-version SSA stream with optional memory phis, runs one small
  normalization pass for same-base identity copies, trivial register or memory
  phis, and later-use canonicalization of trivial register-forwarding copies,
  stage 8 now snapshots that coarse memory state at call boundaries and can
  bind a trivially forwarded register carrier to the forwarded SSA value,
  stage 10 now carries those coarse memory versions on recorded `LOAD` and
  `STORE` accesses, stage 17 can now carry selected simple merge phis for
  returned call-result carriers through one synthetic local, and stage 18 can
  now collapse one supported direct multi-register wrapper forwarder into one
  typed temporary plus one aggregate return mapping and one supported direct
  projected call-result return into one typed temporary plus projected field
  uses and can group one supported call-result cluster into rendered-only call
  temporaries, but broader SSA cleanup and wider source-level call/return
  modeling are still absent.
- Checkpoint 3 is partially implemented: `tiny_dec/analysis/interproc/`
  recovers conservative register-carried prototypes plus supported internal
  stack-carried parameters, no-return classification, caller invalidation
  suggestions, suppresses compare-scratch, observed-unconsumed secondary, and
  unsupported forwarded internal return carriers, ignores duplicate trivially
  forwarded caller-carrier aliases when refining observed internal parameter
  hints, refuses to invent observed-only register parameters for internal
  callees without local support, prunes root-value-only local parameters when
  observed internal callers never supply that carrier, and can reuse one
  exposed single-register
  internal-callee scalar return type for a directly forwarded caller carrier,
  and now also suppresses unsupported external secondary return carriers when
  stage 8 attached a known external signature; stage 8 now also recovers
  outgoing stack-argument snapshots, ordered undefined-external fallback
  names, small curated known-external signatures, and one explicit unresolved
  indirect callee carrier value without also misclassifying that carrier as an
  ordinary argument; stage 17 and stage 18 now consume that refined surface
  when rendering unresolved indirect calls as `call_indirect(target, ...)`
  alongside named libc-style calls and supported internal stack-argument
  calls, but the pipeline still does not support variadics or recover concrete
  indirect callees once the target flows through memory.
- Checkpoint 4 is partially implemented: `tiny_dec/analysis/memory/` preserves
  compatible tracked address forms through phi joins and one scaled dynamic
  index and now surfaces the coarse stage-7 memory versions on each recorded
  access, but partition-local memory-version refinement, alias analysis, heap
  modeling, and richer multi-root address reasoning are still absent.
- Checkpoint 5 is partially implemented: `tiny_dec/structuring/` now elides
  jump-only branch trampolines and recovers one narrow constant-equality
  dispatch ladder as a dedicated `StructuredSwitch`, while `tiny_dec/c_emit/`
  lowers and renders that subset as a real `switch` statement, but the
  pipeline still does not reconstruct higher-level condition expressions
  generally, normalize irreducible CFG regions, or recover broader switch
  families such as table-based dispatch.
- Checkpoint 6 is partially implemented: `tiny_dec/analysis/types/` can now
  promote one stored call-result local through later `+/- const` arithmetic to
  `int`, which improves downstream variable and final-C typing for that narrow
  slice, but signed-versus-unsigned distinctions, nicer recovered names, and
  alias-aware high-variable merging are still not implemented.
- Checkpoint 7 is partially implemented: `tiny_dec/c_emit/` now renders stable
  final source, folds selected primary call results, and materializes selected
  directly consumed or simple-merge carried call-return carriers into
  synthetic locals, and scalarizes one critical single-register internal
  call-wrapper case in final C; it also now applies one shared
  precedence-aware expression formatter across the stage-17 and stage-18
  surfaces so negated comparisons and `+/-` constant spellings read more like
  C and exact recovered stack-slot addresses now spell as `&local_*` instead
  of raw entry-stack arithmetic, but residual `raw<...>` expressions and
  synthetic names remain visible where ABI or SSA facts are still missing.
- In the ordered enhancement plan, checkpoint 2 remains the earliest unmet
  dependency for most further semantic cleanup because upstream SSA still lacks
  richer call-result shaping and broader SSA cleanup before later
  partition-aware memory refinement and final C cleanup can build on it.

## Current documentation split

- `implementation.md`: current architecture and implementation snapshot
- `development.md`: development environment, validation rhythm, and workflow
