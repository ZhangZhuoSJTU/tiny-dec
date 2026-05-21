"""Stage-4 builders that materialize durable IR containers from disassembly.

This file owns the transformation from stage-3 `DisasmFunction` snapshots into
`FunctionIR` and `ProgramIR`.

Implementation plan:
1. Reuse stage-3 disassembly rather than rediscovering blocks here.
2. Build a deterministic instruction index in block/instruction order.
3. Scan lifted p-code for `CALL` and `CALLIND` to derive typed callsites.
4. Build `FunctionIR` first, then walk direct calls from the chosen root to
   build `ProgramIR`.
5. Classify direct calls as internal, external, or unresolved without trying
   to recover indirect targets yet.

Failure policy:
- Unmapped or undecodable targets do not crash program construction unless they
  are the selected root entry. They are recorded as unresolved direct edges.
- Indirect calls are preserved as callsites but do not become call-graph edges.
- Future stages may re-invoke stage 4 when newly discovered functions appear.
"""

from __future__ import annotations

from collections import deque

from tiny_dec.decode import DecodeError
from tiny_dec.disasm.builder import disassemble_function
from tiny_dec.disasm.models import BlockInstruction, BlockTerminator, DisasmFunction
from tiny_dec.ir.function_ir import CallSite, FunctionIR
from tiny_dec.ir.pcode import PcodeOp, PcodeOpcode, PcodeSpace
from tiny_dec.ir.program_ir import CallGraphEdge, CallGraphEdgeKind, ProgramIR
from tiny_dec.loader import AddressNotMappedError, ExternalFunction, ProgramView


def build_function_ir(
    view: ProgramView,
    entry: int,
    *,
    disasm: DisasmFunction | None = None,
) -> FunctionIR:
    """Build one `FunctionIR` from one entry address.

    Concrete implementation notes:
    - If `disasm` is not provided, stage 3 is re-run from `entry`.
    - Instruction order must match `DisasmFunction.ordered_blocks()`.
    - Callsite order must match the instruction index order.
    - Return blocks come directly from the owned block terminators.
    """
    function_disasm = disasm if disasm is not None else disassemble_function(view, entry)
    instruction_index: dict[int, BlockInstruction] = {}
    callsites: list[CallSite] = []
    direct_callees: list[int] = []
    seen_direct_callees: set[int] = set()
    seen_callsites: set[tuple[int, bool, int | None]] = set()
    return_blocks: list[int] = []

    for block in function_disasm.ordered_blocks():
        if block.terminator == BlockTerminator.RETURN:
            return_blocks.append(block.start)

        for lifted in block.instructions:
            instruction_index.setdefault(lifted.address, lifted)
            for callsite in _instruction_callsites(view, block.start, lifted):
                callsite_key = (
                    callsite.instruction_address,
                    callsite.is_indirect,
                    callsite.target,
                )
                if callsite_key in seen_callsites:
                    continue
                seen_callsites.add(callsite_key)
                callsites.append(callsite)
                if callsite.is_indirect or callsite.target is None:
                    continue
                if callsite.target in seen_direct_callees:
                    continue
                direct_callees.append(callsite.target)
                seen_direct_callees.add(callsite.target)

    return FunctionIR(
        entry=entry,
        name=view.get_symbol_name(entry),
        disasm=function_disasm,
        instruction_index=instruction_index,
        callsites=tuple(callsites),
        return_blocks=tuple(return_blocks),
        direct_callees=tuple(direct_callees),
    )


def build_program_ir(view: ProgramView, root_entry: int) -> ProgramIR:
    """Build a `ProgramIR` rooted at one function entry.

    Concrete implementation notes:
    - Seed a deterministic worklist with `root_entry`.
    - Materialize `FunctionIR` for each scheduled entry.
    - Record direct call-graph edges in caller/callsite order.
    - Schedule only direct internal callees discovered at this stage.
    - Keep `pending_entries` and `invalidated_entries` empty for now.
    """
    functions: dict[int, FunctionIR] = {}
    discovery_order: list[int] = []
    call_graph: list[CallGraphEdge] = []
    disasm_cache: dict[int, DisasmFunction | None] = {}
    unresolved_externals = deque(view.ordered_unresolved_external_functions())
    scheduled = {root_entry}
    worklist: deque[int] = deque([root_entry])

    while worklist:
        entry = worklist.popleft()
        if entry in functions:
            continue

        cached = disasm_cache.get(entry)
        function = build_function_ir(view, entry, disasm=cached)
        functions[entry] = function
        discovery_order.append(entry)

        for callsite in function.callsites:
            edge = _classify_direct_call(
                view,
                functions,
                function,
                callsite,
                disasm_cache,
                unresolved_externals,
            )
            if edge is None:
                continue
            call_graph.append(edge)

            if edge.kind != CallGraphEdgeKind.INTERNAL or edge.callee_address is None:
                continue
            if edge.callee_address in scheduled:
                continue
            worklist.append(edge.callee_address)
            scheduled.add(edge.callee_address)

    return ProgramIR(
        root_entry=root_entry,
        functions=functions,
        discovery_order=tuple(discovery_order),
        externals=tuple(view.external_functions()),
        call_graph=tuple(call_graph),
        pending_entries=(),
        invalidated_entries=(),
    )


