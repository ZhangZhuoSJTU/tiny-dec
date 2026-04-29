# Post 11: Scalar Types

Stage-11 tests cover:

- scalar-type model invariants and deterministic pretty-printers
- synthetic recovery of `pointer`, `int`, `bool`, and fallback `word` facts
- downstream typed partitions for value roots preserved through compatible
  memory-address phi joins
- downstream typed partitions for scaled-index pointer walks normalized onto
  one stable root plus field offset
- preservation of embedded stage-10 memory-access version annotations when
  scalar-type facts wrap memory facts unchanged
- preservation of upstream pending-entry and invalidation state
- fixture-backed contract checks for typed partitions and typed values
- CLI coverage for `tiny-dec decompile --stage scalar_types`
- persistent end-to-end harness coverage for `scalar_types:`
