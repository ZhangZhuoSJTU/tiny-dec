"""RV32I instruction decoder.

This module decodes one 32-bit RV32I instruction word into a deterministic
instruction model that downstream stages can consume directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, IntEnum


class DecodeError(ValueError):
    """Raised when input bytes are outside the decoder's configured ISA scope."""


class Mnemonic(str, Enum):
    LUI = "lui"
    AUIPC = "auipc"
    JAL = "jal"
    JALR = "jalr"
    BEQ = "beq"
    BNE = "bne"
    BLT = "blt"
    BGE = "bge"
    BLTU = "bltu"
    BGEU = "bgeu"
    LB = "lb"
    LH = "lh"
    LW = "lw"
    LBU = "lbu"
    LHU = "lhu"
    SB = "sb"
    SH = "sh"
    SW = "sw"
    ADDI = "addi"
    SLTI = "slti"
    SLTIU = "sltiu"
    XORI = "xori"
    ORI = "ori"
    ANDI = "andi"
    SLLI = "slli"
    SRLI = "srli"
    SRAI = "srai"
    ADD = "add"
    SUB = "sub"
    SLL = "sll"
    SLT = "slt"
    SLTU = "sltu"
    XOR = "xor"
    SRL = "srl"
    SRA = "sra"
    OR = "or"
    AND = "and"
    FENCE = "fence"
    ECALL = "ecall"
    EBREAK = "ebreak"
    ILLEGAL = "illegal"


class InstructionFormat(str, Enum):
    R = "R"
    I = "I"  # noqa: E741
    S = "S"
    B = "B"
    U = "U"
    J = "J"
    UNKNOWN = "UNKNOWN"


class Register(IntEnum):
    X0 = 0
    X1 = 1
    X2 = 2
    X3 = 3
    X4 = 4
    X5 = 5
    X6 = 6
    X7 = 7
    X8 = 8
    X9 = 9
    X10 = 10
    X11 = 11
    X12 = 12
    X13 = 13
    X14 = 14
    X15 = 15
    X16 = 16
    X17 = 17
    X18 = 18
    X19 = 19
    X20 = 20
    X21 = 21
    X22 = 22
    X23 = 23
    X24 = 24
    X25 = 25
    X26 = 26
    X27 = 27
    X28 = 28
    X29 = 29
    X30 = 30
    X31 = 31

    @classmethod
    def from_index(cls, value: int) -> "Register":
        return cls(value)


@dataclass(frozen=True, slots=True)
class Instruction:
    address: int
    word: int
    mnemonic: str
    format: InstructionFormat = InstructionFormat.UNKNOWN
    size: int = 4

    @property
    def registers(self) -> tuple[Register, ...]:
        return ()

    @property
    def immediates(self) -> tuple[int, ...]:
        return ()

    @property
    def addresses(self) -> tuple[int, ...]:
        return ()

    def __str__(self) -> str:
        return _mnemonic_text(self.mnemonic)


