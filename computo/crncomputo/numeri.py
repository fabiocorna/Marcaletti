"""Numeri, arrotondamenti e formule delle righe di misura.

Gli importi si calcolano con ``Decimal`` (niente errori di virgola mobile). Le misure
accettano espressioni come «3,20+0,15», «2*(4,5+3)» o «12,5/2»: la virgola è il
separatore decimale, come si scrive in Italia.
"""
from __future__ import annotations

import ast
import operator
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

ZERO = Decimal("0")
CENT = Decimal("0.01")

_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.Pow: operator.pow,
}


class FormulaError(ValueError):
    pass


def _normalize(text: str) -> str:
    s = text.strip().replace(" ", "").replace("×", "*").replace("x", "*").replace("X", "*")
    s = s.replace("^", "**").replace("[", "(").replace("]", ")").replace("{", "(").replace("}", ")")
    # "1.234,56" → "1234.56"; "3,20" → "3.20"
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return s


def _eval(node) -> Decimal:
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return Decimal(str(node.value))
    if isinstance(node, ast.BinOp) and type(node.op) in _OPS:
        left, right = _eval(node.left), _eval(node.right)
        if isinstance(node.op, ast.Div) and right == 0:
            raise FormulaError("divisione per zero")
        if isinstance(node.op, ast.Pow):
            if right != right.to_integral_value() or abs(right) > 6:
                raise FormulaError("potenza non ammessa (solo esponenti interi fino a 6)")
            return left ** int(right)
        return _OPS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        v = _eval(node.operand)
        return -v if isinstance(node.op, ast.USub) else v
    raise FormulaError("espressione non valida")


def evaluate(text: str | None) -> Decimal | None:
    """Valore di un campo di misura; ``None`` se il campo è vuoto."""
    if text is None:
        return None
    s = _normalize(str(text))
    if not s:
        return None
    if len(s) > 200:
        raise FormulaError("espressione troppo lunga")
    try:
        tree = ast.parse(s, mode="eval")
    except SyntaxError as exc:
        raise FormulaError(f"espressione non valida: «{text}»") from exc
    try:
        return _eval(tree)
    except (InvalidOperation, OverflowError) as exc:
        raise FormulaError(f"espressione non valida: «{text}»") from exc


def to_decimal(value) -> Decimal:
    """Numero da testo («1.234,56», «12.5»), intero o Decimal."""
    if isinstance(value, Decimal):
        return value
    if isinstance(value, bool):
        raise ValueError("valore non numerico")
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    s = str(value or "").strip().replace("€", "").replace(" ", "").replace(" ", "")
    if not s:
        return ZERO
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return Decimal(s)
    except InvalidOperation as exc:
        raise ValueError(f"numero non valido: «{value}»") from exc


def round2(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


def fmt(value: Decimal | None, decimals: int = 2, empty_zero: bool = False) -> str:
    """Formato italiano: 1.234,56."""
    if value is None or (empty_zero and value == 0):
        return ""
    q = Decimal(1).scaleb(-decimals)
    s = f"{value.quantize(q, rounding=ROUND_HALF_UP):,.{decimals}f}"
    return s.replace(",", "\u0001").replace(".", ",").replace("\u0001", ".")


def fmt_euro(value: Decimal) -> str:
    return "€ " + fmt(value)


def fmt_pct(value: Decimal) -> str:
    s = fmt(value, 2)
    if "," in s:
        s = s.rstrip("0").rstrip(",")
    return s + "%"
