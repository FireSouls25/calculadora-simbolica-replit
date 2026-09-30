"""Catálogos de símbolos, constantes y funciones.

Este módulo es la única fuente de verdad sobre *qué* sabe calcular la
aplicación. El analizador de LaTeX (``forma.latex``) y el evaluador
(``forma.evaluator``) consultan estas tablas, de modo que añadir una función
nueva es siempre una entrada más aquí (y, si se quiere, un botón en
``forma.palette``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping

import sympy as sp

from .errors import CalculationError

# ---------------------------------------------------------------------------
# Límites de seguridad
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Limits:
    """Límites estáticos que impiden que una expresión reviente la máquina."""

    max_length: int = 4_000
    max_nodes: int = 3_000
    max_exponent: int = 10_000
    max_factorial: int = 500
    max_iterations: int = 100_000
    max_series_order: int = 200
    max_matrix_cells: int = 400
    max_sqrt_degree: int = 1_000
    max_expansion: int = 5_000  # monomios estimados al elevar una suma


DEFAULT_LIMITS = Limits()


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------


def _degree() -> sp.Expr:
    """``\\degree`` -> pi/180.  ``30\\degree`` vale pi/6."""
    return sp.pi / 180


CONSTANTS: Mapping[str, sp.Expr] = {
    "pi": sp.pi,
    "π": sp.pi,
    "tau": sp.Integer(2) * sp.pi,
    "e": sp.E,
    "E": sp.E,
    "I": sp.I,
    "i": sp.I,
    "j": sp.I,
    "oo": sp.oo,
    "inf": sp.oo,
    "infinity": sp.oo,
    "infty": sp.oo,
    "nan": sp.nan,
    "NaN": sp.nan,
    "Catalan": sp.Catalan,
    "EulerGamma": sp.EulerGamma,
    "GoldenRatio": sp.GoldenRatio,
    "phi": sp.GoldenRatio,
    "degree": _degree(),
    "half": sp.Rational(1, 2),
}

#: Nombres que funcionan como constante aunque no sean comandos LaTeX.
CONSTANT_NAMES = frozenset(CONSTANTS)


# ---------------------------------------------------------------------------
# Funciones
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FunctionSpec:
    """Función whitelisted: nombre, implementation y número de argumentos."""

    name: str
    func: Callable[..., sp.Expr]
    min_args: int = 1
    max_args: int | None = 1

    def check(self, count: int) -> None:
        if count < self.min_args or (self.max_args is not None and count > self.max_args):
            expected = (
                str(self.min_args)
                if self.max_args == self.min_args
                else f"{self.min_args} o más"
                if self.max_args is None
                else f"entre {self.min_args} y {self.max_args}"
            )
            raise CalculationError(
                f"{self.name}() necesita {expected} argumento(s); le has dado {count}."
            )


def _log(*args: sp.Expr) -> sp.Expr:
    """``\\log x`` es logaritmo decimal; ``\\log_b x`` cambia la base."""
    if len(args) == 1:
        return sp.log(args[0], 10)
    return sp.log(args[0], args[1])


def _round(*args: sp.Expr) -> sp.Expr:
    if len(args) == 1:
        return sp.Integer(round(sp.N(args[0])))
    digits = int(args[1])
    return sp.Rational(round(sp.N(args[0]) * 10**digits), 10**digits)


def _subs(expression: sp.Expr, old: sp.Expr, new: sp.Expr) -> sp.Expr:
    return expression.subs(old, new)


def _base(convert: Any, value: sp.Expr) -> sp.Expr:
    if value.is_Integer is not True:
        raise CalculationError("La conversión de base solo acepta enteros.")
    if value < 0:
        raise CalculationError("La conversión de base solo acepta enteros positivos.")
    return sp.Symbol(convert(int(value)))


def _num_digits(value: sp.Expr) -> sp.Expr:
    if value.is_Integer is not True:
        raise CalculationError("num_digits() solo acepta números enteros.")
    text = str(abs(int(value)))
    if len(text) > 4_000:
        raise CalculationError("El número es demasiado largo.")
    return sp.Integer(len(text))


def _digit_sum(value: sp.Expr) -> sp.Expr:
    if value.is_Integer is not True:
        raise CalculationError("sum_digits() solo acepta números enteros.")
    return sp.Integer(sum(int(digit) for digit in str(abs(int(value)))))


def _make_table() -> dict[str, FunctionSpec]:
    entries: list[tuple[str, Callable[..., sp.Expr], int, int | None]] = [
        # Trigonometría
        ("sin", sp.sin, 1, 1), ("cos", sp.cos, 1, 1), ("tan", sp.tan, 1, 1),
        ("cot", sp.cot, 1, 1), ("sec", sp.sec, 1, 1), ("csc", sp.csc, 1, 1),
        ("asin", sp.asin, 1, 1), ("acos", sp.acos, 1, 1), ("atan", sp.atan, 1, 1),
        ("acot", sp.acot, 1, 1), ("asec", sp.asec, 1, 1), ("acsc", sp.acsc, 1, 1),
        ("atan2", sp.atan2, 2, 2),
        ("sinh", sp.sinh, 1, 1), ("cosh", sp.cosh, 1, 1), ("tanh", sp.tanh, 1, 1),
        ("coth", sp.coth, 1, 1), ("sech", sp.sech, 1, 1), ("csch", sp.csch, 1, 1),
        ("asinh", sp.asinh, 1, 1), ("acosh", sp.acosh, 1, 1), ("atanh", sp.atanh, 1, 1),
        # Logaritmos y exponentes
        ("exp", sp.exp, 1, 1), ("ln", sp.log, 1, 1), ("log", _log, 1, 2),
        ("log10", lambda v: sp.log(v, 10), 1, 1), ("log2", lambda v: sp.log(v, 2), 1, 1),
        # Raíces y potencias
        ("sqrt", sp.sqrt, 1, 1), ("cbrt", sp.real_root, 2, 2), ("root", sp.root, 2, 2),
        ("hypot", lambda a, b: sp.sqrt(a**2 + b**2), 2, 2),
        # Elementales
        ("abs", sp.Abs, 1, 1), ("Abs", sp.Abs, 1, 1),
        ("sgn", sp.sign, 1, 1), ("sign", sp.sign, 1, 1),
        ("floor", sp.floor, 1, 1), ("ceil", sp.ceiling, 1, 1),
        ("frac", sp.frac, 1, 1), ("round", _round, 1, 2),
        ("min", sp.Min, 1, None), ("max", sp.Max, 1, None),
        ("gcd", sp.gcd, 2, None), ("lcm", sp.lcm, 2, None),
        ("mod", sp.Mod, 2, 2), ("rem", sp.rem, 2, 2),
        ("factorial", sp.factorial, 1, 1), ("fact", sp.factorial, 1, 1),
        ("factorial2", sp.factorial2, 1, 1),
        ("gamma", sp.gamma, 1, 1), ("beta", sp.beta, 2, 2),
        ("erf", sp.erf, 1, 1), ("erfc", sp.erfc, 1, 1),
        # Números
        ("binom", sp.binomial, 2, 2), ("binomial", sp.binomial, 2, 2),
        ("nCr", sp.binomial, 2, 2),
        ("nPr", sp.ff, 2, 2), ("permutations", sp.ff, 2, 2),
        ("isprime", sp.isprime, 1, 1), ("nextprime", sp.nextprime, 1, 1),
        ("prevprime", sp.prevprime, 1, 1),
        ("num_digits", _num_digits, 1, 1), ("sum_digits", _digit_sum, 1, 1),
        ("divisor_count", sp.divisor_count, 1, 1),
        # Números complejos
        ("re", sp.re, 1, 1), ("im", sp.im, 1, 1), ("arg", sp.arg, 1, 1),
        ("conj", sp.conjugate, 1, 1), ("conjugate", sp.conjugate, 1, 1),
        # Álgebra
        ("simplify", sp.simplify, 1, 1), ("expand", sp.expand, 1, 1),
        ("factor", sp.factor, 1, 1), ("cancel", sp.cancel, 1, 1),
        ("trigsimp", sp.trigsimp, 1, 1), ("together", sp.together, 1, 1),
        ("apart", sp.apart, 1, 1), ("nsimplify", sp.nsimplify, 1, 1),
        ("subs", _subs, 3, 3),
        ("solve", sp.solve, 1, 2), ("roots", sp.roots, 1, 1),
        ("degree_poly", sp.degree, 1, 2),
        # Cálculo
        ("diff", sp.diff, 2, 2), ("derivative", sp.diff, 2, 2),
        ("integrate", sp.integrate, 2, 4), ("antiderivative", sp.integrate, 2, 2),
        ("limit", sp.limit, 3, 4),
        ("series", sp.series, 3, 4), ("taylor", sp.series, 3, 4),
        # Matrices
        ("det", lambda m: sp.Matrix(m).det(), 1, 1),
        ("inv", lambda m: sp.Matrix(m).inv(), 1, 1),
        ("transpose", lambda m: sp.Matrix(m).transpose(), 1, 1),
        ("rank", lambda m: sp.Matrix(m).rank(), 1, 1),
        ("trace", lambda m: sp.Matrix(m).trace(), 1, 1),
        ("eigenvals", lambda m: sp.Matrix(m).eigenvals(), 1, 1),
        ("rref", lambda m: sp.Matrix(m).rref()[0], 1, 1),
        # Conversión de base
        ("bin", lambda v: _base(bin, v), 1, 1),
        ("hex", lambda v: _base(hex, v), 1, 1),
        ("oct", lambda v: _base(oct, v), 1, 1),
    ]
    table = {name: FunctionSpec(name, func, low, high) for name, func, low, high in entries}
    table["cbrt"] = FunctionSpec("cbrt", lambda v: sp.real_root(v, 3), 1, 1)
    return table


FUNCTIONS: Mapping[str, FunctionSpec] = _make_table()

#: Alias en LaTeX -> nombre interno de función.
FUNCTION_COMMANDS: Mapping[str, str] = {
    r"\sin": "sin", r"\cos": "cos", r"\tan": "tan", r"\cot": "cot",
    r"\sec": "sec", r"\csc": "csc",
    r"\arcsin": "asin", r"\arccos": "acos", r"\arctan": "atan",
    r"\arcsin ": "asin",
    r"\arccot": "acot", r"\arcsec": "asec", r"\arccsc": "acsc",
    r"\sinh": "sinh", r"\cosh": "cosh", r"\tanh": "tanh", r"\coth": "coth",
    r"\sech": "sech", r"\csch": "csch",
    r"\arsinh": "asinh", r"\arcosh": "acosh", r"\artanh": "atanh",
    r"\exp": "exp", r"\ln": "ln", r"\log": "log", r"\lg": "log",
    r"\sqrt": "sqrt", r"\cbrt": "cbrt",
    r"\det": "det", r"\gcd": "gcd", r"\dim": "degree_poly",
    r"\abs": "abs", r"\sign": "sign", r"\sgn": "sign",
    r"\min": "min", r"\max": "max", r"\arg": "arg", r"\conj": "conj",
    r"\deg": "degree", r"\arctan2": "atan2",
}

#: Comandos LaTeX -> constantes internas.
CONSTANT_COMMANDS: Mapping[str, str] = {
    r"\pi": "pi", r"\tau": "tau", r"\infty": "oo", r"\nan": "nan",
    r"\catalan": "Catalan", r"\euler": "EulerGamma", r"\goldenratio": "GoldenRatio",
    r"\degree": "degree", r"\percent": "percent", r"\imath": "i", r"\jmath": "i",
}

#: Comandos LaTeX -> símbolos griegos (nombre interno, nombre LaTeX canónico).
GREEK_SYMBOLS: Mapping[str, tuple[str, str]] = {
    r"\alpha": ("alpha", r"\alpha"), r"\beta": ("beta", r"\beta"),
    r"\gamma": ("gamma", r"\gamma"), r"\delta": ("delta", r"\delta"),
    r"\epsilon": ("epsilon", r"\epsilon"), r"\varepsilon": ("varepsilon", r"\varepsilon"),
    r"\zeta": ("zeta", r"\zeta"), r"\eta": ("eta", r"\eta"),
    r"\theta": ("theta", r"\theta"), r"\vartheta": ("vartheta", r"\vartheta"),
    r"\iota": ("iota", r"\iota"), r"\kappa": ("kappa", r"\kappa"),
    r"\lambda": ("lambda", r"\lambda"), r"\mu": ("mu", r"\mu"),
    r"\nu": ("nu", r"\nu"), r"\xi": ("xi", r"\xi"),
    r"\omicron": ("omicron", r"\omicron"), r"\rho": ("rho", r"\rho"),
    r"\varrho": ("varrho", r"\varrho"), r"\sigma": ("sigma", r"\sigma"),
    r"\varsigma": ("varsigma", r"\varsigma"), r"\tau": ("tau", r"\tau"),
    r"\upsilon": ("upsilon", r"\upsilon"), r"\phi": ("varphi", r"\varphi"),
    r"\varphi": ("varphi", r"\varphi"), r"\chi": ("chi", r"\chi"),
    r"\psi": ("psi", r"\psi"), r"\omega": ("omega", r"\omega"),
    r"\Gamma": ("Gamma", r"\Gamma"), r"\Delta": ("Delta", r"\Delta"),
    r"\Theta": ("Theta", r"\Theta"), r"\Lambda": ("Lambda", r"\Lambda"),
    r"\Xi": ("Xi", r"\Xi"), r"\Pi": ("Pi", r"\Pi"), r"\Sigma": ("Sigma", r"\Sigma"),
    r"\Upsilon": ("Upsilon", r"\Upsilon"), r"\Phi": ("Phi", r"\Phi"),
    r"\Psi": ("Psi", r"\Psi"), r"\Omega": ("Omega", r"\Omega"),
}

#: Nombres de conjuntos Famous usados por ``\mathbb``.
BB_FONT_SETS: Mapping[str, sp.Expr] = {
    "R": sp.S.Reals, "N": sp.S.Naturals0, "Z": sp.S.Integers,
    "Q": sp.S.Rationals, "C": sp.S.Complexes,
}

#: Comandos de relaciones -> operador interno.
RELATION_COMMANDS: Mapping[str, str] = {
    r"\ne": "!=", r"\neq": "!=", "≠": "!=",
    r"\le": "<=", r"\leq": "<=", "≤": "<=",
    r"\ge": ">=", r"\geq": ">=", "≥": ">=",
    r"\lt": "<", r"<": "<",
    r"\gt": ">", r">": ">",
    r"\approx": "~~", r"\equiv": "===", r"\sim": "~",
    r"\simeq": "~=", r"\propto": "prop", r"\doteq": "===",
    r"\in": "in", r"\ni": "ni", r"\notin": "notin",
    r"\subset": "subset", r"\subseteq": "subseteq",
    r"\supset": "supset", r"\supseteq": "supseteq",
}

#: Comandos que empiezan un valor (para la multiplicación implícita).
VALUE_COMMANDS: frozenset[str] = frozenset(
    set(GREEK_SYMBOLS)
    | set(FUNCTION_COMMANDS)
    | set(CONSTANT_COMMANDS)
    | {
        r"\frac", r"\dfrac", r"\tfrac", r"\cfrac", r"\sqrt", r"\binom", r"\choose",
        r"\sum", r"\prod", r"\int", r"\iint", r"\lim", r"\left", r"\middle",
        r"\mathbb", r"\mathbf", r"\mathrm", r"\mathit", r"\mathsf", r"\mathtt",
        r"\operatorname", r"\text", r"\textbf", r"\textit",
        r"\overline", r"\bar", r"\vec", r"\hat", r"\tilde", r"\dot", r"\ddot",
        r"\lfloor", r"\lceil", r"\lvert", r"\lVert", r"\{",
        r"\emptyset", r"\varnothing", r"\forall", r"\exists", r"\not", r"\neg",
        r"\infty", r"\bigcup", r"\bigcap", r"\ldots", r"\cdots", r"\vdots",
    }
)

#: Comandos que NUNCA empiezan un valor (delimitadores de cierre y operadores).
NON_VALUE_COMMANDS: frozenset[str] = frozenset(
    {
        r"\right", r"\rfloor", r"\rceil", r"\rvert", r"\rVert", r"\mid",
        r"\pm", r"\mp", r"\cdot", r"\times", r"\div", r"\ast", r"\ast",
        r"\land", r"\lor", r"\wedge", r"\vee", r"\implies", r"\iff",
        r"\Rightarrow", r"\Leftrightarrow", r"\to", r"\rightarrow", r"\mapsto",
        r"\bmod", r"\mod", r"\pmod", r"\%", r"\prime", r"\circ",
        r"\cup", r"\cap", r"\setminus", r"\oplus", r"\pm", r"\mp",
    }
    | set(RELATION_COMMANDS)
)

#: Comandos que el analizador simplemente ignora.
IGNORED_COMMANDS: frozenset[str] = frozenset(
    {
        r"\,", r"\;", r"\:", r"\!", r"\ ", r"\quad", r"\qquad", r"\thinspace",
        r"\medspace", r"\thickspace", r"\negthinspace", r"\displaystyle",
        r"\textstyle", r"\limits", r"\nolimits", r"\big", r"\Big", r"\bigg",
        r"\Bigg", r"\left.", r"\nonumber", r"\notag",
        # «\partial x/\partial y» es decorativo: la derivada se calcula con diff().
        r"\partial",
    }
)

#: Acentos que se aplican a un símbolo (nombre interno -> LaTeX).
ACCENT_COMMANDS: Mapping[str, str] = {
    r"\vec": r"\vec", r"\hat": r"\hat", r"\widehat": r"\hat",
    r"\tilde": r"\tilde", r"\widetilde": r"\tilde",
    r"\dot": r"\dot", r"\ddot": r"\ddot", r"\bar": r"\bar",
}