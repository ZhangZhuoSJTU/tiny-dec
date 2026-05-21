"""Stage-7 SSA construction from stage-6 dataflow snapshots.

This file owns the transformation from stage-6 dataflow facts into a
deterministic low-level SSA form.

Implementation notes:
- SSA is constructed only for blocks whose stage-6 `in_state` is reachable.
- Dominators, immediate dominators, and dominance frontiers are computed with
  explicit small-set algorithms rather than a generic graph framework.
- Phi nodes are inserted only for registers. `unique` temporaries are renamed
  into function-wide single-assignment names but never receive phis.
- Register live-ins are created lazily as version `0` during rename.
- One conservative low-level memory version is threaded through `LOAD`, `STORE`,
  `CALL`, and `CALLIND`, with at most one memory phi per reachable block.
"""

from __future__ import annotations

from collections import deque

from tiny_dec.analysis._helpers import opcode_text, space_name
from tiny_dec.analysis.dataflow import (
    FunctionDataflowFacts,
    ProgramDataflowFacts,
    build_function_dataflow,
    build_program_dataflow,
)
from tiny_dec.analysis.simplify import CanonicalBlock
from tiny_dec.analysis.ssa.call_defs import build_call_return_ops
from tiny_dec.analysis.ssa.normalize import normalize_function_ssa
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
    SSAProgramIR,
    SSAPhiInput,
    SSAPhiNode,
    SSAValue,
)
from tiny_dec.ir.pcode import PcodeSpace, Varnode, const_varnode
from tiny_dec.loader import ProgramView

type UniqueKey = tuple[int, int]


def construct_function_ssa(function: FunctionDataflowFacts) -> SSAFunctionIR:
    """Construct one SSA function from stage-6 dataflow facts."""
    canonical = function.function
    reachable_order = tuple(
        start
        for start in canonical.ordered_block_starts()
        if function.blocks[start].in_state.reachable
    )
    if not reachable_order:
        raise ValueError("ssa construction requires a reachable entry block")

    reachable_set = set(reachable_order)
    order_index = {start: index for index, start in enumerate(reachable_order)}
    unreachable_blocks = tuple(
        start for start in canonical.ordered_block_starts() if start not in reachable_set
    )
    predecessors = _build_predecessors(canonical.blocks, reachable_set)
    successors = _build_successors(canonical.blocks, reachable_set)
    dominators = _compute_dominators(canonical.entry, reachable_order, predecessors)
    immediate_dominators = _compute_immediate_dominators(
        canonical.entry,
        reachable_order,
        dominators,
        order_index,
    )
    dominator_children = _build_dominator_tree(immediate_dominators, order_index)
    dominance_frontiers = _compute_dominance_frontiers(
        canonical.entry,
        successors,
        immediate_dominators,
        dominator_children,
        order_index,
    )
    register_sizes = _collect_register_sizes(canonical.blocks, reachable_order)
    phi_registers = _place_phi_nodes(
        canonical.blocks,
        reachable_order,
        dominance_frontiers,
        order_index,
    )
    memory_phi_blocks = _place_memory_phi_nodes(
        canonical.blocks,
        reachable_order,
        dominance_frontiers,
        order_index,
    )
    renamed_blocks, live_ins, memory_live_in = _rename_function(
        function=function,
        reachable_order=reachable_order,
        predecessors=predecessors,
        dominator_children=dominator_children,
        phi_registers=phi_registers,
        memory_phi_blocks=memory_phi_blocks,
        register_sizes=register_sizes,
    )

    ssa = SSAFunctionIR(
        dataflow=function,
        blocks=renamed_blocks,
        immediate_dominators=immediate_dominators,
        dominance_frontiers=dominance_frontiers,
        live_ins=live_ins,
        memory_live_in=memory_live_in,
        unreachable_blocks=unreachable_blocks,
    )
    return normalize_function_ssa(ssa)


def construct_program_ssa(program: ProgramDataflowFacts) -> SSAProgramIR:
    """Construct one SSA program from stage-6 dataflow facts."""
    functions = {
        function.function.entry: construct_function_ssa(function)
        for function in program.ordered_functions()
    }
    return SSAProgramIR(dataflow=program, functions=functions)


def build_ssa_function_ir(view: ProgramView, entry: int) -> SSAFunctionIR:
    """Build stage-6 function dataflow first, then convert it into SSA."""
    function = build_function_dataflow(view, entry)
    return construct_function_ssa(function)