@dataclass(frozen=True, slots=True)
class RV32IInstruction(Instruction):
    """Canonical RV32I instruction model used by stage-1 decode."""

    format: InstructionFormat = InstructionFormat.UNKNOWN
    size: int = 4
    opcode: int = 0
    funct3: int | None = None
    funct7: int | None = None
    rd: Register | None = None
    rs1: Register | None = None
    rs2: Register | None = None
    imm: int | None = None
    target: int | None = None

    @property
    def registers(self) -> tuple[Register, ...]:
        regs: list[Register] = []
        if self.rd is not None:
            regs.append(self.rd)
        if self.rs1 is not None:
            regs.append(self.rs1)
        if self.rs2 is not None:
            regs.append(self.rs2)
        return tuple(regs)

    @property
    def immediates(self) -> tuple[int, ...]:
        if self.imm is None:
            return ()
        return (self.imm,)

    @property
    def addresses(self) -> tuple[int, ...]:
        if self.target is None:
            return ()
        return (self.target,)

    def __str__(self) -> str:
        mnem = _mnemonic_text(self.mnemonic)

        if self.format == InstructionFormat.R:
            return (
                f"{mnem} {_format_register(self.rd)}, {_format_register(self.rs1)}, "
                f"{_format_register(self.rs2)}"
            )

        if self.format == InstructionFormat.I:
            if mnem in {"lb", "lh", "lw", "lbu", "lhu", "jalr"}:
                return (
                    f"{mnem} {_format_register(self.rd)}, {_format_immediate(self.imm)}"
                    f"({_format_register(self.rs1)})"
                )
            if mnem in {"ecall", "ebreak", "fence"}:
                return mnem
            return (
                f"{mnem} {_format_register(self.rd)}, {_format_register(self.rs1)}, "
                f"{_format_immediate(self.imm)}"
            )

        if self.format == InstructionFormat.S:
            return (
                f"{mnem} {_format_register(self.rs2)}, {_format_immediate(self.imm)}"
                f"({_format_register(self.rs1)})"
            )

        if self.format == InstructionFormat.B:
            destination = (
                _format_address(self.target)
                if self.target is not None
                else _format_immediate(self.imm)
            )
            return (
                f"{mnem} {_format_register(self.rs1)}, {_format_register(self.rs2)}, "
                f"{destination}"
            )

        if self.format == InstructionFormat.U:
            return f"{mnem} {_format_register(self.rd)}, {_format_immediate(self.imm)}"

        if self.format == InstructionFormat.J:
            destination = (
                _format_address(self.target)
                if self.target is not None
                else _format_immediate(self.imm)
            )
            return f"{mnem} {_format_register(self.rd)}, {destination}"

        return mnem

    def to_pretty_line(self) -> str:
        return f"0x{self.address:08x}: 0x{self.word:08x}  {self}"


def instruction_size(word: int) -> int:
    """Return instruction size in bytes for this RV32I decoder."""
    if word == 0:  # all-zeros padding treated as 4-byte illegal
        return 4
    if (word & 0x3) != 0x3:
        raise DecodeError("unsupported instruction-length encoding for RV32I decoder")
    return 4


def decode_rv32i(word: int, address: int) -> RV32IInstruction:
    """Decode one 32-bit RV32I instruction word.

    RV32I uses a fixed 32-bit encoding with six formats (R/I/S/B/U/J).
    All formats share the same opcode[6:0], rd[11:7], and funct3[14:12]
    bit positions.  Immediates are scattered across different bit ranges
    per format but always sign-extended from the topmost bit (bit 31).
    We pre-extract all six immediate forms here and let the dispatch
    function pick the one that matches the decoded opcode.
    """
    instruction_size(word)

    word &= 0xFFFFFFFF

    # Fixed bit-field positions shared by all RV32I formats (RISC-V spec §2.2).
    opcode = word & 0x7F
    rd = (word >> 7) & 0x1F
    funct3 = (word >> 12) & 0x7
    rs1 = (word >> 15) & 0x1F
    rs2 = (word >> 20) & 0x1F
    funct7 = (word >> 25) & 0x7F

    # Pre-extract all immediate forms.  Each format scatters the immediate
    # across different bit ranges; we reassemble and sign-extend each one
    # so the dispatch function can pick the correct form by opcode alone.
    imm_i = _sign_extend((word >> 20) & 0xFFF, 12)
    imm_s = _sign_extend((((word >> 25) & 0x7F) << 5) | ((word >> 7) & 0x1F), 12)
    # B-type: branch offset; bit 0 is implicitly zero (halfword-aligned).
    imm_b = _sign_extend(
        (((word >> 31) & 0x1) << 12)
        | (((word >> 7) & 0x1) << 11)
        | (((word >> 25) & 0x3F) << 5)
        | (((word >> 8) & 0xF) << 1),
        13,
    )
    # U-type: upper 20 bits, pre-shifted left by 12.
    imm_u = _sign_extend((word & 0xFFFFF000) >> 12, 20) << 12
    # J-type: jump offset; bit 0 is implicitly zero (halfword-aligned).
    imm_j = _sign_extend(
        (((word >> 31) & 0x1) << 20)
        | (((word >> 12) & 0xFF) << 12)
        | (((word >> 20) & 0x1) << 11)
        | (((word >> 21) & 0x3FF) << 1),
        21,
    )

    return _decode_rv32i_dispatch(
        word=word,
        address=address,
        opcode=opcode,
        rd=rd,
        rs1=rs1,
        rs2=rs2,
        funct3=funct3,
        funct7=funct7,
        imm_i=imm_i,
        imm_s=imm_s,
        imm_b=imm_b,
        imm_u=imm_u,
        imm_j=imm_j,
    )


