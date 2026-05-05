# Stage 18: C Render

## What It Does
The final stage! It takes the C-like IR from stage 17 and renders it as **readable C source code** — with proper indentation, struct type definitions, function signatures, includes, and formatting. This is the output the user actually reads.

**Analogy:** This is the typesetter — all the content is written, and now it's being formatted for publication. Indentation, line breaks, and visual hierarchy make the difference between readable code and a wall of text.

## Key Concepts
- **Precedence-aware formatting**: Only adds parentheses where needed by C operator precedence rules.
- **Declaration emission**: Struct types are emitted before functions that use them. Local variables are declared at function top.
- **Include generation**: Adds `#include <stdint.h>` for the fixed-width types used in declarations.
- **Multi-function output**: When decompiling the whole program, functions are emitted in dependency order.

## Source Files
- `tiny_dec/pipeline/passes.py` — `build_scheduled_c_rendered_program()` orchestrates the final rendering.
- `tiny_dec/c_emit/` — The rendering logic that converts C-like IR nodes to text.

Look at how the renderer walks the C-like IR tree and emits text. Pay attention to indentation tracking and how nested structures are formatted.

## CLI Demonstration

```bash
# The full pipeline — raw bytes to C
tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --func parse_record

# Compare C lowering (stage 17) with final C (stage 18)
tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --stage c_lowering --func parse_record
tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --stage c --func parse_record
```

The final output includes `#include`, struct typedefs, function signatures, and properly indented body.

## Quiz

**Q1:** You've now seen all 19 stages. If you had to pick the three most important stages for output quality, which would they be and why?

<details>
<summary>Answer</summary>
Reasonable choices include: (1) SSA (stage 07) — without it, variable tracking is imprecise and everything downstream suffers. (2) Structuring (stage 16) — without it, the output is flat blocks with gotos instead of if/while/switch. (3) Type inference (stages 11-12) — without it, everything is raw `uint32_t` words and there are no struct definitions. Other valid picks: stack recovery (stage 09) for local variables, or interproc (stage 15) for multi-function programs.
</details>

**Q2:** Looking back at the full pipeline, why does tiny-dec use 19 separate stages instead of combining them into fewer, larger passes?

<details>
<summary>Answer</summary>
This is a teaching tool — the separation lets you inspect what each concept does in isolation. A production decompiler (Ghidra, IDA) would fuse many of these for performance: SSA + simplification + constant propagation in one pass, type inference + variable recovery together, etc. tiny-dec trades efficiency for clarity: if you can follow each stage here, you understand what the production tools do under the hood.
</details>

## Dynamic Exercise — Full Pipeline Comparison

This is the capstone exercise. Run the full pipeline on a fixture and trace key transformations:
```bash
# Pick the struct fixture — it exercises the most stages
tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --stage decode --func parse_record
tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --stage ssa --func parse_record
tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --stage aggregate_types --func parse_record
tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --stage structuring --func parse_record
tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --func parse_record
```
"Trace the journey of the struct's field access. In decode, it's raw memory loads at offsets. In SSA, the loads get versioned. In aggregate_types, the struct layout is recovered. In structuring, the loop appears. In the final C, it all comes together. Can you follow one field access through all five views?"

## Advanced Exercise (Modification)

```bash
git checkout -b learn/stage-18-c-render
```
Open `tiny_dec/c_emit/render_expr.py`. Find the `_BINARY_PRECEDENCE` table (line 23) and `_maybe_parenthesize()` (line 232) — these control when parentheses are added around expressions. Currently, parentheses are added only when needed for correctness (child precedence < parent precedence). Modify `_maybe_parenthesize()` to **always add parentheses** around every binary expression (just return `f"({text})"` unconditionally). Run on `fixture_basic_O0_nopie.elf --func main` and compare with the normal output. Which is more readable? Then try the opposite: remove ALL parenthesization (never wrap). Does the output still parse as valid C?

**Why this matters:** Precedence-aware formatting is the difference between `a + b * c` and `(a + (b * c))`. Real decompilers tune this carefully for readability.

**Test idea:** Run the full pipeline on a fixture with nested arithmetic. Assert the output contains no unnecessary parentheses normally, and assert it has parentheses around every binary op after your change.

When done: `git checkout main`

## Congratulations!

You've completed all 19 stages of the decompilation pipeline. You now understand:
- How raw bytes become structured IR (Frontend)
- How analysis recovers types, variables, and control flow (Analysis)
- How structured code becomes readable C (Backend)

**Next steps:**
- Try your own C code with Docker: say "try my own code"
- Revisit any stage for a deeper dive: say "stage 7" or "take me to SSA"
- Explore the source code on your own — you now have the map
- If you found anything confusing or have suggestions, say "report issue" and I'll help you file it
