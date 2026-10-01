"""Evaluador: convierte el árbol del analizador en expresiones de SymPy.

Aquí no se ejecuta código de la persona usuaria: cada nodo se traduce a una de
las operaciones de la lista blanca de ``forma.symbols``.
"""

from __future__ import annotations

import math
import sys
from typing import Any, Callable

import sympy as sp

from .errors import CalculationError
from .latex import (
    BigOperator,
    Binary,
    Call,
    Factorial,
    Implication,
    Logical,
    MatrixLiteral,
    Number,
    Quantifier,
    Relation,
    Scale,
    SetBuilder,
    SetLiteral,
    Symbol,
    Unary,
    render_name,
)
from .symbols import (
    CONSTANTS,
    DEFAULT_LIMITS,
    DEGREE_ARGUMENT_FUNCTIONS,
    DEGREE_RESULT_FUNCTIONS,
    FUNCTIONS,
    Limits,
)

# SymPyBlocked: Python limita en 4300 dígitos la conversión entero -> texto.
if hasattr(sys, "set_int_max_str_digits"):  # pragma: no branch
    sys.set_int_max_str_digits(40_000)

_SCALE_FACTORS = {
    "percent": sp.Rational(1, 100),
    "permille": sp.Rational(1, 1000),
    "degree": sp.pi / 180,
}

_RELATIONS = {
    "=": sp.Eq,
    "!=": sp.Ne,
    "<": sp.Lt,
    "<=": sp.Le,
    ">": sp.Gt,
    ">=": sp.Ge,
}

_MEMBERSHIP = ("in", "ni", "notin")
_SUBSETS = ("subset", "subseteq", "supset", "supseteq")


