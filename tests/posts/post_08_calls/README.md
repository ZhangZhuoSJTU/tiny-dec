# Post 08: Calls

This directory owns the stage-scoped tests for call modeling on top of SSA.

The stage should cover:

- callsite target classification
- ABI carrier snapshots for arguments and returns
- coarse low-level memory snapshots at call boundaries
- downstream carrier snapshots from normalized stage-7 loop-header SSA
- downstream carrier snapshots from trivial stage-7 register-forwarding copies
- refined call graph construction
- pending-entry emission for newly discovered internal callees
- deterministic function and program pretty-printing

The persistent e2e harness for this stage should render `calls:`.