def build_ssa_program_ir(view: ProgramView, root_entry: int) -> SSAProgramIR:
    """Build stage-6 program dataflow first, then convert it into SSA."""
    program = build_program_dataflow(view, root_entry)
    return construct_program_ssa(program)


def _build_predecessors(
    blocks: dict[int, CanonicalBlock],
    reachable_set: set[int],
) -> dict[int, tuple[int, ...]]:
    predecessors: dict[int, list[int]] = {start: [] for start in reachable_set}
    for start in reachable_set:
        block = blocks[start]
        for successor in block.successors:
            if successor.target in reachable_set:
                predecessors[successor.target].append(start)
    return {
        start: tuple(sorted(sources))
        for start, sources in predecessors.items()
    }


def _build_successors(
    blocks: dict[int, CanonicalBlock],
    reachable_set: set[int],
) -> dict[int, tuple[int, ...]]:
    return {
        start: tuple(
            successor.target
            for successor in blocks[start].successors
            if successor.target in reachable_set
        )
        for start in reachable_set
    }


def _compute_dominators(
    entry: int,
    reachable_order: tuple[int, ...],
    predecessors: dict[int, tuple[int, ...]],
) -> dict[int, set[int]]:
    # Classic iterative dominator computation (Allen & Cocke, 1976).
    # Dom(entry) = {entry}; Dom(n) = {n} ∪ ∩{Dom(p) | p ∈ preds(n)}.
    # Iterate until fixed point.  O(n²) per iteration on the block count,
    # which is acceptable for the small function sizes in this pipeline.
    all_reachable = set(reachable_order)
    dominators = {start: set(all_reachable) for start in reachable_order}
    dominators[entry] = {entry}

    changed = True
    while changed:
        changed = False
        for start in reachable_order:
            if start == entry:
                continue
            incoming = predecessors[start]
            if not incoming:
                new_dominators = {start}
            else:
                new_dominators = {start} | set.intersection(
                    *(dominators[source] for source in incoming)
                )
            if new_dominators != dominators[start]:
                dominators[start] = new_dominators
                changed = True
    return dominators


def _compute_immediate_dominators(
    entry: int,
    reachable_order: tuple[int, ...],
    dominators: dict[int, set[int]],
    order_index: dict[int, int],
) -> dict[int, int | None]:
    immediate_dominators: dict[int, int | None] = {entry: None}

    for start in reachable_order:
        if start == entry:
            continue
        strict = sorted(dominators[start] - {start}, key=order_index.__getitem__)
        candidate = None
        for dominator in reversed(strict):
            if all(
                other in dominators[dominator]
                for other in strict
                if other != dominator
            ):
                candidate = dominator
                break
        if candidate is None:
            raise ValueError(f"unable to derive immediate dominator for block 0x{start:x}")
        immediate_dominators[start] = candidate

    return immediate_dominators


def _build_dominator_tree(
    immediate_dominators: dict[int, int | None],
    order_index: dict[int, int],
) -> dict[int, tuple[int, ...]]:
    children: dict[int, list[int]] = {start: [] for start in immediate_dominators}
    for start, dominator in immediate_dominators.items():
        if dominator is None:
            continue
        children[dominator].append(start)
    return {
        start: tuple(sorted(blocks, key=order_index.__getitem__))
        for start, blocks in children.items()
    }


def _compute_dominance_frontiers(
    entry: int,
    successors: dict[int, tuple[int, ...]],
    immediate_dominators: dict[int, int | None],
    dominator_children: dict[int, tuple[int, ...]],
    order_index: dict[int, int],
) -> dict[int, tuple[int, ...]]:
    frontiers: dict[int, tuple[int, ...]] = {start: () for start in immediate_dominators}

    def visit(start: int) -> tuple[int, ...]:
        frontier: set[int] = set()
        for successor in successors[start]:
            if immediate_dominators[successor] != start:
                frontier.add(successor)

        for child in dominator_children[start]:
            child_frontier = visit(child)
            for frontier_block in child_frontier:
                if immediate_dominators[frontier_block] != start:
                    frontier.add(frontier_block)

        ordered = tuple(sorted(frontier, key=order_index.__getitem__))
        frontiers[start] = ordered
        return ordered

    visit(entry)
    return frontiers


