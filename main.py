from __future__ import annotations

import ast
import json
import math
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse

import pint
import sympy as sp


ROOT = Path(__file__).parent
UNITS = pint.UnitRegistry(autoconvert_offset_to_baseunit=True)

CONSTANTS = {
    "pi": sp.pi,
    "π": sp.pi,
    "e": sp.E,
    "E": sp.E,
    "tau": 2 * sp.pi,
    "inf": sp.oo,
}
FUNCTIONS = {
    "sqrt": sp.sqrt,
    "sin": sp.sin,
    "cos": sp.cos,
    "tan": sp.tan,
    "asin": sp.asin,
    "acos": sp.acos,
    "atan": sp.atan,
    "sinh": sp.sinh,
    "cosh": sp.cosh,
    "tanh": sp.tanh,
    "ln": sp.log,
    "log": sp.log,
    "exp": sp.exp,
    "abs": sp.Abs,
    "factorial": sp.factorial,
    "gamma": sp.gamma,
    "floor": sp.floor,
    "ceil": sp.ceiling,
    "sign": sp.sign,
    "simplify": sp.simplify,
    "expand": sp.expand,
    "factor": sp.factor,
    "diff": sp.diff,
    "integrate": sp.integrate,
    "binomial": sp.binomial,
    "gcd": sp.gcd,
}


def read_braced(text: str, start: int) -> tuple[str, int]:
    """Read the balanced { ... } beginning at start."""
    if start >= len(text) or text[start] != "{":
        raise ValueError("Falta un argumento entre llaves.")
    depth = 0
    for pos in range(start, len(text)):
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : pos], pos + 1
    raise ValueError("Hay una llave sin cerrar.")


def latex_to_expression(source: str) -> str:
    """Convert the common MathLive LaTeX subset into safe Python expression syntax."""
    text = source.strip()
    text = re.sub(r"\\(?:left|right|displaystyle|,|;|!|quad|qquad)\s*", "", text)
    text = text.replace(r"\cdot", "*").replace(r"\times", "*")
    text = text.replace(r"\div", "/").replace(r"\pi", "pi")
    text = text.replace(r"\infty", "inf").replace(r"\degree", "degree")
    text = text.replace(r"\theta", "theta")
    text = text.replace(r"\%", "%")
    text = text.replace(r"\,", "")
    text = text.replace("−", "-").replace("×", "*").replace("÷", "/")

    # Parse nested fractions and radicals without flattening their contents.
    out: list[str] = []
    i = 0
    while i < len(text):
        if text.startswith(r"\frac", i) or text.startswith(r"\dfrac", i) or text.startswith(r"\tfrac", i):
            command = next(cmd for cmd in (r"\dfrac", r"\tfrac", r"\frac") if text.startswith(cmd, i))
            pos = i + len(command)
            numerator, pos = read_braced(text, pos)
            denominator, pos = read_braced(text, pos)
            out.append(f"(({latex_to_expression(numerator)})/({latex_to_expression(denominator)}))")
            i = pos
        elif text.startswith(r"\sqrt", i):
            pos = i + len(r"\sqrt")
            index = None
            if pos < len(text) and text[pos] == "[":
                end = text.find("]", pos)
                if end < 0:
                    raise ValueError("El índice de la raíz no está cerrado.")
                index = text[pos + 1 : end]
                pos = end + 1
            radicand, pos = read_braced(text, pos)
            radicand_expr = latex_to_expression(radicand)
            if index is None:
                out.append(f"sqrt({radicand_expr})")
            else:
                out.append(f"(({radicand_expr})**(1/({latex_to_expression(index)})))")
            i = pos
        elif text.startswith(r"\operatorname", i) or text.startswith(r"\mathrm", i) or text.startswith(r"\text", i):
            command = next(cmd for cmd in (r"\operatorname", r"\mathrm", r"\text") if text.startswith(cmd, i))
            content, pos = read_braced(text, i + len(command))
            out.append(content)
            i = pos
        else:
            out.append(text[i])
            i += 1
    text = "".join(out)

    for command, name in (
        (r"\arcsin", "asin"), (r"\arccos", "acos"), (r"\arctan", "atan"),
        (r"\sinh", "sinh"), (r"\cosh", "cosh"), (r"\tanh", "tanh"),
        (r"\sin", "sin"), (r"\cos", "cos"), (r"\tan", "tan"),
        (r"\ln", "ln"), (r"\log", "log"), (r"\exp", "exp"),
    ):
        text = text.replace(command, name)

    # MathLive represents powers and subscripts using braces.
    text = re.sub(r"\^\s*\{([^{}]*)\}", r"**(\1)", text)
    text = re.sub(r"_\s*\{([^{}]*)\}", r"_\1", text)
    text = text.replace("{", "(").replace("}", ")")
    text = text.replace("^", "**")
    text = text.replace(r"\!", "!")
    text = re.sub(r"(?<![A-Za-z0-9_])\s+", "", text)
    # Factorial suffixes are translated before AST validation.
    text = re.sub(r"(\b\d+(?:\.\d+)?|\b[A-Za-z_]\w*|\([^()]*\))!", r"factorial(\1)", text)
    return text


