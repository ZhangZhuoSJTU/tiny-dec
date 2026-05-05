# Post 12: Aggregate Types

Stage-12 tests cover:

- aggregate model invariants and deterministic pretty-printers
- synthetic recovery of pointer-rooted aggregate layouts and repeated strides
- preservation of upstream pending-entry and invalidation state
- fixture-backed contract checks for recovered aggregate roots and fields
- CLI coverage for `tiny-dec decompile --stage aggregate_types`
- default decompile-stop coverage for the aggregate-types stage frontier
- persistent end-to-end harness coverage for `aggregate_types:`
