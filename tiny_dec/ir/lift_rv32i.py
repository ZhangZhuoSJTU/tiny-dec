from __future__ import annotations

from dataclasses import dataclass, field

from tiny_dec.decode import Instruction, Mnemonic, RV32IInstruction, Register
from tiny_dec.ir.pcode import (
    PcodeOp,
    PcodeOpcode,
    Varnode,
    const_varnode,
    register_varnode,
    unique_varnode,
)


def lift_instruction(insn: Instruction) -> list[PcodeOp]:
    """Lift one decoded RV32I instruction into low-level pcode ops.

    Algorithm:
    1. Normalize/validate instruction type and mnemonic text.
    2. Build register/constant varnodes for all referenced operands.
    3. Dispatch mnemonic to a dedicated lift routine.
    4. Emit pcode in architectural execution order.
    5. Allocate deterministic unique temporaries per lifted instruction.

    Invariants:
    - Return value is deterministic for equal input instruction objects.
    - Returned pcode is low-level (non-SSA).
    - Unsupported instructions fail explicitly instead of silently dropping ops.
    """
    if not isinstance(insn, RV32IInstruction):
        raise TypeError("lift_instruction expects RV32IInstruction input")

    ctx = _LiftContext(insn=insn)
    mnemonic = _mnemonic_text(insn.mnemonic)

    if mnemonic == Mnemonic.LUI.value:
        _lift_lui(ctx)
    elif mnemonic == Mnemonic.AUIPC.value:
        _lift_auipc(ctx)
    elif mnemonic == Mnemonic.JAL.value:
        _lift_jal(ctx)
    elif mnemonic == Mnemonic.JALR.value:
        _lift_jalr(ctx)
    elif mnemonic in {
        Mnemonic.BEQ.value,
        Mnemonic.BNE.value,
        Mnemonic.BLT.value,
        Mnemonic.BGE.value,
        Mnemonic.BLTU.value,
        Mnemonic.BGEU.value,
    }:
        _lift_branch(ctx, mnemonic)
    elif mnemonic in {
        Mnemonic.LB.value,
        Mnemonic.LH.value,
        Mnemonic.LW.value,
        Mnemonic.LBU.value,
        Mnemonic.LHU.value,
    }:
        _lift_load(ctx, mnemonic)
    elif mnemonic in {
        Mnemonic.SB.value,
        Mnemonic.SH.value,
        Mnemonic.SW.value,
    }:
        _lift_store(ctx, mnemonic)
    elif mnemonic in {
        Mnemonic.ADDI.value,
        Mnemonic.SLTI.value,
        Mnemonic.SLTIU.value,
        Mnemonic.XORI.value,
        Mnemonic.ORI.value,
        Mnemonic.ANDI.value,
        Mnemonic.SLLI.value,
        Mnemonic.SRLI.value,
        Mnemonic.SRAI.value,
    }:
        _lift_op_imm(ctx, mnemonic)
    elif mnemonic in {
        Mnemonic.ADD.value,
        Mnemonic.SUB.value,
        Mnemonic.SLL.value,
        Mnemonic.SLT.value,
        Mnemonic.SLTU.value,
        Mnemonic.XOR.value,
        Mnemonic.SRL.value,
        Mnemonic.SRA.value,
        Mnemonic.OR.value,
        Mnemonic.AND.value,
    }:
        _lift_op(ctx, mnemonic)
    elif mnemonic == Mnemonic.FENCE.value:
        ctx.emit(PcodeOpcode.CALLOTHER, ctx.const32(0))
    elif mnemonic == Mnemonic.ECALL.value:
        ctx.emit(PcodeOpcode.CALLOTHER, ctx.const32(1))
    elif mnemonic == Mnemonic.EBREAK.value:
        ctx.emit(PcodeOpcode.CALLOTHER, ctx.const32(2))
    elif mnemonic == Mnemonic.ILLEGAL.value:
        ctx.emit(PcodeOpcode.TRAP, ctx.const32(insn.word))
    else:
        raise NotImplementedError(f"unsupported RV32I mnemonic in lifter: {mnemonic}")

    return ctx.ops


@dataclass(slots=True)
class _LiftContext:
    insn: RV32IInstruction
    ops: list[PcodeOp] = field(default_factory=list)
    _next_unique: int = 0

    def tmp(self, *, size: int) -> Varnode:
        # Unique temporaries are allocated with a stride of 4 bytes so
        # non-overlapping 1/2/4-byte temporaries never alias in the
        # unique address space, matching Ghidra's p-code convention.
        out = unique_varnode(self._next_unique, size=size)
        self._next_unique += 4
        return out

    def const32(self, value: int) -> Varnode:
        return const_varnode(value, size=4)

    def imm32(self) -> Varnode:
        return const_varnode(0 if self.insn.imm is None else self.insn.imm, size=4)

    def read_reg(self, reg: Register | None) -> Varnode:
        if reg is None:
            raise ValueError("missing register operand")
        # RV32I hardwires x0 to zero; reads always produce 0.
        if reg == Register.X0:
            return self.const32(0)
        return register_varnode(int(reg), size=4)

    def write_reg(self, reg: Register | None) -> Varnode | None:
        # Writes to x0 are silently discarded (architectural zero register).
        if reg is None or reg == Register.X0:
            return None
        return register_varnode(int(reg), size=4)

    def emit(
        self, opcode: PcodeOpcode, *inputs: Varnode, output: Varnode | None = None
    ) -> None:
        self.ops.append(PcodeOp(opcode=opcode, inputs=tuple(inputs), output=output))

    def branch_target_const(self) -> Varnode:
        if self.insn.target is not None:
            return self.const32(self.insn.target)
        base = self.insn.address
        displacement = self.insn.imm or 0
        return self.const32(base + displacement)


