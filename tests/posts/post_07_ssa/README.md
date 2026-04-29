# Post 07: SSA

Stage-7 tests cover:

- SSA model invariants and deterministic pretty-printers
- synthetic dominator, phi-placement, and renaming cases
- coarse low-level memory-version threading and memory-phi cases
- same-base identity-copy and trivial register or memory-phi normalization cases
- later-use rewriting for trivial register-forwarding copies that stay explicit
- loop-header phi construction
- unreachable-block exclusion from reachable SSA blocks
- synthetic `CALL_RETURN` op rendering and fixture-backed call-return SSA defs
- fixture-backed CLI, contract, and end-to-end snapshot coverage

The current fixture binaries are useful for deterministic SSA snapshots and
live-in naming, but the strongest phi-placement cases are still synthetic and
explicit here.
