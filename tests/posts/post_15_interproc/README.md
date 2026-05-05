# Post 15: Interproc

Stage-15 tests cover:

- interproc model invariants and deterministic pretty-printers
- synthetic prototype and effect-summary recovery
- pruning of root-value-only internal parameters when observed callers do not
  supply that carrier
- suppression of compare-scratch, unconsumed-secondary, and unsupported
  internal-callee return carriers
- scheduler invalidation behavior for no-return internal callees
- fixture-backed contract checks for recovered parameter carriers
- CLI coverage for `tiny-dec decompile --stage interproc`
- default decompile-stop coverage for the interproc stage frontier
- persistent end-to-end harness coverage for `interproc:`
