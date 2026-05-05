"""Stage-8 call-model data structures built on top of stage-7 SSA facts."""

from __future__ import annotations

from dataclasses import dataclass, field

from tiny_dec.analysis.ssa.models import (
    MemoryVersion,
    SSAFunctionIR,
    SSAProgramIR,
    SSAValue,
)
from tiny_dec.ir.program_ir import CallGraphEdge, CallGraphEdgeKind


def _validate_register_list(registers: tuple[int, ...], message: str) -> None:
    if any(register < 0 for register in registers):
        raise ValueError("register lists must contain only non-negative registers")
    if registers != tuple(sorted(registers)) or len(set(registers)) != len(registers):
        raise ValueError(message)


def _format_register_list(registers: tuple[int, ...]) -> str:
    return ", ".join(f"x{register}" for register in registers)


def _validate_stack_offset_list(offsets: tuple[int, ...], message: str) -> None:
    if any(offset < 0 for offset in offsets):
        raise ValueError("stack-offset lists must contain only non-negative offsets")
    if offsets != tuple(sorted(offsets)) or len(set(offsets)) != len(offsets):
        raise ValueError(message)


def _format_stack_offset_list(offsets: tuple[int, ...]) -> str:
    return ", ".join(f"stack+{offset}" for offset in offsets)


@dataclass(frozen=True, slots=True)
class CallABI:
    name: str
    argument_registers: tuple[int, ...]
    return_registers: tuple[int, ...]
    clobbered_registers: tuple[int, ...]

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("call abi name must not be empty")
        _validate_register_list(
            self.argument_registers,
            "call abi argument registers must be unique and sorted",
        )
        _validate_register_list(
            self.return_registers,
            "call abi return registers must be unique and sorted",
        )
        _validate_register_list(
            self.clobbered_registers,
            "call abi clobbered registers must be unique and sorted",
        )

    def to_pretty(self) -> str:
        args = _format_register_list(self.argument_registers)
        returns = _format_register_list(self.return_registers)
        clobbers = _format_register_list(self.clobbered_registers)
        return (
            f"{self.name} args=[{args}] returns=[{returns}] clobbers=[{clobbers}]"
        )


RV32I_ILP32_CALL_ABI = CallABI(
    name="rv32i_ilp32",
    argument_registers=(10, 11, 12, 13, 14, 15, 16, 17),
    return_registers=(10, 11),
    clobbered_registers=(1, 5, 6, 7, 10, 11, 12, 13, 14, 15, 16, 17, 28, 29, 30, 31),
)


@dataclass(frozen=True, slots=True)
class CallRegisterValue:
    register: int
    value: SSAValue

    def __post_init__(self) -> None:
        if self.register < 0:
            raise ValueError("call register value register must be non-negative")

    def to_pretty(self) -> str:
        return f"x{self.register}={self.value.to_pretty()}"


@dataclass(frozen=True, slots=True)
class CallStackValue:
    stack_offset: int
    value: SSAValue

    def __post_init__(self) -> None:
        if self.stack_offset < 0:
            raise ValueError("call stack value offset must be non-negative")

    def to_pretty(self) -> str:
        return f"stack+{self.stack_offset}={self.value.to_pretty()}"


@dataclass(frozen=True, slots=True)
class KnownExternalSignature:
    name: str
    parameter_registers: tuple[int, ...] = ()
    parameter_stack_offsets: tuple[int, ...] = ()
    return_registers: tuple[int, ...] = ()
    no_return: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("known external signature name must not be empty")
        _validate_register_list(
            self.parameter_registers,
            "known external signature parameter registers must be unique and sorted",
        )
        _validate_stack_offset_list(
            self.parameter_stack_offsets,
            "known external signature parameter stack offsets must be unique and sorted",
        )
        _validate_register_list(
            self.return_registers,
            "known external signature return registers must be unique and sorted",
        )
        if self.no_return and self.return_registers:
            raise ValueError("no-return external signatures must not carry return registers")

    def to_pretty(self) -> str:
        registers = _format_register_list(self.parameter_registers)
        stack_offsets = _format_stack_offset_list(self.parameter_stack_offsets)
        returns = _format_register_list(self.return_registers)
        return (
            f"{self.name} regs=[{registers}] stack=[{stack_offsets}] "
            f"returns=[{returns}] no_return={'yes' if self.no_return else 'no'}"
        )


