"""Stage-17 and stage-18 C-emission data structures.

This module owns both:

- the stage-17 C-like IR produced from structured control flow
- the stage-18 rendered-C surface that packages final source text in a stable,
  diff-friendly way
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from tiny_dec.analysis.interproc.models import InterprocInvalidation
from tiny_dec.structuring.models import FunctionStructuredFacts, ProgramStructuredFacts


class CLoweredVariableKind(str, Enum):
    PARAMETER = "parameter"
    LOCAL = "local"


@dataclass(frozen=True, slots=True)
class CLoweredType:
    spelling: str
    size: int | None = None

    def __post_init__(self) -> None:
        if not self.spelling:
            raise ValueError("c-lowered type spelling must not be empty")
        if self.size is not None and self.size <= 0:
            raise ValueError("c-lowered type size must be positive when present")

    def to_pretty(self) -> str:
        return self.spelling


@dataclass(frozen=True, slots=True)
class CLoweredVariable:
    name: str
    kind: CLoweredVariableKind
    ctype: CLoweredType
    register: int | None = None
    stack_offset: int | None = None

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("c-lowered variable name must not be empty")
        if self.stack_offset is not None and self.stack_offset < 0:
            raise ValueError("c-lowered stack offset must be non-negative")
        if self.kind == CLoweredVariableKind.PARAMETER:
            has_register = self.register is not None and self.register >= 0
            has_stack_offset = self.stack_offset is not None
            if has_register == has_stack_offset:
                raise ValueError(
                    "c-lowered parameter declarations must carry exactly one non-negative register or stack offset"
                )
            return
        if self.register is not None or self.stack_offset is not None:
            raise ValueError("c-lowered local declarations must not carry a parameter location")

    def to_pretty(self) -> str:
        if self.kind == CLoweredVariableKind.PARAMETER:
            if self.register is not None:
                return f"param x{self.register} {self.ctype.to_pretty()} {self.name}"
            assert self.stack_offset is not None
            return f"param stack+{self.stack_offset} {self.ctype.to_pretty()} {self.name}"
        return f"local {self.ctype.to_pretty()} {self.name}"


@dataclass(frozen=True, slots=True)
class CLoweredReturn:
    register: int
    ctype: CLoweredType

    def __post_init__(self) -> None:
        if self.register < 0:
            raise ValueError("c-lowered return register must be non-negative")

    def to_pretty(self) -> str:
        return f"return x{self.register} {self.ctype.to_pretty()}"


class CCallTargetKind(str, Enum):
    INTERNAL = "internal"
    EXTERNAL = "external"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class CCallTarget:
    kind: CCallTargetKind
    address: int | None = None
    name: str | None = None
    indirect: bool = False

    def __post_init__(self) -> None:
        if self.address is not None and self.address < 0:
            raise ValueError("c-lowered call target address must be non-negative")
        if self.name == "":
            raise ValueError("c-lowered call target name must not be empty")

    def to_pretty(self) -> str:
        if self.name is not None:
            return self.name
        if self.address is not None:
            if self.indirect:
                return f"call_indirect_0x{self.address:x}"
            if self.kind == CCallTargetKind.INTERNAL:
                return f"fn_0x{self.address:x}"
            if self.kind == CCallTargetKind.EXTERNAL:
                return f"extern_0x{self.address:x}"
            return f"call_0x{self.address:x}"
        return "call_indirect" if self.indirect else "call_unknown"


@dataclass(frozen=True, slots=True)
class CNameExpr:
    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("c-lowered name expressions must not be empty")

    def to_pretty(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class CFieldExpr:
    base_name: str
    field_offset: int
    field_name: str
    index: CExpr | None = None

    def __post_init__(self) -> None:
        if not self.base_name:
            raise ValueError("c-lowered field-expression base name must not be empty")
        if self.field_offset < 0:
            raise ValueError("c-lowered field-expression offset must be non-negative")
        if not self.field_name:
            raise ValueError("c-lowered field-expression field name must not be empty")

    def to_pretty(self) -> str:
        from tiny_dec.c_emit.render_expr import render_c_expr

        if self.index is None:
            return f"{self.base_name}->{self.field_name}"
        return f"{self.base_name}[{render_c_expr(self.index)}].{self.field_name}"


@dataclass(frozen=True, slots=True)
class CGlobalExpr:
    address: int
    size: int
    name: str | None = None

    def __post_init__(self) -> None:
        if self.address < 0:
            raise ValueError("c-lowered global-expression address must be non-negative")
        if self.size <= 0:
            raise ValueError("c-lowered global-expression size must be positive")
        if self.name == "":
            raise ValueError("c-lowered global-expression name must not be empty")

    def to_pretty(self) -> str:
        if self.name is not None:
            return self.name
        return f"global_0x{self.address:x}_{self.size}"


@dataclass(frozen=True, slots=True)
class CRawExpr:
    text: str

    def __post_init__(self) -> None:
        if not self.text:
            raise ValueError("c-lowered raw expressions must not be empty")

    def to_pretty(self) -> str:
        return f"raw<{self.text}>"


@dataclass(frozen=True, slots=True)
class CConstExpr:
    value: int
    size: int

    def __post_init__(self) -> None:
        if self.size <= 0:
            raise ValueError("c-lowered constant-expression size must be positive")

    def to_pretty(self) -> str:
        bits = self.size * 8
        mask = (1 << bits) - 1
        masked = self.value & mask
        sign_bit = 1 << (bits - 1)
        signed = masked - (1 << bits) if masked & sign_bit else masked
        if -1024 < signed < 1024:
            return str(signed)
        return f"0x{masked:x}"


@dataclass(frozen=True, slots=True)
class CUnaryExpr:
    op: str
    operand: CExpr

    def __post_init__(self) -> None:
        if not self.op:
            raise ValueError("c-lowered unary-expression op must not be empty")

    def to_pretty(self) -> str:
        from tiny_dec.c_emit.render_expr import render_c_expr

        return render_c_expr(self)


@dataclass(frozen=True, slots=True)
class CBinaryExpr:
    op: str
    left: CExpr
    right: CExpr

    def __post_init__(self) -> None:
        if not self.op:
            raise ValueError("c-lowered binary-expression op must not be empty")

    def to_pretty(self) -> str:
        from tiny_dec.c_emit.render_expr import render_c_expr

        return render_c_expr(self)


@dataclass(frozen=True, slots=True)
class CCallExpr:
    target: CCallTarget
    arguments: tuple[CExpr, ...] = ()

    def to_pretty(self) -> str:
        from tiny_dec.c_emit.render_expr import render_c_expr

        return render_c_expr(self)


type CExpr = (
    CNameExpr
    | CFieldExpr
    | CGlobalExpr
    | CRawExpr
    | CConstExpr
    | CUnaryExpr
    | CBinaryExpr
    | CCallExpr
)

type CLValueExpr = CNameExpr | CFieldExpr | CGlobalExpr | CRawExpr


@dataclass(frozen=True, slots=True)
class CAssignStmt:
    target: CLValueExpr
    value: CExpr

    def to_pretty(self) -> str:
        from tiny_dec.c_emit.render_expr import render_c_expr, render_c_lvalue

        return f"{render_c_lvalue(self.target)} = {render_c_expr(self.value)};"


@dataclass(frozen=True, slots=True)
class CExprStmt:
    expr: CExpr

    def to_pretty(self) -> str:
        from tiny_dec.c_emit.render_expr import render_c_expr

        return f"{render_c_expr(self.expr)};"


@dataclass(frozen=True, slots=True)
class CReturnBinding:
    register: int
    value: CExpr

    def __post_init__(self) -> None:
        if self.register < 0:
            raise ValueError("c-lowered return binding register must be non-negative")

    def to_pretty(self) -> str:
        from tiny_dec.c_emit.render_expr import render_c_expr

        return f"x{self.register}={render_c_expr(self.value)}"


@dataclass(frozen=True, slots=True)
class CGotoStmt:
    target: int

    def __post_init__(self) -> None:
        if self.target < 0:
            raise ValueError("c-lowered goto target must be non-negative")

    def to_pretty(self) -> str:
        return f"goto label_0x{self.target:x};"


@dataclass(frozen=True, slots=True)
class CBreakStmt:
    target: int

    def __post_init__(self) -> None:
        if self.target < 0:
            raise ValueError("c-lowered break target must be non-negative")

    def to_pretty(self) -> str:
        return f"break /* 0x{self.target:x} */;"


@dataclass(frozen=True, slots=True)
class CContinueStmt:
    target: int

    def __post_init__(self) -> None:
        if self.target < 0:
            raise ValueError("c-lowered continue target must be non-negative")

    def to_pretty(self) -> str:
        return f"continue /* 0x{self.target:x} */;"


type CStmt = (
    CAssignStmt
    | CExprStmt
    | CReturnStmt
    | CIfStmt
    | CSwitchStmt
    | CWhileStmt
    | CGotoStmt
    | CBreakStmt
    | CContinueStmt
)


@dataclass(frozen=True, slots=True)
class CStmtSequence:
    items: tuple[CStmt, ...] = ()

    def statement_count(self) -> int:
        return sum(_statement_count(item) for item in self.items)


@dataclass(frozen=True, slots=True)
class CReturnStmt:
    values: tuple[CReturnBinding, ...] = ()

    def __post_init__(self) -> None:
        registers = tuple(binding.register for binding in self.values)
        if registers != tuple(sorted(registers)):
            raise ValueError("c-lowered return bindings must be ordered by register")
        if len(set(registers)) != len(registers):
            raise ValueError("c-lowered return bindings must be unique by register")

    def to_pretty(self) -> str:
        values = ", ".join(binding.to_pretty() for binding in self.values)
        return f"return [{values}];" if values else "return;"


@dataclass(frozen=True, slots=True)
class CIfStmt:
    condition: CExpr
    then_body: CStmtSequence = CStmtSequence()
    else_body: CStmtSequence = CStmtSequence()

    def to_pretty(self) -> str:
        from tiny_dec.c_emit.render_expr import render_c_expr

        return f"if ({render_c_expr(self.condition)})"


@dataclass(frozen=True, slots=True)
class CWhileStmt:
    condition: CExpr
    body: CStmtSequence = CStmtSequence()

    def to_pretty(self) -> str:
        from tiny_dec.c_emit.render_expr import render_c_expr

        return f"while ({render_c_expr(self.condition)})"


@dataclass(frozen=True, slots=True)
class CSwitchCase:
    value: int
    body: CStmtSequence = CStmtSequence()

    def to_pretty(self) -> str:
        return f"case {self.value}:"


@dataclass(frozen=True, slots=True)
class CSwitchStmt:
    selector: CExpr
    cases: tuple[CSwitchCase, ...] = ()
    default_body: CStmtSequence = CStmtSequence()

    def __post_init__(self) -> None:
        case_values = tuple(case.value for case in self.cases)
        if len(set(case_values)) != len(case_values):
            raise ValueError("c-lowered switch cases must be unique by value")

    def to_pretty(self) -> str:
        from tiny_dec.c_emit.render_expr import render_c_expr

        return f"switch ({render_c_expr(self.selector)})"


@dataclass(slots=True)
class FunctionCLowered:
    structured: FunctionStructuredFacts
    parameters: tuple[CLoweredVariable, ...] = ()
    returns: tuple[CLoweredReturn, ...] = ()
    locals: tuple[CLoweredVariable, ...] = ()
    body: CStmtSequence = CStmtSequence()

    def __post_init__(self) -> None:
        parameter_names = tuple(parameter.name for parameter in self.parameters)
        if len(set(parameter_names)) != len(parameter_names):
            raise ValueError("c-lowered parameters must be unique by name")
        if any(parameter.kind != CLoweredVariableKind.PARAMETER for parameter in self.parameters):
            raise ValueError("c-lowered parameter list must contain only parameter declarations")
        parameter_locations = tuple(
            ("register", parameter.register)
            if parameter.register is not None
            else ("stack", parameter.stack_offset)
            for parameter in self.parameters
        )
        if len(set(parameter_locations)) != len(parameter_locations):
            raise ValueError("c-lowered parameters must be unique by location")

        local_names = tuple(local.name for local in self.locals)
        if len(set(local_names)) != len(local_names):
            raise ValueError("c-lowered locals must be unique by name")
        if any(local.kind != CLoweredVariableKind.LOCAL for local in self.locals):
            raise ValueError("c-lowered local list must contain only local declarations")

        if set(parameter_names) & set(local_names):
            raise ValueError("c-lowered parameter and local names must be disjoint")

        expected_returns = tuple(sorted(self.returns, key=lambda carrier: carrier.register))
        if self.returns != expected_returns:
            raise ValueError("c-lowered returns must be ordered deterministically by register")
        if len({carrier.register for carrier in self.returns}) != len(self.returns):
            raise ValueError("c-lowered returns must be unique by register")

    @property
    def entry(self) -> int:
        return self.structured.entry

    @property
    def name(self) -> str | None:
        return self.structured.name

    @property
    def pending_entries(self) -> tuple[int, ...]:
        return self.structured.pending_entries

    @property
    def frame_size(self) -> int | None:
        return self.structured.frame_size

    @property
    def dynamic_stack_pointer(self) -> bool:
        return self.structured.dynamic_stack_pointer

    @property
    def statement_count(self) -> int:
        return self.body.statement_count()


@dataclass(slots=True)
class ProgramCLowered:
    structured: ProgramStructuredFacts
    functions: dict[int, FunctionCLowered] = field(default_factory=dict)
    pending_entries: tuple[int, ...] = ()
    invalidated_entries: tuple[int, ...] = ()
    scheduler_invalidations: tuple[InterprocInvalidation, ...] = ()

    def __post_init__(self) -> None:
        if set(self.functions) != set(self.structured.functions):
            raise ValueError("program c-lowered facts must cover structured functions exactly")
        if self.pending_entries != self.structured.pending_entries:
            raise ValueError("program c-lowered pending entries must match structured facts")
        if self.invalidated_entries != self.structured.invalidated_entries:
            raise ValueError(
                "program c-lowered invalidated entries must match structured facts"
            )
        if self.scheduler_invalidations != self.structured.scheduler_invalidations:
            raise ValueError(
                "program c-lowered scheduler invalidations must match structured facts"
            )

    def ordered_function_entries(self) -> tuple[int, ...]:
        return self.structured.ordered_function_entries()

    def ordered_functions(self) -> tuple[FunctionCLowered, ...]:
        return tuple(self.functions[entry] for entry in self.ordered_function_entries())


def _statement_count(item: CStmt) -> int:
    if isinstance(item, CIfStmt):
        return 1 + item.then_body.statement_count() + item.else_body.statement_count()
    if isinstance(item, CSwitchStmt):
        return 1 + sum(case.body.statement_count() for case in item.cases) + item.default_body.statement_count()
    if isinstance(item, CWhileStmt):
        return 1 + item.body.statement_count()
    return 1


@dataclass(frozen=True, slots=True)
class FunctionCRendered:
    c_lowered: FunctionCLowered
    function_name: str
    return_type: str
    prototype: str
    includes: tuple[str, ...] = ()
    type_declarations: tuple[str, ...] = ()
    local_declarations: tuple[str, ...] = ()
    statement_lines: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.function_name:
            raise ValueError("rendered-C function name must not be empty")
        if not self.return_type:
            raise ValueError("rendered-C function return type must not be empty")
        if not self.prototype:
            raise ValueError("rendered-C function prototype must not be empty")
        if len(set(self.includes)) != len(self.includes):
            raise ValueError("rendered-C function includes must be unique")
        if len(set(self.type_declarations)) != len(self.type_declarations):
            raise ValueError("rendered-C function type declarations must be unique")
        if any(not line for line in self.local_declarations):
            raise ValueError("rendered-C local declarations must not be empty")
        if any("\n" in line for line in self.local_declarations):
            raise ValueError("rendered-C local declarations must be single lines")
        if any(not line for line in self.statement_lines):
            raise ValueError("rendered-C statement lines must not be empty")
        if any("\n" in line for line in self.statement_lines):
            raise ValueError("rendered-C statement lines must be single lines")

    @property
    def entry(self) -> int:
        return self.c_lowered.entry

    @property
    def name(self) -> str | None:
        return self.c_lowered.name

    @property
    def pending_entries(self) -> tuple[int, ...]:
        return self.c_lowered.pending_entries


@dataclass(slots=True)
class ProgramCRendered:
    c_lowered: ProgramCLowered
    includes: tuple[str, ...] = ()
    type_declarations: tuple[str, ...] = ()
    prototypes: tuple[str, ...] = ()
    functions: dict[int, FunctionCRendered] = field(default_factory=dict)
    pending_entries: tuple[int, ...] = ()
    invalidated_entries: tuple[int, ...] = ()
    scheduler_invalidations: tuple[InterprocInvalidation, ...] = ()

    def __post_init__(self) -> None:
        if set(self.functions) != set(self.c_lowered.functions):
            raise ValueError("rendered-C program functions must cover lowered program exactly")
        if len(set(self.includes)) != len(self.includes):
            raise ValueError("rendered-C includes must be unique")
        if len(set(self.type_declarations)) != len(self.type_declarations):
            raise ValueError("rendered-C type declarations must be unique")
        if len(set(self.prototypes)) != len(self.prototypes):
            raise ValueError("rendered-C prototypes must be unique")
        if self.pending_entries != self.c_lowered.pending_entries:
            raise ValueError("rendered-C pending entries must match lowered program")
        if self.invalidated_entries != self.c_lowered.invalidated_entries:
            raise ValueError("rendered-C invalidated entries must match lowered program")
        if self.scheduler_invalidations != self.c_lowered.scheduler_invalidations:
            raise ValueError(
                "rendered-C scheduler invalidations must match lowered program"
            )

    @property
    def root_entry(self) -> int:
        return self.c_lowered.structured.interproc.ranges.variables.aggregate_types.scalar_types.memory.stack.calls.ssa.dataflow.program.root_entry

    def ordered_function_entries(self) -> tuple[int, ...]:
        return self.c_lowered.ordered_function_entries()

    def ordered_functions(self) -> tuple[FunctionCRendered, ...]:
        return tuple(self.functions[entry] for entry in self.ordered_function_entries())
