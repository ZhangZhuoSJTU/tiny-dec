# Post 17: C Lowering

Executable tests for stage-17 C-like IR lowering.

Coverage includes:
- c-lowered model invariants and deterministic pretty-printers
- fixture-backed lowering expectations for loop, switch, struct, and call-heavy
  functions
- fixture-backed contract checks for declaration recovery, aggregate field
  recovery, stable pretty-printing, loop-signature cleanup from stage-15
  prototype refinement, program-mode single-return cleanup from stage-15
  suppression of unconsumed secondary internal returns, supported primary
  call-result assignment folds, synthetic locals for directly consumed
  call-return carriers used in later calls, conditions, and returns, and
  selected simple merge-phi locals for carried call-return values at
  structured `if` joins
- a persistent fixture-wide e2e pretty-print harness
- CLI expectations for `tiny-dec decompile --stage c_lowering`