def _decode_rv32i_dispatch(
    *,
    word: int,
    address: int,
    opcode: int,
    rd: int,
    rs1: int,
    rs2: int,
    funct3: int,
    funct7: int,
    imm_i: int,
    imm_s: int,
    imm_b: int,
    imm_u: int,
    imm_j: int,
) -> RV32IInstruction:
    # Dispatch on the 7-bit opcode field.  RV32I uses a flat opcode space
    # (no variable-length prefix trees), so a simple if-chain suffices.
    # A production decoder would use a lookup table; the explicit chain
    # is clearer for educational purposes.
    if opcode == 0x37:
        return _rv32i(
            address=address,
            word=word,
            mnemonic=Mnemonic.LUI,
            fmt=InstructionFormat.U,
            opcode=opcode,
            rd=rd,
            imm=imm_u,
        )

    if opcode == 0x17:
        return _rv32i(
            address=address,
            word=word,
            mnemonic=Mnemonic.AUIPC,
            fmt=InstructionFormat.U,
            opcode=opcode,
            rd=rd,
            imm=imm_u,
        )

    if opcode == 0x6F:
        return _rv32i(
            address=address,
            word=word,
            mnemonic=Mnemonic.JAL,
            fmt=InstructionFormat.J,
            opcode=opcode,
            rd=rd,
            imm=imm_j,
            target=address + imm_j,
        )

    if opcode == 0x67:
        if funct3 != 0x0:
            return _illegal(
                address=address,
                word=word,
                opcode=opcode,
                funct3=funct3,
                funct7=funct7,
                rd=rd,
                rs1=rs1,
                rs2=rs2,
                imm=imm_i,
            )
        return _rv32i(
            address=address,
            word=word,
            mnemonic=Mnemonic.JALR,
            fmt=InstructionFormat.I,
            opcode=opcode,
            funct3=funct3,
            rd=rd,
            rs1=rs1,
            imm=imm_i,
        )

    if opcode == 0x63:
        branch_mnemonic = {
            0x0: Mnemonic.BEQ,
            0x1: Mnemonic.BNE,
            0x4: Mnemonic.BLT,
            0x5: Mnemonic.BGE,
            0x6: Mnemonic.BLTU,
            0x7: Mnemonic.BGEU,
        }.get(funct3)
        if branch_mnemonic is None:
            return _illegal(
                address=address,
                word=word,
                opcode=opcode,
                funct3=funct3,
                funct7=funct7,
                rs1=rs1,
                rs2=rs2,
                imm=imm_b,
                target=address + imm_b,
            )
        return _rv32i(
            address=address,
            word=word,
            mnemonic=branch_mnemonic,
            fmt=InstructionFormat.B,
            opcode=opcode,
            funct3=funct3,
            rs1=rs1,
            rs2=rs2,
            imm=imm_b,
            target=address + imm_b,
        )

    if opcode == 0x03:
        load_mnemonic = {
            0x0: Mnemonic.LB,
            0x1: Mnemonic.LH,
            0x2: Mnemonic.LW,
            0x4: Mnemonic.LBU,
            0x5: Mnemonic.LHU,
        }.get(funct3)
        if load_mnemonic is None:
            return _illegal(
                address=address,
                word=word,
                opcode=opcode,
                funct3=funct3,
                funct7=funct7,
                rd=rd,
                rs1=rs1,
                imm=imm_i,
            )
        return _rv32i(
            address=address,
            word=word,
            mnemonic=load_mnemonic,
            fmt=InstructionFormat.I,
            opcode=opcode,
            funct3=funct3,
            rd=rd,
            rs1=rs1,
            imm=imm_i,
        )

    if opcode == 0x23:
        store_mnemonic = {
            0x0: Mnemonic.SB,
            0x1: Mnemonic.SH,
            0x2: Mnemonic.SW,
        }.get(funct3)
        if store_mnemonic is None:
            return _illegal(
                address=address,
                word=word,
                opcode=opcode,
                funct3=funct3,
                funct7=funct7,
                rs1=rs1,
                rs2=rs2,
                imm=imm_s,
            )
        return _rv32i(
            address=address,
            word=word,
            mnemonic=store_mnemonic,
            fmt=InstructionFormat.S,
            opcode=opcode,
            funct3=funct3,
            rs1=rs1,
            rs2=rs2,
            imm=imm_s,
        )

    if opcode == 0x13:
        if funct3 == 0x0:
            return _rv32i(
                address=address,
                word=word,
                mnemonic=Mnemonic.ADDI,
                fmt=InstructionFormat.I,
                opcode=opcode,
                funct3=funct3,
                rd=rd,
                rs1=rs1,
                imm=imm_i,
            )
        if funct3 == 0x2:
            return _rv32i(
                address=address,
                word=word,
                mnemonic=Mnemonic.SLTI,
                fmt=InstructionFormat.I,
                opcode=opcode,
                funct3=funct3,
                rd=rd,
                rs1=rs1,
                imm=imm_i,
            )
        if funct3 == 0x3:
            return _rv32i(
                address=address,
                word=word,
                mnemonic=Mnemonic.SLTIU,
                fmt=InstructionFormat.I,
                opcode=opcode,
                funct3=funct3,
                rd=rd,
                rs1=rs1,
                imm=imm_i,
            )
        if funct3 == 0x4:
            return _rv32i(
                address=address,
                word=word,
                mnemonic=Mnemonic.XORI,
                fmt=InstructionFormat.I,
                opcode=opcode,
                funct3=funct3,
                rd=rd,
                rs1=rs1,
                imm=imm_i,
            )
        if funct3 == 0x6:
            return _rv32i(
                address=address,
                word=word,
                mnemonic=Mnemonic.ORI,
                fmt=InstructionFormat.I,
                opcode=opcode,
                funct3=funct3,
                rd=rd,
                rs1=rs1,
                imm=imm_i,
            )
        if funct3 == 0x7:
            return _rv32i(
                address=address,
                word=word,
                mnemonic=Mnemonic.ANDI,
                fmt=InstructionFormat.I,
                opcode=opcode,
                funct3=funct3,
                rd=rd,
                rs1=rs1,
                imm=imm_i,
            )
        if funct3 == 0x1:
            if funct7 != 0x00:
                return _illegal(
                    address=address,
                    word=word,
                    opcode=opcode,
                    funct3=funct3,
                    funct7=funct7,
                    rd=rd,
                    rs1=rs1,
                    imm=(word >> 20) & 0x1F,
                )
            return _rv32i(
                address=address,
                word=word,
                mnemonic=Mnemonic.SLLI,
                fmt=InstructionFormat.I,
                opcode=opcode,
                funct3=funct3,
                funct7=funct7,
                rd=rd,
                rs1=rs1,
                imm=(word >> 20) & 0x1F,
            )
        if funct3 == 0x5:
            shamt = (word >> 20) & 0x1F
            if funct7 == 0x00:
                mnemonic = Mnemonic.SRLI
            elif funct7 == 0x20:
                mnemonic = Mnemonic.SRAI
            else:
                return _illegal(
                    address=address,
                    word=word,
                    opcode=opcode,
                    funct3=funct3,
                    funct7=funct7,
                    rd=rd,
                    rs1=rs1,
                    imm=shamt,
                )
            return _rv32i(
                address=address,
                word=word,
                mnemonic=mnemonic,
                fmt=InstructionFormat.I,
                opcode=opcode,
                funct3=funct3,
                funct7=funct7,
                rd=rd,
                rs1=rs1,
                imm=shamt,
            )
        return _illegal(
            address=address,
            word=word,
            opcode=opcode,
            funct3=funct3,
            funct7=funct7,
            rd=rd,
            rs1=rs1,
            imm=imm_i,
        )

    if opcode == 0x33:
        r_mnemonic = {
            (0x0, 0x00): Mnemonic.ADD,
            (0x0, 0x20): Mnemonic.SUB,
            (0x1, 0x00): Mnemonic.SLL,
            (0x2, 0x00): Mnemonic.SLT,
            (0x3, 0x00): Mnemonic.SLTU,
            (0x4, 0x00): Mnemonic.XOR,
            (0x5, 0x00): Mnemonic.SRL,
            (0x5, 0x20): Mnemonic.SRA,
            (0x6, 0x00): Mnemonic.OR,
            (0x7, 0x00): Mnemonic.AND,
        }.get((funct3, funct7))
        if r_mnemonic is None:
            return _illegal(
                address=address,
                word=word,
                opcode=opcode,
                funct3=funct3,
                funct7=funct7,
                rd=rd,
                rs1=rs1,
                rs2=rs2,
            )
        return _rv32i(
            address=address,
            word=word,
            mnemonic=r_mnemonic,
            fmt=InstructionFormat.R,
            opcode=opcode,
            funct3=funct3,
            funct7=funct7,
            rd=rd,
            rs1=rs1,
            rs2=rs2,
        )

    if opcode == 0x0F:
        if funct3 != 0x0:
            return _illegal(
                address=address,
                word=word,
                opcode=opcode,
                funct3=funct3,
                funct7=funct7,
                rd=rd,
                rs1=rs1,
                imm=imm_i,
            )
        return _rv32i(
            address=address,
            word=word,
            mnemonic=Mnemonic.FENCE,
            fmt=InstructionFormat.I,
            opcode=opcode,
            funct3=funct3,
        )

    if opcode == 0x73:
        if funct3 == 0x0 and rd == 0 and rs1 == 0:
            if imm_i == 0:
                return _rv32i(
                    address=address,
                    word=word,
                    mnemonic=Mnemonic.ECALL,
                    fmt=InstructionFormat.I,
                    opcode=opcode,
                    funct3=funct3,
                )
            if imm_i == 1:
                return _rv32i(
                    address=address,
                    word=word,
                    mnemonic=Mnemonic.EBREAK,
                    fmt=InstructionFormat.I,
                    opcode=opcode,
                    funct3=funct3,
                )
        return _illegal(
            address=address,
            word=word,
            opcode=opcode,
            funct3=funct3,
            funct7=funct7,
            rd=rd,
            rs1=rs1,
            rs2=rs2,
            imm=imm_i,
        )

    return _illegal(
        address=address,
        word=word,
        opcode=opcode,
        funct3=funct3,
        funct7=funct7,
        rd=rd,
        rs1=rs1,
        rs2=rs2,
    )


