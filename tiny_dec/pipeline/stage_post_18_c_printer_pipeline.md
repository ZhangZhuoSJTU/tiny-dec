# Stage Contract: `post_18_c_printer_pipeline`

## Summary

- Stage name: `post_18_c_printer_pipeline`
- Owner directories:
  - primary: `tiny_dec/pipeline/`
  - supporting printer owner: `tiny_dec/c_emit/`
- Immediate predecessor: `post_17_c_lowering`
- Immediate successor: none; this is the current final public stage

## Purpose

Turn the stage-17 C-like IR into the repository's first final user-facing
artifact: rendered C-like source text.

This stage has two tightly coupled responsibilities:

- `tiny_dec/c_emit/`
  - own deterministic source rendering from `FunctionCLowered` and
    `ProgramCLowered`
  - synthesize helper declarations for aggregate pointer layouts and explicit
    multi-register return carriers
- `tiny_dec/pipeline/`
  - own the final `tiny-dec decompile` driver behavior
  - own the explicit rerun scheduler that consumes preserved
    `pending_entries`, `invalidated_entries`, and scheduler invalidations
    around the final rendered-C builder
  - expose the new final stage stop as `c`
  - keep earlier debug stage stops, especially `c_lowering`, available

The rendered artifact is intentionally conservative. It is more source-shaped
than stage 17, but it still prints synthetic names, residual raw expressions,
and explicit synthesized helper types where the upstream pipeline has not yet
recovered more source-level intent.

## Inputs

- `ProgramCLowered` from `tiny_dec.c_emit.models`
- `FunctionCLowered` from `tiny_dec.c_emit.models`
- `ProgramCRendered` from `tiny_dec.c_emit.models`
- embedded stage-16 structure, stage-15 prototypes, stage-13 variables,
  stage-12 aggregate layouts, and earlier preserved scheduler state reachable
  through the existing upstream chain
- the existing public stage-stop driver in `tiny_dec/pipeline/decompile.py`
- the existing stage-debug CLI surfaces in `tiny_dec/cli.py`
- explicit pipeline helpers in:
  - `tiny_dec/pipeline/scheduler.py`
  - `tiny_dec/pipeline/passes.py`

Assumptions:

- stage-17 declaration order, statement order, function order, and type
  spellings are already deterministic
- stage-17 explicit raw expressions and explicit register-carried returns are
  truthful and must remain visible rather than guessed away
- aggregate field names remain synthetic (`field_<offset>`) unless earlier
  stages already recovered better names
- the final printed artifact does not need to be valid ISO C as long as it is
  stable, readable, and honest about unsupported cases

## Outputs

- `FunctionCRendered`
  - one deterministic function-level rendered-C snapshot
  - stores the chosen function name, rendered return type spelling, stable
    prototype line, and rendered body lines
- `ProgramCRendered`
  - one deterministic program-level rendered-C snapshot
  - stores helper include lines, synthesized type declarations, forward
    declarations, rendered functions, and preserved scheduler state
- `format_function_c_rendered(...)`
  - render one function snapshot into stable source text
- `format_program_c_rendered(...)`
  - render one full program snapshot into stable source text
- `build_function_c_rendered(...)`
  - derive one rendered function from a `ProgramView`
- `build_program_c_rendered(...)`
  - derive the final rendered program from a `ProgramView`
- `ScheduledPassRun`
  - one deterministic record of which entry roots were built, rerun, and left
    pending by the explicit scheduler
- `ScheduledCRenderedProgram`
  - one deterministic final translation-unit snapshot assembled from one or
    more scheduled stage-18 program renders
- `build_scheduled_c_rendered_program(...)`
  - run the explicit scheduler around stage-18 program rendering and merge the
    completed roots into one final artifact
- `format_scheduled_c_rendered_program(...)`
  - render the scheduled final program snapshot into stable source text
- `render_scheduled_c_program(...)`
  - convenience entrypoint that builds and formats one scheduled final program
- `tiny-dec decompile [--stage c]`
  - final pipeline driver entrypoint that defaults to rendered C

Output invariants:

- rendered program function coverage matches the stage-17 program exactly
- scheduled final-program function coverage is the deterministic union of the
  scheduled root snapshots that completed in the current scheduler run
- helper declarations are ordered deterministically and deduplicated by shape
- aggregate helper types are named from their stable synthetic stage-17
  spellings, such as `agg_8`
- multi-register returns become explicit synthesized helper structs, such as
  `ret_x10_x11`
- single-register returns stay as one scalar or pointer type spelling
- empty parameter lists print as `void`
- rendered statements preserve stage-17 order and control structure without
  inventing missing source constructs
