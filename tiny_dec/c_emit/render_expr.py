"""Private expression-rendering helpers for stage-17 and stage-18 C emission."""

from __future__ import annotations

from collections.abc import Mapping

from tiny_dec.c_emit.models import (
    CBinaryExpr,
    CCallExpr,
    CConstExpr,
    CExpr,
    CFieldExpr,
    CGlobalExpr,
    CLValueExpr,
    CNameExpr,
    CRawExpr,
    CUnaryExpr,
)


_PRIMARY_PRECEDENCE = 100
_UNARY_PRECEDENCE = 90
_BINARY_PRECEDENCE = {
    "|": 10,
    "^": 20,
    "&": 30,
    "==": 40,
    "!=": 40,
    "<": 50,
    "<=": 50,
    ">": 50,
    ">=": 50,
    "<s": 50,
    "<=s": 50,
    ">s": 50,
    ">=s": 50,
    "<u": 50,
    "<=u": 50,
    ">u": 50,
    ">=u": 50,
    "<<": 60,
    ">>": 60,
    ">>u": 60,
    "+": 70,
    "-": 70,
    "*": 80,
    "/": 80,
    "%": 80,
}
_INVERTED_BINARY_OPS = {
    "==": "!=",
    "!=": "==",
    "<": ">=",
    "<=": ">",
    ">": "<=",
    ">=": "<",
    "<s": ">=s",
    "<=s": ">s",
    ">s": "<=s",
    ">=s": "<s",
    "<u": ">=u",
    "<=u": ">u",
    ">u": "<=u",
    ">=u": "<u",
}


def render_c_expr(
    expr: CExpr,
    *,
    replacements: Mapping[str, str] | None = None,
) -> str:
    return _render_expr(expr, replacements or {}, parent_precedence=-1, side="top")


def render_c_lvalue(
    target: CLValueExpr,
    *,
    replacements: Mapping[str, str] | None = None,
) -> str:
    replacement_map = replacements or {}
    if isinstance(target, CNameExpr):
        return replacement_map.get(target.name, target.name)
    if isinstance(target, CFieldExpr):
        if target.index is None:
            return f"{target.base_name}->{target.field_name}"
        index = render_c_expr(target.index, replacements=replacement_map)
        return f"{target.base_name}[{index}].{target.field_name}"
    if isinstance(target, CGlobalExpr):
        return target.to_pretty()
    return target.to_pretty()


def _render_expr(
    expr: CExpr,
    replacements: Mapping[str, str],
    *,
    parent_precedence: int,
    side: str,
) -> str:
    if isinstance(expr, CNameExpr):
        return _maybe_parenthesize(
            replacements.get(expr.name, expr.name),
            _PRIMARY_PRECEDENCE,
            parent_precedence=parent_precedence,
            side=side,
            binary_like=False,
        )
    if isinstance(expr, CFieldExpr):
        if expr.index is None:
            text = f"{expr.base_name}->{expr.field_name}"
        else:
            index = _render_expr(
                expr.index,
                replacements,
                parent_precedence=-1,
                side="top",
            )
            text = f"{expr.base_name}[{index}].{expr.field_name}"
        return _maybe_parenthesize(
            text,
            _PRIMARY_PRECEDENCE,
            parent_precedence=parent_precedence,
            side=side,
            binary_like=False,
        )
    if isinstance(expr, CGlobalExpr):
        return _maybe_parenthesize(
            expr.to_pretty(),
            _PRIMARY_PRECEDENCE,
            parent_precedence=parent_precedence,
            side=side,
            binary_like=False,
        )
    if isinstance(expr, CRawExpr):
        return _maybe_parenthesize(
            expr.to_pretty(),
            _PRIMARY_PRECEDENCE,
            parent_precedence=parent_precedence,
            side=side,
            binary_like=False,
        )
    if isinstance(expr, CConstExpr):
        return _maybe_parenthesize(
            expr.to_pretty(),
            _PRIMARY_PRECEDENCE,
            parent_precedence=parent_precedence,
            side=side,
            binary_like=False,
        )
    if isinstance(expr, CCallExpr):
        arguments = ", ".join(
            _render_expr(argument, replacements, parent_precedence=-1, side="top")
            for argument in expr.arguments
        )
        text = f"{expr.target.to_pretty()}({arguments})"
        return _maybe_parenthesize(
            text,
            _PRIMARY_PRECEDENCE,
            parent_precedence=parent_precedence,
            side=side,
            binary_like=False,
        )
    if isinstance(expr, CUnaryExpr):
        normalized = _normalize_inverted_condition(expr)
        if normalized is not None:
            op, left, right = normalized
            return _render_binary(
                op,
                left,
                right,
                replacements,
                parent_precedence=parent_precedence,
                side=side,
            )
        operand = _render_expr(
            expr.operand,
            replacements,
            parent_precedence=_UNARY_PRECEDENCE,
            side="right",
        )
        return _maybe_parenthesize(
            f"{expr.op}{operand}",
            _UNARY_PRECEDENCE,
            parent_precedence=parent_precedence,
            side=side,
            binary_like=False,
        )
    assert isinstance(expr, CBinaryExpr)
    op, left, right = _normalize_binary(expr)
    return _render_binary(
        op,
        left,
        right,
        replacements,
        parent_precedence=parent_precedence,
        side=side,
    )


def _render_binary(
    op: str,
    left: CExpr,
    right: CExpr,
    replacements: Mapping[str, str],
    *,
    parent_precedence: int,
    side: str,
) -> str:
    precedence = _BINARY_PRECEDENCE.get(op, 0)
    left_text = _render_expr(
        left,
        replacements,
        parent_precedence=precedence,
        side="left",
    )
    right_text = _render_expr(
        right,
        replacements,
        parent_precedence=precedence,
        side="right",
    )
    return _maybe_parenthesize(
        f"{left_text} {op} {right_text}",
        precedence,
        parent_precedence=parent_precedence,
        side=side,
        binary_like=True,
    )


def _maybe_parenthesize(
    text: str,
    precedence: int,
    *,
    parent_precedence: int,
    side: str,
    binary_like: bool,
) -> str:
    if parent_precedence < 0:
        return text
    if precedence < parent_precedence:
        return f"({text})"
    if side == "right" and binary_like and precedence == parent_precedence:
        return f"({text})"
    return text


def _normalize_inverted_condition(expr: CUnaryExpr) -> tuple[str, CExpr, CExpr] | None:
    if expr.op != "!" or not isinstance(expr.operand, CBinaryExpr):
        return None
    op, left, right = _normalize_binary(expr.operand)
    inverted = _INVERTED_BINARY_OPS.get(op)
    if inverted is None:
        return None
    return inverted, left, right


def _normalize_binary(expr: CBinaryExpr) -> tuple[str, CExpr, CExpr]:
    op = expr.op
    right_const = expr.right if isinstance(expr.right, CConstExpr) else None
    signed_right = _signed_const_value(right_const) if right_const is not None else None
    if right_const is not None and signed_right is not None and signed_right < 0:
        if op == "+":
            return "-", expr.left, CConstExpr(-signed_right, right_const.size)
        if op == "-":
            return "+", expr.left, CConstExpr(-signed_right, right_const.size)
    return op, expr.left, expr.right


def _signed_const_value(expr: CConstExpr) -> int:
    bits = expr.size * 8
    mask = (1 << bits) - 1
    masked = expr.value & mask
    sign_bit = 1 << (bits - 1)
    return masked - (1 << bits) if masked & sign_bit else masked
