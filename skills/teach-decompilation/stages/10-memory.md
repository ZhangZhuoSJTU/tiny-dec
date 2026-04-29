# Stage 10: Memory

## What It Does
This stage partitions all memory accesses into **abstract partitions** — grouping accesses that touch the same logical region (a stack variable, a global, a heap object accessed through a pointer). It determines which memory operations alias (might access the same location) and which are independent.

**Analogy:** Imagine a mailroom with many mailboxes. This stage figures out which deliveries go to which mailbox — even when the addresses look different (a pointer dereference vs. a direct stack access), they might be the same slot.

## Key Concepts
- **Memory partitions**: Abstract groups of memory accesses. A partition might be "all accesses to stack slot at fp-12" or "all accesses through pointer argument x10".
- **Alias analysis**: Determining whether two memory operations might access the same location. If they can't, they're in different partitions and analyses can treat them independently.
- **Stack vs. global vs. pointer**: Three major partition classes. Stack accesses use sp/fp-relative addresses, globals use absolute addresses, pointer accesses go through argument registers.

## Source Files
- `tiny_dec/analysis/memory/transform.py` — `analyze_program_memory()` partitions accesses and computes alias facts.

Read how memory accesses are classified into partition categories based on the base address expression.

## CLI Demonstration

```bash
# Memory partitioning for the struct fixture (pointer access patterns)
tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --stage memory --func parse_record
```

Look for partition annotations on LOAD and STORE operations.

## Quiz

**Q1:** Why does the decompiler need to partition memory instead of treating all LOAD/STORE operations uniformly?

<details>
<summary>Answer</summary>
Without partitioning, the decompiler must assume any store might affect any load (they might alias). This kills all memory-related optimizations and analysis. By proving that stack accesses and pointer accesses are independent, later stages can track them separately — enabling accurate variable recovery and type inference.
</details>

**Q2:** Function `parse_record` takes a pointer parameter. How does the decompiler know that stores through this pointer don't clobber the function's own local variables on the stack?

<details>
<summary>Answer</summary>
Stack accesses use addresses relative to sp/fp, which point into the current function's frame. Pointer arguments point to caller-provided memory elsewhere in the address space. The memory partitioning stage recognizes this distinction: sp/fp-based accesses are in a "stack" partition and pointer-based accesses are in a separate "parameter pointer" partition. They can't alias because they address different regions.
</details>

## Dynamic Exercise

Compare memory for a simple function vs. one with pointers:
```bash
tiny-dec decompile tests/fixtures/bin/fixture_basic_O0_nopie.elf --stage memory --func helper
tiny-dec decompile tests/fixtures/bin/fixture_struct_O0_nopie.elf --stage memory --func parse_record
```
**Before running the second command, predict:** `parse_record` takes a pointer argument (`agg_8* records`). The `helper` function has no pointer parameters. How do you think the memory partitions will differ? Now compare — do you see separate partitions for stack vs. pointer accesses in `parse_record`? Run through to the variables stage (`--stage variables`) on both and see how the partition difference affects variable recovery.

## Advanced Exercise (Modification)

```bash
git checkout -b learn/stage-10-memory
```
Open `tiny_dec/analysis/memory/transform.py`. Find the logic that classifies an access as stack vs. pointer. What criteria does it use? What happens if you force all accesses to be classified as "stack"? Run it on `fixture_struct_O0_nopie.elf` and observe how it affects later stages.

When done: `git checkout main`