- recovered stage-17 switch statements render as one braced `switch (...)`
  statement with ordered `case` labels and one `default:` section
- the stage-18 owner artifact still preserves `pending_entries`,
  `invalidated_entries`, and scheduler invalidations unchanged
- the pipeline scheduler may consume those preserved suggestions and emit the
  remaining queue state after the scheduler run in the final source comments
- each scheduled root is built at least once
- each unique invalidation cause triggers at most one additional rerun of the
  affected entry during one scheduler run

## Re-trigger and invalidation rules

- The stage-18 builder remains read-only with respect to stage-17 C lowering
  and all earlier stages.
- The pipeline scheduler does not mutate stage-owned facts in place; it only
  decides which entry roots to rebuild and how to merge their rendered outputs.
- Newly observed `pending_entries` schedule additional root builds during the
  same final pipeline run.
- Newly observed `invalidated_entries` and scheduler invalidations schedule one
  additional rerun of the affected entry during the same final pipeline run.
- The final scheduled artifact exposes the remaining, unconsumed queue state as
  leading comments rather than the raw per-root preserved suggestions.

## Non-goals

- source-name recovery beyond existing synthetic parameter, local, global, and
  field spellings
- full compilable ISO C output for every unsupported raw expression
- source-level return-signature normalization beyond explicit synthesized
  helper structs for multi-register returns
- new control-structure recovery beyond the stage-16 structured tree
- call-result rewriting beyond what stage 17 already modeled
- header-file splitting, include minimization, or cross-translation-unit output

## Algorithm sketch

1. Start from one `ProgramCLowered`.
2. Scan all ordered functions to gather the helper declarations the final
   printed source needs:
   - aggregate helper structs from variable aggregate layouts
   - synthesized return structs for any function with more than one return
     carrier
3. Deduplicate helper declarations by structural shape and emit them in stable
   order.
4. Render each function deterministically:
   - choose one printed function name from the existing symbol name or a stable
     synthetic fallback such as `fn_0x110e4`
   - choose one printed return type:
     - `void` for zero carriers
     - the single lowered carrier type for one carrier
     - one synthesized return helper struct name for multiple carriers
   - render parameters in prototype order and locals in declaration order
   - render statement trees recursively with braces and indentation
   - render switch statements with deterministic case order and explicit
     `break;` lines when the case body does not already terminate
   - turn explicit stage-17 return bindings into either:
     - `return;`
     - `return <expr>;`
      - `return (<ret_type>){ .x10 = ..., .x11 = ... };`
5. Render one stage-18 program source:
   - optional leading comments with root entry and preserved queue state
   - stable include lines for the scalar type spellings already used
   - helper declarations
   - forward declarations for ordered functions
   - full function definitions in discovery order
6. Wrap the stage-18 builder in one explicit scheduler:
   - start from the requested root entry
   - build one stage-18 program snapshot for that root
   - enqueue newly observed `pending_entries` as additional roots
   - enqueue newly observed invalidated callers for one rerun per unique cause
   - keep queue processing deterministic by first-seen order
7. Merge the completed root snapshots into one final program artifact:
   - deduplicate includes, helper declarations, prototypes, and function
     definitions deterministically
   - keep one `scheduled_roots` list for debug visibility
   - keep only the remaining queue state after the scheduler has consumed what
     it can in the current run
8. Update `tiny-dec decompile` and `tiny-dec decompile --stage c` so:
   - earlier stage stops keep their current debug behavior
   - `--stage c_lowering` still prints the stage-17 debug tree
   - `--stage c` prints final rendered C
   - the default stage becomes `c`

Failure and bailout rules:

- if one function has no recovered name, print a stable synthetic one rather
  than guessing
- if one expression or lvalue is still raw at stage 17, preserve that raw text
  in the final rendered output instead of inventing cleaner syntax
- if one aggregate layout or return shape repeats, reuse the same helper
  declaration name rather than re-emitting duplicates
- if one function is unresolved in the decompile driver, keep the existing
  unresolved behavior instead of emitting partial guessed source
- if one scheduled root keeps reporting the same invalidation cause after its
  one additional rerun, stop rerunning it in the current scheduler pass and
  leave that state visible in the remaining queue comments

## Data structures

- `FunctionCRendered`
  - owner: `tiny_dec/c_emit/models.py`
  - fields:
    - `c_lowered`
    - `function_name`
    - `return_type`
    - `prototype`
    - `body_lines`
  - invariants:
    - function name, return type, and prototype are non-empty
    - body lines contain no embedded newlines
  - pretty:
    - one rendered function definition with declarations and braced statements
