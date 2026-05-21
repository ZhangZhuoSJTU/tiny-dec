# Post 10: Memory

Stage-10 tests cover:

- memory model invariants and deterministic pretty-printers
- synthetic partition recovery for stack-slot, absolute, propagated value, and
  fallback value accesses
- preservation of coarse stage-7 memory versions on recorded `LOAD` and
  `STORE` accesses
- phi-merged pointer-root propagation when all incoming tracked addresses agree
- scaled-index pointer walks that still normalize onto one stable root plus
  field offset
- preservation of upstream pending-entry and invalidation state
- fixture-backed contract checks for recovered stack and value partitions
- CLI coverage for `tiny-dec decompile --stage memory`
- persistent end-to-end harness coverage for `memory:`
