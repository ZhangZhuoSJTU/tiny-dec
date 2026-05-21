from tiny_dec.decode import decode_rv32i
from tiny_dec.disasm import (
    BasicBlock,
    BlockInstruction,
    BlockTerminator,
    DisasmFunction,
    format_disasm,
)
from tiny_dec.ir import lift_instruction


def _lifted(word: int, address: int) -> BlockInstruction:
    instruction = decode_rv32i(word, address)
    return BlockInstruction(
        instruction=instruction,
        pcode_ops=tuple(lift_instruction(instruction)),
    )


def test_basic_block_and_disasm_pretty_print_are_deterministic() -> None:
    first = _lifted(0x00100513, 0x1000)
    second = _lifted(0x00008067, 0x1004)
    block = BasicBlock(
        start=0x1000,
        instructions=(first, second),
        successors=(),
        terminator=BlockTerminator.RETURN,
        call_targets=(0x1110,),
        has_indirect_call=True,
    )
    function = DisasmFunction(
        entry=0x1000,
        blocks={0x1000: block},
        discovery_order=(0x1000,),
    )

    expected = "\n".join(
        [
            "entry: 0x1000",
            "order: 0x1000",
            "block 0x1000 term=return succ=[] calls=[0x1110] indirect_call=yes",
            "  0x00001000: 0x00100513  addi x10, x0, 1",
            "    INT_ADD register[0xa:4] <- const[0x0:4], const[0x1:4]",
            "  0x00001004: 0x00008067  jalr x0, 0(x1)",
            "    INT_ADD unique[0x0:4] <- register[0x1:4], const[0x0:4]",
            "    INT_AND unique[0x4:4] <- unique[0x0:4], const[0xfffffffe:4]",
            "    RETURN unique[0x4:4]",
        ]
    )

    assert format_disasm(function) == expected
    assert format_disasm(function) == expected


def test_basic_block_rejects_empty_instruction_lists() -> None:
    try:
        BasicBlock(start=0x1000, instructions=())
    except ValueError as exc:
        assert str(exc) == "basic block must contain at least one instruction"
    else:
        raise AssertionError("expected ValueError for empty basic block")


def test_disasm_function_requires_entry_block_when_blocks_are_present() -> None:
    block = BasicBlock(start=0x1004, instructions=(_lifted(0x00008067, 0x1004),))

    try:
        DisasmFunction(entry=0x1000, blocks={0x1004: block})
    except ValueError as exc:
        assert str(exc) == "disasm function entry must be present in blocks"
    else:
        raise AssertionError("expected ValueError for missing entry block")
