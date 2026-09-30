"""Servidor HTTP: sirve la interfaz y expone la API de cálculo."""

from __future__ import annotations

import json
import os
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

from .calculator import quick_reference
from .errors import CalculationError
from .palette import palette
from .sandbox import DEFAULT_TIMEOUT, calculate_safely
from .units import CATEGORIES, CATEGORY_LABELS, convert

STATIC_DIR = Path(__file__).parent / "static"
MAX_BODY_BYTES = 64_000

_CONTENT_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".js": "text/javascript; charset=utf-8",
    ".svg": "image/svg+xml",
    ".ico": "image/x-icon",
    ".json": "application/json; charset=utf-8",
    ".woff2": "font/woff2",
}


class AppHandler(BaseHTTPRequestHandler):
    server_version = "forma"
    protocol_version = "HTTP/1.1"

    # -- utilidades ----------------------------------------------------------

    def send_json(self, status: int, payload: dict) -> None:
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(encoded)

    def send_error_message(self, status: int, message: str) -> None:
        self.send_json(status, {"ok": False, "error": message})

    def read_payload(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY_BYTES:
            raise CalculationError("La solicitud es demasiado grande.")
        if length <= 0:
            return {}
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise CalculationError("No se pudo leer la solicitud.") from exc
        if not isinstance(payload, dict):
            raise CalculationError("La solicitud no tiene el formato esperado.")
        return payload

    # -- rutas ---------------------------------------------------------------

    def do_GET(self) -> None:  # noqa: N802 - firma de BaseHTTPRequestHandler
        path = unquote(urlparse(self.path).path)
        if path == "/favicon.ico":
            self.send_response(204)
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if path == "/api/palette":
            self.send_json(200, {
                "ok": True,
                **palette(),
                "unitCategories": [
                    {"id": key, "label": CATEGORY_LABELS[key], "units": CATEGORIES[key]}
                    for key in CATEGORIES
                ],
                "examples": quick_reference(),
                "timeout": DEFAULT_TIMEOUT,
            })
            return
        if path in ("/healthz", "/api/health"):
            self.send_json(200, {"ok": True})
            return
        self.serve_static(path)

    def do_HEAD(self) -> None:  # noqa: N802
        self.do_GET()

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        try:
            payload = self.read_payload()
            if path == "/api/calculate":
                result = calculate_safely(payload.get("expression", ""))
                self.send_json(200 if result.get("ok") else 400, result)
                return
            if path == "/api/convert":
                self.send_json(200, convert(
                    payload.get("value", 0), payload.get("from", ""), payload.get("to", "")
                ))
                return
            self.send_error_message(404, "Ruta no encontrada.")
        except CalculationError as exception:
            self.send_error_message(400, str(exception))
        except (TypeError, ValueError) as exception:
            self.send_error_message(400, str(exception) or "Solicitud no válida.")
        except (BrokenPipeError, ConnectionResetError):  # pragma: no cover
            pass
        except Exception:  # noqa: BLE001 - nunca queremos filtrar el traceback
            self.send_error_message(500, "No se pudo completar la operación.")

    # -- estáticos -----------------------------------------------------------

    def serve_static(self, path: str) -> None:
        relative = "index.html" if path in ("/", "") else path.lstrip("/")
        target = (STATIC_DIR / relative).resolve()
        if not str(target).startswith(str(STATIC_DIR.resolve())) or not target.is_file():
            self.send_error(404)
            return
        content = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", _CONTENT_TYPES.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(content)

    def log_message(self, fmt: str, *args) -> None:
        sys.stdout.write(f"[{self.log_date_time_string()}] {fmt % args}\n")


def build_server(port: int, host: str = "0.0.0.0") -> ThreadingHTTPServer:
    server = ThreadingHTTPServer((host, port), AppHandler)
    server.daemon_threads = True
    return server


def main() -> None:
    port = int(os.environ.get("PORT", "5000"))
    server = build_server(port)
    print(f"Calculadora lista en http://0.0.0.0:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:  # pragma: no cover
        print("\nHasta luego.")
    finally:
        server.server_close()