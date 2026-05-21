from __future__ import annotations

from typing import cast

from tiny_dec.ir.containers import build_function_ir, build_program_ir
from tiny_dec.ir.program_ir import CallGraphEdgeKind
from tiny_dec.loader import AddressNotMappedError, ExternalFunction, ProgramView


def _enc_i(opcode: int, rd: int, funct3: int, rs1: int, imm: int) -> int:
    return (
        ((imm & 0xFFF) << 20)
        | ((rs1 & 0x1F) << 15)
        | ((funct3 & 0x7) << 12)
        | ((rd & 0x1F) << 7)
        | (opcode & 0x7F)
    )


def _enc_j(opcode: int, rd: int, imm: int) -> int:
    imm21 = imm & 0x1FFFFF
    bit20 = (imm21 >> 20) & 0x1
    bits10_1 = (imm21 >> 1) & 0x3FF
    bit11 = (imm21 >> 11) & 0x1
    bits19_12 = (imm21 >> 12) & 0xFF
    return (
        (bit20 << 31)
        | (bits19_12 << 12)
        | (bit11 << 20)
        | (bits10_1 << 21)
        | ((rd & 0x1F) << 7)
        | (opcode & 0x7F)
    )


class FakeProgramView:
    def __init__(
        self,
        words: dict[int, int],
        *,
        symbol_names: dict[int, str] | None = None,
        externals: tuple[ExternalFunction, ...] = (),
    ) -> None:
        self._words = dict(words)
        self._symbol_names = dict(symbol_names or {})
        self._externals = tuple(externals)

    def read_u32(self, address: int) -> int:
        if address not in self._words:
            raise AddressNotMappedError(f"missing word at {address:#x}")
        return self._words[address]

    def get_symbol_name(self, address: int) -> str | None:
        return self._symbol_names.get(address)

    def contains_address(self, address: int, *, size: int = 1) -> bool:
        if size <= 0:
            return size == 0
        return all((address + offset) in self._words for offset in range(0, size, 4))

    def external_functions(self) -> list[ExternalFunction]:
        return list(self._externals)

    def ordered_unresolved_external_functions(self) -> tuple[ExternalFunction, ...]:
        return tuple(
            external
            for external in self._externals
            if external.plt_address is None
            and external.got_address is None
            and external.symbol_address is None
        )

    def external_function_by_address(self, address: int) -> ExternalFunction | None:
        for external in self._externals:
            addresses = (
                external.plt_address,
                external.got_address,
                external.symbol_address,
            )
            if address in addresses:
                return external
        return None


def _view(
    words: dict[int, int],
    *,
    symbol_names: dict[int, str] | None = None,
    externals: tuple[ExternalFunction, ...] = (),
) -> ProgramView:
    return cast(
        ProgramView,
        FakeProgramView(words, symbol_names=symbol_names, externals=externals),
    )


def test_build_function_ir_indexes_instructions_and_callsites_in_order() -> None:
    function = build_function_ir(
        _view(
            {
                0x1000: _enc_j(0x6F, 1, 0x100),
                0x1004: 0x00008067,
                0x1100: 0x00008067,
            },
            symbol_names={0x1000: "main", 0x1100: "helper"},
        ),
        0x1000,
    )

    assert function.entry == 0x1000
    assert function.name == "main"
    assert tuple(function.instruction_index) == (0x1000, 0x1004)
    assert function.return_blocks == (0x1000,)
    assert function.direct_callees == (0x1100,)
    assert len(function.callsites) == 1
    assert function.callsites[0].target == 0x1100
    assert function.callsites[0].target_name == "helper"


def test_build_function_ir_records_indirect_calls_without_direct_callee() -> None:
    function = build_function_ir(
        _view(
            {
                0x1000: _enc_i(0x67, 1, 0x0, 5, 0),
                0x1004: 0x00008067,
            },
            symbol_names={0x1000: "main"},
        ),
        0x1000,
    )

    assert function.direct_callees == ()
    assert len(function.callsites) == 1
    assert function.callsites[0].is_indirect is True
    assert function.callsites[0].target is None