def _mnemonic_text(mnemonic: str | Mnemonic) -> str:
    if isinstance(mnemonic, Mnemonic):
        return mnemonic.value
    return mnemonic


def _lift_lui(ctx: _LiftContext) -> None:
    rd = ctx.write_reg(ctx.insn.rd)
    if rd is None:
        return
    ctx.emit(PcodeOpcode.COPY, ctx.imm32(), output=rd)


def _lift_auipc(ctx: _LiftContext) -> None:
    rd = ctx.write_reg(ctx.insn.rd)
    if rd is None:
        return
    ctx.emit(
        PcodeOpcode.INT_ADD,
        ctx.const32(ctx.insn.address),
        ctx.imm32(),
        output=rd,
    )


def _lift_jal(ctx: _LiftContext) -> None:
    # Any non-x0 rd is treated as a call (link). RV32I allows x5 as an
    # alternate link register; we treat all non-x0 cases uniformly.
    rd = ctx.write_reg(ctx.insn.rd)
    if rd is None:
        ctx.emit(PcodeOpcode.BRANCH, ctx.branch_target_const())
        return

    ctx.emit(PcodeOpcode.COPY, ctx.const32(ctx.insn.address + 4), output=rd)
    ctx.emit(PcodeOpcode.CALL, ctx.branch_target_const())


def _lift_jalr(ctx: _LiftContext) -> None:
    # JALR computes target = (rs1 + imm) & ~1.  The low-bit mask is
    # architectural (RISC-V spec §2.5) and ensures halfword alignment.
    base = ctx.read_reg(ctx.insn.rs1)
    imm = ctx.imm32()

    target = ctx.tmp(size=4)
    ctx.emit(PcodeOpcode.INT_ADD, base, imm, output=target)

    masked = ctx.tmp(size=4)
    ctx.emit(
        PcodeOpcode.INT_AND,
        target,
        ctx.const32(0xFFFFFFFE),
        output=masked,
    )

    rd = ctx.write_reg(ctx.insn.rd)
    if rd is None:
        # jalr x0, x1, 0 is the standard return idiom (jr ra).
        if ctx.insn.rs1 == Register.X1 and (ctx.insn.imm or 0) == 0:
            ctx.emit(PcodeOpcode.RETURN, masked)
            return
        ctx.emit(PcodeOpcode.BRANCHIND, masked)
        return

    ctx.emit(PcodeOpcode.COPY, ctx.const32(ctx.insn.address + 4), output=rd)
    ctx.emit(PcodeOpcode.CALLIND, masked)


def _lift_branch(ctx: _LiftContext, mnemonic: str) -> None:
    lhs = ctx.read_reg(ctx.insn.rs1)
    rhs = ctx.read_reg(ctx.insn.rs2)

    compare_map: dict[str, PcodeOpcode] = {
        Mnemonic.BEQ.value: PcodeOpcode.INT_EQUAL,
        Mnemonic.BNE.value: PcodeOpcode.INT_NOTEQUAL,
        Mnemonic.BLT.value: PcodeOpcode.INT_SLESS,
        Mnemonic.BLTU.value: PcodeOpcode.INT_LESS,
        Mnemonic.BGE.value: PcodeOpcode.INT_SLESS,
        Mnemonic.BGEU.value: PcodeOpcode.INT_LESS,
    }
    condition = ctx.tmp(size=1)
    ctx.emit(compare_map[mnemonic], lhs, rhs, output=condition)

    if mnemonic in {Mnemonic.BGE.value, Mnemonic.BGEU.value}:
        negated = ctx.tmp(size=1)
        ctx.emit(PcodeOpcode.BOOL_NEGATE, condition, output=negated)
        condition = negated

    ctx.emit(PcodeOpcode.CBRANCH, ctx.branch_target_const(), condition)


