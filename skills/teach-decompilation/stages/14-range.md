# Stage 14: Range

## What It Does
This stage computes **integer value ranges** for variables and refines branch predicates. For a loop counter `i` that goes from 0 to n, the analysis determines that `i ∈ [0, n)`. This information helps later stages understand branch conditions and produce cleaner output.

**Analogy:** Range analysis is like a detective narrowing down a suspect's whereabouts. "They were somewhere in the city" becomes "they were between 5th and 10th street between 3pm and 5pm." Each piece of evidence (a branch condition, an assignment) narrows the range until you have a useful bound.

## Key Concepts
- **Interval analysis**: Track [min, max] bounds for each variable. Operations narrow or widen bounds: `x = y + 1` where `y ∈ [0, 9]` gives `x ∈ [1, 10]`.
- **Branch predicate refinement**: On the "true" edge of `if (x < 10)`, we know `x ∈ [INT_MIN, 9]`. On the "false" edge, `x ∈ [10, INT_MAX]`. This is path-sensitive information.
- **Widening**: For loops, ranges might grow unboundedly. Widening is a technique to force convergence by jumping to infinity when bounds grow too fast.

## Source Files
- `tiny_dec/analysis/range/transform.py` — `analyze_program_ranges()` computes ranges and refines predicates.

Look at how ranges are propagated through operations and how branch conditions split ranges.

## CLI Demonstration

```bash
# Range analysis on a loop
tiny-dec decompile tests/fixtures/bin/fixture_loop_O0_nopie.elf --stage range --func sum_to_n
```

Look for range annotations on variables, especially the loop counter.

## Quiz

**Q1:** In a loop `for (int i = 0; i < n; i++)`, what range does the analysis assign to `i` inside the loop body?

<details>
<summary>Answer</summary>
Inside the loop body (after the condition check passes), `i ∈ [0, n-1]` because the condition `i < n` was true. The analysis knows the lower bound from initialization (0) and the upper bound from the branch condition (< n means ≤ n-1).
</details>

**Q2:** What is "widening" and why is it needed for loops?

<details>
<summary>Answer</summary>
Without widening, the analysis might iterate forever trying to find the exact range of a loop variable. On each iteration, the range grows: [0,0], [0,1], [0,2], ... This never converges if the bound is symbolic. Widening jumps directly to [0, +∞) when it detects the upper bound is growing, ensuring the analysis terminates. It's an over-approximation but it's safe — the actual range is a subset.
</details>

## Dynamic Exercise

Run range analysis on the loop fixture:
```bash
tiny-dec decompile tests/fixtures/bin/fixture_loop_O0_nopie.elf --stage range --func sum_to_n
```
Before looking at the output, **predict:** the loop counter `i` starts at 0 and is compared with `< n`. What range should the analysis assign to `i` inside the loop body? What about after the loop exits? Now check — did the analysis match your prediction? If not, why might it be less precise?

## Advanced Exercise (Modification)

```bash
git checkout -b learn/stage-14-range
```
Open `tiny_dec/analysis/range/transform.py`. Find the widening logic (look for "widen" — it kicks in after a few monotone expansions to force convergence). What happens if you disable widening (always use the exact range)?

**Warning:** Without widening, the analysis may not terminate on loops with symbolic bounds. Use a timeout: `timeout 10 tiny-dec decompile tests/fixtures/bin/fixture_loop_O0_nopie.elf --stage range --func sum_to_n`. If it hangs, that's the point — you've just proven why widening is necessary!

For the simple fixture (concrete loop bound), the analysis may still terminate but take more iterations. Try counting iterations by adding a counter.

**Why this matters:** Widening is the fundamental technique that makes abstract interpretation practical. Without it, any analysis over loops risks non-termination.

**Test idea:** Write a test that runs range analysis with and without widening on a fixture. Assert both produce the same final result, but measure that widening converges in fewer iterations.

When done: `git checkout main`
