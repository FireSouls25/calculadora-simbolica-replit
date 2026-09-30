"""Conversión de unidades.

Las magnitudes viven aquí (y no en el JavaScript) para que el servidor sea la
única fuente de verdad: el frontend pinta lo que devuelve ``/api/palette``.
"""

from __future__ import annotations

import re
from typing import Any

import pint

from .errors import CalculationError

UNITS = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)

#: Magnitud -> [(unidad para pint, etiqueta), ...]
CATEGORIES: dict[str, list[tuple[str, str]]] = {
    "length": [
        ("meter", "metros"),
        ("kilometer", "kilómetros"),
        ("centimeter", "centímetros"),
        ("millimeter", "milímetros"),
        ("mile", "millas"),
        ("foot", "pies"),
        ("inch", "pulgadas"),
    ],
    "mass": [
        ("kilogram", "kilogramos"),
        ("gram", "gramos"),
        ("milligram", "miligramos"),
        ("tonne", "toneladas"),
        ("pound", "libras"),
        ("ounce", "onzas"),
    ],
    "temperature": [
        ("degC", "°C · Celsius"),
        ("degF", "°F · Fahrenheit"),
        ("kelvin", "K · Kelvin"),
    ],
    "volume": [
        ("liter", "litros"),
        ("milliliter", "mililitros"),
        ("meter ** 3", "metros cúbicos"),
        ("gallon", "galones (US)"),
        ("cup", "tazas (US)"),
        ("fluid_ounce", "onzas líquidas (US)"),
    ],
    "time": [
        ("second", "segundos"),
        ("millisecond", "milisegundos"),
        ("minute", "minutos"),
        ("hour", "horas"),
        ("day", "días"),
        ("week", "semanas"),
        ("year", "años"),
    ],
    "speed": [
        ("meter / second", "m/s"),
        ("kilometer / hour", "km/h"),
        ("mile / hour", "mph"),
        ("knot", "nudos"),
        ("foot / second", "pies/s"),
    ],
    "area": [
        ("meter ** 2", "m²"),
        ("kilometer ** 2", "km²"),
        ("hectare", "hectáreas"),
        ("acre", "acres"),
        ("foot ** 2", "pies²"),
    ],
    "data": [
        ("byte", "bytes"),
        ("kilobyte", "kilobytes"),
        ("megabyte", "megabytes"),
        ("gigabyte", "gigabytes"),
        ("terabyte", "terabytes"),
    ],
}

CATEGORY_LABELS = {
    "length": "Longitud",
    "mass": "Masa",
    "temperature": "Temperatura",
    "volume": "Volumen",
    "time": "Tiempo",
    "speed": "Velocidad",
    "area": "Área",
    "data": "Datos",
}

_FRACTION = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*/\s*(-?\d+(?:\.\d+)?)\s*$")


def parse_value(raw: Any) -> float:
    """Acepta «12», «1.5e3» o «3/4»."""
    if isinstance(raw, (int, float)) and not isinstance(raw, bool):
        return float(raw)
    text = str(raw or "").strip()
    if not text:
        raise CalculationError("Escribe un valor numérico.")
    fraction = _FRACTION.match(text)
    if fraction:
        divisor = float(fraction.group(2))
        if divisor == 0:
            raise CalculationError("No se puede dividir por cero.")
        return float(fraction.group(1)) / divisor
    try:
        return float(text)
    except ValueError as exc:
        raise CalculationError(f"No se reconoce el valor «{text}».") from exc


def format_value(number: float) -> str:
    """Número sin ceros sobrantes y con notación científica si hace falta."""
    if number != number:  # NaN
        return "—"
    if number in (float("inf"), float("-inf")):
        return "∞" if number > 0 else "-∞"
    if number == int(number) and abs(number) < 1e15:
        return str(int(number))
    return f"{number:.12g}"


def convert(value: Any, from_unit: str, to_unit: str) -> dict:
    """Convierte entre unidades compatibles."""
    magnitude = parse_value(value)
    source = str(from_unit or "").strip()
    target = str(to_unit or "").strip()
    if not source or not target:
        raise CalculationError("Elige las unidades de origen y destino.")
    try:
        quantity = UNITS.Quantity(magnitude, UNITS.parse_units(source))
        converted = quantity.to(UNITS.parse_units(target))
        result = float(converted.magnitude)
    except pint.errors.DimensionalityError as exc:
        raise CalculationError("Estas unidades no son compatibles entre sí.") from exc
    except (pint.errors.UndefinedUnitError, pint.errors.DefinitionSyntaxError) as exc:
        raise CalculationError("No reconozco una de esas unidades.") from exc
    except (ValueError, TypeError) as exc:
        raise CalculationError("No se pudo convertir ese valor.") from exc
    if result == 0:
        result = 0.0
    return {
        "ok": True,
        "value": result,
        "formatted": format_value(result),
        "unit": target,
    }