def _lift_load(ctx: _LiftContext, mnemonic: str) -> None:
    width_map: dict[str, int] = {
        Mnemonic.LB.value: 1,
        Mnemonic.LBU.value: 1,
        Mnemonic.LH.value: 2,
        Mnemonic.LHU.value: 2,
        Mnemonic.LW.value: 4,
    }
    signed_map: dict[str, bool] = {
        Mnemonic.LB.value: True,
        Mnemonic.LBU.value: False,
        Mnemonic.LH.value: True,
        Mnemonic.LHU.value: False,
        Mnemonic.LW.value: False,
    }

    base = ctx.read_reg(ctx.insn.rs1)
    displacement = ctx.imm32()
    addr = ctx.tmp(size=4)
    ctx.emit(PcodeOpcode.INT_ADD, base, displacement, output=addr)

    width = width_map[mnemonic]
    raw = ctx.tmp(size=width)
    ctx.emit(PcodeOpcode.LOAD, addr, output=raw)

    rd = ctx.write_reg(ctx.insn.rd)
    if rd is None:
        return
    if width == 4:
        ctx.emit(PcodeOpcode.COPY, raw, output=rd)
        return

    ext_opcode = PcodeOpcode.INT_SEXT if signed_map[mnemonic] else PcodeOpcode.INT_ZEXT
    ctx.emit(ext_opcode, raw, output=rd)


def _lift_store(ctx: _LiftContext, mnemonic: str) -> None:
    width_map: dict[str, int] = {
        Mnemonic.SB.value: 1,
        Mnemonic.SH.value: 2,
        Mnemonic.SW.value: 4,
    }
    width = width_map[mnemonic]

    base = ctx.read_reg(ctx.insn.rs1)
    displacement = ctx.imm32()
    addr = ctx.tmp(size=4)
    ctx.emit(PcodeOpcode.INT_ADD, base, displacement, output=addr)

    value = ctx.read_reg(ctx.insn.rs2)
    if width == 4:
        ctx.emit(PcodeOpcode.STORE, addr, value)
        return

    narrowed = ctx.tmp(size=width)
    ctx.emit(PcodeOpcode.SUBPIECE, value, ctx.const32(0), output=narrowed)
    ctx.emit(PcodeOpcode.STORE, addr, narrowed)


def _lift_op_imm(ctx: _LiftContext, mnemonic: str) -> None:
    rd = ctx.write_reg(ctx.insn.rd)
    if rd is None:
        return

    lhs = ctx.read_reg(ctx.insn.rs1)
    rhs = ctx.imm32()

    bin_map: dict[str, PcodeOpcode] = {
        Mnemonic.ADDI.value: PcodeOpcode.INT_ADD,
        Mnemonic.XORI.value: PcodeOpcode.INT_XOR,
        Mnemonic.ORI.value: PcodeOpcode.INT_OR,
        Mnemonic.ANDI.value: PcodeOpcode.INT_AND,
        Mnemonic.SLLI.value: PcodeOpcode.INT_LEFT,
        Mnemonic.SRLI.value: PcodeOpcode.INT_RIGHT,
        Mnemonic.SRAI.value: PcodeOpcode.INT_SRIGHT,
    }
    if mnemonic in bin_map:
        ctx.emit(bin_map[mnemonic], lhs, rhs, output=rd)
        return

    cmp_map: dict[str, PcodeOpcode] = {
        Mnemonic.SLTI.value: PcodeOpcode.INT_SLESS,
        Mnemonic.SLTIU.value: PcodeOpcode.INT_LESS,
    }
    predicate = ctx.tmp(size=1)
    ctx.emit(cmp_map[mnemonic], lhs, rhs, output=predicate)
    ctx.emit(PcodeOpcode.INT_ZEXT, predicate, output=rd)


def _lift_op(ctx: _LiftContext, mnemonic: str) -> None:
    rd = ctx.write_reg(ctx.insn.rd)
    if rd is None:
        return

    lhs = ctx.read_reg(ctx.insn.rs1)
    rhs = ctx.read_reg(ctx.insn.rs2)

    shift_map: dict[str, PcodeOpcode] = {
        Mnemonic.SLL.value: PcodeOpcode.INT_LEFT,
        Mnemonic.SRL.value: PcodeOpcode.INT_RIGHT,
        Mnemonic.SRA.value: PcodeOpcode.INT_SRIGHT,
    }
    if mnemonic in shift_map:
        masked_rhs = ctx.tmp(size=4)
        ctx.emit(PcodeOpcode.INT_AND, rhs, ctx.const32(0x1F), output=masked_rhs)
        ctx.emit(shift_map[mnemonic], lhs, masked_rhs, output=rd)
        return

    bin_map: dict[str, PcodeOpcode] = {
        Mnemonic.ADD.value: PcodeOpcode.INT_ADD,
        Mnemonic.SUB.value: PcodeOpcode.INT_SUB,
        Mnemonic.XOR.value: PcodeOpcode.INT_XOR,
        Mnemonic.OR.value: PcodeOpcode.INT_OR,
        Mnemonic.AND.value: PcodeOpcode.INT_AND,
    }
    if mnemonic in bin_map:
        ctx.emit(bin_map[mnemonic], lhs, rhs, output=rd)
        return

    cmp_map: dict[str, PcodeOpcode] = {
        Mnemonic.SLT.value: PcodeOpcode.INT_SLESS,
        Mnemonic.SLTU.value: PcodeOpcode.INT_LESS,
    }
    predicate = ctx.tmp(size=1)
    ctx.emit(cmp_map[mnemonic], lhs, rhs, output=predicate)
    ctx.emit(PcodeOpcode.INT_ZEXT, predicate, output=rd)