def _rv32i(
    *,
    address: int,
    word: int,
    mnemonic: Mnemonic,
    fmt: InstructionFormat,
    opcode: int,
    funct3: int | None = None,
    funct7: int | None = None,
    rd: int | None = None,
    rs1: int | None = None,
    rs2: int | None = None,
    imm: int | None = None,
    target: int | None = None,
) -> RV32IInstruction:
    return RV32IInstruction(
        address=address,
        word=word,
        mnemonic=mnemonic,
        format=fmt,
        opcode=opcode,
        funct3=funct3,
        funct7=funct7,
        rd=Register.from_index(rd) if rd is not None else None,
        rs1=Register.from_index(rs1) if rs1 is not None else None,
        rs2=Register.from_index(rs2) if rs2 is not None else None,
        imm=imm,
        target=target,
    )


def _illegal(
    *,
    address: int,
    word: int,
    opcode: int,
    funct3: int | None = None,
    funct7: int | None = None,
    rd: int | None = None,
    rs1: int | None = None,
    rs2: int | None = None,
    imm: int | None = None,
    target: int | None = None,
) -> RV32IInstruction:
    return _rv32i(
        address=address,
        word=word,
        mnemonic=Mnemonic.ILLEGAL,
        fmt=InstructionFormat.UNKNOWN,
        opcode=opcode,
        funct3=funct3,
        funct7=funct7,
        rd=rd,
        rs1=rs1,
        rs2=rs2,
        imm=imm,
        target=target,
    )


def _sign_extend(value: int, bits: int) -> int:
    sign_bit = 1 << (bits - 1)
    return (value ^ sign_bit) - sign_bit


def _mnemonic_text(mnemonic: str) -> str:
    if isinstance(mnemonic, Mnemonic):
        return mnemonic.value
    return mnemonic


def _format_register(register: Register | None) -> str:
    if register is None:
        return "?"
    return f"x{int(register)}"


def _format_immediate(imm: int | None) -> str:
    if imm is None:
        return "?"
    return str(imm)


def _format_address(address: int | None) -> str:
    if address is None:
        return "?"
    return f"0x{address:x}"
