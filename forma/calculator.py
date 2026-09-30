"""Orquestación: de la cadena LaTeX que escribe la persona al resultado final."""

from __future__ import annotations

from itertools import product

from . import formatting, latex
from .errors import CalculationError
from .evaluator import Evaluator
from .symbols import DEFAULT_LIMITS, Limits

#: Marcadores de «más o menos» que generan las dos ramas del resultado.
_PM_MARKERS = (r"\pm", "±")

#: Cuántos ``±`` se aceptan como mucho (2^3 = 8 resultados).
_MAX_BRANCH_MARKERS = 3


def calculate(source: str, limits: Limits = DEFAULT_LIMITS) -> dict:
    """Calcula una expresión y devuelve la respuesta para el frontend."""
    if not isinstance(source, str) or not source.strip():
        raise CalculationError("Escribe una expresión para calcular.")

    branches = _split_pm(source)
    if branches is None:
        return _evaluate_source(source, limits)

    payloads = [_evaluate_source(branch, limits) for branch in branches]
    unique: list[dict] = []
    for payload in payloads:
        if payload["latex"] not in {seen["latex"] for seen in unique}:
            unique.append(payload)
    if len(unique) == 1:
        return unique[0]
    return {
        "ok": True,
        "exact": "{" + ", ".join(item["exact"] for item in unique) + "}",
        "latex": r"\left\{" + r"\;,\;".join(item["latex"] for item in unique) + r"\right\}",
        "approx": None,
        "symbolic": any(item["symbolic"] for item in unique),
        "kind": "branches",
        "branches": unique,
    }


def _evaluate_source(source: str, limits: Limits) -> dict:
    tree = latex.parse(source, limits)
    result = Evaluator(limits).evaluate(tree)
    result = formatting.simplify(result)
    return formatting.build_payload(result)


def _split_pm(source: str) -> list[str] | None:
    """Devuelve las variantes ``+``/``-`` de una expresión con ``±``, o ``None``."""
    positions: list[tuple[int, str]] = []
    for marker in _PM_MARKERS:
        start = 0
        while True:
            index = source.find(marker, start)
            if index < 0:
                break
            positions.append((index, marker))
            start = index + len(marker)
    if not positions:
        return None
    positions.sort()
    if len(positions) > _MAX_BRANCH_MARKERS:
        raise CalculationError(
            f"Usa como mucho {_MAX_BRANCH_MARKERS} símbolos ± por expresión."
        )
    variants: list[str] = []
    for signs in product(("+", "-"), repeat=len(positions)):
        text = source
        for (index, marker), sign in sorted(
            zip(positions, signs), key=lambda pair: pair[0][0], reverse=True
        ):
            text = text[:index] + sign + text[index + len(marker) :]
        variants.append(text)
    return variants


def quick_reference() -> list[dict]:
    """Ejemplos que la interfaz muestra para aprender la sintaxis."""
    return [
        {"expression": r"\sqrt{12+18}", "note": "raíces y grupos"},
        {"expression": r"\frac{1}{3}+\frac{1}{6}", "note": "fracciones exactas"},
        {"expression": r"\sin{\pi/6}", "note": "trigonometría exacta"},
        {"expression": r"\sum_{i=1}^{10} i^2", "note": "sumas y productos"},
        {"expression": r"\int_0^1 x^2 dx", "note": "integrales"},
        {"expression": r"\lim_{x\to 0}\frac{\sin x}{x}", "note": "límites"},
        {"expression": r"(1+i)^8", "note": "números complejos"},
        {"expression": r"50\% \cdot 200", "note": "porcentajes"},
        {"expression": r"\det{[1,2;3,4]}", "note": "matrices"},
        {"expression": r"solve(x^2-5x+6, x)", "note": "ecuaciones"},
        {"expression": r"series(e^x, x, 0, 4)", "note": "series de Taylor"},
        {"expression": r"x^2\pm x", "note": "resultados dobles con ±"},
    ]