@dataclass(frozen=True, slots=True)
class ModeledCallSite:
    instruction_address: int
    block_start: int
    target_kind: CallGraphEdgeKind
    target_address: int | None = None
    callee_name: str | None = None
    is_indirect: bool = False
    resolved_from_recovered_target: bool = False
    indirect_target_value: SSAValue | None = None
    argument_values: tuple[CallRegisterValue, ...] = ()
    stack_argument_values: tuple[CallStackValue, ...] = ()
    memory_before: MemoryVersion | None = None
    memory_after: MemoryVersion | None = None
    return_values: tuple[CallRegisterValue, ...] = ()
    external_signature: KnownExternalSignature | None = None

    def __post_init__(self) -> None:
        if self.instruction_address < 0:
            raise ValueError("modeled callsite instruction address must be non-negative")
        if self.block_start < 0:
            raise ValueError("modeled callsite block start must be non-negative")
        if self.resolved_from_recovered_target and not self.is_indirect:
            raise ValueError(
                "modeled callsite can only mark recovered targets for indirect calls"
            )
        if self.indirect_target_value is not None and not self.is_indirect:
            raise ValueError(
                "modeled callsite can only carry an explicit indirect target value for indirect calls"
            )
        if self.target_kind == CallGraphEdgeKind.INTERNAL and self.target_address is None:
            raise ValueError("internal modeled callsite must carry a target address")
        if (
            self.target_kind == CallGraphEdgeKind.EXTERNAL
            and self.target_address is None
            and self.callee_name is None
        ):
            raise ValueError("external modeled callsite must carry an address or name")
        if self.external_signature is not None and self.target_kind != CallGraphEdgeKind.EXTERNAL:
            raise ValueError(
                "modeled callsite can only carry an external signature for external targets"
            )
        if self.memory_after is not None and self.memory_before is None:
            raise ValueError("modeled callsite memory_after requires memory_before")

        registers = tuple(value.register for value in self.argument_values)
        if registers != tuple(sorted(registers)):
            raise ValueError("modeled callsite argument values must be sorted by register")
        if len(set(registers)) != len(registers):
            raise ValueError("modeled callsite argument values must be unique by register")
        stack_offsets = tuple(value.stack_offset for value in self.stack_argument_values)
        if stack_offsets != tuple(sorted(stack_offsets)):
            raise ValueError(
                "modeled callsite stack argument values must be sorted by offset"
            )
        if len(set(stack_offsets)) != len(stack_offsets):
            raise ValueError(
                "modeled callsite stack argument values must be unique by offset"
            )
        return_registers = tuple(value.register for value in self.return_values)
        if return_registers != tuple(sorted(return_registers)):
            raise ValueError("modeled callsite return values must be sorted by register")
        if len(set(return_registers)) != len(return_registers):
            raise ValueError("modeled callsite return values must be unique by register")

    def to_pretty(self) -> str:
        via = "indirect" if self.is_indirect else "direct"
        target = self.target_kind.value
        if self.target_address is not None:
            target += f" 0x{self.target_address:x}"
        if self.callee_name is not None:
            target += f" name={self.callee_name}"
        if self.resolved_from_recovered_target:
            target += " source=recovered"
        if self.external_signature is not None:
            target += f" sig={self.external_signature.to_pretty()}"
        target_value_text = (
            f" target_value={self.indirect_target_value.to_pretty()}"
            if self.indirect_target_value is not None
            else ""
        )
        args = ", ".join(value.to_pretty() for value in self.argument_values)
        arg_text = f"[{args}]" if args else "[]"
        stack_args = ", ".join(value.to_pretty() for value in self.stack_argument_values)
        stack_arg_text = f" stack_args=[{stack_args}]" if stack_args else ""
        memory_text = ""
        if self.memory_before is not None:
            after = (
                self.memory_after.to_pretty()
                if self.memory_after is not None
                else self.memory_before.to_pretty()
            )
            memory_text = f" mem=[{self.memory_before.to_pretty()} -> {after}]"
        returns = ", ".join(value.to_pretty() for value in self.return_values)
        return_text = f"[{returns}]" if returns else "[]"
        return (
            f"call 0x{self.instruction_address:x} block=0x{self.block_start:x} "
            f"via={via} -> {target}{target_value_text} args={arg_text}{stack_arg_text}"
            f"{memory_text} returns={return_text}"
        )


@dataclass(slots=True)
class FunctionCallFacts:
    ssa: SSAFunctionIR
    abi: CallABI = RV32I_ILP32_CALL_ABI
    callsites: tuple[ModeledCallSite, ...] = ()
    pending_entries: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        expected = tuple(
            (callsite.instruction_address, callsite.block_start, callsite.is_indirect)
            for callsite in self.ssa.dataflow.function.callsites
        )
        actual = tuple(
            (callsite.instruction_address, callsite.block_start, callsite.is_indirect)
            for callsite in self.callsites
        )
        if actual != expected:
            raise ValueError("function call facts callsites must match upstream order")
        if self.pending_entries != tuple(sorted(set(self.pending_entries))):
            raise ValueError("function call facts pending entries must be unique and sorted")

    @property
    def entry(self) -> int:
        return self.ssa.entry

    @property
    def name(self) -> str | None:
        return self.ssa.name


@dataclass(slots=True)
class ProgramCallFacts:
    ssa: SSAProgramIR
    abi: CallABI = RV32I_ILP32_CALL_ABI
    functions: dict[int, FunctionCallFacts] = field(default_factory=dict)
    call_graph: tuple[CallGraphEdge, ...] = ()
    pending_entries: tuple[int, ...] = ()
    invalidated_entries: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        if set(self.functions) != set(self.ssa.functions):
            raise ValueError("program call facts must cover SSA program functions exactly")
        if self.pending_entries != tuple(sorted(set(self.pending_entries))):
            raise ValueError("program call facts pending entries must be unique and sorted")
        if self.invalidated_entries != tuple(sorted(set(self.invalidated_entries))):
            raise ValueError(
                "program call facts invalidated entries must be unique and sorted"
            )

        expected_callsites = tuple(
            (function.entry, callsite.instruction_address)
            for function in self.ordered_functions()
            for callsite in function.callsites
            if callsite.target_address is not None
        )
        actual_callsites = tuple(
            (edge.caller, edge.callsite_address)
            for edge in self.call_graph
        )
        if actual_callsites != expected_callsites:
            raise ValueError("program call facts call graph must follow function and callsite order")

    def ordered_function_entries(self) -> tuple[int, ...]:
        return self.ssa.ordered_function_entries()

    def ordered_functions(self) -> tuple[FunctionCallFacts, ...]:
        return tuple(self.functions[entry] for entry in self.ordered_function_entries())
