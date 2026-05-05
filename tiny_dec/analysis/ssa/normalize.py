"""Small SSA normalization helpers for stage 7.

This file owns the conservative post-rename cleanup that runs after SSA
construction:

- drop same-base identity copies such as `COPY x10_3 <- x10_2`
- rewrite later SSA uses to the surviving carrier value
- rewrite later uses of trivial register-forwarding copies such as
  `COPY x12_1 <- x10_0` to the forwarded register value while keeping the
  explicit register copy op
- remove trivial register or memory phis whose non-self rewritten inputs agree

The pass stays deliberately small. It is not a general optimizer, does not
coalesce arbitrary copies, and does not rewrite control flow.
"""

from __future__ import annotations

from tiny_dec.analysis.ssa.models import (
    MemoryVersion,
    SSABlock,
    SSAFunctionIR,
    SSAInstruction,
    SSAMemoryPhiInput,
    SSAMemoryPhiNode,
    SSAName,
    SSANameKind,
    SSAOp,
    SSAPhiInput,
    SSAPhiNode,
    SSAValue,
)

type _ValueAliases = dict[SSAName, SSAValue]
type _MemoryAliases = dict[MemoryVersion, MemoryVersion]


def normalize_function_ssa(function: SSAFunctionIR) -> SSAFunctionIR:
    """Apply the small stage-7 normalization pass to one SSA function."""

    value_aliases: _ValueAliases = {}
    memory_aliases: _MemoryAliases = {}

    while True:
        changed = False
        for start in function.ordered_block_starts():
            block = _rewrite_block(function.blocks[start], value_aliases, memory_aliases)

            for phi in block.phis:
                alias = _trivial_phi_alias(phi, value_aliases)
                if alias is None:
                    continue
                resolved = _rewrite_value(alias, value_aliases)
                if value_aliases.get(phi.output) == resolved:
                    continue
                value_aliases[phi.output] = resolved
                changed = True

            memory_phi = block.memory_phi
            if memory_phi is not None:
                memory_alias = _trivial_memory_phi_alias(memory_phi, memory_aliases)
                if memory_alias is not None:
                    resolved_memory = _rewrite_memory(memory_alias, memory_aliases)
                    if memory_aliases.get(memory_phi.output) != resolved_memory:
                        memory_aliases[memory_phi.output] = resolved_memory
                        changed = True

            for instruction in block.instructions:
                for op in instruction.ops:
                    value_alias = _trivial_copy_alias(op, value_aliases)
                    if value_alias is None or op.output is None:
                        continue
                    resolved_value = _rewrite_value(value_alias, value_aliases)
                    if value_aliases.get(op.output) == resolved_value:
                        continue
                    value_aliases[op.output] = resolved_value
                    changed = True

        if not changed:
            break

    normalized_blocks = {
        start: _filter_block(
            _rewrite_block(function.blocks[start], value_aliases, memory_aliases),
            value_aliases,
            memory_aliases,
        )
        for start in function.ordered_block_starts()
    }

    return SSAFunctionIR(
        dataflow=function.dataflow,
        blocks=normalized_blocks,
        immediate_dominators=function.immediate_dominators,
        dominance_frontiers=function.dominance_frontiers,
        live_ins=function.live_ins,
        memory_live_in=function.memory_live_in,
        unreachable_blocks=function.unreachable_blocks,
    )


def _rewrite_block(
    block: SSABlock,
    value_aliases: _ValueAliases,
    memory_aliases: _MemoryAliases,
) -> SSABlock:
    memory_phi = block.memory_phi
    rewritten_memory_phi = (
        None
        if memory_phi is None
        else SSAMemoryPhiNode(
            output=memory_phi.output,
            inputs=tuple(
                SSAMemoryPhiInput(
                    predecessor=phi_input.predecessor,
                    value=_rewrite_memory(phi_input.value, memory_aliases),
                )
                for phi_input in memory_phi.inputs
            ),
        )
    )
    rewritten_phis = tuple(
        SSAPhiNode(
            output=phi.output,
            inputs=tuple(
                SSAPhiInput(
                    predecessor=phi_input.predecessor,
                    value=_rewrite_value(phi_input.value, value_aliases),
                )
                for phi_input in phi.inputs
            ),
        )
        for phi in block.phis
    )
    rewritten_instructions = tuple(
        SSAInstruction(
            instruction=instruction.instruction,
            ops=tuple(
                SSAOp(
                    opcode=op.opcode,
                    inputs=tuple(_rewrite_value(value, value_aliases) for value in op.inputs),
                    output=op.output,
                    memory_before=(
                        None
                        if op.memory_before is None
                        else _rewrite_memory(op.memory_before, memory_aliases)
                    ),
                    memory_after=(
                        None
                        if op.memory_after is None
                        else _rewrite_memory(op.memory_after, memory_aliases)
                    ),
                )
                for op in instruction.ops
            ),
        )
        for instruction in block.instructions
    )
    return SSABlock(
        start=block.start,
        phis=rewritten_phis,
        memory_phi=rewritten_memory_phi,
        instructions=rewritten_instructions,
        successors=block.successors,
        terminator=block.terminator,
        call_targets=block.call_targets,
        has_indirect_call=block.has_indirect_call,
    )