class Evaluator:
    """Traduce el árbol del analizador a SymPy respetando los límites."""

    def __init__(self, limits: Limits = DEFAULT_LIMITS) -> None:
        self.limits = limits
        self._scopes: list[dict[str, sp.Expr]] = []

    # -- API -----------------------------------------------------------------

    def evaluate(self, node: Any) -> sp.Basic:
        return self.visit(node)

    # -- tabla de símbolos ----------------------------------------------------

    def lookup(self, name: str) -> sp.Expr:
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        if name in CONSTANTS:
            return CONSTANTS[name]
        return sp.Symbol(name)

    def bind(self, name: str, value: sp.Expr | None = None) -> sp.Symbol:
        symbol = value if isinstance(value, sp.Symbol) else sp.Symbol(name)
        self._scopes.append({name: symbol})
        return symbol

    def unbind(self) -> None:
        self._scopes.pop()

    def _bound(self, name: str) -> sp.Expr | None:
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        return None

    def _scoped(self, name: str, action: Callable[[], Any]) -> Any:
        self.bind(name)
        try:
            return action()
        finally:
            self.unbind()

    # -- recorrido -----------------------------------------------------------

    def visit(self, node: Any) -> sp.Basic:
        if isinstance(node, Number):
            return self.visit_number(node)
        if isinstance(node, Symbol):
            return self.lookup(node.name)
        if isinstance(node, Unary):
            operand = self.visit(node.operand)
            return operand if node.op == "+" else -operand
        if isinstance(node, Binary):
            return self.visit_binary(node)
        if isinstance(node, Scale):
            return self.visit(node.operand) * _SCALE_FACTORS[node.factor]
        if isinstance(node, Factorial):
            return self.visit_factorial(node)
        if isinstance(node, Relation):
            return self.visit_relation(node)
        if isinstance(node, Logical):
            return self.visit_logical(node)
        if isinstance(node, Implication):
            left, right = self.visit(node.left), self.visit(node.right)
            return sp.Implies(left, right) if node.op == "implies" else sp.Equivalent(left, right)
        if isinstance(node, Quantifier):
            return self.visit_quantifier(node)
        if isinstance(node, Call):
            return self.visit_call(node)
        if isinstance(node, BigOperator):
            return self.visit_big_operator(node)
        if isinstance(node, SetLiteral):
            return sp.FiniteSet(*[self.visit(item) for item in node.items])
        if isinstance(node, SetBuilder):
            return self.visit_set_builder(node)
        if isinstance(node, MatrixLiteral):
            return self.visit_matrix(node)
        raise CalculationError(f"No se sabe interpretar «{render_name(node)}».")

    def visit_number(self, node: Number) -> sp.Expr:
        try:
            return sp.Rational(node.text)
        except (ValueError, ZeroDivisionError) as exc:
            raise CalculationError(f"No se reconoce el número «{node.text}».") from exc

    def visit_factorial(self, node: Factorial) -> sp.Expr:
        value = self.visit(node.operand)
        if value.is_number:
            if value.is_real is False:
                raise CalculationError("El factorial solo existe para números reales.")
            if value < 0:
                raise CalculationError("El factorial solo existe para números no negativos.")
            if float(value) > self.limits.max_factorial:
                raise CalculationError(f"El factorial está limitado a {self.limits.max_factorial}.")
        function = sp.factorial2 if node.double else sp.factorial
        return function(value)

    def visit_binary(self, node: Binary) -> sp.Basic:
        left = self.visit(node.left)
        right = self.visit(node.right)
        operator = node.op
        if operator == "+":
            return left + right
        if operator == "-":
            return left - right
        if operator == "*":
            return left * right
        if operator == "/":
            if right.is_number and right.is_zero:
                raise CalculationError("No se puede dividir por cero.")
            return left / right
        if operator == "**":
            return self.visit_power(node, left, right)
        if operator == "mod":
            return self.visit_modulo(left, right)
        if operator == "cup":
            return sp.Union(left, right)
        if operator == "cap":
            return sp.Intersection(left, right)
        if operator == "setminus":
            return sp.Complement(left, right)
        raise CalculationError(f"No se soporta el operador «{operator}».")

    def visit_power(self, node: Binary, left: sp.Expr, right: sp.Expr) -> sp.Expr:
        if right.is_number and right.is_finite is not False:
            try:
                magnitude = float(sp.N(abs(right), 20))
            except (TypeError, ValueError, OverflowError):
                return left**right
            if magnitude > self.limits.max_exponent:
                raise CalculationError(f"El exponente no puede pasar de {self.limits.max_exponent}.")
            if right.is_integer is True and right.is_real is True and right > 8:
                monomials = _monomials(_term_count(node.left), int(right))
                if monomials > self.limits.max_expansion:
                    raise CalculationError(
                        f"Esa potencia daría unos {monomials} términos; "
                        "usa factor(…) o simplify(…) para acortarla."
                    )
        return left**right

    def visit_modulo(self, left: sp.Expr, right: sp.Expr) -> sp.Expr:
        if right.is_number and right.is_zero:
            raise CalculationError("No se puede calcular el resto módulo cero.")
        return sp.Mod(left, right)

    def visit_relation(self, node: Relation) -> Any:
        operator = node.op
        if operator in _MEMBERSHIP or operator in _SUBSETS:
            return self.visit_set_relation(operator, node)
        left = self.visit(node.left)
        right = self.visit(node.right)
        if operator in _RELATIONS:
            relation = _RELATIONS[operator]
            try:
                return relation(left, right)
            except TypeError:
                return relation(left, right, evaluate=False)
        if operator in ("~", "~~", "~="):
            return self.visit_approximate(left, right, operator)
        if operator == "===":
            return sp.Eq(left, right, evaluate=False)
        if operator == "prop":
            return sp.Eq(left, right * sp.Symbol("k", real=True))
        raise CalculationError(f"No se soporta la relación «{operator}».")

    def visit_approximate(self, left: sp.Expr, right: sp.Expr, operator: str) -> Any:
        symbol = {"~": "~", "~~": "≈", "~=": "≃"}[operator]
        if left.free_symbols or right.free_symbols:
            raise CalculationError(
                f"«{symbol}» compara números; con símbolos usa «=» o escribe la relación como texto."
            )
        tolerance = sp.Rational(1, 1000) * (abs(left) + abs(right) + 1)
        return sp.Abs(sp.simplify(left - right)) <= tolerance

    def visit_set_relation(self, operator: str, node: Relation) -> Any:
        left = self.visit(node.left)
        right = self.visit(node.right)
        if operator == "in":
            return sp.Contains(left, right)
        if operator in ("ni", "notin"):
            return sp.Not(sp.Contains(left, right))
        if operator in ("subset", "subseteq"):
            return sp.Contains(left, sp.PowerSet(right))
        return sp.Contains(right, sp.PowerSet(left))

    def visit_logical(self, node: Logical) -> Any:
        if node.op == "not":
            return sp.Not(self.visit(node.args[0]))
        values = [self.visit(argument) for argument in node.args]
        if node.op == "and":
            return sp.And(*values)
        if node.op == "or":
            return sp.Or(*values)
        if node.op == "xor":
            return sp.Xor(*values)
        raise CalculationError(f"No se soporta el operador «{node.op}».")

    def visit_quantifier(self, node: Quantifier) -> Any:
        def build() -> Any:
            body = self.visit(node.body)
            domain = self.visit(node.domain) if node.domain is not None else None
            if domain is not None and not isinstance(domain, sp.Set):
                raise CalculationError("El dominio de un cuantificador debe ser un conjunto.")
            return body, domain

        symbol, (body, domain) = self._with_symbol(node.var, build)
        factory = sp.Exists if node.op == "exists" else sp.ForAll
        return factory(symbol, body, domain)

    def visit_call(self, node: Call) -> sp.Basic:
        name = node.name
        if name == "emptyset":
            return sp.S.EmptySet
        if not node.args:
            # «i» o «e» son constantes, pero si un operador mayor ya las ha
            # ligado (∑_{i=1}^{n}) mandan ellas.
            bound = self._bound(name)
            if bound is not None:
                return bound
            if name in CONSTANTS:
                return CONSTANTS[name]
        spec = FUNCTIONS.get(name)
        if spec is None:
            raise CalculationError(f"No conozco la función «{name}».")
        spec.check(len(node.args))
        arguments = [self.visit(argument) for argument in node.args]
        if name in DEGREE_ARGUMENT_FUNCTIONS and len(arguments) == 1:
            arguments[0] = _to_radians(arguments[0])
        try:
            result = spec.func(*arguments)
            if name in DEGREE_RESULT_FUNCTIONS:
                result = _to_degrees(result)
            return _coerce(result)
        except CalculationError:
            raise
        except (TypeError, ValueError, ZeroDivisionError) as exc:
            raise CalculationError(f"No se pudo calcular {name}(…): {_friendly(exc)}") from exc
        except Exception as exc:  # noqa: BLE001 - SymPy lanza excepciones muy variadas
            raise CalculationError(f"{name}(…) no se pudo calcular con esos valores.") from exc

    def visit_set_builder(self, node: SetBuilder) -> sp.Basic:
        if isinstance(node.binder, Symbol):
            symbol, condition = self._with_symbol(node.binder.name, lambda: self.visit(node.condition))
            return sp.ConditionSet(symbol, condition)
        domain = self.visit(node.binder)
        if not isinstance(domain, sp.Set):
            raise CalculationError("Se necesita un conjunto a la izquierda de «\\mid».")
        raise CalculationError(
            "Antes de «\\mid» hace falta una variable, por ejemplo: {n | n > 0}"
        )

    def visit_matrix(self, node: MatrixLiteral) -> sp.MatrixBase:
        rows = [[self.visit(item) for item in row] for row in node.rows]
        if len({len(row) for row in rows}) > 1:
            raise CalculationError("Todas las filas de la matriz deben tener el mismo número de columnas.")
        try:
            return sp.Matrix(rows)
        except (TypeError, ValueError) as exc:
            raise CalculationError("No se pudo construir la matriz.") from exc

    # -- operadores grandes --------------------------------------------------

    def visit_big_operator(self, node: BigOperator) -> sp.Basic:
        if node.op in ("int", "iint", "oint"):
            return self.visit_integral(node)
        if node.op == "limit":
            return self.visit_limit(node)
        if node.op in ("bigcup", "bigcap"):
            return self.visit_set_big_operator(node)
        return self.visit_sum(node)

    def _with_symbol(self, name: str, action: Callable[[], Any]) -> tuple[sp.Symbol, Any]:
        self.bind(name)
        try:
            return self._scopes[-1][name], action()
        finally:
            self.unbind()

    def _infer_variable(self, body: sp.Expr, hint: str, node: BigOperator) -> str:
        if node.var:
            return node.var
        symbols = sorted(body.free_symbols, key=lambda symbol: symbol.name)
        if len(symbols) == 1:
            return symbols[0].name
        raise CalculationError(hint)

    def visit_sum(self, node: BigOperator) -> sp.Basic:
        hint = "Indica el índice de la suma: \\sum_{i=1}^{n} …"
        probe = self.visit(node.body)
        name = self._infer_variable(probe, hint, node)

        def build() -> Any:
            body = self.visit(node.body)
            lower = self.visit(node.lower) if node.lower is not None else None
            upper = self.visit(node.upper) if node.upper is not None else None
            return body, lower, upper

        symbol, (body, lower, upper) = self._with_symbol(name, build)
        if lower is None and upper is None:
            raise CalculationError("Los límites se escriben \\sum_{i=1}^{n} …")
        if lower is None or upper is None:
            raise CalculationError("Falta el límite inferior o el superior de la suma.")
        factory = sp.Sum if node.op == "sum" else sp.Product
        expression = factory(body, (symbol, lower, upper))
        steps = self._iteration_count(lower, upper)
        if steps is None:
            return expression
        if steps > self.limits.max_iterations:
            raise CalculationError(
                f"Esa suma recorre {steps} términos y el límite es {self.limits.max_iterations}."
            )
        try:
            return expression.doit()
        except Exception:  # noqa: BLE001 - si no se sabe integrar, se devuelve sin evaluar
            return expression

    def visit_integral(self, node: BigOperator) -> sp.Basic:
        hint = "Indica la variable de integración: \\int x^2 dx"
        probe = self.visit(node.body)
        name = self._infer_variable(probe, hint, node)

        def build() -> Any:
            body = self.visit(node.body)
            lower = self.visit(node.lower) if node.lower is not None else None
            upper = self.visit(node.upper) if node.upper is not None else None
            return body, lower, upper

        symbol, (body, lower, upper) = self._with_symbol(name, build)
        if lower is None and upper is None:
            try:
                return sp.integrate(body, symbol)
            except Exception:  # noqa: BLE001
                return sp.Integral(body, symbol)
        if lower is None or upper is None:
            raise CalculationError("Una integral con límites necesita los dos: \\int_0^1 x^2 dx")
        try:
            return sp.integrate(body, (symbol, lower, upper))
        except Exception:  # noqa: BLE001
            return sp.Integral(body, (symbol, lower, upper))

    def visit_limit(self, node: BigOperator) -> sp.Basic:
        if not node.var:
            raise CalculationError("«\\lim» necesita una variable: \\lim_{x\\to 0} …")

        def build() -> Any:
            body = self.visit(node.body)
            target = self.visit(node.lower) if node.lower is not None else None
            return body, target

        symbol, (body, target) = self._with_symbol(node.var, build)
        if target is None:
            raise CalculationError("«\\lim» necesita hacia dónde se tiende: \\lim_{x\\to 0} …")
        try:
            return sp.limit(body, symbol, target, dir=node.direction)
        except Exception:  # noqa: BLE001
            return sp.Limit(body, symbol, target, dir=node.direction)

    def visit_set_big_operator(self, node: BigOperator) -> sp.Basic:
        probe = self.visit(node.body)
        name = self._infer_variable(probe, "Indica el índice de la unión.", node)

        def build() -> Any:
            body = self.visit(node.body)
            lower = self.visit(node.lower) if node.lower is not None else None
            upper = self.visit(node.upper) if node.upper is not None else None
            return body, lower, upper

        symbol, (body, lower, upper) = self._with_symbol(name, build)
        steps = self._iteration_count(lower, upper) if lower is not None and upper is not None else None
        if not steps or steps > self.limits.max_iterations:
            raise CalculationError("Esta operación necesita límites numéricos pequeños.")
        values = [body.subs(symbol, lower + offset) for offset in range(steps)]
        return sp.Union(*values) if node.op == "bigcup" else sp.Intersection(*values)

    def _iteration_count(self, lower: sp.Expr, upper: sp.Expr) -> int | None:
        if lower.is_Integer is True and upper.is_Integer is True:
            return max(0, int(upper) - int(lower) + 1)
        return None


