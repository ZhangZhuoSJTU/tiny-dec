# Post 16: Structuring

Executable tests for stage-16 control-structure recovery.

Coverage includes:
- structuring model invariants and deterministic pretty-printers
- synthetic transform tests for straight-line prefixes, reducible `if` regions,
  and pretested `while` loops
- fixture-backed contract checks for the loop and switch fixtures
- CLI expectations for `tiny-dec decompile --stage structuring`
- a persistent fixture-wide e2e pretty-print harness
