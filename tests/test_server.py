"""Pruebas de conversión de unidades y del servidor HTTP."""

from __future__ import annotations

import json
import threading
import urllib.request

import pytest

from forma.errors import CalculationError
from forma.server import build_server
from forma.units import CATEGORIES, convert, parse_value


@pytest.mark.parametrize(
    "value, source, target, expected",
    [
        (1, "kilometer", "meter", "1000"),
        (1, "hour", "second", "3600"),
        (0, "degC", "degF", "32"),
        (100, "degC", "kelvin", "373.15"),
        (1, "gallon", "liter", "3.785411784"),
        (1, "byte", "bit", "8"),
        (2.5, "mile", "kilometer", "4.02336"),
    ],
)
def test_conversion(value: float, source: str, target: str, expected: str) -> None:
    result = convert(value, source, target)
    assert float(result["formatted"]) == pytest.approx(float(expected), rel=1e-9)


def test_unidades_incompatibles() -> None:
    with pytest.raises(CalculationError):
        convert(1, "meter", "second")


def test_unidad_desconocida() -> None:
    with pytest.raises(CalculationError):
        convert(1, "watermelon", "meter")


def test_valores_como_fraccion() -> None:
    assert parse_value("3/4") == 0.75
    assert parse_value("1.5e3") == 1500.0


def test_todas_las_unidades_de_la_paleta_existen() -> None:
    import pint

    registry = pint.UnitRegistry()
    for units in CATEGORIES.values():
        for expression, _ in units:
            registry.parse_units(expression)  # lanza si no es válida


# --- servidor --------------------------------------------------------------


@pytest.fixture(scope="module")
def server():
    instance = build_server(0, "127.0.0.1")
    thread = threading.Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{instance.server_address[1]}"
    instance.shutdown()
    instance.server_close()


def post(server: str, path: str, payload: dict) -> tuple[int, dict]:
    request = urllib.request.Request(
        f"{server}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request) as response:
            return response.status, json.loads(response.read())
    except urllib.error.HTTPError as error:
        return error.code, json.loads(error.read())


def get(server: str, path: str) -> tuple[int, str]:
    try:
        with urllib.request.urlopen(f"{server}{path}") as response:
            return response.status, response.read().decode()
    except urllib.error.HTTPError as error:
        return error.code, error.read().decode()


def test_api_calculate(server: str) -> None:
    status, payload = post(server, "/api/calculate", {"expression": r"\sqrt{2}"})
    assert status == 200
    assert payload["exact"] == "sqrt(2)"
    assert payload["approx"] == "1.41421356237"


def test_api_calculate_error_legible(server: str) -> None:
    status, payload = post(server, "/api/calculate", {"expression": "1/0"})
    assert status == 400
    assert payload["ok"] is False
    assert "cero" in payload["error"]


def test_api_convert(server: str) -> None:
    status, payload = post(server, "/api/convert", {"value": 1, "from": "km", "to": "m"})
    assert status == 200
    assert payload["formatted"] == "1000"


def test_api_palette(server: str) -> None:
    status, body = get(server, "/api/palette")
    payload = json.loads(body)
    assert status == 200
    assert payload["groups"] and payload["symbols"]
    assert any(entry["id"] == "length" for entry in payload["unitCategories"])
    assert payload["examples"]


def test_sirve_la_interfaz(server: str) -> None:
    status, body = get(server, "/")
    assert status == 200
    assert "Calculadora.ipynb" in body
    assert "/js/main.js" in body
    assert 'id="symbol-shelf"' in body


def test_sirve_los_modulos_javascript(server: str) -> None:
    for module in ("main", "cells", "symbols", "converter", "api", "state"):
        status, body = get(server, f"/js/{module}.js")
        assert status == 200, module
        assert "import" in body or "export" in body


def test_no_sirve_fuera_del_directorio(server: str) -> None:
    status, _ = get(server, "/../main.py")
    assert status in (404, 400)