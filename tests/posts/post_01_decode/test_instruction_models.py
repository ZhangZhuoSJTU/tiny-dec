from tiny_dec.decode import Instruction, InstructionFormat, Mnemonic, RV32IInstruction, Register

RV32I_BASE_MNEMONICS = {
    "lui",
    "auipc",
    "jal",
    "jalr",
    "beq",
    "bne",
    "blt",
    "bge",
    "bltu",
    "bgeu",
    "lb",
    "lh",
    "lw",
    "lbu",
    "lhu",
    "sb",
    "sh",
    "sw",
    "addi",
    "slti",
    "sltiu",
    "xori",
    "ori",
    "andi",
    "slli",
    "srli",
    "srai",
    "add",
    "sub",
    "sll",
    "slt",
    "sltu",
    "xor",
    "srl",
    "sra",
    "or",
    "and",
    "fence",
    "ecall",
    "ebreak",
}


def test_mnemonic_enum_covers_rv32i_base_set() -> None:
    all_mnemonics = {mnemonic.value for mnemonic in Mnemonic}
    assert RV32I_BASE_MNEMONICS.issubset(all_mnemonics)


def test_instruction_base_and_rv32i_model_fields() -> None:
    base = Instruction(address=0x1000, word=0x13, mnemonic="nop")
    assert base.format == InstructionFormat.UNKNOWN
    assert base.registers == ()
    assert base.immediates == ()
    assert base.addresses == ()
    assert str(base) == "nop"

    insn = RV32IInstruction(
        address=0x1004,
        word=0x003100B3,
        mnemonic=Mnemonic.ADD,
        format=InstructionFormat.R,
        opcode=0x33,
        funct3=0x0,
        funct7=0x00,
        rd=Register.X1,
        rs1=Register.X2,
        rs2=Register.X3,
    )
    assert insn.registers == (Register.X1, Register.X2, Register.X3)
    assert insn.immediates == ()
    assert insn.addresses == ()
    assert str(insn) == "add x1, x2, x3"
    assert insn.to_pretty_line() == "0x00001004: 0x003100b3  add x1, x2, x3"


def test_rv32i_model_pretty_print_for_control_flow() -> None:
    branch = RV32IInstruction(
        address=0x1010,
        word=0x00208663,
        mnemonic=Mnemonic.BEQ,
        format=InstructionFormat.B,
        opcode=0x63,
        funct3=0x0,
        rs1=Register.X1,
        rs2=Register.X2,
        imm=12,
        target=0x101C,
    )
    assert branch.immediates == (12,)
    assert branch.addresses == (0x101C,)
    assert str(branch) == "beq x1, x2, 0x101c"

    jump = RV32IInstruction(
        address=0x1014,
        word=0x008000EF,
        mnemonic=Mnemonic.JAL,
        format=InstructionFormat.J,
        opcode=0x6F,
        rd=Register.X1,
        imm=8,
        target=0x101C,
    )
    assert jump.registers == (Register.X1,)
    assert jump.immediates == (8,)
    assert jump.addresses == (0x101C,)
    assert str(jump) == "jal x1, 0x101c"
