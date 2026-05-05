# Stage 17: C Lowering

## What It Does
This stage translates the structured IR into a **C-like intermediate representation** — with typed variable declarations, expressions with proper operator precedence, type casts, and C-style statements. It bridges the gap between the analysis output and actual C syntax.

**Analogy:** You've written the outline (structuring) and gathered all the facts (analysis). Now you're drafting the actual prose — choosing words (C syntax), adding punctuation (operators, semicolons), and polishing grammar (type casts, declarations).

## Key Concepts
- **Expression trees**: P-code operations get combined into C expressions. Instead of three separate operations `temp = a + b; result = temp * c`, you get `result = (a + b) * c`.
- **Type casts**: When the analysis says a value is `int32_t` but it's used as `uint32_t`, a cast is inserted: `(uint32_t)x`.
- **Variable declarations**: Stack slots and register variables become local variable declarations with types at the top of the function.
- **Precedence**: The lowering respects C operator precedence so the output doesn't need excessive parentheses.

## Source Files
- `tiny_dec/c_emit/transform.py` — `analyze_program_c_lowering()` lowers to C-like IR.

Read how p-code operations get translated into C expression nodes. Look for the precedence-aware parenthesization logic.

## CLI Demonstration

```bash
# Before lowering (structured IR)
tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --stage structuring --func parse_record

# After lowering (C-like IR)
tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --stage c_lowering --func parse_record
```

The output now looks much more like C — variables have types, expressions are inlined, and statements use C syntax.

## Quiz

**Q1:** Why is C lowering a separate stage from the final C rendering (stage 18)?

<details>
<summary>Answer</summary>
Separation of concerns: C lowering makes semantic decisions (how to form expressions, where to cast, what to declare), while rendering makes syntactic decisions (indentation, line breaks, comment placement). Keeping them separate means you can change the output style without touching the semantic lowering, or change how expressions are formed without breaking the formatter.
</details>

**Q2:** The analysis recovered `local_20_4` as a `int32_t`. But the function returns it in a0, which the ABI says is `uint32_t` for the return value. How should the lowering handle this?

<details>
<summary>Answer</summary>
Insert an explicit cast: `return (uint32_t)local_20_4`. The lowering must respect both the variable's inferred type and the context where it's used. Type mismatches between variable types and usage contexts produce casts, which are important for correctness — especially for signed/unsigned confusion.
</details>

## Dynamic Exercise

Compare the C lowering output for the same function at different optimization levels:
```bash
tiny-dec decompile tests/fixtures/bin/fixture_loop_O0_nopie.elf --stage c_lowering --func sum_to_n
tiny-dec decompile tests/fixtures/bin/fixture_loop_O2_nopie.elf --stage c_lowering --func sum_to_n
```
"How does optimization affect the lowered C? Are there more or fewer variables? More or fewer casts?"

## Advanced Exercise (Modification)

```bash
git checkout -b learn/stage-17-c-lowering
```
Open `tiny_dec/c_emit/transform.py`. Find `_lower_value()` (line 2314) — this method builds a `CExpr` for each SSA value using a cache (`_value_cache`). The cache is what enables expression inlining: when a value is used only once, its expression gets folded into its consumer. Try this: modify `_lower_value()` to **never cache** (always rebuild the expression). Run on `fixture_basic_O0_nopie.elf --stage c_lowering --func main`. How does the output change? Are expressions duplicated? Then try the opposite: force **every** value into its own local variable (never inline). Compare the verbosity.

**Why this matters:** The balance between inlining and statement splitting determines readability. Too much inlining creates unreadable nested expressions; too little creates a wall of trivial assignments.

**Test idea:** Run the full pipeline on `fixture_basic_O0_nopie.elf` and count the number of local variable declarations. Assert it changes when you modify the caching behavior.

When done: `git checkout main`