def test_build_program_ir_discovers_direct_internal_callee_once() -> None:
    program = build_program_ir(
        _view(
            {
                0x1000: _enc_j(0x6F, 1, 0x100),
                0x1004: _enc_j(0x6F, 1, 0xFC),
                0x1008: 0x00008067,
                0x1100: 0x00008067,
            },
            symbol_names={0x1000: "main", 0x1100: "helper"},
        ),
        0x1000,
    )

    assert program.discovery_order == (0x1000, 0x1100)
    assert tuple(program.functions) == (0x1000, 0x1100)
    assert len(program.call_graph) == 2
    assert all(edge.kind == CallGraphEdgeKind.INTERNAL for edge in program.call_graph)
    assert all(edge.callee_address == 0x1100 for edge in program.call_graph)


def test_build_program_ir_classifies_external_direct_targets_without_disassembly() -> None:
    program = build_program_ir(
        _view(
            {
                0x1000: _enc_j(0x6F, 1, 0x1000),
                0x1004: 0x00008067,
            },
            symbol_names={0x1000: "main"},
            externals=(
                ExternalFunction(
                    name="puts",
                    plt_address=0x2000,
                    got_address=None,
                    symbol_address=None,
                ),
            ),
        ),
        0x1000,
    )

    assert program.discovery_order == (0x1000,)
    assert tuple(program.functions) == (0x1000,)
    assert len(program.call_graph) == 1
    assert program.call_graph[0].kind == CallGraphEdgeKind.EXTERNAL
    assert program.call_graph[0].callee_name == "puts"


def test_build_program_ir_classifies_got_backed_external_direct_targets() -> None:
    program = build_program_ir(
        _view(
            {
                0x1000: _enc_j(0x6F, 1, 0x1000),
                0x1004: 0x00008067,
            },
            symbol_names={0x1000: "main"},
            externals=(
                ExternalFunction(
                    name="free",
                    plt_address=None,
                    got_address=0x2000,
                    symbol_address=None,
                ),
            ),
        ),
        0x1000,
    )

    assert program.discovery_order == (0x1000,)
    assert tuple(program.functions) == (0x1000,)
    assert len(program.call_graph) == 1
    assert program.call_graph[0].kind == CallGraphEdgeKind.EXTERNAL
    assert program.call_graph[0].callee_name == "free"


def test_build_program_ir_keeps_unresolved_direct_targets_out_of_function_table() -> None:
    program = build_program_ir(
        _view(
            {
                0x1000: _enc_j(0x6F, 1, 0x2000),
                0x1004: 0x00008067,
            },
            symbol_names={0x1000: "main"},
        ),
        0x1000,
    )

    assert program.discovery_order == (0x1000,)
    assert tuple(program.functions) == (0x1000,)
    assert len(program.call_graph) == 1
    assert program.call_graph[0].kind == CallGraphEdgeKind.UNRESOLVED
    assert program.call_graph[0].callee_address == 0x3000


def test_build_program_ir_treats_direct_call_into_current_body_as_unresolved() -> None:
    program = build_program_ir(
        _view(
            {
                0x1000: _enc_j(0x6F, 1, 4),
                0x1004: 0x00008067,
            },
            symbol_names={0x1000: "main"},
        ),
        0x1000,
    )

    assert tuple(program.functions) == (0x1000,)
    assert len(program.call_graph) == 1
    assert program.call_graph[0].kind == CallGraphEdgeKind.UNRESOLVED
    assert program.call_graph[0].callee_address == 0x1004


def test_build_program_ir_resolves_self_targeting_calls_to_ordered_undefined_externals() -> None:
    program = build_program_ir(
        _view(
            {
                0x1000: _enc_j(0x6F, 1, 0),
                0x1004: _enc_j(0x6F, 1, 0),
                0x1008: 0x00008067,
            },
            externals=(
                ExternalFunction(
                    name="malloc",
                    plt_address=None,
                    got_address=None,
                    symbol_address=None,
                ),
                ExternalFunction(
                    name="puts",
                    plt_address=None,
                    got_address=None,
                    symbol_address=None,
                ),
            ),
        ),
        0x1000,
    )

    assert tuple(program.functions) == (0x1000,)
    assert len(program.call_graph) == 2
    assert [edge.kind for edge in program.call_graph] == [
        CallGraphEdgeKind.EXTERNAL,
        CallGraphEdgeKind.EXTERNAL,
    ]
    assert [edge.callee_name for edge in program.call_graph] == ["malloc", "puts"]