def _collect_register_sizes(
    blocks: dict[int, CanonicalBlock],
    reachable_order: tuple[int, ...],
) -> dict[int, int]:
    register_sizes: dict[int, int] = {}
    for start in reachable_order:
        for instruction in blocks[start].instructions:
            for op in instruction.ops:
                for varnode in _iter_register_varnodes(op):
                    if varnode.offset == 0:
                        continue
                    register_sizes.setdefault(varnode.offset, varnode.size)
    return register_sizes


def _iter_register_varnodes(op) -> tuple[Varnode, ...]:
    varnodes: list[Varnode] = []
    if op.output is not None and _space_name(op.output) == PcodeSpace.REGISTER.value:
        varnodes.append(op.output)
    for input_ in op.inputs:
        if _space_name(input_) == PcodeSpace.REGISTER.value:
            varnodes.append(input_)
    return tuple(varnodes)


def _place_phi_nodes(
    blocks: dict[int, CanonicalBlock],
    reachable_order: tuple[int, ...],
    dominance_frontiers: dict[int, tuple[int, ...]],
    order_index: dict[int, int],
) -> dict[int, tuple[int, ...]]:
    # Cytron et al. (1991) iterated dominance-frontier phi placement.
    # For each register with multiple definition sites, insert a phi
    # at every dominance-frontier block that does not already have one,
    # treating each inserted phi as a new definition site.
    phi_registers: dict[int, set[int]] = {start: set() for start in reachable_order}
    definition_blocks: dict[int, set[int]] = {}

    for start in reachable_order:
        for instruction in blocks[start].instructions:
            for op in instruction.ops:
                output = op.output
                if output is None or _space_name(output) != PcodeSpace.REGISTER.value:
                    continue
                if output.offset == 0:
                    continue
                definition_blocks.setdefault(output.offset, set()).add(start)

    for register, definition_sites in definition_blocks.items():
        worklist = deque(sorted(definition_sites, key=order_index.__getitem__))
        seen = set(definition_sites)
        while worklist:
            start = worklist.popleft()
            for frontier in dominance_frontiers[start]:
                if register in phi_registers[frontier]:
                    continue
                phi_registers[frontier].add(register)
                if frontier not in seen:
                    seen.add(frontier)
                    worklist.append(frontier)

    return {
        start: tuple(sorted(registers))
        for start, registers in phi_registers.items()
    }


def _place_memory_phi_nodes(
    blocks: dict[int, CanonicalBlock],
    reachable_order: tuple[int, ...],
    dominance_frontiers: dict[int, tuple[int, ...]],
    order_index: dict[int, int],
) -> set[int]:
    # Limitation: the entire memory state is modeled as a single SSA
    # variable.  Every STORE/CALL/CALLIND defines a new version and every
    # LOAD reads the current version, so all memory accesses are serialized.
    # This is intentionally coarse; later stages (stack, memory partitions)
    # recover finer-grained alias information.
    definition_blocks = {
        start
        for start in reachable_order
        if any(
            _opcode_text(op.opcode) in {"STORE", "CALL", "CALLIND"}
            for instruction in blocks[start].instructions
            for op in instruction.ops
        )
    }
    phi_blocks: set[int] = set()
    worklist = deque(sorted(definition_blocks, key=order_index.__getitem__))
    seen = set(definition_blocks)
    while worklist:
        start = worklist.popleft()
        for frontier in dominance_frontiers[start]:
            if frontier in phi_blocks:
                continue
            phi_blocks.add(frontier)
            if frontier not in seen:
                seen.add(frontier)
                worklist.append(frontier)
    return phi_blocks