def add_implicit_multiplication(source: str) -> str:
    token_re = re.compile(r"(?:\d+(?:\.\d*)?(?:[eE][+-]?\d+)?|[A-Za-z_]\w*|[()+\-*/%,])")
    tokens = token_re.findall(source)
    if "".join(tokens).replace(" ", "") != source.replace(" ", ""):
        raise ValueError("La expresión contiene un símbolo no compatible.")
    result: list[str] = []
    prev = ""
    for token in tokens:
        prev_is_value = bool(prev) and (
            prev == ")" or prev[0].isdigit() or prev[0].isalpha() or prev[0] == "_"
        )
        curr_is_value_start = token == "(" or token[0].isdigit() or token[0].isalpha() or token[0] == "_"
        is_function_call = prev in FUNCTIONS and token == "("
        if prev_is_value and curr_is_value_start and not is_function_call:
            result.append("*")
        result.append(token)
        prev = token
    return "".join(result)


class SafeExpression(ast.NodeVisitor):
    def visit_Expression(self, node: ast.Expression):
        return self.visit(node.body)

    def visit_Constant(self, node: ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise ValueError("Solo se permiten números en la expresión.")
        return sp.Integer(node.value) if isinstance(node.value, int) else sp.Float(node.value)

    def visit_Name(self, node: ast.Name):
        if node.id.startswith("__"):
            raise ValueError("Nombre no permitido.")
        if node.id in CONSTANTS:
            return CONSTANTS[node.id]
        if node.id in FUNCTIONS:
            return FUNCTIONS[node.id]
        return sp.Symbol(node.id)

    def visit_BinOp(self, node: ast.BinOp):
        left, right = self.visit(node.left), self.visit(node.right)
        operations = {
            ast.Add: lambda: left + right,
            ast.Sub: lambda: left - right,
            ast.Mult: lambda: left * right,
            ast.Div: lambda: left / right,
            ast.Pow: lambda: left**right,
            ast.Mod: lambda: sp.Mod(left, right),
        }
        operation = operations.get(type(node.op))
        if operation is None:
            raise ValueError("Ese operador no está permitido.")
        if isinstance(node.op, ast.Pow) and right.is_number and abs(float(right)) > 10000:
            raise ValueError("El exponente es demasiado grande.")
        return operation()

    def visit_UnaryOp(self, node: ast.UnaryOp):
        value = self.visit(node.operand)
        if isinstance(node.op, ast.UAdd):
            return value
        if isinstance(node.op, ast.USub):
            return -value
        raise ValueError("Ese operador no está permitido.")

    def visit_Call(self, node: ast.Call):
        if not isinstance(node.func, ast.Name) or node.func.id not in FUNCTIONS:
            raise ValueError("Función no permitida.")
        if node.keywords:
            raise ValueError("No se permiten argumentos con nombre.")
        args = [self.visit(arg) for arg in node.args]
        try:
            return FUNCTIONS[node.func.id](*args)
        except TypeError as exc:
            raise ValueError(f"Revisa los argumentos de {node.func.id}().") from exc

    def generic_visit(self, node):
        raise ValueError("La expresión contiene una operación no permitida.")


def calculate_branch(source: str) -> dict:
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Escribe una expresión para calcular.")
    expression_text = latex_to_expression(source)
    expression_text = add_implicit_multiplication(expression_text)
    try:
        tree = ast.parse(expression_text, mode="eval")
    except SyntaxError as exc:
        raise ValueError("No pude interpretar la expresión. Revisa los paréntesis y operadores.") from exc
    result = SafeExpression().visit(tree)
    result = sp.simplify(result)
    exact = str(result)
    symbolic_latex = sp.latex(result)
    approximate = None
    if not getattr(result, "free_symbols", set()) and result not in (sp.oo, -sp.oo, sp.zoo, sp.nan):
        try:
            value = sp.N(result, 14)
            if value.is_real:
                approximate = str(value)
        except (TypeError, ValueError, OverflowError):
            pass
    return {
        "ok": True,
        "exact": exact,
        "latex": symbolic_latex,
        "approx": approximate,
        "symbolic": bool(getattr(result, "free_symbols", set())),
    }


def calculate(source: str) -> dict:
    if not isinstance(source, str) or not source.strip():
        raise ValueError("Escribe una expresión para calcular.")
    marker = r"\pm" if r"\pm" in source else ("±" if "±" in source else None)
    if marker is None:
        return calculate_branch(source)
    if source.count(marker) > 1:
        raise ValueError("Usa un solo símbolo ± por expresión para mostrar sus dos resultados.")
    positive = calculate_branch(source.replace(marker, "+", 1))
    negative = calculate_branch(source.replace(marker, "-", 1))
    exact = f"{{{positive['exact']}, {negative['exact']}}}"
    latex_result = rf"\left\{{{positive['latex']},\;{negative['latex']}\right\}}"
    return {
        "ok": True,
        "exact": exact,
        "latex": latex_result,
        "approx": None,
        "symbolic": positive["symbolic"] or negative["symbolic"],
        "branches": [positive, negative],
    }


def convert_units(payload: dict) -> dict:
    try:
        value = float(payload.get("value", 0))
        from_unit = str(payload.get("from", "")).strip()
        to_unit = str(payload.get("to", "")).strip()
        if not from_unit or not to_unit:
            raise ValueError("Elige las unidades de origen y destino.")
        quantity = UNITS.Quantity(value, UNITS.parse_units(from_unit))
        converted = quantity.to(UNITS.parse_units(to_unit))
        magnitude = float(converted.magnitude)
        if math.isclose(magnitude, 0.0, abs_tol=1e-12):
            magnitude = 0.0
        return {
            "ok": True,
            "value": magnitude,
            "formatted": f"{magnitude:.12g}",
            "unit": to_unit,
        }
    except pint.errors.DimensionalityError as exc:
        raise ValueError("Estas unidades no son compatibles entre sí.") from exc
    except (pint.errors.UndefinedUnitError, pint.errors.DefinitionSyntaxError) as exc:
        raise ValueError("No reconozco una de esas unidades.") from exc


class AppHandler(BaseHTTPRequestHandler):
    def send_json(self, status: int, payload: dict):
        encoded = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_GET(self):
        path = unquote(urlparse(self.path).path)
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        if path == "/":
            path = "/index.html"
        if path not in ("/index.html", "/styles.css", "/app.js"):
            self.send_error(404)
            return
        file_path = ROOT / path.lstrip("/")
        content_type = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
        }[file_path.suffix]
        content = file_path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_POST(self):
        path = urlparse(self.path).path
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length > 1_000_000:
                self.send_json(413, {"ok": False, "error": "La solicitud es demasiado grande."})
                return
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if path == "/api/calculate":
                self.send_json(200, calculate(payload.get("expression", "")))
            elif path == "/api/convert":
                self.send_json(200, convert_units(payload))
            else:
                self.send_json(404, {"ok": False, "error": "Ruta no encontrada."})
        except (ValueError, TypeError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            self.send_json(400, {"ok": False, "error": str(exc)})
        except Exception:
            self.send_json(400, {"ok": False, "error": "No se pudo completar el cálculo."})

    def log_message(self, fmt, *args):
        print(f"[{self.log_date_time_string()}] {fmt % args}")


if __name__ == "__main__":
    port = int(__import__("os").environ.get("PORT", "5000"))
    server = ThreadingHTTPServer(("0.0.0.0", port), AppHandler)
    print(f"Calculadora lista en http://0.0.0.0:{port}")
    server.serve_forever()