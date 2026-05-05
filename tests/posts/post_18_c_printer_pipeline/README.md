# Post 18: C Printer Pipeline

Executable tests for stage-18 rendered C output and the final decompile driver.

Coverage includes:
- rendered-C model invariants and deterministic pretty-printers
- fixture-backed rendering expectations for loop, basic, struct-heavy, and
  call-heavy functions
- fixture-backed contract checks for helper type declarations, final function
  signatures, stable rendered output, folded primary call-result assignments,
  named synthetic locals for directly consumed call-return carriers that
  survive to final C in later calls, conditions, and returns, and selected
  simple merge-phi locals for carried call-return values at structured `if`
  joins, plus rendered-only simplifications for direct multi-register call
  returns, direct projected call-result returns, grouped call-result
  temporaries in the call-heavy fixture, scalar direct-call wrapper
  simplification in the switch fixture, and program-mode scalar return cleanup
  from stage-15 prototype refinement so rendered internal signatures match
  their callsites in the loop, basic, and struct fixtures
- pipeline-scheduler unit tests for pending-entry execution, invalidation
  reruns, and deterministic merged final-C output
- CLI expectations for `tiny-dec decompile --stage c`
- a persistent fixture-wide e2e rendered-source harness driven by the scheduled
  final renderer
