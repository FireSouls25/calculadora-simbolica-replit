"""Analizador de LaTeX: convierte la entrada de MathLive en un árbol propio.

Antes se traducía el LaTeX a Python y se evaluaba con ``ast``; eso obligaba a
detectar la multiplicación implícita con expresiones regulares y rompía cosas
como ``sin x``, ``\\log 100``, ``\\int x^2 dx`` o ``2x``. Aquí hay un analizador
de verdad (lexer + parser descendente recursivo) que produce un árbol
independiente de SymPy y respeta la precedencia matemática.

Precedencia, de más débil a más fuerte:

    implicación → o → y → relación → suma → producto → unario → potencia → postfijo
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .errors import CalculationError
from .symbols import (
    ACCENT_COMMANDS,
    BB_FONT_SETS,
    CONSTANTS,
    CONSTANT_COMMANDS,
    CONSTANT_NAMES,
    FUNCTIONS,
    FUNCTION_COMMANDS,
    GREEK_SYMBOLS,
    IGNORED_COMMANDS,
    NON_VALUE_COMMANDS,
    RELATION_COMMANDS,
    VALUE_COMMANDS,
    DEFAULT_LIMITS,
    Limits,
)

# ---------------------------------------------------------------------------
# Nodos del árbol
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Number:
    """Literal numérico tal cual lo escribió la persona (``1.5e3``)."""

    text: str


@dataclass(frozen=True)
class Symbol:
    name: str
    latex: str | None = None


@dataclass(frozen=True)
class Unary:
    op: str  # "+" | "-"
    operand: Any


@dataclass(frozen=True)
class Binary:
    op: str  # + - * / ** mod and or xor cup cap setminus
    left: Any
    right: Any


@dataclass(frozen=True)
class Relation:
    op: str  # = != < <= > >= ~~ === ~ prop in ni notin subset subseteq supset superseteq
    left: Any
    right: Any


@dataclass(frozen=True)
class Implication:
    op: str  # implies | iff
    left: Any
    right: Any


@dataclass(frozen=True)
class Logical:
    op: str  # and | or | not | xor
    args: tuple


@dataclass(frozen=True)
class Quantifier:
    op: str  # forall | exists
    var: str
    domain: Any | None
    body: Any


@dataclass(frozen=True)
class Call:
    name: str
    args: tuple


@dataclass(frozen=True)
class BigOperator:
    op: str  # sum | prod | int | iint | oint | limit
    var: str | None
    lower: Any | None
    upper: Any | None
    body: Any
    direction: str = "+"


@dataclass(frozen=True)
class SetLiteral:
    items: tuple


@dataclass(frozen=True)
class SetBuilder:
    binder: Any
    condition: Any
    domain: Any | None = None


@dataclass(frozen=True)
class MatrixLiteral:
    rows: tuple


@dataclass(frozen=True)
class Scale:
    """Sufijo que multiplica por una constante: ``50\\%``, ``30\\degree``."""

    operand: Any
    factor: str  # percent | permille | degree


@dataclass(frozen=True)
class Factorial:
    operand: Any
    double: bool = False


# ---------------------------------------------------------------------------
# Normalización de la entrada
# ---------------------------------------------------------------------------

#: Caracteres Unicode habituales en un ``math-field`` -> LaTeX equivalente.
UNICODE_MAP: dict[str, str] = {
    "\u2212": "-", "\u2013": "-", "\u2014": "-",
    "\u00d7": r"\times", "\u00f7": r"\div", "\u00b7": r"\cdot",
    "\u22c5": r"\cdot", "\u2217": r"\ast", "\u2299": r"\oplus",
    "\u2264": r"\le", "\u2265": r"\ge", "\u2260": r"\ne", "\u2261": r"\equiv",
    "\u2248": r"\approx", "\u2243": r"\simeq", "\u223c": r"\sim", "\u221d": r"\propto",
    "\u03c0": r"\pi", "\u221e": r"\infty", "\u2205": r"\emptyset",
    "\u2208": r"\in", "\u2209": r"\notin", "\u220b": r"\ni",
    "\u2282": r"\subset", "\u2286": r"\subseteq", "\u2283": r"\supset", "\u2287": r"\supseteq",
    "\u222a": r"\cup", "\u2229": r"\cap", "\u2296": r"\setminus",
    "\u2200": r"\forall", "\u2203": r"\exists", "\u00ac": r"\neg",
    "\u2227": r"\land", "\u2228": r"\lor", "\u21d2": r"\implies",
    "\u21d4": r"\iff", "\u27f9": r"\implies", "\u21d0": r"\iff",
    "\u2192": r"\to", "\u27f6": r"\to",
    "\u2211": r"\sum", "\u220f": r"\prod", "\u222b": r"\int",
    "\u222c": r"\iint", "\u222e": r"\oint", "\u221a": r"\sqrt",
    "\u221b": r"\cbrt", "\u221c": r"\sqrt[4]",
    "\u2308": r"\lceil", "\u2309": r"\rceil", "\u230a": r"\lfloor", "\u230b": r"\rfloor",
    "\u211d": r"\mathbb{R}", "\u2115": r"\mathbb{N}", "\u2124": r"\mathbb{Z}",
    "\u211a": r"\mathbb{Q}", "\u2102": r"\mathbb{C}",
    "\u2026": r"\ldots", "\u22ef": r"\cdots", "\u22ee": r"\vdots", "\u22f1": r"\ddots",
    "\u2130": "e", "\u2147": "e", "\uff05": r"\%", "\u2030": r"\permille",
    "\u00b0": r"\degree", "\u2032": r"\prime", "\u2217": r"\ast",
    "\u2261": r"\equiv", "\u226a": r"\ll", "\u226b": r"\gg",
}

_SPACING_COMMANDS = frozenset(
    {r"\,", r"\;", r"\:", r"\!", r"\ ", r"\quad", r"\qquad", r"\thinspace", r"\medspace"}
)

_KEYWORD_OPERATORS = frozenset(
    {"mod", "Mod", "in", "and", "or", "xor", "not", "to", "union", "intersection"}
)

#: Identificadores que, escritos sin argumentos, son funciones prefijadas.
_PREFIX_FUNCTION_NAMES = frozenset(
    {
        "sin", "cos", "tan", "cot", "sec", "csc", "asin", "acos", "atan",
        "sinh", "cosh", "tanh", "log", "ln", "exp", "gcd", "lcm",
        "min", "max", "abs", "sqrt", "sign", "sgn", "floor", "ceil", "round",
    }
)

_SAFE_ENVIRONMENTS = frozenset(
    {"matrix", "pmatrix", "bmatrix", "Bmatrix", "vmatrix", "Vmatrix", "cases", "smallmatrix"}
)

_TOKEN_RE = re.compile(
    r"""
      (?P<space>\s+)
    | (?P<command>\\[a-zA-Z]+|\\.)
    | (?P<number>(?:\d+\.\d*|\.\d+|\d+)(?:[eE][+-]?\d+)?)
    | (?P<ident>[a-zA-Z]+)
    | (?P<symbol>.)
    """,
    re.VERBOSE | re.DOTALL,
)


@dataclass(frozen=True)
class Token:
    kind: str  # number | ident | command | symbol | end
    value: str
    position: int


def normalize(source: str) -> str:
    """Limpia y homogeneiza el LaTeX que llega del editor."""
    text = source.replace("\u00a0", " ").replace("\u200b", "")
    return "".join(UNICODE_MAP.get(char, char) for char in text)


def tokenize(source: str) -> list[Token]:
    tokens: list[Token] = []
    for match in _TOKEN_RE.finditer(normalize(source)):
        kind = match.lastgroup or "symbol"
        if kind == "space":
            continue
        value = match.group()
        if kind == "number" and value.endswith("."):
            value = value[:-1]
        tokens.append(Token(kind, value, match.start()))
    tokens.append(Token("end", "", len(source)))
    return _join_function_names(tokens)


def _join_function_names(tokens: list[Token]) -> list[Token]:
    """``atan2`` llega como ``atan`` + ``2``: se unen si la función existe."""
    joined: list[Token] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        following = tokens[index + 1] if index + 1 < len(tokens) else None
        if (
            token.kind == "ident"
            and following is not None
            and following.kind == "number"
            and following.position == token.position + len(token.value)
            and f"{token.value}{following.value}" in FUNCTIONS
        ):
            joined.append(Token("ident", f"{token.value}{following.value}", token.position))
            index += 2
            continue
        joined.append(token)
        index += 1
    return joined


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------


class Parser:
    """Parser descendente recursivo para el subconjunto de LaTeX soportado."""

    def __init__(self, source: str, limits: Limits = DEFAULT_LIMITS) -> None:
        self.source = source
        self.limits = limits
        self.tokens = tokenize(source)
        self.index = 0

    # -- utilidades de tokens ------------------------------------------------

    def peek(self, offset: int = 0) -> Token:
        return self.tokens[min(self.index + offset, len(self.tokens) - 1)]

    def advance(self) -> Token:
        token = self.peek()
        if token.kind != "end":
            self.index += 1
        return token

    def at_end(self) -> bool:
        return self.peek().kind == "end"

    def check(self, kind: str, value: str) -> bool:
        token = self.peek()
        return token.kind == kind and token.value == value

    def check_any(self, kind: str, values: frozenset[str] | set[str]) -> bool:
        token = self.peek()
        return token.kind == kind and token.value in values

    def accept(self, kind: str, value: str) -> bool:
        if self.check(kind, value):
            self.advance()
            return True
        return False

    def accept_command(self, *names: str) -> bool:
        token = self.peek()
        if token.kind == "command" and token.value in names:
            self.advance()
            return True
        return False

    def fail(self, message: str) -> CalculationError:
        return CalculationError(message)

    # -- gramática ------------------------------------------------------------

    def parse(self) -> Any:
        if self.at_end():
            raise self.fail("Escribe una expresión para calcular.")
        node = self.parse_implication()
        if not self.at_end():
            leftover = self.source[self.peek().position :][:24].strip()
            raise self.fail(f"Hay un trozo sin entender al final: «{leftover}».")
        return node

    def parse_implication(self) -> Any:
        node = self.parse_disjunction()
        while self.check_any(
            "command", {r"\implies", r"\iff", r"\Rightarrow", r"\Leftrightarrow", r"\to", r"\rightarrow"}
        ):
            op = self.advance().value
            right = self.parse_disjunction()
            kind = "iff" if op in (r"\iff", r"\Leftrightarrow") else "implies"
            node = Implication(kind, node, right)
        return node

    def parse_disjunction(self) -> Any:
        node = self.parse_conjunction()
        while self.check_any("command", {r"\lor", r"\vee"}) or self.check("ident", "or"):
            self.advance()
            node = Logical("or", (node, self.parse_conjunction()))
        return node

    def parse_conjunction(self) -> Any:
        node = self.parse_relation()
        while self.check_any("command", {r"\land", r"\wedge"}) or self.check("ident", "and"):
            self.advance()
            node = Logical("and", (node, self.parse_relation()))
        return node

    def parse_relation(self) -> Any:
        operands = [self.parse_additive()]
        operators: list[str] = []
        while True:
            operator = self.match_relation()
            if operator is None:
                break
            operators.append(operator)
            operands.append(self.parse_additive())
        if not operators:
            return operands[0]
        parts = [
            Relation(op, left, right)
            for op, left, right in zip(operators, operands, operands[1:])
        ]
        return parts[0] if len(parts) == 1 else Logical("and", tuple(parts))

    def match_relation(self) -> str | None:
        token = self.peek()
        if token.kind == "command" and token.value in RELATION_COMMANDS:
            self.advance()
            return RELATION_COMMANDS[token.value]
        if token.kind == "command" and token.value == r"\notin":
            self.advance()
            return "notin"
        if token.kind == "symbol" and token.value in ("=", "<", ">"):
            self.advance()
            return token.value
        if (
            token.kind == "symbol"
            and token.value == "!"
            and self.peek(1).kind == "symbol"
            and self.peek(1).value == "="
        ):
            self.advance()
            self.advance()
            return "!="
        if token.kind == "ident" and token.value in ("in", "subset", "supset", "subseteq", "supseteq"):
            self.advance()
            return token.value
        return None

    def parse_additive(self, stop_at_differential: bool = False) -> Any:
        node = self.parse_multiplicative(stop_at_differential)
        while True:
            token = self.peek()
            operator: str | None = None
            if token.kind == "symbol" and token.value in ("+", "-"):
                operator = token.value
            elif token.kind == "command" and token.value in (r"\pm", r"\mp"):
                raise self.fail("«\\pm» se calcula solo: la calculadora muestra los dos resultados.")
            elif token.kind == "command" and token.value in (r"\cup", r"\oplus"):
                operator = "cup" if token.value == r"\cup" else "+"
            elif token.kind == "ident" and token.value == "union":
                operator = "cup"
            elif token.kind == "command" and token.value in (r"\bmod", r"\mod", r"\pmod"):
                operator = "mod"
            elif token.kind == "ident" and token.value == "mod":
                operator = "mod"
            if operator is None:
                break
            self.advance()
            node = Binary(operator, node, self.parse_multiplicative(stop_at_differential))
        return node

    def parse_multiplicative(self, stop_at_differential: bool = False) -> Any:
        node = self.parse_unary(stop_at_differential)
        while True:
            token = self.peek()
            operator: str | None = None
            if token.kind == "command" and token.value in (r"\cdot", r"\times", r"\ast", r"\ast"):
                operator = "*"
            elif token.kind == "command" and token.value in (r"\div", r"\over"):
                operator = "/"
            elif token.kind == "command" and token.value == r"\setminus":
                operator = "setminus"
            elif token.kind == "command" and token.value == r"\cap":
                operator = "cap"
            elif token.kind == "ident" and token.value == "intersection":
                operator = "cap"
            elif token.kind == "symbol" and token.value in ("*", "/"):
                operator = token.value
            if operator is not None:
                self.advance()
                node = Binary(operator, node, self.parse_unary(stop_at_differential))
                continue
            if self.at_differential():
                if stop_at_differential:
                    break
                raise self.fail(
                    "«d» se interpreta como diferencial. Usa «d\\cdot x» si es una variable."
                )
            if self.starts_value(self.peek()):
                node = Binary("*", node, self.parse_unary(stop_at_differential))
                continue
            break
        return node

    def parse_unary(self, stop_at_differential: bool = False) -> Any:
        token = self.peek()
        if token.kind == "symbol" and token.value in ("+", "-"):
            self.advance()
            return Unary(token.value, self.parse_unary(stop_at_differential))
        if token.kind == "command" and token.value in (r"\neg", r"\lnot", r"\not"):
            self.advance()
            return Logical("not", (self.parse_unary(stop_at_differential),))
        if token.kind == "ident" and token.value == "not":
            self.advance()
            return Logical("not", (self.parse_unary(stop_at_differential),))
        return self.parse_power(stop_at_differential)

    def parse_power(self, stop_at_differential: bool = False) -> Any:
        base = self.parse_postfix(stop_at_differential)
        if self.check("symbol", "^"):
            self.advance()
            return Binary("**", base, self.parse_unary(stop_at_differential))
        return base

    def parse_postfix(self, stop_at_differential: bool = False) -> Any:
        node = self.parse_primary(stop_at_differential)
        while True:
            token = self.peek()
            if token.kind == "symbol" and token.value == "!":
                if self.peek(1).kind == "symbol" and self.peek(1).value == "=":
                    break  # es el operador !=, que vive en el nivel de relación
                self.advance()
                node = Factorial(node)
                continue
            if token.kind == "symbol" and token.value == "%":
                self.advance()
                node = Scale(node, "percent")
                continue
            if token.kind == "command" and token.value in (
                r"\%", r"\percent", r"\permille", r"\degree", r"\deg",
            ):
                self.advance()
                factor = {
                    r"\%": "percent", r"\percent": "percent",
                    r"\permille": "permille", r"\degree": "degree", r"\deg": "degree",
                }[token.value]
                node = Scale(node, factor)
                continue
            if token.kind == "command" and token.value == r"\prime":
                self.advance()
                if isinstance(node, Symbol):
                    node = Symbol(f"{node.name}'", f"{node.latex or _identifier_latex(node.name)}'")
                continue
            break
        return node

    # -- primarios -----------------------------------------------------------

    def parse_primary(self, stop_at_differential: bool = False) -> Any:
        token = self.advance()
        if token.kind == "number":
            return Number(token.value)
        if token.kind == "ident":
            return self.parse_ident(token)
        if token.kind == "symbol":
            return self.parse_symbol(token, stop_at_differential)
        if token.kind == "command":
            return self.parse_command(token, stop_at_differential)
        raise self.fail("La expresión está incompleta.")

    def parse_ident(self, token: Token) -> Any:
        name = token.value
        following = self.peek()
        has_parenthesis = following.kind == "symbol" and following.value == "("
        if name in FUNCTIONS and has_parenthesis:
            return Call(name, tuple(self.parse_argument_list()))
        if name in CONSTANT_NAMES and not has_parenthesis:
            return self.apply_scripts(Call(name, ()))
        if name in _PREFIX_FUNCTION_NAMES and self.starts_value(following):
            return Call(name, (self.parse_unary(),))
        if name in ("union", "intersection"):
            raise self.fail(f"«{name}» debe ir entre dos conjuntos.")
        return self.apply_scripts(Symbol(name, _identifier_latex(name)))

    def parse_symbol(self, token: Token, stop_at_differential: bool) -> Any:
        value = token.value
        if value == "(":
            node = self.parse_expression()
            self.expect_closer(")")
            return self.apply_scripts(node)
        if value == "{":
            return self.apply_scripts(self.parse_group_or_set("}"))
        if value == "[":
            return self.parse_matrix()
        if value == "|":
            node = self.parse_expression()
            self.expect_closer("|")
            return Call("abs", (node,))
        if value in ("+", "-"):
            raise self.fail("Falta un valor antes del signo.")
        if value == "!":
            raise self.fail("No hay nada a la izquierda del signo «!».")
        if value in (",", ";"):
            raise self.fail("Hay un separador sin contenido.")
        if value == "^":
            raise self.fail("Falta la base de la potencia.")
        if value == "_":
            raise self.fail("Falta el símbolo al que pertenece el subíndice.")
        raise self.fail(f"No se reconoce el carácter «{value}».")

    def parse_command(self, token: Token, stop_at_differential: bool) -> Any:
        name = token.value

        if name in IGNORED_COMMANDS:
            return self.parse_primary(stop_at_differential)

        # --- delimitadores -----------------------------------------------------
        if name == r"\left":
            return self.parse_left_group()
        if name == r"\middle":
            self.consume_delimiter()
            return self.parse_primary(stop_at_differential)
        if name in (r"\lvert", r"\vert"):
            node = self.parse_expression()
            self.expect_closer(r"\rvert" if name == r"\lvert" else r"\rvert")
            return Call("abs", (node,))
        if name in (r"\lVert", r"\Vert"):
            node = self.parse_expression()
            self.expect_closer(r"\rVert" if name == r"\lVert" else r"\rVert")
            return node
        if name == r"\|":
            node = self.parse_expression()
            self.expect_closer(r"\|")
            return node
        if name == r"\lfloor":
            node = self.parse_expression()
            self.expect_closer(r"\rfloor")
            return Call("floor", (node,))
        if name == r"\lceil":
            node = self.parse_expression()
            self.expect_closer(r"\rceil")
            return Call("ceil", (node,))

        # --- estructuras -------------------------------------------------------
        if name in (r"\frac", r"\dfrac", r"\tfrac", r"\cfrac"):
            numerator = self.parse_argument()
            denominator = self.parse_argument()
            return Binary("/", numerator, denominator)
        if name == r"\sqrt":
            return self.parse_sqrt()
        if name == r"\cbrt":
            return Call("cbrt", (self.parse_argument(),))
        if name in (r"\binom", r"\choose"):
            return Call("binom", (self.parse_argument(), self.parse_argument()))
        if name == r"\begin":
            return self.parse_environment()
        if name == r"\{":  # \{ … \}
            return self.parse_set()
        if name in (r"\emptyset", r"\varnothing"):
            return Call("emptyset", ())

        # -- operadores grandes ------------------------------------------------
        if name in (r"\sum", r"\prod", r"\int", r"\iint", r"\oint", r"\bigcup", r"\bigcap"):
            return self.parse_big_operator(name)
        if name in (r"\lim", r"\min", r"\max"):
            return self.parse_limiting_operator(name)
        if name in (r"\forall", r"\exists"):
            return self.parse_quantifier(name)

        # --- símbolos y funciones----------------------------------------------
        if name in CONSTANT_COMMANDS:
            return self.apply_scripts(Call(CONSTANT_COMMANDS[name], ()))
        if name in FUNCTION_COMMANDS:
            return self.parse_named_function(name)
        if name in GREEK_SYMBOLS:
            symbol_name, latex = GREEK_SYMBOLS[name]
            return self.apply_scripts(Symbol(symbol_name, latex))
        if name in (r"\overline", r"\bar"):
            return Call("conj", (self.parse_argument(),))
        if name in ACCENT_COMMANDS:
            return self.parse_accent(ACCENT_COMMANDS[name])
        if name == r"\mathbb":
            return self.parse_blackboard()
        if name in (r"\mathrm", r"\mathit", r"\mathsf", r"\mathtt", r"\mathbf", r"\bm",
                    r"\operatorname", r"\text", r"\textbf", r"\textit", r"\mathrm"):
            return self.parse_text_name()
        if name in (r"\ldots", r"\cdots", r"\dots"):
            return Symbol("ellipsis", r"\ldots")
        if name == r"\vdots":
            return Symbol("vdots", r"\vdots")

        if name in NON_VALUE_COMMANDS:
            raise self.fail(f"«{name}» necesita un valor a su izquierda.")
        raise self.fail(f"No se reconoce el comando «{name}».")

    # -- grupos y delimitadores ---------------------------------------------

    def parse_left_group(self) -> Any:
        delimiter = self.consume_delimiter()
        if delimiter == r"\{":
            return self.parse_set(close=r"\right\}")
        if delimiter in ("|", r"\lvert", r"\vert", r"\mid"):
            node = self.parse_expression()
            self.expect_closer(r"\right")
            return Call("abs", (node,))
        if delimiter in ("(", "["):
            # \left(1,2,3\right) también sirve para escribir vectores y filas.
            items = [self.parse_expression()]
            while self.accept("symbol", ","):
                items.append(self.parse_expression())
            self.expect_closer(r"\right")
            if len(items) == 1:
                return items[0]
            # ([1,2],[3,4]) apila filas; (1,2,3) es un vector de una fila.
            if all(isinstance(item, MatrixLiteral) and len(item.rows) == 1 for item in items):
                return MatrixLiteral(tuple(item.rows[0] for item in items))
            return MatrixLiteral((tuple(items),))
        node = self.parse_expression()
        self.expect_closer(r"\right")
        return node

    def consume_delimiter(self) -> str:
        token = self.peek()
        if token.kind == "symbol" and token.value in "()[]{}|./":
            self.advance()
            return token.value
        if token.kind == "command" and token.value in (
            r"\{", r"\}", r"\langle", r"\rangle", r"\lvert", r"\rvert",
            r"\lVert", r"\rVert", r"\lfloor", r"\rfloor", r"\lceil", r"\rceil",
            r"\vert", r"\Vert", r"\|",
        ):
            self.advance()
            return token.value
        raise self.fail("Falta el delimitador después de «\\left».")

    def expect_closer(self, closer: str) -> None:
        """Consume el cierre de un grupo, tolerando el ``\\right`` de MathLive."""
        token = self.peek()
        if closer.startswith(r"\right"):
            delimiter = closer[len(r"\right") :]
            if token.kind == "command" and token.value == r"\right":
                self.advance()
                if delimiter:
                    following = self.peek()
                    if following.kind == "command" and following.value == delimiter:
                        self.advance()
                    elif following.kind == "symbol" and delimiter == r"\}" and following.value == "}":
                        self.advance()
                elif not (self.peek().kind == "symbol" and self.peek().value == "."):
                    if self.peek().kind in ("command", "symbol"):
                        self.consume_delimiter()
                return
            raise self.fail("Falta «\\right» para cerrar el grupo.")
        if token.kind == "command" and token.value == closer:
            self.advance()
            return
        if token.kind == "symbol" and token.value == closer:
            self.advance()
            return
        if token.kind == "command" and closer == r"\right":
            self.expect_closer(r"\right")
            return
        if token.kind == "command" and token.value == r"\right":
            self.expect_closer(r"\right")
            return
        raise self.fail(f"Falta el cierre «{closer}» de la expresión.")

    def parse_group(self, opener: str, closer: str, content_parser: Any = None) -> Any:
        if not self.accept("symbol", opener):
            raise self.fail(f"Se esperaba «{opener}».")
        node = content_parser() if content_parser else self.parse_expression()
        self.expect_closer(closer)
        return node

    def parse_expression(self) -> Any:
        return self.parse_implication()

    # -- elementos concretos -------------------------------------------------

    def parse_sqrt(self) -> Any:
        degree: Any = None
        if self.check("symbol", "["):
            self.advance()
            degree = self.parse_expression()
            self.expect_closer("]")
        radicand = self.parse_argument()
        if degree is None:
            return Call("sqrt", (radicand,))
        return Binary("**", radicand, Binary("/", Number("1"), degree))

    def parse_matrix(self) -> MatrixLiteral:
        rows: list[list[Any]] = [[]]
        if self.check("symbol", "]"):
            raise self.fail("La matriz está vacía.")
        while True:
            rows[-1].append(self.parse_expression())
            if self.accept("symbol", ","):
                continue
            if self.accept("symbol", ";"):
                rows.append([])
                continue
            break
        self.expect_closer("]")
        return self._build_matrix(rows)

    def parse_environment(self) -> MatrixLiteral:
        if not self.accept("symbol", "{"):
            raise self.fail("«\\begin» necesita un nombre de entorno.")
        name_token = self.advance()
        name = name_token.value
        self.expect_closer("}")
        if name not in _SAFE_ENVIRONMENTS:
            raise self.fail(f"El entorno «{name}» no está soportado.")
        rows: list[list[Any]] = [[]]
        while not self.check("command", r"\end"):
            if self.at_end():
                raise self.fail(f"Falta «\\end{{{name}}}».")
            rows[-1].append(self.parse_expression())
            if self.accept_command(r"\\", r"\cr"):
                rows.append([])
                continue
            if self.accept("symbol", "&"):
                continue
            if self.check("command", r"\end"):
                break
            raise self.fail("Símbolo inesperado dentro de la matriz.")
        self.advance()  # \end
        self.accept("symbol", "{")
        self.advance()
        self.expect_closer("}")
        return self._build_matrix(rows)

    def _build_matrix(self, rows: list[list[Any]]) -> MatrixLiteral:
        while len(rows) > 1 and not rows[-1]:
            rows.pop()
        if any(not row for row in rows):
            raise self.fail("Hay una fila vacía en la matriz.")
        total = sum(len(row) for row in rows)
        if total > self.limits.max_matrix_cells:
            raise self.fail("La matriz es demasiado grande.")
        return MatrixLiteral(tuple(tuple(row) for row in rows))

    def parse_group_or_set(self, closer: str) -> Any:
        """``{x+1}`` es un grupo; ``{n | n > 0}`` es un conjunto por propiedad."""
        items: list[Any] = []
        conditions: list[Any] = []
        binder: Any = None
        saw_divider = False
        while True:
            node = self.parse_relation()
            if self.check("command", r"\mid") or self.check("symbol", "|"):
                self.advance()
                saw_divider = True
                binder = items.pop() if items else node
                conditions.append(self.parse_relation())
                while self.accept("symbol", ","):
                    conditions.append(self.parse_relation())
                break
            items.append(node)
            if self.accept("symbol", ","):
                continue
            break
        self.expect_closer(closer)
        if saw_divider:
            condition = conditions[0] if len(conditions) == 1 else Logical("and", tuple(conditions))
            return SetBuilder(binder, condition)
        if len(items) > 1:
            raise self.fail("Aquí las llaves agrupan un solo valor; un conjunto se escribe \\{ … \\}.")
        return items[0]

    def parse_set(self, close: str = r"\}") -> Any:
        items: list[Any] = []
        conditions: list[Any] = []
        binder: Any = None
        while True:
            node = self.parse_relation()
            if self.check("command", r"\mid") or (self.check("symbol", "|") and not items):
                self.advance()
                binder = items.pop() if items else node
                conditions.append(self.parse_relation())
                while self.accept("symbol", ","):
                    conditions.append(self.parse_relation())
                break
            items.append(node)
            if self.accept("symbol", ","):
                continue
            break
        self.expect_closer(close)
        if conditions:
            condition = conditions[0] if len(conditions) == 1 else Logical("and", tuple(conditions))
            return SetBuilder(binder, condition)
        if not items:
            return Call("emptyset", ())
        return SetLiteral(tuple(items))

    def parse_big_operator(self, command: str) -> BigOperator:
        op = command[1:]
        lower: Any = None
        upper: Any = None
        var: str | None = None
        if self.check("symbol", "_"):
            self.advance()
            lower = self.parse_limit_group()
            if isinstance(lower, tuple):
                var_node, lower = lower
                var = render_name(var_node)
        if self.check("symbol", "^"):
            self.advance()
            upper = self.parse_bound()
        body = self.parse_additive(stop_at_differential=True)
        differential = self.consume_differential()
        if op in ("int", "iint", "oint") and differential:
            var = differential
        return BigOperator(op, var, lower, upper, body)

    def parse_limiting_operator(self, command: str) -> BigOperator:
        op = command[1:]
        var: str | None = None
        target: Any = None
        direction = "+"
        if not self.check("symbol", "_"):
            raise self.fail(f"«{command}» necesita un subíndice del tipo \\{command}_{{x\\to 0}}…")
        self.advance()
        if self.accept("symbol", "{"):
            node = self.parse_index_variable()
            var = node.name
            if not self.accept_command(r"\to", r"\rightarrow", r"\mapsto", r"\rightarrow"):
                raise self.fail(f"Usa «\\{command}_{{variable \\to valor}}».")
            target = self.parse_bound()
            if self.check("symbol", "^"):
                self.advance()
                sign = self.peek()
                if sign.kind == "symbol" and sign.value in ("+", "-"):
                    self.advance()
                    direction = sign.value
            self.expect_closer("}")
        else:
            raise self.fail(f"«{command}» necesita un subíndice del tipo \\{command}_{{x\\to 0}}…")
        body = self.parse_additive()
        return BigOperator("limit" if op == "lim" else op, var, target, None, body, direction)

    def parse_quantifier(self, command: str) -> Quantifier:
        op = command[1:]
        token = self.peek()
        if token.kind != "ident":
            raise self.fail(f"«\\{op}» necesita una variable: \\{op} x …")
        self.advance()
        domain: Any = None
        if self.accept_command(r"\in") or self.accept("ident", "in"):
            domain = self.parse_additive()
        self.accept("symbol", ":")
        self.accept("symbol", ",")
        body = self.parse_additive()
        return Quantifier(op, token.value, domain, body)

    def parse_named_function(self, command: str) -> Any:
        function = FUNCTION_COMMANDS[command]
        if function == "log" and self.check("symbol", "_"):
            self.advance()
            base = self.parse_bound()
            return Call("log", (self.parse_argument(), base))
        if self.check("symbol", "{"):
            self.advance()
            argument = self.parse_expression()
            self.expect_closer("}")
            return Call(function, (argument,))
        if self.check("symbol", "("):
            return Call(function, tuple(self.parse_argument_list()))
        return Call(function, (self.parse_unary(),))

    def parse_conjugate(self) -> Any:
        return Call("conj", (self.parse_argument(),))

    def parse_accent(self, accent: str) -> Any:
        inner = self.parse_argument()
        name = _identifier_latex(render_name(inner))
        return Symbol(f"{accent}{{{name}}}", f"{accent}{{{name}}}")

    def parse_blackboard(self) -> Any:
        if self.accept("symbol", "{"):
            token = self.peek()
            if token.kind not in ("ident", "number"):
                raise self.fail("«\\mathbb» espera una letra: \\mathbb{R}.")
            self.advance()
            self.expect_closer("}")
            letter = token.value
            if letter in BB_FONT_SETS:
                return BB_FONT_SETS[letter]
            return Symbol(f"mathbb_{letter}", f"\\mathbb{{{letter}}}")
        return self.parse_argument()

    def parse_text_name(self) -> Any:
        if not self.accept("symbol", "{"):
            content = self.advance().value
        else:
            pieces: list[str] = []
            while not self.check("symbol", "}"):
                if self.at_end():
                    raise self.fail("Falta la llave de cierre.")
                token = self.advance()
                if token.kind == "command":
                    pieces.append(GREEK_SYMBOLS.get(token.value, (None, token.value))[1])
                else:
                    pieces.append(token.value)
            self.expect_closer("}")
            content = "".join(pieces).strip()
        if not content:
            raise self.fail("«\\mathrm» necesita contenido.")
        if content in CONSTANT_NAMES:
            return self.apply_scripts(Call(content, ()))
        if content in FUNCTIONS:
            if self.check("symbol", "("):
                return Call(content, tuple(self.parse_argument_list()))
            if self.accept("symbol", "{"):
                argument = self.parse_expression()
                self.expect_closer("}")
                return Call(content, (argument,))
            if self.starts_value(self.peek()):
                return Call(content, (self.parse_unary(),))
        return self.apply_scripts(Symbol(content, _identifier_latex(content)))

    def parse_argument_list(self) -> list[Any]:
        """Argumentos de una llamada: el ``(`` debe ser el token actual."""
        if not self.accept("symbol", "("):
            raise self.fail("Se esperaba un paréntesis tras el nombre de la función.")
        arguments: list[Any] = []
        if self.accept("symbol", ")"):
            return arguments
        while True:
            arguments.append(self.parse_expression())
            if self.accept("symbol", ","):
                continue
            self.expect_closer(")")
            return arguments

    def parse_argument(self) -> Any:
        token = self.peek()
        if token.kind == "symbol" and token.value == "{":
            self.advance()
            node = self.parse_expression()
            self.expect_closer("}")
            return node
        if token.kind == "symbol" and token.value == "(":
            self.advance()
            node = self.parse_expression()
            self.expect_closer(")")
            return node
        if self.starts_value(token):
            return self.parse_postfix()
        raise self.fail("Falta un valor (usa llaves, por ejemplo \\frac{1}{2}).")

    def parse_index_variable(self) -> Symbol:
        """Variable de índice: siempre un símbolo, aunque se llame ``i`` o ``e``."""
        token = self.peek()
        if token.kind != "ident":
            raise self.fail("Los límites empiezan por una variable, por ejemplo i=1.")
        self.advance()
        return Symbol(token.value, _identifier_latex(token.value))

    def parse_limit_group(self) -> Any:
        """``\\sum_{i=1}^{n}``: devuelve ``(variable, límite)`` o un nodo simple."""
        if not self.accept("symbol", "{"):
            return self.parse_bound()
        node = self.parse_index_variable()
        if self.accept("symbol", "="):
            upper = self.parse_additive()
            self.expect_closer("}")
            return (node, upper)
        self.expect_closer("}")
        return node

    def parse_bound(self) -> Any:
        token = self.peek()
        if token.kind == "symbol" and token.value in ("+", "-"):
            self.advance()
            return Unary(token.value, self.parse_postfix())
        return self.parse_postfix()

    # -- subíndices ----------------------------------------------------------

    def apply_scripts(self, node: Any) -> Any:
        if not self.check("symbol", "_"):
            return node
        self.advance()
        subscript = self.parse_argument()
        if not isinstance(node, Symbol):
            raise self.fail("Los subíndices solo se pueden poner sobre símbolos.")
        base_latex = node.latex or _identifier_latex(node.name)
        return Symbol(
            f"{node.name}_{render_name(subscript)}",
            f"{base_latex}_{{{_node_latex(subscript)}}}",
        )

    # -- diferenciales -------------------------------------------------------

    def differential_end(self) -> int | None:
        """Posición final del diferencial ``dx`` si aparece a continuación."""
        index = self.index
        tokens = self.tokens
        while index < len(tokens) and tokens[index].kind == "command" and tokens[index].value in _SPACING_COMMANDS:
            index += 1
        token = tokens[index]
        if token.kind == "command" and token.value in (r"\mathrm", r"\text", r"\operatorname", r"\mathnormal"):
            following = tokens[index + 1] if index + 1 < len(tokens) else None
            if following is not None and following.kind == "ident" and following.value == "d":
                return index + 2 if index + 2 < len(tokens) else None
            return None
        if token.kind != "ident":
            return None
        value = token.value
        if len(value) > 1 and value[0] == "d" and value.isidentifier():
            return index + 1
        if value == "d":
            following = tokens[index + 1] if index + 1 < len(tokens) else None
            if following is not None and following.kind == "ident" and following.value != "d":
                return index + 2
        return None

    def at_differential(self) -> bool:
        return self.differential_end() is not None

    def consume_differential(self) -> str | None:
        end = self.differential_end()
        if end is None:
            return None
        name = self.tokens[end - 1].value if end - 1 < len(self.tokens) else "x"
        if len(name) > 1 and name.startswith("d"):
            name = name[1:]
        self.index = end
        return name

    # -- utilidades ----------------------------------------------------------

    def starts_value(self, token: Token | None) -> bool:
        if token is None:
            return False
        if token.kind == "number":
            return True
        if token.kind == "ident":
            return token.value not in _KEYWORD_OPERATORS
        if token.kind == "symbol":
            return token.value in ("(", "[", "{")
        if token.kind == "command":
            if token.value in NON_VALUE_COMMANDS:
                return False
            return token.value in VALUE_COMMANDS
        return False


# ---------------------------------------------------------------------------
# Utilidades sobre el árbol
# ---------------------------------------------------------------------------


def _identifier_latex(name: str) -> str:
    """Convierte un identificador en LaTeX legible (``x_1`` -> ``x_{1}``)."""
    if "_" in name:
        base, _, index = name.partition("_")
        return f"{base}_{{{index}}}"
    if len(name) > 1 and name.isalpha():
        return f"\\mathit{{{name}}}"
    return name


def _node_latex(node: Any) -> str:
    if isinstance(node, Number):
        return node.text
    if isinstance(node, Symbol):
        return node.latex or _identifier_latex(node.name)
    if isinstance(node, Unary):
        return f"{node.op}{_node_latex(node.operand)}"
    if isinstance(node, Scale):
        return f"{_node_latex(node.operand)}\\{node.factor}"
    if isinstance(node, Factorial):
        return f"{_node_latex(node.operand)}!"
    if isinstance(node, Binary):
        return f"{_node_latex(node.left)} {node.op} {_node_latex(node.right)}"
    if isinstance(node, Call):
        joined = ", ".join(_node_latex(argument) for argument in node.args)
        return f"{node.name}\\left({joined}\\right)"
    return render_name(node)


def render_name(node: Any) -> str:
    """Nombre legible de un nodo, para construir símbolos con subíndices."""
    if isinstance(node, Number):
        return node.text
    if isinstance(node, Symbol):
        return node.name
    if isinstance(node, Unary):
        return f"-{render_name(node.operand)}" if node.op == "-" else render_name(node.operand)
    if isinstance(node, Scale):
        return render_name(node.operand)
    if isinstance(node, Factorial):
        return f"{render_name(node.operand)}!"
    if isinstance(node, Binary):
        left, right = render_name(node.left), render_name(node.right)
        if node.op in ("+", "-"):
            return f"{left}{node.op}{right}"
        if node.op == "*":
            return f"{left}*{right}"
        if node.op == "/":
            return f"({left})/({right})"
        if node.op == "**":
            return f"({left})**({right})"
        return f"({left}){node.op}({right})"
    if isinstance(node, Relation):
        return f"{render_name(node.left)}{node.op}{render_name(node.right)}"
    if isinstance(node, Call):
        return f"{node.name}({','.join(render_name(argument) for argument in node.args)})"
    return "expr"


def count_nodes(node: Any) -> int:
    """Número de nodos del árbol; sirve para aplicar los límites."""
    total = 0
    stack: list[Any] = [node]
    while stack:
        current = stack.pop()
        total += 1
        if isinstance(current, (list, tuple)):
            stack.extend(current)
        elif isinstance(current, BigOperator):
            stack.extend(v for v in (current.lower, current.upper, current.body) if v is not None)
        elif isinstance(current, SetLiteral):
            stack.extend(current.items)
        elif isinstance(current, MatrixLiteral):
            stack.extend(row for row in current.rows)
        elif isinstance(current, Logical):
            stack.extend(current.args)
        elif isinstance(current, Call):
            stack.extend(current.args)
        elif isinstance(current, (Binary, Relation, Implication)):
            stack.extend((current.left, current.right))
        elif isinstance(current, (Unary, Scale, Factorial)):
            stack.append(current.operand)
        elif isinstance(current, SetBuilder):
            stack.extend(v for v in (current.binder, current.condition, current.domain) if v is not None)
        elif isinstance(current, Quantifier):
            stack.extend(v for v in (current.domain, current.body) if v is not None)
    return total


def parse(source: str, limits: Limits = DEFAULT_LIMITS) -> Any:
    """Analiza una expresión LaTeX y devuelve su árbol."""
    if not isinstance(source, str) or not source.strip():
        raise CalculationError("Escribe una expresión para calcular.")
    if len(source) > limits.max_length:
        raise CalculationError("La expresión es demasiado larga.")
    tree = Parser(source, limits).parse()
    if count_nodes(tree) > limits.max_nodes:
        raise CalculationError("La expresión tiene demasiadas operaciones.")
    return tree


#: Reexportado para el evaluador.
CONSTANT_TABLE = CONSTANTS