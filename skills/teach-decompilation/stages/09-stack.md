# Stage 09: Stack

## What It Does
This stage recovers the **stack frame layout** — it identifies how much stack space the function allocates, where saved registers go, and where local variables live. It maps raw stack pointer offsets (like `sp + 12`) to named **stack slots**.

**Analogy:** The stack frame is like an organized desk drawer. This stage figures out the drawer's layout: "the top section holds saved registers, the middle has local variables, and the bottom is scratch space."

## Key Concepts
- **Stack frame**: The block of memory a function allocates on the stack for its local data. Created by decrementing sp at function entry, freed by incrementing sp at exit.
- **Frame pointer (fp/x8)**: Some functions use x8 as a stable reference point within the frame. Local variables are accessed as `fp - offset` rather than `sp + offset`.
- **Stack slots**: Named regions within the frame. Each slot has an offset and size, and may correspond to a local variable, a saved register, or a function argument passed on the stack.
- **Prologue/epilogue**: The function entry code that sets up the frame (save ra, save fp, decrement sp) and the exit code that tears it down.

## Source Files
- `tiny_dec/analysis/stack/transform.py` — `analyze_program_stack()` recovers frame layout and identifies slots.

Trace how the analysis identifies the prologue pattern (sp adjustment + register saves) and maps memory accesses to slots.

## CLI Demonstration

```bash
# Stack recovery for a function with local variables
tiny-dec decompile tests/fixtures/bin/fixture_loop_O0_nopie.elf --stage stack --func sum_to_n

# Compare with the struct fixture (more complex frame)
tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --stage stack --func parse_record
```

Look at how stack pointer offsets get named. The struct fixture should show a larger frame with more slots.

## Quiz

**Q1:** A function starts with `addi sp, sp, -32`. What does this tell you about the stack frame?

<details>
<summary>Answer</summary>
The function allocates 32 bytes on the stack. Since the stack grows downward (toward lower addresses), decrementing sp by 32 reserves 32 bytes of space. This will hold saved registers (ra, fp), local variables, and possibly function arguments.
</details>

**Q2:** Why does the decompiler need to recover stack slots instead of just leaving raw memory offsets?

<details>
<summary>Answer</summary>
Raw offsets like `mem[sp+12]` are meaningless in C. By identifying that `sp+12` through `sp+15` are always accessed as a 4-byte unit, the decompiler can create a local variable: `int local_12_4`. This is essential for producing readable decompiled output with named variables instead of memory address arithmetic.
</details>

## Dynamic Exercise

Run stack analysis on both optimization levels:
```bash
tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --stage stack --func parse_record
tiny-dec decompile tests/fixtures/bin/fixture_struct_O2_nopie.elf --stage stack --func parse_record
```
"How does the stack frame differ between -O0 and -O2? Does the optimized version still use a frame pointer? Why might the optimizer eliminate it?"

## Advanced Exercise (Modification)

```bash
git checkout -b learn/stage-09-stack
```
Open `tiny_dec/analysis/stack/transform.py`. Find `analyze_function_stack()` — it walks the dominator tree tracking `frame_top_delta` for x2 (SP). The entry block seeds `frame_top_delta=0`. What happens if you change that initial value to something wrong, like `-4`? Make the change, run on `fixture_basic_O0_nopie.elf --stage stack --func main`, and observe how all stack slot offsets shift. Then restore it and try another experiment: skip the `INT_SUB` case in the delta tracking (around line 288). What happens to frame layout recovery?

**Why this matters:** Stack analysis is the foundation for variable recovery — small errors here cascade through every later stage.

**Test idea:** Write a test that asserts the frame size of `fixture_basic_O0_nopie.elf`'s `main` is a specific value, then break the initial delta and confirm the test fails.

When done: `git checkout main`
