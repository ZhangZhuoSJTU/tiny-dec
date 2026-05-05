# Stage 16: Structuring

## What It Does
This is one of the most visually dramatic stages. It takes the flat CFG (a graph of basic blocks and edges) and recovers **high-level control structures**: `if/else`, `while` loops, `switch` statements. The spaghetti of branches becomes structured code.

**Analogy:** You have a subway map (the CFG) and need to write directions as "take line A to station X, then if it's rush hour take line B, otherwise wait for line C." You're converting a graph into sequential, nested instructions.

## Key Concepts
- **Loop detection**: Back-edges in the CFG indicate loops. A back-edge from block B to block A (where A dominates B) means there's a loop from A to B.
- **If/else recovery**: A block with two successors and a condition creates an if/else. The decompiler figures out which successor is "then" and which is "else" and where they merge.
- **Switch recovery**: An equality-ladder pattern (multiple comparisons of the same value against constants) is recognized as a switch statement.
- **Reducibility**: Some CFGs can't be perfectly structured (they'd need `goto` in C). tiny-dec handles the common reducible cases.

## Source Files
- `tiny_dec/structuring/transform.py` — `analyze_program_structuring()` converts CFGs to structured ASTs.

This is the stage where the "magic" happens visually. Read how loop headers are detected and how if/else regions are carved out of the CFG.

## CLI Demonstration

```bash
# Structure a loop
tiny-dec decompile tests/fixtures/bin/fixture_loop_O0_nopie.elf --stage structuring --func sum_to_n

# Structure a switch
tiny-dec decompile tests/fixtures/bin/fixture_switch_O0_nopie.elf --stage structuring --func dispatch

# Structure nested control flow
tiny-dec decompile tests/fixtures/bin/fixture_nested_O0_nopie.elf --stage structuring --func main
```

Compare the structuring output with the disasm stage (flat CFG) — the transformation is dramatic.

## Quiz

**Q1:** Why can't we just map basic blocks directly to if/while statements without a structuring algorithm?

<details>
<summary>Answer</summary>
A CFG is a general graph — blocks can have arbitrary connections. A structured program has nested, well-defined regions (every if has a matching merge, every loop has a single header). Mapping requires identifying which blocks form a loop body, which form if/else arms, and where they merge. A simple block-to-statement mapping would miss nesting and produce incorrect structure — or worse, require gotos everywhere.
</details>

**Q2:** How does the decompiler distinguish a `while` loop from an `if` statement? Both involve a condition and a branch.

<details>
<summary>Answer</summary>
The key is the back-edge. A `while` loop has a back-edge — the loop body eventually jumps back to the condition block. An `if` statement has no back-edge — control flows forward to the "then"/"else" blocks and merges afterward. The structuring algorithm first identifies back-edges to find loops, then handles the remaining forward-only structures as if/else.
</details>

## Dynamic Exercise

Run structuring on the switch_loop fixture (combines switch and loop):
```bash
tiny-dec decompile tests/fixtures/bin/fixture_switch_loop_O0_nopie.elf --stage structuring --func main
```
"How does the decompiler nest the switch inside the loop? Compare with `tests/fixtures/src/fixture_switch_loop.c` — does the recovered structure match the original?"

## Advanced Exercise (Modification)

```bash
git checkout -b learn/stage-16-structuring
```
Open `tiny_dec/structuring/transform.py`. Find the loop detection logic. What happens if you disable back-edge detection and treat all edges as forward edges? Run it on `fixture_loop_O0_nopie.elf` — does the loop become an infinite chain of if statements?

When done: `git checkout main`