- `ProgramCRendered`
  - owner: `tiny_dec/c_emit/models.py`
  - fields:
    - `c_lowered`
    - `includes`
    - `type_declarations`
    - `prototypes`
    - `functions`
    - `pending_entries`
    - `invalidated_entries`
    - `scheduler_invalidations`
  - invariants:
    - function coverage matches the stage-17 program exactly
    - includes, helper declarations, and prototypes are unique and ordered
      deterministically
  - pretty:
    - one full rendered translation unit with leading comments, helper
      declarations, prototypes, and definitions
- `ScheduledPassRun`
  - owner: `tiny_dec/pipeline/scheduler.py`
  - fields:
    - `root_entry`
    - `scheduled_roots`
    - `execution_order`
    - `results`
    - `pending_entries`
    - `invalidated_entries`
    - `scheduler_invalidations`
  - invariants:
    - `scheduled_roots` is unique and starts with `root_entry`
    - `execution_order` only references scheduled roots
    - `results` stores the latest snapshot for each executed root
    - queue fields represent remaining work after the scheduler run
- `ScheduledCRenderedProgram`
  - owner: `tiny_dec/pipeline/passes.py`
  - fields:
    - `root_entry`
    - `scheduled_roots`
    - `execution_order`
    - `includes`
    - `type_declarations`
    - `prototypes`
    - `functions`
    - `pending_entries`
    - `invalidated_entries`
    - `scheduler_invalidations`
  - invariants:
    - root and scheduled-root order are deterministic
    - includes, helper declarations, prototypes, and function entries are
      unique and diff-friendly
    - function coverage is the deterministic union of the scheduled root
      snapshots
  - pretty:
    - one full rendered translation unit with `root`, `scheduled_roots`,
      remaining queue comments, helper declarations, prototypes, and
      definitions

## Edge cases

- functions with no parameters should print `void`
- functions with no returns should print `void` and `return;`
- functions with one return carrier should not synthesize a helper struct
- functions with more than one return carrier should reuse one deterministic
  helper return type across matching shapes
- repeated aggregate pointer layouts should reuse one deterministic helper type
- residual `goto`, `break`, and `continue` nodes must remain explicit
- unresolved internal names, raw expressions, and unknown globals must stay
  readable and deterministic rather than silently disappearing

## Pretty-print contract

- `format_function_c_rendered(...)` returns a compact function-level rendered
  source snapshot with:
  - any required local declarations at the top of the body
  - stable two-space indentation
  - braces on the same line as `if`, `else`, and `while`
  - one blank line between local declarations and the first statement when both
    sections exist
- `format_program_c_rendered(...)` returns the full rendered translation unit
  with:
  - leading `/* ... */` comments for root entry and preserved scheduler state
  - stable include lines
  - helper declarations before forward declarations
  - forward declarations before definitions
  - one blank line between top-level sections
- `format_scheduled_c_rendered_program(...)` returns the full scheduled final
  translation unit with:
  - leading `/* ... */` comments for:
    - root entry
    - scheduled roots
    - remaining `pending_entries`
    - remaining `invalidated_entries`
    - observed scheduler invalidations
  - the same stable section ordering as stage 18 for includes, helper
    declarations, prototypes, and definitions
- no output line may depend on dict iteration order or object identity

## End-to-end harness exposure

The stage-18 e2e harness should iterate every fixture ELF, build the scheduled
final rendered program, and print:

- the fixture binary name
- the resolved start address
- a `c:` marker
- the full rendered translation unit

Plausible output should show:

- helper `typedef struct` blocks when aggregates or multi-register returns are
  present
- a `/* scheduled_roots: ... */` comment even when only the selected root ran
- rendered `while` and `if` bodies rather than debug-tree labels
- synthetic but readable function signatures and calls
- raw expressions only where earlier stages still lacked cleaner recovery

## Validation commands

Record the commands that should be used while iterating:

- stage tests:
  `poetry run pytest -q tests/posts/post_18_c_printer_pipeline`
- e2e harness:
  `poetry run pytest -q tests/posts/post_18_c_printer_pipeline/test_c_printer_pipeline_e2e_harness.py`
- cli:
  `poetry run tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --func main --stage c`
- downstream cli:
  `poetry run tiny-dec decompile tests/fixtures/bin/fixture_basic_O2_nopie.elf --func main`
- ruff:
  `poetry run ruff check tiny_dec/c_emit tiny_dec/pipeline tiny_dec/cli.py tests/posts/post_18_c_printer_pipeline`
- mypy:
  `poetry run mypy tiny_dec/c_emit tiny_dec/pipeline tiny_dec/cli.py tests/posts/post_18_c_printer_pipeline`

## Open questions

- The final rendered artifact will still be conservative pseudo-C when stage-17
  raw expressions survive. That is acceptable for post 18 as long as the
  printed output stays deterministic and honest.
