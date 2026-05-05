# Stage 08: Calls

## What It Does
This stage identifies function calls in the p-code and determines what arguments are passed and what values are returned, based on the **RISC-V calling convention (ABI)**. It classifies each call (direct, indirect, external) and snapshots the register state at the call site.

**Analogy:** When you hear someone dial a phone number, you can figure out who they're calling (the target function), what message they're sending (arguments in a0-a7), and what reply to expect (return value in a0).

## Key Concepts
- **Calling convention**: RISC-V uses registers a0-a7 (x10-x17) for the first 8 arguments and a0 (x10) for the return value. Extra arguments go on the stack.
- **Call classification**: Direct calls (known target), indirect calls (target computed at runtime), external calls (library functions like `malloc`).
- **ABI snapshots**: At each call site, record which argument registers are live (have meaningful values) and which hold the return value afterward.

## Source Files
- `tiny_dec/analysis/calls/transform.py` — `analyze_program_calls()` classifies calls and builds ABI snapshots.

Read how each call instruction gets matched to a target and how argument registers are determined.

## CLI Demonstration

```bash
# See call analysis for a multi-function program
tiny-dec decompile tests/fixtures/bin/fixture_calls_O0_nopie.elf --stage calls --func main
```

Look for CALL annotations showing the target function, arguments, and return value.

```bash
# Compare: a program with a chain of calls
tiny-dec decompile tests/fixtures/bin/fixture_chain_O0_nopie.elf --stage calls --func main
```

## Quiz

**Q1:** In RV32I, `jal x1, <offset>` is a function call and `jalr x0, 0(x1)` is a return. How does the decompiler tell them apart from other jumps?

<details>
<summary>Answer</summary>
`jal x1, ...` saves the return address in x1 (ra) — this is the signature of a call (it needs to come back). `jalr x0, 0(x1)` jumps to the address in x1 (ra) and discards the link (x0 is the zero register) — this is a return. Regular jumps (like loop branches) use `jal x0, ...` (no return address saved) or conditional branches.
</details>

**Q2:** Why does the decompiler need to know which registers hold arguments at a call site?

<details>
<summary>Answer</summary>
Without argument information, the decompiler can't generate correct function calls in C output. It needs to know that `x10` and `x11` hold the first two arguments so it can produce `func(arg0, arg1)` instead of just `func()`. Argument registers also affect what the caller needs to save/restore around the call.
</details>

## Dynamic Exercise

Run calls on the basic fixture (which has a helper function):
```bash
tiny-dec decompile tests/fixtures/bin/fixture_basic_O0_nopie.elf --stage calls --func main
```
**Before looking at the output, predict:** `fixture_basic.c` calls `helper(7)` — that's one argument. Which register should hold it in RISC-V? (Hint: first argument goes in a0/x10.) Now check the calls output — does the analysis agree? How many arguments does it detect?

## Advanced Exercise (Modification)

```bash
git checkout -b learn/stage-08-calls
```
Open `tiny_dec/analysis/calls/transform.py`. Find where argument registers (a0-a7 / x10-x17) are snapshotted at each call site. The analysis captures all ABI argument registers that have a current SSA value. What happens if you **cap the maximum detected arguments at 2** (ignore a2-a7)? Run on `fixture_calls_O0_nopie.elf --stage calls --func main` — which calls lose arguments? Then run the full pipeline to `c` stage and see how the C output changes.

**Why this matters:** Real calling conventions have edge cases (variadic functions, struct-by-value). Understanding how argument detection works helps you see why decompiler output sometimes has wrong argument counts.

**Test idea:** Run the calls stage on a fixture that passes 3+ arguments. Assert all arguments are captured normally, then verify your cap drops the extras.

When done: `git checkout main`