def _instruction_callsites(
    view: ProgramView,
    block_start: int,
    lifted: BlockInstruction,
) -> tuple[CallSite, ...]:
    callsites: list[CallSite] = []
    for op in lifted.pcode_ops:
        opcode = _opcode_text(op)
        if opcode == PcodeOpcode.CALL.value:
            target = _const_target(op)
            callsites.append(
                CallSite(
                    instruction_address=lifted.address,
                    block_start=block_start,
                    target=target,
                    target_name=_target_name(view, target),
                )
            )
            continue

        if opcode == PcodeOpcode.CALLIND.value:
            callsites.append(
                CallSite(
                    instruction_address=lifted.address,
                    block_start=block_start,
                    is_indirect=True,
                )
            )

    return tuple(callsites)


def _classify_direct_call(
    view: ProgramView,
    functions: dict[int, FunctionIR],
    caller: FunctionIR,
    callsite: CallSite,
    disasm_cache: dict[int, DisasmFunction | None],
    unresolved_externals: deque[ExternalFunction],
) -> CallGraphEdge | None:
    if callsite.is_indirect or callsite.target is None:
        return None

    target = callsite.target
    external = view.external_function_by_address(target)
    if external is not None:
        return CallGraphEdge(
            caller=caller.entry,
            callsite_address=callsite.instruction_address,
            kind=CallGraphEdgeKind.EXTERNAL,
            callee_address=target,
            callee_name=external.name,
        )

    # Self-targeting unresolved jal: the linker encodes a self-jump for
    # calls to undefined externals.  Consume one name from the loader's
    # ordered undefined-external list per such callsite encountered.
    if (
        target == callsite.instruction_address
        and callsite.target_name is None
        and unresolved_externals
    ):
        fallback = unresolved_externals.popleft()
        return CallGraphEdge(
            caller=caller.entry,
            callsite_address=callsite.instruction_address,
            kind=CallGraphEdgeKind.EXTERNAL,
            callee_address=target,
            callee_name=fallback.name,
        )

    if target in caller.instruction_index and target != caller.entry:
        return CallGraphEdge(
            caller=caller.entry,
            callsite_address=callsite.instruction_address,
            kind=CallGraphEdgeKind.UNRESOLVED,
            callee_address=target,
            callee_name=callsite.target_name,
        )

    if target in functions:
        return CallGraphEdge(
            caller=caller.entry,
            callsite_address=callsite.instruction_address,
            kind=CallGraphEdgeKind.INTERNAL,
            callee_address=target,
            callee_name=functions[target].name,
        )

    if _is_known_non_entry_address(functions, target):
        return CallGraphEdge(
            caller=caller.entry,
            callsite_address=callsite.instruction_address,
            kind=CallGraphEdgeKind.UNRESOLVED,
            callee_address=target,
            callee_name=callsite.target_name,
        )

    if _probe_disasm(view, target, disasm_cache) is not None:
        return CallGraphEdge(
            caller=caller.entry,
            callsite_address=callsite.instruction_address,
            kind=CallGraphEdgeKind.INTERNAL,
            callee_address=target,
            callee_name=view.get_symbol_name(target),
        )

    return CallGraphEdge(
        caller=caller.entry,
        callsite_address=callsite.instruction_address,
        kind=CallGraphEdgeKind.UNRESOLVED,
        callee_address=target,
        callee_name=callsite.target_name,
    )


def _probe_disasm(
    view: ProgramView,
    entry: int,
    cache: dict[int, DisasmFunction | None],
) -> DisasmFunction | None:
    if entry not in cache:
        try:
            cache[entry] = disassemble_function(view, entry)
        except (
            AddressNotMappedError,
            DecodeError,
            NotImplementedError,
            ValueError,
        ):
            cache[entry] = None
    return cache[entry]


def _is_known_non_entry_address(functions: dict[int, FunctionIR], address: int) -> bool:
    for function in functions.values():
        if address not in function.instruction_index:
            continue
        if address == function.entry:
            return False
        return True
    return False


def _target_name(view: ProgramView, target: int) -> str | None:
    external = view.external_function_by_address(target)
    if external is not None:
        return external.name
    return view.get_symbol_name(target)


def _const_target(op: PcodeOp) -> int:
    if not op.inputs:
        raise AddressNotMappedError("expected direct call target input")

    target = op.inputs[0]
    space_name = target.space.value if isinstance(target.space, PcodeSpace) else target.space
    if space_name != PcodeSpace.CONST.value:
        raise AddressNotMappedError("expected direct call target to be constant")
    return target.offset


def _opcode_text(op: PcodeOp) -> str:
    opcode = op.opcode
    if isinstance(opcode, PcodeOpcode):
        return opcode.value
    return opcode
