"""Stage-17 C-like IR lowering and stage-18 rendering support.

This file owns the transformation from stage-16 structure into the stage-17
C-like IR surface, and the final stage-18 rendering entrypoints that will
package stage-17 output into rendered source text.

Implementation notes:
- The stage is read-only with respect to upstream structure, interprocedural
  summaries, variable recovery, aggregate layouts, scalar types, memory facts,
  stack facts, call modeling, and SSA.
- It preserves upstream `pending_entries`, `invalidated_entries`, and
  `scheduler_invalidations` unchanged.
- The lowering is intentionally conservative: it prefers explicit locals,
  parameters, aggregate field references, and calls, but it falls back to raw
  expressions when the current SSA or memory evidence does not justify cleaner
  source syntax.
- Callsites can now consume stage-7 `CALL_RETURN` defs through stage-8
  callsite snapshots, but only the simplest primary-return-to-lvalue pattern
  is lowered as one explicit call assignment.
- Pure SSA operations are lowered lazily into expressions. Stage 17 only emits
  statements for side effects, control structure, and explicit returns.
- The rendered output uses non-standard C operators for signedness-aware
  semantics that standard C cannot express: ``<s`` / ``>=s`` (signed compare),
  ``<u`` / ``>=u`` (unsigned compare), ``>>u`` (unsigned right shift).  The
  output is C-like pseudocode, not compilable C.
- Stage 18 is read-only with respect to stage-17 lowered IR. It preserves
  queue and invalidation state unchanged while synthesizing helper
  declarations and rendered source text.

Architecture:
- The lowering works in two passes.  Pass 1 builds a lazy expression
  graph from SSA ops: each SSA value maps to a `CExpr` node that is
  only materialized into source text when a statement references it.
  Pass 2 walks the structured control tree and emits `CStmt` nodes for
  assignments, calls, returns, and control flow, inlining expression
  trees on demand.
- This two-pass design avoids emitting dead SSA operations (e.g. phi
  nodes whose result is never used) and naturally produces expression
  nesting that resembles hand-written C.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property

from tiny_dec.analysis.calls.models import ModeledCallSite
from tiny_dec.analysis.highvars.models import RecoveredVariable, VariableBindingKind, VariableKind
from tiny_dec.analysis.interproc.models import (
    FunctionInterprocFacts,
    PrototypeRegister,
    PrototypeStackParameter,
)
from tiny_dec.analysis.memory.models import MemoryAccessKind, MemoryPartition, MemoryPartitionKind
from tiny_dec.analysis.ssa.models import SSAFunctionIR, SSAName, SSANameKind, SSAOp, SSAPhiNode, SSAValue
from tiny_dec.analysis.types.aggregate_models import AggregateLayout
from tiny_dec.analysis.types.models import ScalarType, ScalarTypeKind
from tiny_dec.c_emit.models import (
    CAssignStmt,
    CBinaryExpr,
    CBreakStmt,
    CCallExpr,
    CCallTarget,
    CCallTargetKind,
    CConstExpr,
    CContinueStmt,
    CExpr,
    CExprStmt,
    CFieldExpr,
    CGlobalExpr,
    CGotoStmt,
    CIfStmt,
    CLValueExpr,
    CLoweredReturn,
    CLoweredType,
    CLoweredVariable,
    CLoweredVariableKind,
    CNameExpr,
    CRawExpr,
    CReturnBinding,
    CReturnStmt,
    CStmt,
    CStmtSequence,
    CSwitchCase,
    CSwitchStmt,
    CUnaryExpr,
    CWhileStmt,
    FunctionCLowered,
    FunctionCRendered,
    ProgramCLowered,
    ProgramCRendered,
)
from tiny_dec.c_emit.render_expr import render_c_expr, render_c_lvalue
from tiny_dec.ir.program_ir import CallGraphEdgeKind
from tiny_dec.ir.pcode import PcodeSpace, Varnode
from tiny_dec.loader import ProgramView
from tiny_dec.structuring import (
    FunctionStructuredFacts,
    ProgramStructuredFacts,
    StructuredBlock,
    StructuredBreak,
    StructuredContinue,
    StructuredGoto,
    StructuredIf,
    StructuredSequence,
    StructuredStmt,
    StructuredSwitch,
    StructuredWhile,
    build_program_structured_facts,
)


_BINARY_OPS = {
    "INT_ADD": "+",
    "INT_SUB": "-",
    "INT_MUL": "*",
    "INT_DIV": "/",
    "INT_SDIV": "/",
    "INT_REM": "%",
    "INT_SREM": "%",
    "INT_AND": "&",
    "INT_OR": "|",
    "INT_XOR": "^",
    "INT_LEFT": "<<",
    "INT_RIGHT": ">>u",
    "INT_SRIGHT": ">>",
    "INT_EQUAL": "==",
    "INT_NOTEQUAL": "!=",
    "INT_SLESS": "<s",
    "INT_LESS": "<u",
}

_INVERTED_BINARY_OPS = {
    "==": "!=",
    "!=": "==",
    "<": ">=",
    ">=": "<",
    ">": "<=",
    "<=": ">",
    "<s": ">=s",
    "<=s": ">s",
    ">s": "<=s",
    ">=s": "<s",
    "<u": ">=u",
    "<=u": ">u",
    ">u": "<=u",
    ">=u": "<u",
}


@dataclass(frozen=True, slots=True)
class _DefSite:
    op: SSAOp
    instruction_address: int
    block_start: int


@dataclass(frozen=True, slots=True)
class _FieldAccessInfo:
    variable: RecoveredVariable
    field_offset: int
    field_name: str
    stride: int | None


@dataclass(frozen=True, slots=True)
class _MaterializedCallReturn:
    instruction_address: int
    register: int
    value: SSAName
    local: CLoweredVariable


@dataclass(frozen=True, slots=True)
class _MaterializedMergePhi:
    header: int
    merge_target: int
    output: SSAName
    then_value: SSAValue
    else_value: SSAValue
    local: CLoweredVariable


@dataclass(frozen=True, slots=True)
class _RenderedWrapperForwardPlan:
    local_names_to_remove: frozenset[str]
    temp_declaration: str
    statement_lines: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _GroupedCallPromotion:
    end_index: int
    declaration: str
    assignment_line: str
    removed_local_names: frozenset[str]
    replacements: tuple[tuple[str, str], ...]


def analyze_function_c_lowering(function: FunctionStructuredFacts) -> FunctionCLowered:
    """Lower one structured function into the stage-17 C-like IR surface."""

    return _FunctionLowerer(function).lower()


def analyze_program_c_lowering(program: ProgramStructuredFacts) -> ProgramCLowered:
    """Lower a whole program into the stage-17 C-like IR surface."""

    interproc_by_entry = {
        function.entry: function.interproc
        for function in program.ordered_functions()
    }
    functions = {
        function.entry: _FunctionLowerer(
            function,
            interproc_by_entry=interproc_by_entry,
        ).lower()
        for function in program.ordered_functions()
    }
    return ProgramCLowered(
        structured=program,
        functions=functions,
        pending_entries=program.pending_entries,
        invalidated_entries=program.invalidated_entries,
        scheduler_invalidations=program.scheduler_invalidations,
    )


def build_function_c_lowered(
    view: ProgramView,
    entry: int,
) -> FunctionCLowered:
    """Build stage-16 structure first, then derive stage-17 C-like IR."""

    program = build_program_c_lowered(view, entry)
    return program.functions[entry]


def build_program_c_lowered(
    view: ProgramView,
    root_entry: int,
) -> ProgramCLowered:
    """Build stage-16 structure first, then derive stage-17 C-like IR."""

    program = build_program_structured_facts(view, root_entry)
    return analyze_program_c_lowering(program)


# Stage 18 algorithm outline:
# 1. Scan the lowered program in discovery order.
# 2. Recover the helper declarations needed by the final rendered source:
#    aggregate helper structs and synthesized multi-register return structs.
# 3. Render each function deterministically from stage-17 declarations and
#    statements, preserving raw expressions and explicit fallback control.
# 4. Emit one full translation unit with leading scheduler comments, helper
#    declarations, forward declarations, and final function definitions.
# 5. Preserve upstream pending-entry and invalidation state unchanged.


def analyze_function_c_rendered(function: FunctionCLowered) -> FunctionCRendered:
    """Render one lowered function into the final stage-18 source surface."""

    builder = _RenderedSourceBuilder((function,))
    return builder.render_function(function, include_program_helpers=True)


def analyze_program_c_rendered(program: ProgramCLowered) -> ProgramCRendered:
    """Render a whole lowered program into the final stage-18 source surface."""

    builder = _RenderedSourceBuilder(program.ordered_functions())
    functions = {
        function.entry: builder.render_function(function, include_program_helpers=False)
        for function in program.ordered_functions()
    }
    prototypes = tuple(functions[entry].prototype + ";" for entry in program.ordered_function_entries())
    return ProgramCRendered(
        c_lowered=program,
        includes=builder.includes,
        type_declarations=builder.type_declarations,
        prototypes=prototypes,
        functions=functions,
        pending_entries=program.pending_entries,
        invalidated_entries=program.invalidated_entries,
        scheduler_invalidations=program.scheduler_invalidations,
    )


def build_function_c_rendered(
    view: ProgramView,
    entry: int,
) -> FunctionCRendered:
    """Build stage-17 lowering first, then render one function."""

    function = build_function_c_lowered(view, entry)
    return analyze_function_c_rendered(function)


def build_program_c_rendered(
    view: ProgramView,
    root_entry: int,
) -> ProgramCRendered:
    """Build stage-17 lowering first, then render final stage-18 output."""

    program = build_program_c_lowered(view, root_entry)
    return analyze_program_c_rendered(program)


class _RenderedSourceBuilder:
    def __init__(self, functions: tuple[FunctionCLowered, ...]) -> None:
        self.functions = functions
        self._functions_by_entry = {
            function.entry: function
            for function in functions
        }
        self._aggregate_declarations = self._collect_aggregate_declarations()
        self._return_type_names, self._return_type_declarations = (
            self._collect_return_type_declarations()
        )
        self.includes = self._collect_includes()
        self.type_declarations = (
            *self._aggregate_declarations,
            *self._return_type_declarations,
        )

    def render_function(
        self,
        function: FunctionCLowered,
        *,
        include_program_helpers: bool,
    ) -> FunctionCRendered:
        function_name = function.name or f"fn_0x{function.entry:x}"
        return_type = self._render_function_return_type(function)
        render_plan = self._plan_wrapper_forward_render(
            function,
            return_type=return_type,
        )
        parameters = (
            ", ".join(
                f"{self._render_type(parameter.ctype)} {parameter.name}"
                for parameter in function.parameters
            )
            or "void"
        )
        prototype = f"static {return_type} {function_name}({parameters})"
        local_lines = [
            f"{self._render_type(local.ctype)} {local.name};"
            for local in function.locals
            if render_plan is None or local.name not in render_plan.local_names_to_remove
        ]
        if render_plan is not None:
            local_lines.append(render_plan.temp_declaration)
        locals_ = tuple(local_lines)
        if render_plan is None:
            extra_local_lines, removed_names, statements = self._render_function_body_with_call_groups(
                function,
                return_type=return_type,
            )
            locals_ = tuple(
                [
                    line
                    for line in local_lines
                    if line.rsplit(" ", 1)[-1].removesuffix(";") not in removed_names
                ]
                + list(extra_local_lines)
            )
        else:
            statements = render_plan.statement_lines
        return FunctionCRendered(
            c_lowered=function,
            function_name=function_name,
            return_type=return_type,
            prototype=prototype,
            includes=self.includes if include_program_helpers else (),
            type_declarations=self.type_declarations if include_program_helpers else (),
            local_declarations=locals_,
            statement_lines=statements,
        )

    def _collect_aggregate_declarations(self) -> tuple[str, ...]:
        declarations: list[str] = []
        seen_names: set[str] = set()
        for function in self.functions:
            for variable in function.structured.interproc.ranges.variables.variables:
                layout = variable.aggregate_layout
                if layout is None:
                    continue
                name = f"agg_{_aggregate_size(layout)}"
                if name in seen_names:
                    continue
                field_lines = [
                    f"  {self._render_scalar_type(field.scalar_type)} field_{field.offset};"
                    for field in layout.fields
                ]
                block = "\n".join(
                    [
                        f"typedef struct {name} {{",
                        *field_lines,
                        f"}} {name};",
                    ]
                )
                declarations.append(block)
                seen_names.add(name)
        return tuple(declarations)

    def _collect_return_type_declarations(
        self,
    ) -> tuple[dict[tuple[tuple[int, str], ...], str], tuple[str, ...]]:
        names_by_shape: dict[tuple[tuple[int, str], ...], str] = {}
        name_to_shape: dict[str, tuple[tuple[int, str], ...]] = {}
        declarations: list[str] = []

        for function in self.functions:
            if len(function.returns) <= 1:
                continue

            shape = tuple(
                (carrier.register, self._render_type(carrier.ctype))
                for carrier in function.returns
            )
            if shape in names_by_shape:
                continue

            base_name = "ret_" + "_".join(f"x{register}" for register, _ in shape)
            name = base_name
            suffix = 2
            while name in name_to_shape and name_to_shape[name] != shape:
                name = f"{base_name}_{suffix}"
                suffix += 1

            field_lines = [
                f"  {ctype} x{register};"
                for register, ctype in shape
            ]
            declarations.append(
                "\n".join(
                    [
                        f"typedef struct {name} {{",
                        *field_lines,
                        f"}} {name};",
                    ]
                )
            )
            names_by_shape[shape] = name
            name_to_shape[name] = shape

        return names_by_shape, tuple(declarations)

    def _collect_includes(self) -> tuple[str, ...]:
        used_types: set[str] = set()
        for function in self.functions:
            used_types.update(self._render_type(parameter.ctype) for parameter in function.parameters)
            used_types.update(self._render_type(local.ctype) for local in function.locals)
            used_types.update(self._render_type(carrier.ctype) for carrier in function.returns)
            for variable in function.structured.interproc.ranges.variables.variables:
                layout = variable.aggregate_layout
                if layout is None:
                    continue
                used_types.update(
                    self._render_scalar_type(field.scalar_type) for field in layout.fields
                )

        includes = ["#include <stdint.h>"]
        if "bool" in used_types:
            includes.insert(0, "#include <stdbool.h>")
        return tuple(includes)

    def _render_function_return_type(self, function: FunctionCLowered) -> str:
        if not function.returns:
            return "void"
        if len(function.returns) == 1:
            return self._render_type(function.returns[0].ctype)

        shape = tuple(
            (carrier.register, self._render_type(carrier.ctype))
            for carrier in function.returns
        )
        return self._return_type_names[shape]

    def _render_stmt_sequence(
        self,
        sequence: CStmtSequence,
        *,
        return_type: str,
        indent: str,
    ) -> list[str]:
        lines: list[str] = []
        for item in sequence.items:
            lines.extend(self._render_stmt(item, return_type=return_type, indent=indent))
        return lines

    def _render_stmt(
        self,
        item: CStmt,
        *,
        return_type: str,
        indent: str,
    ) -> list[str]:
        if isinstance(item, (CAssignStmt, CExprStmt, CGotoStmt, CBreakStmt, CContinueStmt)):
            return [f"{indent}{item.to_pretty()}"]

        if isinstance(item, CReturnStmt):
            return [f"{indent}{self._render_return_stmt(item, return_type)}"]

        if isinstance(item, CWhileStmt):
            condition = _strip_wrapping_parens(item.condition.to_pretty())
            lines = [f"{indent}while ({condition}) {{"]
            lines.extend(
                self._render_stmt_sequence(
                    item.body,
                    return_type=return_type,
                    indent=indent + "  ",
                )
            )
            lines.append(f"{indent}}}")
            return lines
        if isinstance(item, CSwitchStmt):
            return self._render_switch_stmt(
                item,
                return_type=return_type,
                indent=indent,
            )

        assert isinstance(item, CIfStmt)
        return self._render_if_stmt(item, return_type=return_type, indent=indent)

    def _render_return_stmt(self, stmt: CReturnStmt, return_type: str) -> str:
        if not stmt.values:
            return "return;"
        if len(stmt.values) == 1:
            return f"return {stmt.values[0].value.to_pretty()};"
        bindings = ", ".join(
            f".x{binding.register} = {binding.value.to_pretty()}"
            for binding in stmt.values
        )
        return f"return ({return_type}){{{bindings}}};"

    def _render_if_stmt(
        self,
        item: CIfStmt,
        *,
        return_type: str,
        indent: str,
    ) -> list[str]:
        condition = _strip_wrapping_parens(item.condition.to_pretty())
        lines = [f"{indent}if ({condition}) {{"]
        lines.extend(
            self._render_stmt_sequence(
                item.then_body,
                return_type=return_type,
                indent=indent + "  ",
            )
        )
        nested_else_if = _single_nested_if(item.else_body)
        if nested_else_if is not None:
            nested_lines = self._render_if_stmt(
                nested_else_if,
                return_type=return_type,
                indent=indent,
            )
            lines.append(f"{indent}}} else {nested_lines[0].removeprefix(indent)}")
            lines.extend(nested_lines[1:])
            return lines
        if item.else_body.items:
            lines.append(f"{indent}}} else {{")
            lines.extend(
                self._render_stmt_sequence(
                    item.else_body,
                    return_type=return_type,
                    indent=indent + "  ",
                )
            )
        lines.append(f"{indent}}}")
        return lines

    def _render_switch_stmt(
        self,
        item: CSwitchStmt,
        *,
        return_type: str,
        indent: str,
    ) -> list[str]:
        selector = _strip_wrapping_parens(item.selector.to_pretty())
        lines = [f"{indent}switch ({selector}) {{"]
        for case in item.cases:
            lines.append(f"{indent}case {case.value}:")
            lines.extend(
                self._render_switch_case_sequence(
                    case.body,
                    return_type=return_type,
                    indent=indent + "  ",
                )
            )
        lines.append(f"{indent}default:")
        lines.extend(
            self._render_switch_case_sequence(
                item.default_body,
                return_type=return_type,
                indent=indent + "  ",
            )
        )
        lines.append(f"{indent}}}")
        return lines

    def _render_switch_case_sequence(
        self,
        sequence: CStmtSequence,
        *,
        return_type: str,
        indent: str,
    ) -> list[str]:
        lines: list[str] = []
        for stmt in sequence.items:
            if isinstance(stmt, CBreakStmt):
                lines.append(f"{indent}break;")
                continue
            lines.extend(self._render_stmt(stmt, return_type=return_type, indent=indent))
        return lines

    def _render_type(self, ctype: CLoweredType) -> str:
        spelling = ctype.spelling
        if spelling.startswith("word") and spelling.endswith("_t"):
            bits = spelling.removeprefix("word").removesuffix("_t")
            if bits.isdigit():
                return f"uint{bits}_t"
        return spelling

    def _render_scalar_type(self, scalar_type: ScalarType) -> str:
        return self._render_type(
            _scalar_type_to_c_lowered_type(scalar_type)
        )

    def _render_function_body_with_call_groups(
        self,
        function: FunctionCLowered,
        *,
        return_type: str,
    ) -> tuple[tuple[str, ...], frozenset[str], tuple[str, ...]]:
        extra_local_lines: list[str] = []
        removed_names: set[str] = set()
        temp_names: set[str] = set()
        statements = self._render_stmt_sequence_with_call_groups(
            function,
            function.body,
            return_type=return_type,
            indent="",
            replacements={},
            extra_local_lines=extra_local_lines,
            removed_names=removed_names,
            temp_names=temp_names,
        )
        return tuple(extra_local_lines), frozenset(removed_names), tuple(statements)

    def _render_stmt_sequence_with_call_groups(
        self,
        function: FunctionCLowered,
        sequence: CStmtSequence,
        *,
        return_type: str,
        indent: str,
        replacements: dict[str, str],
        extra_local_lines: list[str],
        removed_names: set[str],
        temp_names: set[str],
    ) -> list[str]:
        lines: list[str] = []
        current_replacements = dict(replacements)
        items = sequence.items
        index = 0
        while index < len(items):
            promotion = self._match_grouped_call_promotion(
                function,
                items,
                index,
                replacements=current_replacements,
                temp_names=temp_names,
            )
            if promotion is not None:
                extra_local_lines.append(promotion.declaration)
                removed_names.update(promotion.removed_local_names)
                current_replacements.update(dict(promotion.replacements))
                lines.append(f"{indent}{promotion.assignment_line}")
                index = promotion.end_index
                continue
            lines.extend(
                self._render_stmt_with_call_groups(
                    function,
                    items[index],
                    return_type=return_type,
                    indent=indent,
                    replacements=current_replacements,
                    extra_local_lines=extra_local_lines,
                    removed_names=removed_names,
                    temp_names=temp_names,
                )
            )
            index += 1
        return lines

    def _plan_wrapper_forward_render(
        self,
        function: FunctionCLowered,
        *,
        return_type: str,
    ) -> _RenderedWrapperForwardPlan | None:
        if len(function.returns) <= 1:
            return None

        items = function.body.items
        if len(items) < 2:
            return None

        return_stmt = items[-1]
        if not isinstance(return_stmt, CReturnStmt):
            return None

        call_index = len(items) - 2
        while call_index >= 0 and self._is_materialized_call_return_assignment(items[call_index]):
            call_index -= 1
        if call_index < 0:
            return None

        prefix_items = items[:call_index]
        call_stmt = items[call_index]
        call_expr: CCallExpr
        primary_local_name: str | None = None
        if isinstance(call_stmt, CExprStmt) and isinstance(call_stmt.expr, CCallExpr):
            call_expr = call_stmt.expr
        elif (
            isinstance(call_stmt, CAssignStmt)
            and isinstance(call_stmt.target, CNameExpr)
            and isinstance(call_stmt.value, CCallExpr)
        ):
            call_expr = call_stmt.value
            primary_local_name = call_stmt.target.name
        else:
            return None

        callee_target = call_expr.target
        if (
            callee_target.kind != CCallTargetKind.INTERNAL
            or callee_target.address is None
        ):
            return None
        callee = self._functions_by_entry.get(callee_target.address)
        if callee is None or len(callee.returns) != len(function.returns):
            return None

        caller_registers = tuple(carrier.register for carrier in function.returns)
        callee_registers = tuple(carrier.register for carrier in callee.returns)
        if caller_registers != callee_registers:
            return None
        if tuple(binding.register for binding in return_stmt.values) != caller_registers:
            return None

        locals_by_name = {
            local.name: local
            for local in function.locals
        }
        replacements: dict[str, str] = {}
        raw_local_names: set[str] = set()
        callsite_address: int | None = None

        if primary_local_name is not None:
            if primary_local_name not in locals_by_name or 10 not in caller_registers:
                return None
            replacements[primary_local_name] = self._render_projected_temp_field(
                temp_name="$temp",
                register=10,
                source_type=self._render_type(
                    next(
                        carrier.ctype
                        for carrier in callee.returns
                        if carrier.register == 10
                    )
                ),
                target_type=self._render_type(locals_by_name[primary_local_name].ctype),
            )
            raw_local_names.add(primary_local_name)

        for item in items[call_index + 1 : -1]:
            if not self._is_materialized_call_return_assignment(item):
                return None
            assert isinstance(item, CAssignStmt)
            assert isinstance(item.target, CNameExpr)
            parsed = self._parse_materialized_call_return_local_name(item.target.name)
            if parsed is None:
                return None
            item_callsite, register = parsed
            if item.target.name not in locals_by_name:
                return None
            if callsite_address is None:
                callsite_address = item_callsite
            elif callsite_address != item_callsite:
                return None
            if item.target.name in replacements:
                return None
            source_type = self._render_type(
                next(
                    carrier.ctype
                    for carrier in callee.returns
                    if carrier.register == register
                )
            )
            replacements[item.target.name] = self._render_projected_temp_field(
                temp_name="$temp",
                register=register,
                source_type=source_type,
                target_type=self._render_type(locals_by_name[item.target.name].ctype),
            )
            raw_local_names.add(item.target.name)

        if callsite_address is None:
            return None
        if not replacements:
            return None

        used_names = self._collect_expr_name_uses_in_return(return_stmt)
        if not raw_local_names.issubset(used_names):
            return None

        temp_name = self._fresh_wrapper_temp_name(function, callsite_address)
        callee_return_type = self._render_function_return_type(callee)
        projected_replacements = {
            name: text.replace("$temp", temp_name)
            for name, text in replacements.items()
        }
        call_line = f"{temp_name} = {call_expr.to_pretty()};"
        statement_lines = [
            line
            for item in prefix_items
            for line in self._render_stmt(item, return_type=return_type, indent="")
        ]
        statement_lines.append(call_line)
        statement_lines.append(
            self._render_return_stmt_with_replacements(
                return_stmt,
                return_type=return_type,
                replacements=projected_replacements,
            )
        )
        return _RenderedWrapperForwardPlan(
            local_names_to_remove=frozenset(raw_local_names),
            temp_declaration=f"{callee_return_type} {temp_name};",
            statement_lines=tuple(statement_lines),
        )

    def _fresh_wrapper_temp_name(
        self,
        function: FunctionCLowered,
        callsite_address: int,
        *,
        extra_names: set[str] | None = None,
    ) -> str:
        used_names = {
            parameter.name
            for parameter in function.parameters
        }
        used_names.update(local.name for local in function.locals)
        if extra_names is not None:
            used_names.update(extra_names)
        base_name = f"call_0x{callsite_address:x}_ret"
        name = base_name
        suffix = 2
        while name in used_names:
            name = f"{base_name}_{suffix}"
            suffix += 1
        return name

    def _parse_materialized_call_return_local_name(
        self,
        name: str,
    ) -> tuple[int, int] | None:
        if not name.startswith("ret_0x"):
            return None
        payload = name.removeprefix("ret_0x")
        if "_x" not in payload:
            return None
        callsite_text, rest = payload.split("_x", 1)
        if "_" not in rest:
            return None
        register_text, _size_text = rest.split("_", 1)
        try:
            return int(callsite_text, 16), int(register_text)
        except ValueError:
            return None

    def _match_grouped_call_promotion(
        self,
        function: FunctionCLowered,
        items: tuple[CStmt, ...],
        start_index: int,
        *,
        replacements: dict[str, str],
        temp_names: set[str],
    ) -> _GroupedCallPromotion | None:
        if start_index >= len(items):
            return None

        call_item = items[start_index]
        call_expr: CCallExpr
        primary_name: str | None = None
        if isinstance(call_item, CExprStmt) and isinstance(call_item.expr, CCallExpr):
            call_expr = call_item.expr
        elif (
            isinstance(call_item, CAssignStmt)
            and isinstance(call_item.target, CNameExpr)
            and isinstance(call_item.value, CCallExpr)
        ):
            call_expr = call_item.value
            primary_name = call_item.target.name
        else:
            return None

        locals_by_name = {local.name: local for local in function.locals}
        if primary_name is not None and primary_name not in locals_by_name:
            return None
        callee: FunctionCLowered | None = None
        if (
            call_expr.target.kind == CCallTargetKind.INTERNAL
            and call_expr.target.address is not None
        ):
            callee = self._functions_by_entry.get(call_expr.target.address)

        index = start_index + 1
        raw_groups: list[tuple[CAssignStmt, int, int]] = []
        callsite_address: int | None = None
        while index < len(items):
            item = items[index]
            if not self._is_materialized_call_return_assignment(item):
                break
            assert isinstance(item, CAssignStmt)
            assert isinstance(item.target, CNameExpr)
            parsed = self._parse_materialized_call_return_local_name(item.target.name)
            if parsed is None:
                break
            item_callsite, register = parsed
            if callsite_address is None:
                callsite_address = item_callsite
            elif item_callsite != callsite_address:
                break
            if item.target.name not in locals_by_name:
                return None
            raw_groups.append((item, item_callsite, register))
            index += 1

        if not raw_groups or callsite_address is None:
            return None

        later_sequence = CStmtSequence(items[index:])
        assigned_later = self._collect_assigned_names(later_sequence)

        promoted_fields: list[tuple[int, str]] = []
        projected_locals: list[tuple[str, int, str]] = []
        removed_local_names: set[str] = set()

        if primary_name is not None:
            if primary_name in assigned_later:
                return None
            primary_type = self._render_type(locals_by_name[primary_name].ctype)
            promoted_fields.append((10, primary_type))
            projected_locals.append(
                (
                    primary_name,
                    10,
                    primary_type,
                )
            )
            removed_local_names.add(primary_name)

        for item, _item_callsite, register in raw_groups:
            assert isinstance(item.target, CNameExpr)
            name = item.target.name
            if name in assigned_later:
                return None
            local_type = self._render_type(locals_by_name[name].ctype)
            promoted_fields.append((register, local_type))
            projected_locals.append(
                (
                    name,
                    register,
                    local_type,
                )
            )
            removed_local_names.add(name)

        if not promoted_fields:
            return None

        promoted_fields = sorted(dict(promoted_fields).items())
        temp_name = self._fresh_wrapper_temp_name(
            function,
            callsite_address,
            extra_names=temp_names,
        )
        temp_names.add(temp_name)
        scalar_single_return_type: str | None = None
        if (
            callee is not None
            and len(callee.returns) == 1
            and callee.returns[0].register == 10
            and len(promoted_fields) == 1
            and promoted_fields[0][0] == 10
        ):
            scalar_single_return_type = self._render_type(callee.returns[0].ctype)
        declaration = (
            f"{scalar_single_return_type} {temp_name};"
            if scalar_single_return_type is not None
            else self._render_grouped_call_temp_declaration(temp_name, promoted_fields)
        )
        call_text = self._render_expr_with_replacements(call_expr, replacements)
        assignment_line = f"{temp_name} = {call_text};"
        rendered_replacements = tuple(
            (
                name,
                temp_name
                if scalar_single_return_type is not None and register == 10
                else self._render_projected_temp_field(
                    temp_name=temp_name,
                    register=register,
                    source_type=local_type,
                    target_type=local_type,
                ),
            )
            for name, register, local_type in projected_locals
        )
        return _GroupedCallPromotion(
            end_index=index,
            declaration=declaration,
            assignment_line=assignment_line,
            removed_local_names=frozenset(removed_local_names),
            replacements=rendered_replacements,
        )

    def _is_materialized_call_return_assignment(self, item: CStmt) -> bool:
        if not isinstance(item, CAssignStmt):
            return False
        if not isinstance(item.target, CNameExpr) or not isinstance(item.value, CRawExpr):
            return False
        parsed = self._parse_materialized_call_return_local_name(item.target.name)
        if parsed is None:
            return False
        _callsite, register = parsed
        return item.value.text.startswith(f"x{register}_")

    def _render_projected_temp_field(
        self,
        *,
        temp_name: str,
        register: int,
        source_type: str,
        target_type: str,
    ) -> str:
        source = f"{temp_name}.x{register}"
        if source_type != target_type:
            return f"({target_type}){source}"
        return source

    def _render_grouped_call_temp_declaration(
        self,
        temp_name: str,
        fields: list[tuple[int, str]],
    ) -> str:
        field_text = " ".join(f"{ctype} x{register};" for register, ctype in fields)
        return f"struct {{ {field_text} }} {temp_name};"

    def _collect_expr_name_uses_in_return(
        self,
        stmt: CReturnStmt,
    ) -> set[str]:
        used: set[str] = set()
        for binding in stmt.values:
            used.update(self._collect_expr_name_uses(binding.value))
        return used

    def _collect_assigned_names(self, sequence: CStmtSequence) -> set[str]:
        assigned: set[str] = set()
        for item in sequence.items:
            assigned.update(self._collect_assigned_names_stmt(item))
        return assigned

    def _collect_assigned_names_stmt(self, item: CStmt) -> set[str]:
        if isinstance(item, CAssignStmt):
            if isinstance(item.target, CNameExpr):
                return {item.target.name}
            return set()
        if isinstance(item, CIfStmt):
            return self._collect_assigned_names(item.then_body) | self._collect_assigned_names(
                item.else_body
            )
        if isinstance(item, CSwitchStmt):
            assigned = self._collect_assigned_names(item.default_body)
            for case in item.cases:
                assigned |= self._collect_assigned_names(case.body)
            return assigned
        if isinstance(item, CWhileStmt):
            return self._collect_assigned_names(item.body)
        return set()

    def _collect_expr_name_uses(self, expr: CExpr) -> set[str]:
        if isinstance(expr, CNameExpr):
            return {expr.name}
        if isinstance(expr, (CRawExpr, CConstExpr, CGlobalExpr)):
            return set()
        if isinstance(expr, CFieldExpr):
            return set() if expr.index is None else self._collect_expr_name_uses(expr.index)
        if isinstance(expr, CUnaryExpr):
            return self._collect_expr_name_uses(expr.operand)
        if isinstance(expr, CBinaryExpr):
            return self._collect_expr_name_uses(expr.left) | self._collect_expr_name_uses(
                expr.right
            )
        assert isinstance(expr, CCallExpr)
        used: set[str] = set()
        for argument in expr.arguments:
            used.update(self._collect_expr_name_uses(argument))
        return used

    def _render_stmt_with_call_groups(
        self,
        function: FunctionCLowered,
        item: CStmt,
        *,
        return_type: str,
        indent: str,
        replacements: dict[str, str],
        extra_local_lines: list[str],
        removed_names: set[str],
        temp_names: set[str],
    ) -> list[str]:
        if isinstance(item, CAssignStmt):
            target = self._render_lvalue_with_replacements(item.target, replacements)
            value = self._render_expr_with_replacements(item.value, replacements)
            return [f"{indent}{target} = {value};"]
        if isinstance(item, CExprStmt):
            expr = self._render_expr_with_replacements(item.expr, replacements)
            return [f"{indent}{expr};"]
        if isinstance(item, CReturnStmt):
            return [
                f"{indent}{self._render_return_stmt_with_replacements(item, return_type=return_type, replacements=replacements)}"
            ]
        if isinstance(item, CWhileStmt):
            condition = _strip_wrapping_parens(
                self._render_expr_with_replacements(item.condition, replacements)
            )
            lines = [f"{indent}while ({condition}) {{"]
            lines.extend(
                self._render_stmt_sequence_with_call_groups(
                    function,
                    item.body,
                    return_type=return_type,
                    indent=indent + "  ",
                    replacements=dict(replacements),
                    extra_local_lines=extra_local_lines,
                    removed_names=removed_names,
                    temp_names=temp_names,
                )
            )
            lines.append(f"{indent}}}")
            return lines
        if isinstance(item, CSwitchStmt):
            return self._render_switch_stmt_with_call_groups(
                function,
                item,
                return_type=return_type,
                indent=indent,
                replacements=replacements,
                extra_local_lines=extra_local_lines,
                removed_names=removed_names,
                temp_names=temp_names,
            )
        if isinstance(item, CGotoStmt):
            return [f"{indent}goto L_{item.target:x};"]
        if isinstance(item, CBreakStmt):
            return [f"{indent}break;"]
        if isinstance(item, CContinueStmt):
            return [f"{indent}continue;"]

        assert isinstance(item, CIfStmt)
        return self._render_if_stmt_with_call_groups(
            function,
            item,
            return_type=return_type,
            indent=indent,
            replacements=replacements,
            extra_local_lines=extra_local_lines,
            removed_names=removed_names,
            temp_names=temp_names,
        )

    def _render_if_stmt_with_call_groups(
        self,
        function: FunctionCLowered,
        item: CIfStmt,
        *,
        return_type: str,
        indent: str,
        replacements: dict[str, str],
        extra_local_lines: list[str],
        removed_names: set[str],
        temp_names: set[str],
    ) -> list[str]:
        condition = _strip_wrapping_parens(
            self._render_expr_with_replacements(item.condition, replacements)
        )
        lines = [f"{indent}if ({condition}) {{"]
        lines.extend(
            self._render_stmt_sequence_with_call_groups(
                function,
                item.then_body,
                return_type=return_type,
                indent=indent + "  ",
                replacements=dict(replacements),
                extra_local_lines=extra_local_lines,
                removed_names=removed_names,
                temp_names=temp_names,
            )
        )
        nested_else_if = _single_nested_if(item.else_body)
        if nested_else_if is not None:
            nested_lines = self._render_if_stmt_with_call_groups(
                function,
                nested_else_if,
                return_type=return_type,
                indent=indent,
                replacements=dict(replacements),
                extra_local_lines=extra_local_lines,
                removed_names=removed_names,
                temp_names=temp_names,
            )
            lines.append(f"{indent}}} else {nested_lines[0].removeprefix(indent)}")
            lines.extend(nested_lines[1:])
            return lines
        if item.else_body.items:
            lines.append(f"{indent}}} else {{")
            lines.extend(
                self._render_stmt_sequence_with_call_groups(
                    function,
                    item.else_body,
                    return_type=return_type,
                    indent=indent + "  ",
                    replacements=dict(replacements),
                    extra_local_lines=extra_local_lines,
                    removed_names=removed_names,
                    temp_names=temp_names,
                )
            )
        lines.append(f"{indent}}}")
        return lines

    def _render_switch_stmt_with_call_groups(
        self,
        function: FunctionCLowered,
        item: CSwitchStmt,
        *,
        return_type: str,
        indent: str,
        replacements: dict[str, str],
        extra_local_lines: list[str],
        removed_names: set[str],
        temp_names: set[str],
    ) -> list[str]:
        selector = _strip_wrapping_parens(
            self._render_expr_with_replacements(item.selector, replacements)
        )
        lines = [f"{indent}switch ({selector}) {{"]
        for case in item.cases:
            lines.append(f"{indent}case {case.value}:")
            lines.extend(
                self._render_switch_case_sequence_with_call_groups(
                    function,
                    case.body,
                    return_type=return_type,
                    indent=indent + "  ",
                    replacements=dict(replacements),
                    extra_local_lines=extra_local_lines,
                    removed_names=removed_names,
                    temp_names=temp_names,
                )
            )
        lines.append(f"{indent}default:")
        lines.extend(
            self._render_switch_case_sequence_with_call_groups(
                function,
                item.default_body,
                return_type=return_type,
                indent=indent + "  ",
                replacements=dict(replacements),
                extra_local_lines=extra_local_lines,
                removed_names=removed_names,
                temp_names=temp_names,
            )
        )
        lines.append(f"{indent}}}")
        return lines

    def _render_switch_case_sequence_with_call_groups(
        self,
        function: FunctionCLowered,
        sequence: CStmtSequence,
        *,
        return_type: str,
        indent: str,
        replacements: dict[str, str],
        extra_local_lines: list[str],
        removed_names: set[str],
        temp_names: set[str],
    ) -> list[str]:
        lines: list[str] = []
        for stmt in sequence.items:
            if isinstance(stmt, CBreakStmt):
                lines.append(f"{indent}break;")
                continue
            lines.extend(
                self._render_stmt_with_call_groups(
                    function,
                    stmt,
                    return_type=return_type,
                    indent=indent,
                    replacements=dict(replacements),
                    extra_local_lines=extra_local_lines,
                    removed_names=removed_names,
                    temp_names=temp_names,
                )
            )
        return lines

    def _render_lvalue_with_replacements(
        self,
        target: CLValueExpr,
        replacements: dict[str, str],
    ) -> str:
        return render_c_lvalue(target, replacements=replacements)

    def _render_return_stmt_with_replacements(
        self,
        stmt: CReturnStmt,
        *,
        return_type: str,
        replacements: dict[str, str],
    ) -> str:
        if not stmt.values:
            return "return;"
        if len(stmt.values) == 1:
            return (
                "return "
                f"{self._render_expr_with_replacements(stmt.values[0].value, replacements)};"
            )
        bindings = ", ".join(
            (
                f".x{binding.register} = "
                f"{self._render_expr_with_replacements(binding.value, replacements)}"
            )
            for binding in stmt.values
        )
        return f"return ({return_type}){{{bindings}}};"

    def _render_expr_with_replacements(
        self,
        expr: CExpr,
        replacements: dict[str, str],
    ) -> str:
        return render_c_expr(expr, replacements=replacements)


class _FunctionLowerer:
    def __init__(
        self,
        function: FunctionStructuredFacts,
        *,
        interproc_by_entry: dict[int, FunctionInterprocFacts] | None = None,
    ) -> None:
        self.function = function
        self.interproc = function.interproc
        self.range_facts = self.interproc.ranges
        self.variable_facts = self.range_facts.variables
        self.aggregate_facts = self.variable_facts.aggregate_types
        self.scalar_facts = self.aggregate_facts.scalar_types
        self.memory_facts = self.scalar_facts.memory
        self.stack_facts = self.memory_facts.stack
        self.call_facts = self.stack_facts.calls
        self.ssa: SSAFunctionIR = self.call_facts.ssa
        self.prototype = self.interproc.prototype
        self.interproc_by_entry = interproc_by_entry or {}
        self._value_cache: dict[SSAValue, CExpr] = {}

    def lower(self) -> FunctionCLowered:
        return FunctionCLowered(
            structured=self.function,
            parameters=self._collect_parameters(),
            returns=self._collect_returns(),
            locals=self._collect_locals(),
            body=self._lower_sequence(self.function.body),
        )

    @cached_property
    def variables_by_name(self) -> dict[str, RecoveredVariable]:
        return {variable.name: variable for variable in self.variable_facts.variables}

    @cached_property
    def parameter_variables_by_register(self) -> dict[int, RecoveredVariable]:
        result: dict[int, RecoveredVariable] = {}
        prototype_registers = {
            carrier.register
            for carrier in self.prototype.parameters
            if isinstance(carrier, PrototypeRegister)
        }
        for variable in self.variable_facts.variables:
            if variable.kind != VariableKind.PARAMETER:
                continue
            register = _parameter_register(variable)
            if register is not None and register in prototype_registers:
                result[register] = variable
        return result

    @cached_property
    def parameter_variables_by_stack_offset(self) -> dict[int, RecoveredVariable]:
        result: dict[int, RecoveredVariable] = {}
        prototype_stack_offsets = {
            carrier.stack_offset
            for carrier in self.prototype.parameters
            if isinstance(carrier, PrototypeStackParameter)
        }
        for variable in self.variable_facts.variables:
            if variable.kind != VariableKind.LOCAL:
                continue
            if variable.binding.kind != VariableBindingKind.STACK_SLOT:
                continue
            assert variable.binding.stack_slot is not None
            stack_offset = variable.binding.stack_slot.frame_offset
            if stack_offset < 0 or stack_offset not in prototype_stack_offsets:
                continue
            result[stack_offset] = variable
        return result

    @cached_property
    def promoted_stack_parameter_names(self) -> frozenset[str]:
        names: set[str] = set()
        for carrier in self.prototype.parameters:
            if not isinstance(carrier, PrototypeStackParameter):
                continue
            variable = None
            if carrier.variable_name is not None:
                variable = self.variables_by_name.get(carrier.variable_name)
            if variable is None:
                variable = self.parameter_variables_by_stack_offset.get(carrier.stack_offset)
            if variable is not None:
                names.add(variable.name)
            elif carrier.variable_name is not None:
                names.add(carrier.variable_name)
        return frozenset(names)

    @cached_property
    def root_variables(self) -> dict[SSAValue, RecoveredVariable]:
        return {
            variable.root_value: variable
            for variable in self.variable_facts.variables
            if variable.root_value is not None
        }

    @cached_property
    def variables_by_partition(self) -> dict[MemoryPartition, RecoveredVariable]:
        by_partition: dict[MemoryPartition, RecoveredVariable] = {}
        for variable in self.variable_facts.variables:
            for partition in variable.partitions:
                by_partition.setdefault(partition, variable)
        return by_partition

    @cached_property
    def field_accesses(self) -> dict[MemoryPartition, _FieldAccessInfo]:
        accesses: dict[MemoryPartition, _FieldAccessInfo] = {}
        for variable in self.variable_facts.variables:
            layout = variable.aggregate_layout
            if layout is None:
                continue
            for field in layout.fields:
                field_name = f"field_{field.offset}"
                for partition in field.partitions:
                    accesses[partition] = _FieldAccessInfo(
                        variable=variable,
                        field_offset=field.offset,
                        field_name=field_name,
                        stride=_aggregate_size(layout),
                    )
        return accesses

    @cached_property
    def scalar_types_by_value(self) -> dict[SSAValue, ScalarType]:
        return {
            fact.value: fact.scalar_type
            for fact in self.scalar_facts.value_facts
        }

    @cached_property
    def direct_use_counts(self) -> dict[SSAValue, int]:
        counts: dict[SSAValue, int] = {}
        for block in self.ssa.ordered_blocks():
            for phi in block.phis:
                for item in phi.inputs:
                    counts[item.value] = counts.get(item.value, 0) + 1
            for instruction in block.instructions:
                for op in instruction.ops:
                    for value in op.inputs:
                        counts[value] = counts.get(value, 0) + 1
        for callsite in self.call_facts.callsites:
            for argument in callsite.argument_values:
                counts[argument.value] = counts.get(argument.value, 0) + 1
            for stack_argument in callsite.stack_argument_values:
                counts[stack_argument.value] = counts.get(stack_argument.value, 0) + 1
        for block in self.ssa.ordered_blocks():
            if block.terminator.value != "return":
                continue
            snapshot = self.block_end_snapshots.get(block.start, {})
            for carrier in self.prototype.returns:
                return_value: SSAValue | None = snapshot.get(carrier.register)
                if return_value is None:
                    continue
                counts[return_value] = counts.get(return_value, 0) + 1
        return counts

    @cached_property
    def materialized_call_returns(self) -> tuple[_MaterializedCallReturn, ...]:
        materialized: list[_MaterializedCallReturn] = []
        for callsite in self.call_facts.callsites:
            for returned in self._effective_call_returns(callsite):
                if not isinstance(returned.value, SSAName):
                    continue
                if self.direct_use_counts.get(returned.value, 0) == 0:
                    continue
                if returned.value in self.folded_call_return_values:
                    continue
                materialized.append(
                    _MaterializedCallReturn(
                        instruction_address=callsite.instruction_address,
                        register=returned.register,
                        value=returned.value,
                        local=CLoweredVariable(
                            name=(
                                f"ret_0x{callsite.instruction_address:x}_"
                                f"x{returned.register}_{returned.value.size}"
                            ),
                            kind=CLoweredVariableKind.LOCAL,
                            ctype=self._ctype_from_scalar_or_size(
                                self.scalar_types_by_value.get(returned.value),
                                returned.value.size,
                            ),
                        ),
                    )
                )
        return tuple(materialized)

    @cached_property
    def materialized_call_returns_by_value(self) -> dict[SSAValue, _MaterializedCallReturn]:
        return {
            item.value: item
            for item in self.materialized_call_returns
        }

    @cached_property
    def materialized_call_returns_by_instruction(
        self,
    ) -> dict[int, tuple[_MaterializedCallReturn, ...]]:
        grouped: dict[int, list[_MaterializedCallReturn]] = {}
        for item in self.materialized_call_returns:
            grouped.setdefault(item.instruction_address, []).append(item)
        return {
            address: tuple(sorted(items, key=lambda item: item.register))
            for address, items in grouped.items()
        }

    @cached_property
    def materialized_merge_phis(self) -> tuple[_MaterializedMergePhi, ...]:
        items: list[_MaterializedMergePhi] = []

        def visit(sequence: StructuredSequence) -> None:
            for stmt in sequence.items:
                if isinstance(stmt, StructuredIf):
                    items.extend(self._collect_if_merge_phis(stmt))
                    visit(stmt.then_body)
                    visit(stmt.else_body)
                elif isinstance(stmt, StructuredSwitch):
                    for case in stmt.cases:
                        visit(case.body)
                    visit(stmt.default_body)
                elif isinstance(stmt, StructuredWhile):
                    visit(stmt.body)

        visit(self.function.body)
        return tuple(items)

    @cached_property
    def materialized_merge_phis_by_output(self) -> dict[SSAValue, _MaterializedMergePhi]:
        return {
            item.output: item
            for item in self.materialized_merge_phis
        }

    @cached_property
    def materialized_merge_phis_by_header(self) -> dict[int, tuple[_MaterializedMergePhi, ...]]:
        grouped: dict[int, list[_MaterializedMergePhi]] = {}
        for item in self.materialized_merge_phis:
            grouped.setdefault(item.header, []).append(item)
        return {
            header: tuple(
                sorted(items, key=lambda item: (item.output.base, item.output.size))
            )
            for header, items in grouped.items()
        }

    @cached_property
    def folded_call_return_values(self) -> frozenset[SSAValue]:
        folded: set[SSAValue] = set()
        for block in self.ssa.ordered_blocks():
            instructions = block.instructions
            for index, instruction in enumerate(instructions):
                callsite = self.callsites_by_instruction.get(instruction.address)
                if callsite is None or index + 1 >= len(instructions):
                    continue
                primary_return = next(
                    (
                        value.value
                        for value in self._effective_call_returns(callsite)
                        if value.register == 10
                    ),
                    None,
                )
                if primary_return is None:
                    continue
                store = self._extract_supported_immediate_store(instructions[index + 1])
                if store is None:
                    continue
                _address_value, stored_value = store
                if stored_value == primary_return:
                    folded.add(primary_return)
        return frozenset(folded)

    @cached_property
    def callsites_by_instruction(self) -> dict[int, ModeledCallSite]:
        return {
            callsite.instruction_address: callsite
            for callsite in self.call_facts.callsites
        }

    def _effective_call_returns(
        self,
        callsite: ModeledCallSite,
    ) -> tuple:
        if callsite.external_signature is None:
            return callsite.return_values
        allowed = set(callsite.external_signature.return_registers)
        return tuple(
            returned
            for returned in callsite.return_values
            if returned.register in allowed
        )

    @cached_property
    def partition_by_access(self) -> dict[tuple[int, MemoryAccessKind], MemoryPartition]:
        result: dict[tuple[int, MemoryAccessKind], MemoryPartition] = {}
        for partition in self.memory_facts.partitions:
            for access in partition.accesses:
                result[(access.instruction_address, access.kind)] = partition
        return result

    @cached_property
    def def_sites(self) -> dict[SSAName, _DefSite]:
        sites: dict[SSAName, _DefSite] = {}
        for block in self.ssa.ordered_blocks():
            for instruction in block.instructions:
                for op in instruction.ops:
                    if op.output is None:
                        continue
                    sites[op.output] = _DefSite(
                        op=op,
                        instruction_address=instruction.address,
                        block_start=block.start,
                    )
        return sites

    @cached_property
    def phi_sites(self) -> dict[SSAName, SSAPhiNode]:
        return {
            phi.output: phi
            for block in self.ssa.ordered_blocks()
            for phi in block.phis
        }

    @cached_property
    def block_end_snapshots(self) -> dict[int, dict[int, SSAName]]:
        dominator_children: dict[int, tuple[int, ...]] = {
            start: tuple(
                sorted(
                    child
                    for child, idom in self.ssa.immediate_dominators.items()
                    if idom == start
                )
            )
            for start in self.ssa.immediate_dominators
        }
        initial_registers = {
            live_in.base: live_in
            for live_in in self.ssa.live_ins
            if live_in.kind == SSANameKind.REGISTER
        }
        snapshots: dict[int, dict[int, SSAName]] = {}

        def visit(start: int, incoming: dict[int, SSAName]) -> None:
            block = self.ssa.blocks[start]
            current = dict(incoming)

            for phi in block.phis:
                current[phi.output.base] = phi.output

            for instruction in block.instructions:
                for op in instruction.ops:
                    output = op.output
                    if output is None or output.kind != SSANameKind.REGISTER:
                        continue
                    current[output.base] = output

            snapshots[start] = dict(current)

            for child in dominator_children[start]:
                visit(child, current)

        visit(self.ssa.entry, initial_registers)
        return snapshots

    def _collect_parameters(self) -> tuple[CLoweredVariable, ...]:
        parameters: list[CLoweredVariable] = []
        for carrier in self.prototype.parameters:
            variable = None
            if carrier.variable_name is not None:
                variable = self.variables_by_name.get(carrier.variable_name)
            if variable is None and isinstance(carrier, PrototypeRegister):
                variable = self.parameter_variables_by_register.get(carrier.register)
            if variable is None and isinstance(carrier, PrototypeStackParameter):
                variable = self.parameter_variables_by_stack_offset.get(carrier.stack_offset)
            if variable is not None:
                name = variable.name
            elif carrier.variable_name is not None:
                name = carrier.variable_name
            elif isinstance(carrier, PrototypeRegister):
                name = f"arg_x{carrier.register}_{carrier.size}"
            else:
                name = f"arg_stack_{carrier.stack_offset}_{carrier.size}"
            parameters.append(
                CLoweredVariable(
                    name=name,
                    kind=CLoweredVariableKind.PARAMETER,
                    ctype=self._ctype_from_variable_or_scalar(
                        variable=variable,
                        scalar_type=carrier.scalar_type,
                        size=carrier.size,
                    ),
                    register=(
                        carrier.register
                        if isinstance(carrier, PrototypeRegister)
                        else None
                    ),
                    stack_offset=(
                        carrier.stack_offset
                        if isinstance(carrier, PrototypeStackParameter)
                        else None
                    ),
                )
            )
        return tuple(parameters)

    def _collect_returns(self) -> tuple[CLoweredReturn, ...]:
        return tuple(
            CLoweredReturn(
                register=carrier.register,
                ctype=self._ctype_from_scalar_or_size(carrier.scalar_type, carrier.size),
            )
            for carrier in self.prototype.returns
        )

    def _collect_locals(self) -> tuple[CLoweredVariable, ...]:
        locals_: list[CLoweredVariable] = []
        for variable in self.variable_facts.variables:
            if variable.kind != VariableKind.LOCAL:
                continue
            if variable.name in self.promoted_stack_parameter_names:
                continue
            locals_.append(
                CLoweredVariable(
                    name=variable.name,
                    kind=CLoweredVariableKind.LOCAL,
                    ctype=self._ctype_from_variable(variable),
                )
            )
        locals_.extend(item.local for item in self.materialized_call_returns)
        locals_.extend(item.local for item in self.materialized_merge_phis)
        return tuple(locals_)

    def _ctype_from_variable_or_scalar(
        self,
        *,
        variable: RecoveredVariable | None,
        scalar_type: ScalarType | None,
        size: int,
    ) -> CLoweredType:
        if variable is not None:
            if (
                variable.aggregate_layout is None
                and variable.scalar_type is None
                and scalar_type is not None
            ):
                return self._ctype_from_scalar_or_size(scalar_type, size)
            return self._ctype_from_variable(variable)
        return self._ctype_from_scalar_or_size(scalar_type, size)

    def _ctype_from_variable(self, variable: RecoveredVariable) -> CLoweredType:
        if variable.aggregate_layout is not None:
            aggregate_size = _aggregate_size(variable.aggregate_layout)
            return CLoweredType(f"agg_{aggregate_size}*", variable.size)
        return self._ctype_from_scalar_or_size(variable.scalar_type, variable.size)

    def _ctype_from_scalar_or_size(
        self,
        scalar_type: ScalarType | None,
        size: int,
    ) -> CLoweredType:
        if scalar_type is None:
            return CLoweredType(f"word{size * 8}_t", size)
        if scalar_type.kind == ScalarTypeKind.BOOL:
            return CLoweredType("bool", scalar_type.size)
        if scalar_type.kind == ScalarTypeKind.INT:
            return CLoweredType(f"int{scalar_type.size * 8}_t", scalar_type.size)
        if scalar_type.kind == ScalarTypeKind.POINTER:
            return CLoweredType("void*", scalar_type.size)
        return CLoweredType(f"word{scalar_type.size * 8}_t", scalar_type.size)

    def _lower_sequence(self, sequence: StructuredSequence) -> CStmtSequence:
        items: list[CStmt] = []
        for item in sequence.items:
            items.extend(self._lower_structured_stmt(item))
        return CStmtSequence(tuple(items))

    def _lower_structured_stmt(self, item: StructuredStmt) -> list[CStmt]:
        if isinstance(item, StructuredBlock):
            return self._lower_block(item.block_start)
        if isinstance(item, StructuredGoto):
            return [CGotoStmt(item.target)]
        if isinstance(item, StructuredBreak):
            return [CBreakStmt(item.target)]
        if isinstance(item, StructuredContinue):
            return [CContinueStmt(item.target)]
        if isinstance(item, StructuredIf):
            prefix = self._lower_block_side_effects(item.header)
            condition = self._lower_branch_condition(item.header, item.true_target)
            then_items = list(self._lower_sequence(item.then_body).items)
            then_items.extend(self._materialized_merge_phi_assignments(item, then_branch=True))
            else_items = list(self._lower_sequence(item.else_body).items)
            else_items.extend(self._materialized_merge_phi_assignments(item, then_branch=False))
            prefix.append(
                CIfStmt(
                    condition=condition,
                    then_body=CStmtSequence(tuple(then_items)),
                    else_body=CStmtSequence(tuple(else_items)),
                )
            )
            return prefix
        if isinstance(item, StructuredSwitch):
            prefix = self._lower_block_side_effects(item.header)
            prefix.append(
                CSwitchStmt(
                    selector=self._lower_switch_selector(item),
                    cases=tuple(
                        CSwitchCase(
                            value=case.value,
                            body=self._lower_switch_case_body(
                                case.body,
                                merge_target=item.merge_target,
                            ),
                        )
                        for case in item.cases
                    ),
                    default_body=self._lower_switch_case_body(
                        item.default_body,
                        merge_target=item.merge_target,
                    ),
                )
            )
            return prefix
        prefix = self._lower_block_side_effects(item.header)
        condition = self._lower_branch_condition(item.header, item.body_entry)
        prefix.append(
            CWhileStmt(
                condition=condition,
                body=self._lower_sequence(item.body),
            )
        )
        return prefix

    def _lower_block(self, block_start: int) -> list[CStmt]:
        items = self._lower_block_side_effects(block_start)
        block = self.ssa.blocks[block_start]
        if block.terminator.value == "return":
            items.append(self._lower_return_stmt(block_start))
        return items

    def _lower_block_side_effects(self, block_start: int) -> list[CStmt]:
        block = self.ssa.blocks[block_start]
        items: list[CStmt] = []
        consumed_instructions: set[int] = set()
        for index, instruction in enumerate(block.instructions):
            if instruction.address in consumed_instructions:
                continue
            for op in instruction.ops:
                opcode = _opcode_text(op)
                if opcode in {"CALL", "CALLIND"}:
                    folded = self._lower_folded_call_stmt(
                        instructions=block.instructions,
                        index=index,
                        indirect=opcode == "CALLIND",
                    )
                    if folded is not None:
                        folded_stmt, consumed_address = folded
                        items.append(folded_stmt)
                        consumed_instructions.add(consumed_address)
                    else:
                        items.append(self._lower_call_stmt(instruction.address, opcode == "CALLIND"))
                    items.extend(
                        self._materialized_call_return_assignments(instruction.address)
                    )
                    continue
                if opcode != "STORE" or len(op.inputs) < 2:
                    continue
                store_stmt = self._lower_store_stmt(
                    instruction_address=instruction.address,
                    address_value=op.inputs[0],
                    stored_value=op.inputs[-1],
                )
                if store_stmt is not None:
                    items.append(store_stmt)
        return items

    def _lower_call_stmt(self, instruction_address: int, indirect: bool) -> CExprStmt:
        return CExprStmt(self._lower_call_expr(instruction_address, indirect))

    def _materialized_call_return_assignments(
        self,
        instruction_address: int,
    ) -> list[CAssignStmt]:
        items: list[CAssignStmt] = []
        for item in self.materialized_call_returns_by_instruction.get(
            instruction_address,
            (),
        ):
            items.append(
                CAssignStmt(
                    target=CNameExpr(item.local.name),
                    value=CRawExpr(item.value.to_pretty()),
                )
            )
        return items

    def _lower_call_expr(self, instruction_address: int, indirect: bool) -> CCallExpr:
        callsite = self.callsites_by_instruction.get(instruction_address)
        if callsite is None:
            target = CCallTarget(
                kind=CCallTargetKind.UNRESOLVED,
                address=instruction_address,
                indirect=indirect,
            )
            return CCallExpr(target=target)

        target_kind = {
            CallGraphEdgeKind.INTERNAL: CCallTargetKind.INTERNAL,
            CallGraphEdgeKind.EXTERNAL: CCallTargetKind.EXTERNAL,
            CallGraphEdgeKind.UNRESOLVED: CCallTargetKind.UNRESOLVED,
        }[callsite.target_kind]
        target = CCallTarget(
            kind=target_kind,
            address=callsite.target_address,
            name=callsite.callee_name,
            indirect=callsite.is_indirect,
        )
        arguments = tuple(
            self._lower_value(argument)
            for argument in self._ordered_call_arguments(callsite)
        )
        return CCallExpr(target=target, arguments=arguments)

    def _ordered_call_arguments(self, callsite: ModeledCallSite) -> tuple[SSAValue, ...]:
        ordered: tuple[SSAValue, ...]
        if (
            callsite.target_kind == CallGraphEdgeKind.INTERNAL
            and callsite.target_address is not None
            and callsite.target_address in self.interproc_by_entry
        ):
            callee = self.interproc_by_entry[callsite.target_address]
            argument_by_register = {
                argument.register: argument.value
                for argument in callsite.argument_values
            }
            stack_argument_by_offset = {
                argument.stack_offset: argument.value
                for argument in callsite.stack_argument_values
            }
            ordered = tuple(
                (
                    argument_by_register[carrier.register]
                    if isinstance(carrier, PrototypeRegister)
                    else stack_argument_by_offset[carrier.stack_offset]
                )
                for carrier in callee.prototype.parameters
                if (
                    isinstance(carrier, PrototypeRegister)
                    and carrier.register in argument_by_register
                )
                or (
                    isinstance(carrier, PrototypeStackParameter)
                    and carrier.stack_offset in stack_argument_by_offset
                )
            )
            if ordered or (
                not callsite.argument_values and not callsite.stack_argument_values
            ):
                return self._prepend_indirect_target_argument(callsite, ordered)

        if callsite.external_signature is not None:
            argument_by_register = {
                argument.register: argument.value
                for argument in callsite.argument_values
            }
            stack_argument_by_offset = {
                argument.stack_offset: argument.value
                for argument in callsite.stack_argument_values
            }
            ordered = tuple(
                [
                    *(
                        argument_by_register[register]
                        for register in callsite.external_signature.parameter_registers
                        if register in argument_by_register
                    ),
                    *(
                        stack_argument_by_offset[offset]
                        for offset in callsite.external_signature.parameter_stack_offsets
                        if offset in stack_argument_by_offset
                    ),
                ]
            )
            if ordered or (
                not callsite.argument_values and not callsite.stack_argument_values
            ):
                return self._prepend_indirect_target_argument(callsite, ordered)

        ordered = tuple(
            [
                *(argument.value for argument in callsite.argument_values),
                *(argument.value for argument in callsite.stack_argument_values),
            ]
        )
        return self._prepend_indirect_target_argument(callsite, ordered)

    def _prepend_indirect_target_argument(
        self,
        callsite: ModeledCallSite,
        arguments: tuple[SSAValue, ...],
    ) -> tuple[SSAValue, ...]:
        if (
            callsite.is_indirect
            and callsite.target_address is None
            and callsite.indirect_target_value is not None
        ):
            return (callsite.indirect_target_value, *arguments)
        return arguments

    def _lower_folded_call_stmt(
        self,
        *,
        instructions: tuple,
        index: int,
        indirect: bool,
    ) -> tuple[CAssignStmt, int] | None:
        instruction = instructions[index]
        callsite = self.callsites_by_instruction.get(instruction.address)
        if callsite is None:
            return None

        primary_return = next(
            (
                value.value
                for value in self._effective_call_returns(callsite)
                if value.register == 10
            ),
            None,
        )
        if primary_return is None or index + 1 >= len(instructions):
            return None

        next_instruction = instructions[index + 1]
        store = self._extract_supported_immediate_store(next_instruction)
        if store is None:
            return None

        address_value, stored_value = store
        if stored_value != primary_return:
            return None

        target_info = self._resolve_store_target(
            instruction_address=next_instruction.address,
            address_value=address_value,
        )
        if target_info is None:
            return None

        target, _ = target_info
        if isinstance(target, CRawExpr):
            return None

        return (
            CAssignStmt(
                target=target,
                value=self._lower_call_expr(instruction.address, indirect),
            ),
            next_instruction.address,
        )

    def _lower_store_stmt(
        self,
        *,
        instruction_address: int,
        address_value: SSAValue,
        stored_value: SSAValue,
    ) -> CAssignStmt | None:
        target_info = self._resolve_store_target(
            instruction_address=instruction_address,
            address_value=address_value,
        )
        if target_info is None:
            return None
        target, partition = target_info

        source = self._lower_value(stored_value)
        if partition is not None:
            variable = self.variables_by_partition.get(partition)
            if variable is not None and variable.kind == VariableKind.PARAMETER:
                if isinstance(target, CNameExpr) and isinstance(source, CNameExpr):
                    if target.name == variable.name and source.name == variable.name:
                        return None
        return CAssignStmt(target=target, value=source)

    def _resolve_store_target(
        self,
        *,
        instruction_address: int,
        address_value: SSAValue,
    ) -> tuple[CLValueExpr, MemoryPartition | None] | None:
        partition = self.partition_by_access.get((instruction_address, MemoryAccessKind.STORE))
        if partition is None:
            return self._raw_memory_expr(address_value), None
        if (
            partition.kind == MemoryPartitionKind.STACK_SLOT
            and partition.stack_slot is not None
            and partition.stack_slot.role.value == "saved_register"
        ):
            return None
        return self._lower_memory_target(partition, address_value), partition

    def _extract_supported_immediate_store(
        self,
        instruction,
    ) -> tuple[SSAValue, SSAValue] | None:
        store_op: SSAOp | None = None
        for op in instruction.ops:
            opcode = _opcode_text(op)
            if opcode == "STORE" and len(op.inputs) >= 2:
                if store_op is not None:
                    return None
                store_op = op
                continue
            if opcode in {"CALL", "CALLIND", "LOAD", "BRANCH", "CBRANCH", "RETURN"}:
                return None
            if op.output is not None and (
                not isinstance(op.output, SSAName) or op.output.kind != SSANameKind.UNIQUE
            ):
                return None
        if store_op is None:
            return None
        return store_op.inputs[0], store_op.inputs[-1]

    def _lower_return_stmt(self, block_start: int) -> CReturnStmt:
        snapshot = self.block_end_snapshots.get(block_start, {})
        bindings: list[CReturnBinding] = []
        for carrier in self.prototype.returns:
            value = snapshot.get(carrier.register)
            if value is None:
                expression: CExpr = CRawExpr(f"x{carrier.register}_<?>")
            else:
                expression = self._lower_value(value)
            bindings.append(CReturnBinding(register=carrier.register, value=expression))
        return CReturnStmt(tuple(bindings))

    def _lower_branch_condition(self, block_start: int, desired_target: int) -> CExpr:
        block = self.ssa.blocks[block_start]
        branch_target: int | None = None
        condition_value: SSAValue | None = None
        for instruction in reversed(block.instructions):
            for op in reversed(instruction.ops):
                if _opcode_text(op) != "CBRANCH" or len(op.inputs) < 2:
                    continue
                branch_target = _branch_target(op.inputs[0])
                condition_value = op.inputs[-1]
                break
            if condition_value is not None:
                break
        if condition_value is None:
            return CRawExpr(f"branch_0x{block_start:x}")

        expression = self._lower_value(condition_value)
        if branch_target == desired_target:
            return expression
        return _invert_expr(expression)

    def _lower_switch_selector(self, item: StructuredSwitch) -> CExpr:
        selector_value = self._extract_switch_selector_value(item.header)
        if selector_value is None:
            return CRawExpr(f"switch_0x{item.header:x}")
        return self._lower_value(selector_value)

    def _extract_switch_selector_value(self, block_start: int) -> SSAValue | None:
        block = self.ssa.blocks[block_start]
        condition_value: SSAValue | None = None
        for instruction in reversed(block.instructions):
            for op in reversed(instruction.ops):
                if _opcode_text(op) != "CBRANCH" or len(op.inputs) < 2:
                    continue
                condition_value = op.inputs[-1]
                break
            if condition_value is not None:
                break
        if condition_value is None:
            return None

        compare_value = self._unwrap_passthrough_value(condition_value)
        if not isinstance(compare_value, SSAName):
            return None
        def_site = self.def_sites.get(compare_value)
        if def_site is None or _opcode_text(def_site.op) != "INT_EQUAL" or len(def_site.op.inputs) != 2:
            return None

        left, right = def_site.op.inputs
        left_const = self._signed_const_from_ssa_value(left)
        right_const = self._signed_const_from_ssa_value(right)
        if left_const is None and right_const is None:
            return None
        if left_const is not None and right_const is not None:
            return None
        return right if left_const is not None else left

    def _unwrap_passthrough_value(
        self,
        value: SSAValue,
        seen: frozenset[SSAValue] = frozenset(),
    ) -> SSAValue:
        if value in seen or not isinstance(value, SSAName):
            return value
        def_site = self.def_sites.get(value)
        if def_site is None:
            return value
        if _opcode_text(def_site.op) in {"COPY", "INT_ZEXT", "INT_SEXT"} and def_site.op.inputs:
            return self._unwrap_passthrough_value(def_site.op.inputs[0], seen | {value})
        return value

    def _signed_const_from_ssa_value(self, value: SSAValue) -> int | None:
        value = self._unwrap_passthrough_value(value)
        if not isinstance(value, Varnode) or value.space != PcodeSpace.CONST:
            return None
        bits = value.size * 8
        mask = (1 << bits) - 1
        masked = value.offset & mask
        sign_bit = 1 << (bits - 1)
        return masked - (1 << bits) if masked & sign_bit else masked

    def _lower_switch_case_body(
        self,
        body: StructuredSequence,
        *,
        merge_target: int | None,
    ) -> CStmtSequence:
        items = list(self._lower_sequence(body).items)
        sequence = CStmtSequence(tuple(items))
        if merge_target is not None and not self._sequence_terminates(sequence):
            items.append(CBreakStmt(merge_target))
        return CStmtSequence(tuple(items))

    def _sequence_terminates(self, sequence: CStmtSequence) -> bool:
        if not sequence.items:
            return False
        return self._stmt_terminates(sequence.items[-1])

    def _stmt_terminates(self, stmt: CStmt) -> bool:
        if isinstance(stmt, (CReturnStmt, CGotoStmt, CBreakStmt, CContinueStmt)):
            return True
        if isinstance(stmt, CIfStmt):
            return (
                bool(stmt.then_body.items)
                and bool(stmt.else_body.items)
                and self._sequence_terminates(stmt.then_body)
                and self._sequence_terminates(stmt.else_body)
            )
        if isinstance(stmt, CSwitchStmt):
            return (
                bool(stmt.cases)
                and all(self._sequence_terminates(case.body) for case in stmt.cases)
                and self._sequence_terminates(stmt.default_body)
            )
        return False

    def _lower_value(
        self,
        value: SSAValue,
        seen: frozenset[SSAValue] = frozenset(),
        *,
        rewrite_exact_stack_slot_address: bool = True,
    ) -> CExpr:
        if value in seen:
            return CRawExpr(value.to_pretty())

        result = self._value_cache.get(value)
        if result is None:
            result = self._lower_value_uncached(value, seen | {value})
            self._value_cache[value] = result
        if rewrite_exact_stack_slot_address:
            return self._rewrite_exact_stack_slot_address(result)
        return result

    def _lower_value_uncached(self, value: SSAValue, seen: frozenset[SSAValue]) -> CExpr:
        if isinstance(value, Varnode):
            if value.space == PcodeSpace.CONST:
                return CConstExpr(value.offset, value.size)
            return CRawExpr(value.to_pretty())

        materialized_merge_phi = self.materialized_merge_phis_by_output.get(value)
        if materialized_merge_phi is not None:
            return CNameExpr(materialized_merge_phi.local.name)

        materialized_return = self.materialized_call_returns_by_value.get(value)
        if materialized_return is not None:
            return CNameExpr(materialized_return.local.name)

        root_variable = self.root_variables.get(value)
        if root_variable is not None:
            return self._lower_variable_expr(root_variable)

        if value.kind == SSANameKind.REGISTER:
            parameter_variable = self.parameter_variables_by_register.get(value.base)
            if parameter_variable is not None and value.version == 0:
                return self._lower_variable_expr(parameter_variable)

        def_site = self.def_sites.get(value)
        if def_site is not None:
            expression = self._lower_def_site(def_site, seen)
            if expression is not None:
                return expression

        phi = self.phi_sites.get(value)
        if phi is not None:
            phi_exprs = [
                self._lower_value(
                    item.value,
                    seen,
                    rewrite_exact_stack_slot_address=False,
                )
                for item in phi.inputs
            ]
            if phi_exprs and len({expr.to_pretty() for expr in phi_exprs}) == 1:
                return phi_exprs[0]

        return CRawExpr(value.to_pretty())

    @cached_property
    def entry_stack_live_in(self) -> SSAName | None:
        for live_in in self.ssa.live_ins:
            if (
                live_in.kind == SSANameKind.REGISTER
                and live_in.base == 2
                and live_in.version == 0
            ):
                return live_in
        return None

    @cached_property
    def stack_slot_variables_by_frame_offset(self) -> dict[int, RecoveredVariable]:
        variables: dict[int, RecoveredVariable] = {}
        for variable in self.variable_facts.variables:
            if variable.binding.kind != VariableBindingKind.STACK_SLOT:
                continue
            assert variable.binding.stack_slot is not None
            variables.setdefault(variable.binding.stack_slot.frame_offset, variable)
        return variables

    def _rewrite_exact_stack_slot_address(self, expr: CExpr) -> CExpr:
        entry_stack = self.entry_stack_live_in
        if entry_stack is None:
            return expr

        constant, terms = _flatten_additive_expr(expr)
        if len(terms) != 1:
            return expr
        base = terms[0]
        if not isinstance(base, CRawExpr) or base.text != entry_stack.to_pretty():
            return expr

        variable = self.stack_slot_variables_by_frame_offset.get(constant)
        if variable is None:
            return expr
        return CUnaryExpr("&", CNameExpr(variable.name))

    def _lower_def_site(self, def_site: _DefSite, seen: frozenset[SSAValue]) -> CExpr | None:
        op = def_site.op
        opcode = _opcode_text(op)

        if opcode == "COPY" and op.inputs:
            return self._lower_value(op.inputs[0], seen, rewrite_exact_stack_slot_address=False)

        if opcode == "BOOL_NEGATE" and op.inputs:
            return CUnaryExpr(
                "!",
                self._lower_value(op.inputs[0], seen, rewrite_exact_stack_slot_address=False),
            )

        if opcode in _BINARY_OPS and len(op.inputs) == 2:
            left = self._lower_value(op.inputs[0], seen, rewrite_exact_stack_slot_address=False)
            right = self._lower_value(op.inputs[1], seen, rewrite_exact_stack_slot_address=False)
            return _make_binary_expr(_BINARY_OPS[opcode], left, right)

        if opcode in {"INT_SEXT", "INT_ZEXT"} and op.inputs:
            return self._lower_value(op.inputs[0], seen, rewrite_exact_stack_slot_address=False)

        if opcode == "LOAD" and op.inputs:
            partition = self.partition_by_access.get((def_site.instruction_address, MemoryAccessKind.LOAD))
            if partition is None:
                return self._raw_memory_expr(op.inputs[0], seen)
            return self._lower_memory_target(partition, op.inputs[0], seen)

        return None

    def _lower_memory_target(
        self,
        partition: MemoryPartition,
        address_value: SSAValue,
        seen: frozenset[SSAValue] = frozenset(),
    ) -> CLValueExpr:
        field_info = self.field_accesses.get(partition)
        if field_info is not None:
            lowered = self._lower_field_expr(field_info, address_value, seen)
            if lowered is not None:
                return lowered

        variable = self.variables_by_partition.get(partition)
        if variable is not None:
            return self._lower_variable_expr(variable)

        if partition.kind == MemoryPartitionKind.ABSOLUTE and partition.absolute_address is not None:
            return CGlobalExpr(partition.absolute_address, partition.size)

        return self._raw_memory_expr(address_value, seen)

    def _lower_variable_expr(self, variable: RecoveredVariable) -> CLValueExpr:
        if variable.kind == VariableKind.GLOBAL and variable.binding.kind == VariableBindingKind.ABSOLUTE:
            assert variable.binding.absolute_address is not None
            return CGlobalExpr(
                variable.binding.absolute_address,
                variable.size,
                name=variable.name,
            )
        return CNameExpr(variable.name)

    def _lower_field_expr(
        self,
        info: _FieldAccessInfo,
        address_value: SSAValue,
        seen: frozenset[SSAValue],
    ) -> CFieldExpr | None:
        address_expr = self._lower_value(
            address_value,
            seen,
            rewrite_exact_stack_slot_address=False,
        )
        match = _match_aggregate_address(address_expr, info.variable.name, info.stride)
        if match is None or match.field_offset != info.field_offset:
            return None
        return CFieldExpr(
            base_name=info.variable.name,
            field_offset=info.field_offset,
            field_name=info.field_name,
            index=match.index,
        )

    def _raw_memory_expr(
        self,
        address_value: SSAValue,
        seen: frozenset[SSAValue] = frozenset(),
    ) -> CRawExpr:
        address_expr = self._lower_value(
            address_value,
            seen,
            rewrite_exact_stack_slot_address=False,
        )
        return CRawExpr(f"*({address_expr.to_pretty()})")

    def _collect_if_merge_phis(self, item: StructuredIf) -> tuple[_MaterializedMergePhi, ...]:
        if item.merge_target is None:
            return ()
        merge_block = self.ssa.blocks.get(item.merge_target)
        if merge_block is None or merge_block.terminator.value != "return":
            return ()

        return_registers = {carrier.register for carrier in self.prototype.returns}
        then_predecessors = self._sequence_exit_predecessors(item.then_body, item.merge_target)
        else_predecessors = self._sequence_exit_predecessors(item.else_body, item.merge_target)
        if len(then_predecessors) != 1 or len(else_predecessors) != 1:
            return ()
        then_predecessor = then_predecessors[0]
        else_predecessor = else_predecessors[0]

        items: list[_MaterializedMergePhi] = []
        for phi in merge_block.phis:
            if phi.output.base not in return_registers:
                continue
            inputs_by_predecessor = {
                phi_input.predecessor: phi_input.value
                for phi_input in phi.inputs
            }
            then_value = inputs_by_predecessor.get(then_predecessor)
            else_value = inputs_by_predecessor.get(else_predecessor)
            if then_value is None or else_value is None:
                continue
            if (
                then_value not in self.materialized_call_returns_by_value
                or else_value not in self.materialized_call_returns_by_value
            ):
                continue
            items.append(
                _MaterializedMergePhi(
                    header=item.header,
                    merge_target=item.merge_target,
                    output=phi.output,
                    then_value=then_value,
                    else_value=else_value,
                    local=CLoweredVariable(
                        name=f"phi_0x{item.merge_target:x}_x{phi.output.base}_{phi.output.size}",
                        kind=CLoweredVariableKind.LOCAL,
                        ctype=self._ctype_from_scalar_or_size(
                            self.scalar_types_by_value.get(phi.output),
                            phi.output.size,
                        ),
                    ),
                )
            )
        return tuple(items)

    def _sequence_exit_predecessors(
        self,
        sequence: StructuredSequence,
        target: int,
    ) -> tuple[int, ...]:
        predecessors: set[int] = set()
        for stmt in sequence.items:
            predecessors.update(self._stmt_exit_predecessors(stmt, target))
        return tuple(sorted(predecessors))

    def _stmt_exit_predecessors(
        self,
        stmt: StructuredStmt,
        target: int,
    ) -> set[int]:
        if isinstance(stmt, StructuredBlock):
            block = self.ssa.blocks.get(stmt.block_start)
            if block is None:
                return set()
            return {
                stmt.block_start
                for edge in block.successors
                if edge.target == target
            }
        if isinstance(stmt, StructuredIf):
            predecessors = set()
            if stmt.true_target == target or stmt.false_target == target:
                predecessors.add(stmt.header)
            predecessors.update(self._sequence_exit_predecessors(stmt.then_body, target))
            predecessors.update(self._sequence_exit_predecessors(stmt.else_body, target))
            return predecessors
        if isinstance(stmt, StructuredSwitch):
            predecessors = set()
            if stmt.default_target == target:
                predecessors.add(stmt.header)
            for case in stmt.cases:
                if case.target == target:
                    predecessors.add(stmt.header)
                predecessors.update(self._sequence_exit_predecessors(case.body, target))
            predecessors.update(self._sequence_exit_predecessors(stmt.default_body, target))
            return predecessors
        if isinstance(stmt, StructuredWhile):
            predecessors = set()
            if stmt.exit_target == target:
                predecessors.add(stmt.header)
            predecessors.update(self._sequence_exit_predecessors(stmt.body, target))
            return predecessors
        return set()

    def _materialized_merge_phi_assignments(
        self,
        item: StructuredIf,
        *,
        then_branch: bool,
    ) -> list[CAssignStmt]:
        assignments: list[CAssignStmt] = []
        for materialized in self.materialized_merge_phis_by_header.get(item.header, ()):
            value = materialized.then_value if then_branch else materialized.else_value
            assignments.append(
                CAssignStmt(
                    target=CNameExpr(materialized.local.name),
                    value=self._lower_value(value),
                )
            )
        return assignments


@dataclass(frozen=True, slots=True)
class _AggregateAddressMatch:
    field_offset: int
    index: CExpr | None = None


def _match_aggregate_address(
    expr: CExpr,
    base_name: str,
    stride: int | None,
) -> _AggregateAddressMatch | None:
    constant, terms = _flatten_additive_expr(expr)
    has_base = False
    index: CExpr | None = None

    for term in terms:
        if isinstance(term, CNameExpr) and term.name == base_name:
            has_base = True
            continue
        candidate = _match_scaled_index(term, stride)
        if candidate is None:
            return None
        if index is not None:
            return None
        index = candidate

    if not has_base:
        return None
    return _AggregateAddressMatch(field_offset=constant, index=index)


def _single_nested_if(sequence: CStmtSequence) -> CIfStmt | None:
    if len(sequence.items) != 1:
        return None
    item = sequence.items[0]
    if not isinstance(item, CIfStmt):
        return None
    return item


def _flatten_additive_expr(expr: CExpr) -> tuple[int, list[CExpr]]:
    if isinstance(expr, CConstExpr):
        constant = _signed_const_from_const_expr(expr)
        return constant if constant is not None else 0, []
    if isinstance(expr, CBinaryExpr):
        if expr.op == "+":
            left_constant, left_terms = _flatten_additive_expr(expr.left)
            added_constant, right_terms = _flatten_additive_expr(expr.right)
            return left_constant + added_constant, [*left_terms, *right_terms]
        if expr.op == "-":
            left_constant, left_terms = _flatten_additive_expr(expr.left)
            subtracted_constant = _signed_const_from_expr(expr.right)
            if subtracted_constant is not None:
                return left_constant - subtracted_constant, left_terms
    return 0, [expr]


def _match_scaled_index(expr: CExpr, stride: int | None) -> CExpr | None:
    if stride is None:
        return None
    if stride == 1:
        return expr
    if not isinstance(expr, CBinaryExpr) or expr.op != "<<":
        return None
    shift_amount = _signed_const_from_expr(expr.right)
    if shift_amount is None or shift_amount < 0:
        return None
    if 1 << shift_amount != stride:
        return None
    return expr.left


def _invert_expr(expr: CExpr) -> CExpr:
    if isinstance(expr, CUnaryExpr) and expr.op == "!":
        return expr.operand
    if isinstance(expr, CBinaryExpr):
        inverted = _INVERTED_BINARY_OPS.get(expr.op)
        if inverted is not None:
            return CBinaryExpr(inverted, expr.left, expr.right)
    return CUnaryExpr("!", expr)


def _make_binary_expr(op: str, left: CExpr, right: CExpr) -> CExpr:
    if isinstance(left, CConstExpr) and isinstance(right, CConstExpr):
        folded = _fold_binary_const_expr(op, left, right)
        if folded is not None:
            return folded
    return CBinaryExpr(op, left, right)


def _fold_binary_const_expr(op: str, left: CConstExpr, right: CConstExpr) -> CConstExpr | None:
    left_value = _signed_const_from_const_expr(left)
    right_value = _signed_const_from_const_expr(right)
    if left_value is None or right_value is None:
        return None

    size = max(left.size, right.size)
    bits = size * 8
    mask = (1 << bits) - 1

    if op == "+":
        return CConstExpr((left_value + right_value) & mask, size)
    if op == "-":
        return CConstExpr((left_value - right_value) & mask, size)
    if op == "<<":
        if right_value < 0:
            return None
        return CConstExpr((left_value << right_value) & mask, size)
    if op == ">>":
        if right_value < 0:
            return None
        return CConstExpr((left_value >> right_value) & mask, size)
    if op == ">>u":
        if right_value < 0:
            return None
        return CConstExpr(((left_value & mask) >> right_value) & mask, size)
    if op == "&":
        return CConstExpr((left_value & right_value) & mask, size)
    if op == "|":
        return CConstExpr((left_value | right_value) & mask, size)
    if op == "^":
        return CConstExpr((left_value ^ right_value) & mask, size)
    if op == "==":
        return CConstExpr(1 if left_value == right_value else 0, 1)
    if op == "!=":
        return CConstExpr(1 if left_value != right_value else 0, 1)
    if op in {"<", "<s"}:
        return CConstExpr(1 if left_value < right_value else 0, 1)
    if op in {">=", ">=s"}:
        return CConstExpr(1 if left_value >= right_value else 0, 1)
    if op in {"<=", "<=s"}:
        return CConstExpr(1 if left_value <= right_value else 0, 1)
    if op in {">", ">s"}:
        return CConstExpr(1 if left_value > right_value else 0, 1)
    if op == "<u":
        return CConstExpr(1 if (left_value & mask) < (right_value & mask) else 0, 1)
    if op == ">=u":
        return CConstExpr(1 if (left_value & mask) >= (right_value & mask) else 0, 1)
    return None


def _scalar_type_to_c_lowered_type(scalar_type: ScalarType) -> CLoweredType:
    if scalar_type.kind == ScalarTypeKind.BOOL:
        return CLoweredType("bool", scalar_type.size)
    if scalar_type.kind == ScalarTypeKind.INT:
        return CLoweredType(f"int{scalar_type.size * 8}_t", scalar_type.size)
    if scalar_type.kind == ScalarTypeKind.POINTER:
        return CLoweredType("void*", scalar_type.size)
    return CLoweredType(f"word{scalar_type.size * 8}_t", scalar_type.size)


def _strip_wrapping_parens(text: str) -> str:
    while text.startswith("(") and text.endswith(")") and _is_outer_wrapped(text):
        text = text[1:-1]
    return text


def _is_outer_wrapped(text: str) -> bool:
    depth = 0
    for index, char in enumerate(text):
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and index != len(text) - 1:
                return False
    return depth == 0 and len(text) >= 2


def _aggregate_size(layout: AggregateLayout) -> int:
    if layout.root.stride is not None:
        return layout.root.stride
    return max(field.offset + field.size for field in layout.fields)


def _parameter_register(variable: RecoveredVariable) -> int | None:
    if variable.kind != VariableKind.PARAMETER:
        return None
    if variable.binding.kind == VariableBindingKind.STACK_SLOT:
        assert variable.binding.stack_slot is not None
        return variable.binding.stack_slot.argument_register
    if variable.root_value is not None and isinstance(variable.root_value, SSAName):
        return variable.root_value.base
    if variable.binding.kind == VariableBindingKind.ROOT_VALUE and isinstance(variable.binding.root_value, SSAName):
        assert variable.binding.root_value is not None
        return variable.binding.root_value.base
    return None


def _branch_target(value: SSAValue) -> int | None:
    if isinstance(value, Varnode) and value.space == PcodeSpace.CONST:
        return value.offset
    return None


def _signed_const_from_expr(expr: CExpr) -> int | None:
    if isinstance(expr, CConstExpr):
        return _signed_const_from_const_expr(expr)
    return None


def _signed_const_from_const_expr(expr: CConstExpr) -> int | None:
    bits = expr.size * 8
    mask = (1 << bits) - 1
    masked = expr.value & mask
    sign_bit = 1 << (bits - 1)
    return masked - (1 << bits) if masked & sign_bit else masked


def _opcode_text(op: SSAOp) -> str:
    return op.opcode_text
