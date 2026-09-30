"""Formato de resultados: texto plano, LaTeX y aproximación numérica."""

from __future__ import annotations

import math
import re
from typing import Any

import sympy as sp
from sympy.core.relational import Relational
from sympy.logic.boolalg import And, BooleanFunction, Equivalent, Implies, Not, Or, Xor
from sympy.sets.contains import Contains

from .errors import CalculationError

_RELATION_SYMBOLS = {
    "Eq": "=",
    "Ne": "≠",
    "Lt": "<",
    "Le": "≤",
    "Gt": ">",
    "Ge": "≥",
    "StrictLessThan": "<",
    "StrictGreaterThan": ">",
    "LessThan": "≤",
    "GreaterThan": "≥",
    "Equality": "=",
}

_PRECISION = 14
_MAX_OPERATIONS_TO_SIMPLIFY = 400
_MAX_CHARACTERS = 4_000


# ---------------------------------------------------------------------------
# Texto plano
# ---------------------------------------------------------------------------


_ACCENT_CHARS = {"vec": "\u20d7", "hat": "\u0302", "tilde": "\u0303",
                 "bar": "\u0304", "overline": "\u0305", "dot": "\u0307",
                 "ddot": "\u0308"}
_ACCENT_RE = re.compile(r"\\(vec|hat|widetilde|tilde|overline|bar|ddot|dot)\s*\{?\s*([A-Za-z0-9]+)\s*\}?")


def _pretty(name: str) -> str:
    """``\vec{v}`` -> ``v⃗`` para la columna de texto plano."""
    if "\\" not in name:
        return name

    def replace(match: re.Match[str]) -> str:
        accent = _ACCENT_CHARS.get(match.group(1), "")
        return f"{match.group(2)}{accent}"

    return _ACCENT_RE.sub(replace, name)


def to_plain(expr: Any) -> str:
    """Representación en texto plano legible (la columna «exacta»)."""
    if expr is sp.true:
        return "verdadero"
    if expr is sp.false:
        return "falso"
    if isinstance(expr, Contains):
        return f"{to_plain(expr.expr)} ∈ {to_plain(expr.set)}"
    if isinstance(expr, Relational):
        symbol = _RELATION_SYMBOLS.get(type(expr).__name__, str(expr.rel_op))
        return f"{to_plain(expr.lhs)} {symbol} {to_plain(expr.rhs)}"
    if isinstance(expr, Not):
        return f"no {to_plain(expr.args[0])}"
    if isinstance(expr, (And, Or, Xor)):
        joiner = " ∨ " if isinstance(expr, (Or, Xor)) else " ∧ "
        return joiner.join(to_plain(argument) for argument in expr.args)
    if isinstance(expr, Implies):
        return f"{to_plain(expr.args[0])} ⇒ {to_plain(expr.args[1])}"
    if isinstance(expr, Equivalent):
        return f"{to_plain(expr.args[0])} ⇔ {to_plain(expr.args[1])}"
    if isinstance(expr, sp.Sum):
        return _plain_big(expr, "∑", expr.function)
    if isinstance(expr, sp.Product):
        return _plain_big(expr, "∏", expr.function)
    if isinstance(expr, sp.Integral):
        return _plain_integral(expr)
    if isinstance(expr, sp.Limit):
        return f"lím({to_plain(expr.args[0])}, {expr.args[1]}→{to_plain(expr.args[2])})"
    if isinstance(expr, sp.Derivative):
        return f"d/d{expr.variables[0]} {to_plain(expr.expr)}"
    if isinstance(expr, sp.MatrixBase):
        return "\n".join(
            "  ".join(to_plain(entry) for entry in expr.row(index)) for index in range(expr.rows)
        )
    try:
        return _pretty(sp.sstr(expr))
    except (TypeError, ValueError):  # pragma: no cover - defensivo
        return str(expr)


def _plain_big(expr: Any, symbol: str, function: Any) -> str:
    variable, lower, upper = expr.limits[0]
    return f"{symbol}_{{{variable}={to_plain(lower)}..{to_plain(upper)}}} {to_plain(function)}"


def _plain_integral(expr: sp.Integral) -> str:
    function = to_plain(expr.function)
    if expr.limits:
        variable, lower, upper = expr.limits[0]
        return f"∫[{to_plain(lower)},{to_plain(upper)}] {function} d{variable}"
    if len(expr.args) > 1:
        return f"∫ {function} d{expr.args[1]}"
    return f"∫ {function} d?"