def _filter_block(
    block: SSABlock,
    value_aliases: _ValueAliases,
    memory_aliases: _MemoryAliases,
) -> SSABlock:
    filtered_instructions = tuple(
        SSAInstruction(
            instruction=instruction.instruction,
            ops=tuple(
                op
                for op in instruction.ops
                if not _is_elided_copy(op, value_aliases)
            ),
        )
        for instruction in block.instructions
    )
    memory_phi = block.memory_phi
    if memory_phi is not None and memory_phi.output in memory_aliases:
        memory_phi = None
    return SSABlock(
        start=block.start,
        phis=tuple(phi for phi in block.phis if phi.output not in value_aliases),
        memory_phi=memory_phi,
        instructions=filtered_instructions,
        successors=block.successors,
        terminator=block.terminator,
        call_targets=block.call_targets,
        has_indirect_call=block.has_indirect_call,
    )


def _trivial_copy_alias(
    op: SSAOp,
    value_aliases: _ValueAliases,
) -> SSAValue | None:
    if _opcode_text(op) != "COPY" or op.output is None or len(op.inputs) != 1:
        return None
    input_value = _rewrite_value(op.inputs[0], value_aliases)
    output = op.output
    if not isinstance(input_value, SSAName):
        return None
    if (
        output.kind == SSANameKind.REGISTER
        and input_value.kind == SSANameKind.REGISTER
        and input_value.size == output.size
    ):
        return input_value
    return None


def _is_elided_copy(
    op: SSAOp,
    value_aliases: _ValueAliases,
) -> bool:
    if op.output is None or op.output not in value_aliases:
        return False
    output = op.output
    alias = _trivial_copy_alias(op, value_aliases)
    if alias is None or _rewrite_value(alias, value_aliases) != value_aliases[output]:
        return False
    return _is_same_base_identity_copy(output, alias)


def _is_same_base_identity_copy(output: SSAName, alias: SSAValue) -> bool:
    if not isinstance(alias, SSAName):
        return False
    return (
        alias.kind == output.kind
        and alias.base == output.base
        and alias.size == output.size
    )


def _trivial_phi_alias(
    phi: SSAPhiNode,
    value_aliases: _ValueAliases,
) -> SSAValue | None:
    inputs = [
        _rewrite_value(phi_input.value, value_aliases)
        for phi_input in phi.inputs
    ]
    candidates = [value for value in inputs if value != phi.output]
    if not candidates:
        return None
    first = candidates[0]
    if any(value != first for value in candidates[1:]):
        return None
    return first


def _trivial_memory_phi_alias(
    phi: SSAMemoryPhiNode,
    memory_aliases: _MemoryAliases,
) -> MemoryVersion | None:
    inputs = [
        _rewrite_memory(phi_input.value, memory_aliases)
        for phi_input in phi.inputs
    ]
    candidates = [value for value in inputs if value != phi.output]
    if not candidates:
        return None
    first = candidates[0]
    if any(value != first for value in candidates[1:]):
        return None
    return first


def _rewrite_value(value: SSAValue, value_aliases: _ValueAliases) -> SSAValue:
    current = value
    seen: set[SSAName] = set()
    while isinstance(current, SSAName) and current in value_aliases and current not in seen:
        seen.add(current)
        current = value_aliases[current]
    return current


def _rewrite_memory(
    value: MemoryVersion,
    memory_aliases: _MemoryAliases,
) -> MemoryVersion:
    current = value
    seen: set[MemoryVersion] = set()
    while current in memory_aliases and current not in seen:
        seen.add(current)
        current = memory_aliases[current]
    return current


def _opcode_text(op: SSAOp) -> str:
    opcode = op.opcode
    return opcode.value if hasattr(opcode, "value") else str(opcode)
