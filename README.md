# Forma · calculadora simbólica

Un cuaderno de cálculo en el navegador: escribes LaTeX con un editor matemático
y el servidor lo resuelve con **SymPy** de forma exacta (números racionales,
simbólico, complejos, conjuntos, matrices y cálculo).

```
python main.py            # http://0.0.0.0:5000  (PORT=8080 para otro puerto)
```

En Replit el botón **Run** ya lanza esto: el flujo ejecuta `main.py` y publica
el puerto 5000.

## Estructura

```
main.py                 punto de entrada (lo ejecuta Replit)
forma/
  latex.py              lexer + parser: LaTeX -> árbol propio
  evaluator.py          árbol -> SymPy, con límites de seguridad
  symbols.py            catálogo de constantes y funciones (fuente de verdad)
  calculator.py         orquesta: analizar, evaluar, simplificar, formatear
  formatting.py         texto plano, LaTeX y aproximación numérica
  palette.py            símbolos que muestra la barra siempre visible
  units.py              conversión de unidades
  sandbox.py            cálculo en proceso hijo con tiempo máximo
  server.py             rutas HTTP y ficheros estáticos
  static/               index.html, styles.css y js/ (módulos ES)
tests/                  pytest: analizador, cálculo, unidades y servidor
```

Regla de oro: **lo que la interfaz ofrece es lo que el servidor sabe calcular**.
La barra de símbolos se construye con `forma/palette.py`, y cada función vive en
`forma/symbols.py`; añadir una función es una entrada en la tabla.

## API

| Ruta | Método | Qué hace |
| --- | --- | --- |
| `/api/calculate` | POST | `{"expression": "\\int_0^1 x^2 dx"}` → resultado exacto, LaTeX y valor decimal |
| `/api/convert` | POST | `{"value": 1, "from": "km", "to": "m"}` |
| `/api/palette` | GET | Símbolos, magnitudes y ejemplos que usa el frontend |

Respuesta de cálculo:

```json
{"ok": true, "exact": "1/3", "latex": "\\frac{1}{3}", "approx": "0.333333333333",
 "symbolic": false, "kind": "number"}
```

## Qué sabe calcular

- **Aritmética exacta**: `0.1+0.2` → `3/10` (nada de coma flotante), `10/3` → `10/3`.
- **Funciones y constantes**: `log` es decimal y `ln` natural, `\log_{2}{8}`,
  `i` como unidad imaginaria, `e`, `τ`, `φ`, Catalan, EulerGamma.
- **Grados y radianes**: en las trigonométricas los números van en **grados**
  (`sin(90)=1`, `asin(0.5)=30`), como en una calculadora de bolsillo. Si la
  expresión lleva π se respeta el radián (`sin(π/6)=1/2`), y `rad(90)` /
  `deg(π/2)` / `30\degree` sirven para hacerlo explícito.
- **Cálculo**: `\sum`, `\prod`, `\int`, `\lim`, `diff`, `series`, `solve`.
- **Álgebra**: `simplify`, `expand`, `factor`, `cancel`, `subs`, `together`.
- **Conjuntos y lógica**: `{1,2,3}`, `{n | n > 0}`, `\in`, `\cup`, `\cap`,
  `\land`, `\lor`, `\neg`, `\exists`, `\forall`.
- **Matrices**: `[1,2;3,4]` con `det`, `inv`, `rank`, `trace`, `eigenvals`.
- **Números complejos**: `(1+i)^8` → `16`.
- **Porcentajes y grados**: `50%` → `1/2`, `sin(30\degree)` → `1/2`.
- **Resultados dobles**: `x^2\pm x` muestra las dos ramas.
- **Unidades**: longitud, masa, temperatura, volumen, tiempo, velocidad, área y datos.

Atajos: multiplicación implícita (`2x`, `sin x`, `3π`), `\%` es porcentaje y el
resto de una división se escribe `mod` o `\bmod`.

## Seguridad y límites

El analizador **no** genera código Python: todo pasa por una lista blanca de
funciones. Además hay límites estáticos (longitud, número de nodos, exponentes,
factoriales, términos de las sumas) y cada cálculo corre en un proceso hijo con
12 segundos de tiempo máximo, así que una expresión patosa nunca deja la
aplicación colgada.

## Desarrollo

```
uv sync
uv run pytest           # 73 pruebas
uv run python main.py
```