def to_latex(expr: Any) -> str:
    """LaTeX para el visor MathLive."""
    try:
        return sp.latex(expr)
    except (TypeError, ValueError, AttributeError):  # pragma: no cover - defensivo
        return sp.sstr(expr)


# ---------------------------------------------------------------------------
# Aproximación numérica
# ---------------------------------------------------------------------------


def approximate(expr: Any, digits: int = 12) -> str | None:
    """Valor decimal (real o complejo) del resultado, si se puede calcular."""
    if not isinstance(expr, sp.Basic) or isinstance(expr, sp.Dict):
        return None
    if getattr(expr, "free_symbols", set()):
        return None
    try:
        if expr in (sp.zoo, sp.nan) or expr.is_infinite is True:
            return None
        value = sp.N(expr, _PRECISION)
    except (TypeError, ValueError, ArithmeticError, NotImplementedError, AttributeError):
        return None
    if value in (sp.zoo, sp.nan, sp.oo, -sp.oo):
        return None
    try:
        if value.is_real is True:
            return _format_real(value, digits)
        return _format_complex(value, digits)
    except (TypeError, ValueError, OverflowError, ArithmeticError):
        return None


def _format_real(value: sp.Expr, digits: int) -> str:
    """Decimal sin ceros sobrantes, con notación científica si no cabe."""
    if value.is_zero is True:
        return "0"
    if value.is_Integer is True:
        return str(value)
    if abs(value) >= 10**400 or abs(value) < 10**(-400):
        return f"{value.evalf(digits):.{digits}g}"  # ni float() ni int() llegan
    try:
        number = float(value)
    except (OverflowError, TypeError, ValueError):
        return f"{value.evalf(digits):.{digits}g}"
    if number == int(number) and abs(number) < 1e15:
        return str(int(number))
    return f"{number:.{digits}g}"


def _format_complex(value: sp.Expr, digits: int) -> str:
    real, imaginary = sp.re(value), sp.im(value)
    if real.is_zero is True and imaginary.is_zero is True:
        return "0"
    real_text = "" if real.is_zero is True else _format_real(real, digits)
    imaginary_text = _format_real(sp.Abs(imaginary), digits)
    imaginary_number = float(sp.N(imaginary, _PRECISION))
    if real_text:
        sign = "+" if imaginary_number > 0 else "-"
        return f"{real_text} {sign} {imaginary_text}i"
    prefix = "-" if imaginary_number < 0 else ""
    return f"{prefix}{imaginary_text}i"


# ---------------------------------------------------------------------------
# Clasificación y simplificación
# ---------------------------------------------------------------------------


def classify(expr: Any) -> str:
    """Etiqueta corta que la interfaz usa para explicar el resultado."""
    if expr in (sp.oo, -sp.oo):
        return "infinity"
    if expr in (sp.zoo, sp.nan):
        return "undefined"
    if isinstance(expr, (Relational, Contains, BooleanFunction)):
        return "relation"
    if isinstance(expr, (sp.MatrixBase, sp.Dict)):
        return "matrix"
    if isinstance(expr, sp.Set):
        return "set"
    if isinstance(expr, (sp.Sum, sp.Product, sp.Integral, sp.Limit, sp.Derivative)):
        return "formal"
    if getattr(expr, "free_symbols", None):
        return "symbolic"
    if getattr(expr, "is_number", False):
        return "number" if expr.is_real is not False else "complex"
    return "symbolic"


def simplify(expr: Any) -> Any:
    """Simplifica con prudencia: las expresiones grandes se dejan tal cual."""
    if expr is None or isinstance(expr, (BooleanFunction, sp.MatrixBase, sp.Set, sp.Dict)):
        return expr
    if isinstance(expr, (sp.Sum, sp.Product, sp.Integral, sp.Limit, sp.Derivative)):
        return expr
    try:
        if sp.count_ops(expr) > _MAX_OPERATIONS_TO_SIMPLIFY:
            return expr
        if len(sp.sstr(expr)) > _MAX_CHARACTERS:
            return expr
    except (TypeError, ValueError, AttributeError):  # pragma: no cover - defensivo
        return expr
    try:
        return sp.simplify(expr)
    except (TypeError, ValueError, NotImplementedError, RecursionError):
        return expr


def build_payload(result: Any) -> dict:
    """Diccionario que consume el frontend."""
    if result is None:
        raise CalculationError("No se obtuvo ningún resultado.")
    return {
        "ok": True,
        "exact": to_plain(result),
        "latex": to_latex(result),
        "approx": approximate(result),
        "symbolic": bool(getattr(result, "free_symbols", set())),
        "kind": classify(result),
    }