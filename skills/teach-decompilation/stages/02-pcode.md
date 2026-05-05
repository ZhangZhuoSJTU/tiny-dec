# Stage 02: P-code Lift

## What It Does
The lifter translates each decoded RV32I instruction into one or more **p-code operations** — a simple, uniform intermediate language. P-code abstracts away instruction-set details: instead of `add x10, x11, x12`, you get a generic `INT_ADD` operation on named storage locations.

**Analogy:** P-code is like translating every human language into Esperanto before analysis. It doesn't matter if the original was French (ARM), German (x86), or Japanese (RISC-V) — the analyzer only needs to understand one language.

## Key Concepts
- **P-code**: A register-transfer language where each operation has an opcode, inputs, and an output. Ghidra calls this "p-code" too — tiny-dec's version is simplified but the concept is identical. There are 27 opcodes total, grouped into: flow control (BRANCH, CBRANCH, CALL, RETURN, ...), arithmetic (INT_ADD, INT_SUB, INT_AND, INT_OR, INT_XOR, INT_LEFT, INT_RIGHT, ...), comparison (INT_EQUAL, INT_SLESS, INT_LESS, ...), data movement (COPY, LOAD, STORE), and extension (INT_SEXT, INT_ZEXT).
- **One-to-many lifting**: A single RISC-V instruction may become multiple p-code operations. For example, `sw x10, 8(x2)` (store word) becomes: compute address (x2 + 8), then STORE x10 to that address.
- **Varnodes**: P-code operands — each is a triple of (space, offset, size). Four spaces exist: REGISTER (CPU registers), CONST (literal values), UNIQUE (compiler-generated temporaries), and RAM (direct memory addresses). Printed as `space[0xoffset:size]`, e.g., `register[0xa:4]` for x10.

## Source Files
- `tiny_dec/ir/lift_rv32i.py` — `lift_instruction()` is the entry point. One handler per instruction mnemonic.
- `tiny_dec/ir/pcode.py` — P-code operation definitions, opcode enum, varnode types.

Start with `lift_instruction()` and trace what happens for `add` and `sw`. Count how many p-code ops each produces.

## CLI Demonstration

```bash
# See p-code for the basic fixture
tiny-dec decompile tests/fixtures/bin/fixture_basic_O0_nopie.elf --stage pcode --func main

# Compare: decoded instructions vs p-code
tiny-dec decompile tests/fixtures/bin/fixture_basic_O0_nopie.elf --stage decode --func main
```

Notice how each instruction line from decode expands into one or more p-code operations.

## Quiz

**Q1:** Why does a decompiler use an intermediate representation like p-code instead of analyzing RISC-V instructions directly?

<details>
<summary>Answer</summary>
An IR decouples the analysis from the instruction set. All subsequent pipeline stages (SSA, type inference, structuring) only need to understand p-code, not RISC-V. This means the same analysis engine works for any architecture — you just need a new lifter. It also simplifies each p-code operation to do exactly one thing, making analysis more precise.
</details>

**Q2:** The instruction `sw x10, 8(x2)` stores register x10 to memory at address (x2 + 8). How many p-code operations would you expect this to produce, and what would they be?

<details>
<summary>Answer</summary>
Two operations: (1) INT_ADD to compute the address: temp = x2 + 8, (2) STORE to write x10 to memory at that address. The single RISC-V instruction hides the address computation; p-code makes it explicit.
</details>

## Dynamic Exercise

Run pcode on the struct fixture:
```bash
tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --stage pcode --func parse_record
```
The default output shows only the first few instructions (prologue stores). The LOAD operations are further into the function body — find where the output limit is defined in the pipeline code and increase it.

Once you can see the full function, find a LOAD operation. What address is it loading from? Can you trace back through the p-code to figure out what struct field that corresponds to?

## Advanced Exercise (Modification)

```bash
git checkout -b learn/stage-02-pcode
```
Open `tiny_dec/ir/lift_rv32i.py`. Find `_lift_op_imm()` — notice how writes to x0 are silently dropped (`write_reg(X0)` returns `None`), so `addi x0, x0, 0` already produces zero p-code ops. But `addi x10, x10, 0` is a **semantic NOP** (adds zero, changes nothing) that still emits an `INT_ADD` operation. Add a special case: when the instruction is `addi rd, rs, 0` and `rd == rs`, emit a `COPY` instead of `INT_ADD` — or skip it entirely. Run on `fixture_basic_O0_nopie.elf` and check if any such redundant operations disappear.

**Why this matters:** Real decompilers aggressively filter semantic NOPs early — it reduces noise for every later stage. The simplifier (stage 05) catches `x + 0` later, but catching it at lift time is even cleaner.

**Test idea:** Write a test that lifts `addi x10, x10, 0` and asserts the p-code is either empty or a single COPY (not an INT_ADD with a zero constant).

When done: `git checkout main`
