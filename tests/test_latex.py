"""Pruebas del analizador de LaTeX."""

from __future__ import annotations

import pytest

from forma.errors import CalculationError
from forma.latex import BigOperator, Binary, Call, Number, Symbol, count_nodes, parse, tokenize
from forma.symbols import FUNCTIONS


def test_tokeniza_comandos_y_numeros() -> None:
    tokens = tokenize(r"\frac{1}{2}")
    assert [token.kind for token in tokens][:3] == ["command", "symbol", "number"]


def test_precedencia_de_la_potencia() -> None:
    assert parse("2^3^2") == Binary("**", Number("2"), Binary("**", Number("3"), Number("2")))
    assert parse("-2^2") == parse("-(2^2)")


def test_fracciones_anidadas() -> None:
    node = parse(r"\frac{\frac{1}{2}}{\frac{1}{3}}")
    assert isinstance(node, Binary)
    assert node.op == "/"


def test_raiz_con_indice() -> None:
    raiz = parse(r"\sqrt[3]{27}")
    assert isinstance(raiz, Binary) and raiz.op == "**"
    assert parse(r"\sqrt{2}").name == "sqrt"


def test_diferencial_detiene_el_cuerpo() -> None:
    node = parse(r"\int x^2 dx")
    assert isinstance(node, BigOperator)
    assert node.var == "x"
    assert node.body.op == "**" and node.body.left.name == "x"


def test_limite_con_sentido() -> None:
    node = parse(r"\lim_{x\to 0^+} x")
    assert isinstance(node, BigOperator)
    assert node.direction == "+"
    assert node.var == "x"


def test_multiplicacion_implicita_entre_comandos() -> None:
    assert isinstance(parse(r"2\pi"), Binary)
    assert isinstance(parse(r"\sin x \cos x"), Binary)


def test_acentos_y_subindices() -> None:
    node = parse(r"\vec{v}")
    assert isinstance(node, Symbol)
    assert node.name == r"\vec{v}"
    assert parse("x_{1}").name == "x_1"


def test_limite_de_nodos() -> None:
    with pytest.raises(CalculationError):
        parse("x+" * 2000 + "x")


def test_conteo_de_nodos() -> None:
    assert count_nodes(parse("1+2")) == 3
    assert count_nodes(parse("1+2*3")) == 5


#: Botones que son trozos de una expresión y no se analizan solos.
OPERATOR_ONLY = {
    "+", "-", r"\times", r"\div", r"\cdot", "=", r"\ne", "<", ">", r"\le",
    r"\ge", r"\approx", r"\pm", r"\%", "!", r"\in", r"\notin", r"\subset",
    r"\subseteq", r"\cup", r"\cap", r"\land", r"\lor", r"\neg", r"\implies",
    r"\iff", r"\partial", r"\exists", r"\forall", "^{#?}", "^2",
    r"\exists #?", r"\forall #?",
}


def test_todos_los_botones_de_la_paleta_se_entienden() -> None:
    """Lo que la interfaz ofrece debe poder analizarse (o ser un operador suelto)."""
    from forma.palette import SYMBOLS

    for entry in SYMBOLS:
        if entry["latex"] in OPERATOR_ONLY:
            continue
        latex = entry["latex"].replace("#?", "x")
        if r"\pm" in latex:  # el servidor lo parte en dos ramas antes de analizar
            latex = latex.replace(r"\pm", "+")
        try:
            parse(latex)
        except CalculationError as error:  # pragma: no cover - ayuda para depurar
            raise AssertionError(f"{latex!r} no se analiza: {error}") from None


def test_llamadas_por_nombre() -> None:
    assert isinstance(parse("sin(2)"), Call)
    assert parse("sin(2)").name in FUNCTIONS