"""Pruebas de la API pública de cálculo."""

from __future__ import annotations

import pytest

from forma.calculator import calculate
from forma.errors import CalculationError


@pytest.fixture(scope="module")
def sandbox_timeout() -> float:
    return 0.4


def exact(source: str) -> str:
    return calculate(source)["exact"]


def approx(source: str):
    return calculate(source)["approx"]


# --- números exactos -------------------------------------------------------


@pytest.mark.parametrize(
    "source, expected",
    [
        (r"\frac{1}{3}+\frac{1}{6}", "1/2"),
        (r"0.1+0.2", "3/10"),          # sin errores de coma flotante
        ("1.5e3", "1500"),
        (r"2^{10}", "1024"),
        (r"\sqrt{12+18}", "sqrt(30)"),
        (r"\sqrt[3]{27}", "3"),
        (r"\sqrt[4]{16}", "2"),
        (r"10/3", "10/3"),
        ("50%", "1/2"),               # porcentaje
        (r"50\%", "1/2"),
        ("15%", "3/20"),
        (r"180\degree", "pi"),
        (r"\sin{30\degree}", "1/2"),
        ("e^{i*pi}+1", "0"),
        ("(1+i)^8", "16"),
        ("i^2", "-1"),
        (r"7\bmod 3", "1"),
        ("7 mod 3", "1"),
        ("(2+3)!", "120"),
        ("5!", "120"),
        (r"\binom{5}{2}", "10"),
    ],
)
def test_numeros(source: str, expected: str) -> None:
    assert exact(source) == expected


def test_logaritmos_tienen_la_base_correcta() -> None:
    assert exact(r"\log{100}") == "2"        # base 10
    assert exact(r"\ln{e}") == "1"            # natural
    assert exact(r"\log_{2}{8}") == "3"       # base explícita


def test_multiplicacion_implicita() -> None:
    assert exact("2x") == "2*x"
    assert exact("sin x") == "sin(x)"
    assert exact(r"\sqrt 2") == "sqrt(2)"
    assert exact(r"2\pi") == "2*pi"
    assert exact("3(x+1)") == "3*x + 3"


def test_complejos_se_muestran_como_tales() -> None:
    assert approx("i^i") == "0.207879576351"
    assert approx(r"(-8)^{1/3}") == "1 + 1.73205080757i"


def test_aproximaciones_legibles() -> None:
    assert approx("10/3") == "3.33333333333"
    assert approx(r"\frac{1}{2}") == "0.5"
    assert approx("2^{100}").startswith("1.26765060023e+30")
    assert approx(r"\sqrt{-1}") == "1i"


# --- cálculo simbólico ------------------------------------------------------


def test_integral_y_limite() -> None:
    assert exact(r"\int_0^1 x^2 dx") == "1/3"
    assert exact(r"\int x^2 dx") == "x**3/3"
    assert exact(r"\lim_{x\to 0}\frac{\sin x}{x}") == "1"
    assert exact(r"\lim_{x\to 0^+}\frac{1-\cos x}{x^2}") == "1/2"


def test_suma_y_producto() -> None:
    assert exact(r"\sum_{i=1}^{10} i^2") == "385"
    assert exact(r"\prod_{k=1}^{5} k") == "120"
    assert calculate(r"\sum_{k=1}^{n} k^2")["kind"] == "formal"


def test_indice_i_no_es_la_unidad_imaginaria() -> None:
    assert exact(r"\sum_{i=1}^{4} i") == "10"


def test_relaciones_y_conjuntos() -> None:
    assert calculate("1 < x < 3")["latex"] == r"1 < x \wedge x < 3"
    assert calculate(r"\{1,2,3\}")["kind"] == "set"
    assert calculate("{n | n > 0}")["kind"] == "set"
    assert calculate("{(1+2)*3}")["exact"] == "9"  # las llaves siguen agrupando
    assert exact(r"\det{[1,2;3,4]}") == "-2"
    assert exact(r"solve(x^2-5x+6, x)") == "{2, 3}"


def test_valor_absoluto_y_redondeos() -> None:
    assert exact("|-5|") == "5"
    assert exact(r"\left|-5\right|") == "5"
    assert exact(r"\lfloor 3.7 \rfloor") == "3"
    assert exact(r"\lceil 3.2 \rceil") == "4"


def test_unicode_se_normaliza() -> None:
    assert exact("2 × 3") == "6"
    assert exact("2 ÷ 4") == "1/2"
    assert exact("π") == "pi"


def test_dos_resultados_con_pm() -> None:
    result = calculate(r"x^2\pm x")
    assert result["kind"] == "branches"
    assert result["exact"] == "{x*(x + 1), x*(x - 1)}"
    assert len(result["branches"]) == 2


def test_pm_sin_doble_rama() -> None:
    assert exact(r"\pm 0") == "0"


# --- errores ---------------------------------------------------------------


@pytest.mark.parametrize(
    "source",
    [
        "1/0",
        "(-1)!",
        r"2^{100000}",
        r"\frac{1}{0}",
        "",
        "   ",
        "1+",
        "*3",
        r"\unknowncommand",
        "x!0)",
    ],
)
def test_entradas_invalidas(source: str) -> None:
    with pytest.raises(CalculationError):
        calculate(source)


def test_mensajes_en_castellano() -> None:
    with pytest.raises(CalculationError) as error:
        calculate(r"1/0")
    assert "cero" in str(error.value)


# --- límites de seguridad ---------------------------------------------------


def test_potencias_que_se_explotan_demasiado() -> None:
    """(x+y+…)**n con muchos términos se rechaza en vez de colgarse."""
    with pytest.raises(CalculationError) as error:
        calculate(r"(x+y+z+w+u+v+s+t)^{40}")
    assert "términos" in str(error.value)
    # Las potencias de una sola base sí valen.
    assert exact("x^9999") == "x**9999"
    assert exact("2^{2000}").startswith("114813069527425452423283320117")


def test_tiempo_maximo(sandbox_timeout: float) -> None:
    from forma.errors import EvaluationTimeout
    from forma.sandbox import calculate_safely

    # Esta expresión tarda varios segundos en SymPy: el proceso hijo la corta.
    with pytest.raises(EvaluationTimeout):
        calculate_safely("(x+y+z+1)^{20}", timeout=sandbox_timeout)