def _to_radians(value: sp.Expr) -> sp.Expr:
    """``sin(90)`` son 90 grados; ``sin(π/6)`` se queda en radianes.

    Solo se convierten los números exactos: cualquier expresión con π ya está
    escrita en radianes y no hay que tocarla.
    """
    if value.is_Rational is True:
        return value * sp.pi / 180
    return value


def _to_degrees(value: sp.Expr) -> sp.Expr:
    """``asin(0.5)`` son 30 grados, no π/6."""
    if value.is_number and value.is_real is not False and value.is_finite is True:
        return value * sp.Integer(180) / sp.pi
    return value


def _coerce(result: Any) -> Any:
    """Convierte listas y diccionarios de SymPy en objetos imprimibles."""
    if isinstance(result, dict):
        return sp.Dict(*[sp.Tuple(key, value) for key, value in result.items()])
    if isinstance(result, (list, tuple, set, frozenset)):
        return sp.FiniteSet(*result)
    if isinstance(result, bool):
        return sp.true if result else sp.false
    return result


def _term_count(node: Any) -> int:
    """Número aproximado de términos de una suma (evita explosiones al elevar)."""
    if isinstance(node, Binary) and node.op in ("+", "-"):
        return _term_count(node.left) + _term_count(node.right)
    return 1


def _monomials(terms: int, exponent: int) -> int:
    """Cuántos términos tendría ``(a+b+…)`` elevado a ``exponent``."""
    if terms <= 1 or exponent <= 1:
        return 1  # una sola base no se desarrolla: x^9999 es barata
    if exponent > 64 or terms > 64:
        return 10**9  # desborda cualquier estimación razonable
    return math.comb(terms + exponent - 1, exponent)


def _friendly(exception: BaseException) -> str:
    text = str(exception).strip()
    return (text.split("\n")[0] if text else "valores no válidos")[:120]


def evaluate(node: Any, limits: Limits = DEFAULT_LIMITS) -> sp.Basic:
    """Atajo: evalúa un árbol del analizador."""
    return Evaluator(limits).evaluate(node)