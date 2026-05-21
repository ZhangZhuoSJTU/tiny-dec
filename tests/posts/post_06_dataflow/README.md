# Post 06: Dataflow

Stage-6 tests cover:

- dataflow model invariants and deterministic pretty-printers
- synthetic intraprocedural worklist cases for constant propagation and joins
- indirect target recovery from `BRANCHIND` and `CALLIND`
- program-level `pending_entries` and `invalidated_entries` suggestions
- fixture-backed CLI, contract, and end-to-end snapshot coverage

The current fixture binaries do not appear to exercise indirect branch or call
recovery directly, so those cases stay synthetic and explicit here.