def _rename_function(
    *,
    function: FunctionDataflowFacts,
    reachable_order: tuple[int, ...],
    predecessors: dict[int, tuple[int, ...]],
    dominator_children: dict[int, tuple[int, ...]],
    phi_registers: dict[int, tuple[int, ...]],
    memory_phi_blocks: set[int],
    register_sizes: dict[int, int],
) -> tuple[dict[int, SSABlock], tuple[SSAName, ...], MemoryVersion | None]:
    canonical = function.function
    register_stacks: dict[int, list[SSAName]] = {}
    register_next_version: dict[int, int] = {}
    unique_next_version: dict[UniqueKey, int] = {}
    live_ins: dict[int, SSAName] = {}
    memory_stack: list[MemoryVersion] = []
    next_memory_version = 1
    memory_live_in: MemoryVersion | None = None
    phi_outputs: dict[int, dict[int, SSAName]] = {
        start: {} for start in reachable_order
    }
    phi_inputs: dict[int, dict[int, dict[int, SSAValue]]] = {
        start: {register: {} for register in phi_registers[start]}
        for start in reachable_order
    }
    memory_phi_outputs: dict[int, MemoryVersion] = {}
    memory_phi_inputs: dict[int, dict[int, MemoryVersion]] = {
        start: {} for start in memory_phi_blocks
    }
    renamed_instructions: dict[int, tuple[SSAInstruction, ...]] = {}

    def current_register(register: int, size: int) -> SSAName:
        stack = register_stacks.setdefault(register, [])
        if stack:
            return stack[-1]
        live_in = live_ins.get(register)
        if live_in is None:
            live_in = SSAName(SSANameKind.REGISTER, register, 0, size)
            live_ins[register] = live_in
            register_next_version.setdefault(register, 1)
        stack.append(live_in)
        return live_in

    def new_register_definition(register: int, size: int) -> SSAName:
        next_version = register_next_version.get(register, 1)
        name = SSAName(SSANameKind.REGISTER, register, next_version, size)
        register_next_version[register] = next_version + 1
        register_stacks.setdefault(register, []).append(name)
        return name

    def current_unique(
        unique: Varnode,
        local_uniques: dict[UniqueKey, SSAName],
    ) -> SSAName:
        key = (unique.offset, unique.size)
        if key in local_uniques:
            return local_uniques[key]
        name = SSAName(SSANameKind.UNIQUE, unique.offset, 0, unique.size)
        local_uniques[key] = name
        unique_next_version.setdefault(key, 1)
        return name

    def new_unique_definition(
        unique: Varnode,
        local_uniques: dict[UniqueKey, SSAName],
    ) -> SSAName:
        key = (unique.offset, unique.size)
        next_version = unique_next_version.get(key, 1)
        name = SSAName(SSANameKind.UNIQUE, unique.offset, next_version, unique.size)
        unique_next_version[key] = next_version + 1
        local_uniques[key] = name
        return name

    def new_call_return_definition(
        register: int,
        size: int,
        pushed_registers: list[int],
    ) -> SSAName:
        name = new_register_definition(register, size)
        pushed_registers.append(register)
        return name

    def current_memory() -> MemoryVersion:
        nonlocal memory_live_in
        if memory_stack:
            return memory_stack[-1]
        if memory_live_in is None:
            memory_live_in = MemoryVersion(0)
        return memory_live_in

    def new_memory_definition(
        pushed_memories: list[MemoryVersion],
    ) -> MemoryVersion:
        nonlocal next_memory_version
        name = MemoryVersion(next_memory_version)
        next_memory_version += 1
        memory_stack.append(name)
        pushed_memories.append(name)
        return name

    def rename_input(value: Varnode, local_uniques: dict[UniqueKey, SSAName]) -> SSAValue:
        space = _space_name(value)
        if space == PcodeSpace.REGISTER.value:
            if value.offset == 0:
                return const_varnode(0, size=value.size)
            size = register_sizes.get(value.offset, value.size)
            return current_register(value.offset, size)
        if space == PcodeSpace.UNIQUE.value:
            return current_unique(value, local_uniques)
        return value

    def rename_output(
        value: Varnode,
        local_uniques: dict[UniqueKey, SSAName],
        pushed_registers: list[int],
    ) -> SSAName | None:
        space = _space_name(value)
        if space == PcodeSpace.REGISTER.value:
            if value.offset == 0:
                return SSAName(SSANameKind.REGISTER, 0, 0, value.size)
            size = register_sizes.get(value.offset, value.size)
            name = new_register_definition(value.offset, size)
            pushed_registers.append(value.offset)
            return name
        if space == PcodeSpace.UNIQUE.value:
            return new_unique_definition(value, local_uniques)
        return None

    # Iterative rename over the dominator tree using an explicit worklist.
    # The standard SSA rename algorithm recurses on the dominator tree,
    # pushing new SSA names onto per-register stacks as it enters each
    # block, then popping them when backtracking.  We simulate that
    # recursion with an explicit stack: each entry is either a "process"
    # item (is_cleanup=False) or a "cleanup" item that pops pushed defs.
    # Children are pushed in reverse order so the leftmost child is
    # processed first, matching a DFS pre-order traversal.
    worklist: list[tuple[int, bool, list[int], list[MemoryVersion]]] = [
        (canonical.entry, False, [], [])
    ]
    while worklist:
        start, is_cleanup, pushed_registers, pushed_memories = worklist.pop()

        if is_cleanup:
            # Pop everything this block pushed onto the stacks.
            for _ in pushed_memories:
                memory_stack.pop()
            for register in reversed(pushed_registers):
                stack = register_stacks[register]
                stack.pop()
                if not stack:
                    register_stacks.pop(register)
            continue

        # --- Process block (same logic as the former recursive body) ---
        block = canonical.blocks[start]

        for register in phi_registers[start]:
            phi_output = new_register_definition(register, register_sizes.get(register, 4))
            phi_outputs[start][register] = phi_output
            pushed_registers.append(register)
        if start in memory_phi_blocks:
            memory_phi_outputs[start] = new_memory_definition(pushed_memories)

        instructions: list[SSAInstruction] = []
        for instruction in block.instructions:
            local_uniques: dict[UniqueKey, SSAName] = {}
            renamed_ops = []
            for op in instruction.ops:
                opcode_text = _opcode_text(op.opcode)
                renamed_inputs = tuple(rename_input(value, local_uniques) for value in op.inputs)
                renamed_output = (
                    None
                    if op.output is None
                    else rename_output(op.output, local_uniques, pushed_registers)
                )
                memory_before: MemoryVersion | None = None
                memory_after: MemoryVersion | None = None
                if opcode_text in {"LOAD", "STORE", "CALL", "CALLIND"}:
                    memory_before = current_memory()
                if opcode_text in {"STORE", "CALL", "CALLIND"}:
                    memory_after = new_memory_definition(pushed_memories)
                renamed_ops.append(
                    SSAOp(
                        opcode=op.opcode,
                        inputs=renamed_inputs,
                        output=renamed_output,
                        memory_before=memory_before,
                        memory_after=memory_after,
                    )
                )
                if opcode_text in {"CALL", "CALLIND"}:
                    renamed_ops.extend(
                        build_call_return_ops(
                            instruction_address=instruction.address,
                            register_sizes=register_sizes,
                            define_register=lambda register, size: new_call_return_definition(
                                register,
                                size,
                                pushed_registers,
                            ),
                        )
                    )
            instructions.append(
                SSAInstruction(instruction=instruction.instruction, ops=tuple(renamed_ops))
            )
        renamed_instructions[start] = tuple(instructions)

        for successor in block.successors:
            target = successor.target
            if target in phi_inputs:
                for register in phi_registers[target]:
                    phi_inputs[target][register][start] = current_register(
                        register,
                        register_sizes.get(register, 4),
                    )
            if target in memory_phi_inputs:
                memory_phi_inputs[target][start] = current_memory()

        # Push cleanup marker first (will be popped AFTER all children).
        worklist.append((start, True, pushed_registers, pushed_memories))
        # Push children in reverse order so the first child is processed next.
        for child in reversed(dominator_children[start]):
            worklist.append((child, False, [], []))

    blocks: dict[int, SSABlock] = {}
    for start in reachable_order:
        block = canonical.blocks[start]
        phis = tuple(
            SSAPhiNode(
                output=phi_outputs[start][register],
                inputs=tuple(
                    SSAPhiInput(predecessor=predecessor, value=value)
                    for predecessor, value in sorted(phi_inputs[start][register].items())
                    if predecessor in predecessors[start]
                ),
            )
            for register in phi_registers[start]
        )
        memory_phi = None
        if start in memory_phi_blocks:
            memory_phi = SSAMemoryPhiNode(
                output=memory_phi_outputs[start],
                inputs=tuple(
                    SSAMemoryPhiInput(predecessor=predecessor, value=value)
                    for predecessor, value in sorted(memory_phi_inputs[start].items())
                    if predecessor in predecessors[start]
                ),
            )
        blocks[start] = SSABlock(
            start=start,
            phis=phis,
            memory_phi=memory_phi,
            instructions=renamed_instructions[start],
            successors=block.successors,
            terminator=block.terminator,
            call_targets=block.call_targets,
            has_indirect_call=block.has_indirect_call,
        )

    ordered_live_ins = tuple(live_ins[register] for register in sorted(live_ins))
    return blocks, ordered_live_ins, memory_live_in


_space_name = space_name

_opcode_text = opcode_text
