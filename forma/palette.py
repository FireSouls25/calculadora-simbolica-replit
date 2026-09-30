"""Paleta de símbolos que la interfaz muestra siempre visible.

Cada entrada es ``{"latex": ..., "label": ..., "title": ...}``; ``#?`` marca
dónde debe quedar el cursor (es la sintaxis de MathLive). Al vivir en Python, la
paleta y el evaluador no se desincronizan: lo que se ofrece es lo que el
servidor sabe calcular.
"""

from __future__ import annotations

from typing import Any

GROUP_LABELS = {
    "basico": "Básico",
    "potencias": "Potencias",
    "fracciones": "Fracciones",
    "funciones": "Funciones",
    "calculo": "Cálculo",
    "conjuntos": "Lógica y conjuntos",
    "griego": "Griego",
    "constantes": "Constantes",
    "estructuras": "Estructuras",
}

SYMBOLS: list[dict[str, Any]] = [
    # --- básico -------------------------------------------------------------
    {"group": "basico", "latex": "+", "label": "+"},
    {"group": "basico", "latex": "-", "label": "−"},
    {"group": "basico", "latex": r"\times", "label": "×"},
    {"group": "basico", "latex": r"\div", "label": "÷"},
    {"group": "basico", "latex": r"\cdot", "label": "·"},
    {"group": "basico", "latex": r"\left(#?\right)", "label": "( )", "title": "Paréntesis"},
    {"group": "basico", "latex": r"\left[#?\right]", "label": "[ ]", "title": "Corchetes"},
    {"group": "basico", "latex": r"\left|#?\right|", "label": "| |", "title": "Valor absoluto"},
    {"group": "basico", "latex": "=", "label": "=", "title": "Igualdad"},
    {"group": "basico", "latex": r"\ne", "label": "≠"},
    {"group": "basico", "latex": "<", "label": "<"},
    {"group": "basico", "latex": ">", "label": ">"},
    {"group": "basico", "latex": r"\le", "label": "≤"},
    {"group": "basico", "latex": r"\ge", "label": "≥"},
    {"group": "basico", "latex": r"\approx", "label": "≈"},
    {"group": "basico", "latex": r"\pm", "label": "±", "title": "Muestra los dos resultados"},
    {"group": "basico", "latex": r"\%", "label": "%", "title": "Porcentaje"},
    {"group": "basico", "latex": "!", "label": "n!", "title": "Factorial"},
    {"group": "basico", "latex": r"\infty", "label": "∞"},
    # --- potencias -----------------------------------------------------------
    {"group": "potencias", "latex": r"\sqrt{#?}", "label": "√", "title": "Raíz cuadrada"},
    {"group": "potencias", "latex": r"\sqrt[#?]{#?}", "label": "ⁿ√", "title": "Raíz n-ésima"},
    {"group": "potencias", "latex": r"\cbrt{#?}", "label": "∛"},
    {"group": "potencias", "latex": "^{#?}", "label": "xⁿ", "title": "Potencia"},
    {"group": "potencias", "latex": "^2", "label": "x²"},
    {"group": "potencias", "latex": r"x_{#?}", "label": "xₙ", "title": "Subíndice"},
    {"group": "potencias", "latex": r"\left|#?\right|", "label": "|x|"},
    {"group": "potencias", "latex": r"\left\lceil #? \right\rceil", "label": "⌈ ⌉", "title": "Techo"},
    {"group": "potencias", "latex": r"\left\lfloor #? \right\rfloor", "label": "⌊ ⌋", "title": "Parte entera"},
    {"group": "potencias", "latex": r"\frac{1}{#?}", "label": "1/x", "title": "Inversa"},
    # --- fracciones ----------------------------------------------------------
    {"group": "fracciones", "latex": r"\frac{#?}{#?}", "label": "a⁄b", "title": "Fracción"},
    {"group": "fracciones", "latex": r"\frac{#?}{#?}", "label": "x/2"},
    {"group": "fracciones", "latex": r"\frac{1}{2}", "label": "½"},
    {"group": "fracciones", "latex": r"\frac{\pi}{2}", "label": "π⁄2"},
    {"group": "fracciones", "latex": r"\frac{-b\pm\sqrt{b^2-4ac}}{2a}", "label": "Raíces", "title": "Fórmula cuadrática"},
    # --- funciones -----------------------------------------------------------
    {"group": "funciones", "latex": r"\sin\left(#?\right)", "label": "sin"},
    {"group": "funciones", "latex": r"\cos\left(#?\right)", "label": "cos"},
    {"group": "funciones", "latex": r"\tan\left(#?\right)", "label": "tan"},
    {"group": "funciones", "latex": r"\cot\left(#?\right)", "label": "cot"},
    {"group": "funciones", "latex": r"\arcsin\left(#?\right)", "label": "arcsin"},
    {"group": "funciones", "latex": r"\arccos\left(#?\right)", "label": "arccos"},
    {"group": "funciones", "latex": r"\arctan\left(#?\right)", "label": "arctan"},
    {"group": "funciones", "latex": r"\sinh\left(#?\right)", "label": "sinh"},
    {"group": "funciones", "latex": r"\cosh\left(#?\right)", "label": "cosh"},
    {"group": "funciones", "latex": r"\tanh\left(#?\right)", "label": "tanh"},
    {"group": "funciones", "latex": r"\exp\left(#?\right)", "label": "eˣ"},
    {"group": "funciones", "latex": r"\ln\left(#?\right)", "label": "ln", "title": "Logaritmo natural"},
    {"group": "funciones", "latex": r"\log\left(#?\right)", "label": "log", "title": "Logaritmo decimal"},
    {"group": "funciones", "latex": r"\log_{#?}\left(#?\right)", "label": "log_b", "title": "Logaritmo en base b"},
    {"group": "funciones", "latex": r"\abs{#?}", "label": "abs"},
    {"group": "funciones", "latex": r"\operatorname{sgn}\left(#?\right)", "label": "sgn"},
    {"group": "funciones", "latex": r"\operatorname{frac}\left(#?\right)", "label": "frac", "title": "Parte decimal"},
    {"group": "funciones", "latex": r"\operatorname{min}\left(#?\right)", "label": "min"},
    {"group": "funciones", "latex": r"\operatorname{max}\left(#?\right)", "label": "max"},
    {"group": "funciones", "latex": r"\gcd\left(#?,#?\right)", "label": "mcd"},
    {"group": "funciones", "latex": r"\operatorname{lcm}\left(#?,#?\right)", "label": "mcm"},
    {"group": "funciones", "latex": r"#?\bmod #?", "label": "mod", "title": "Resto"},
    {"group": "funciones", "latex": r"\operatorname{nCr}\left(#?,#?\right)", "label": "nCr"},
    {"group": "funciones", "latex": r"\operatorname{nPr}\left(#?,#?\right)", "label": "nPr"},
    {"group": "funciones", "latex": r"\operatorname{gamma}\left(#?\right)", "label": "gamma"},
    # --- cálculo -------------------------------------------------------------
    {"group": "calculo", "latex": r"\int #? \, dx", "label": "∫", "title": "Integral indefinida"},
    {"group": "calculo", "latex": r"\int_{#?}^{#?} #? \, dx", "label": "∫ᵇₐ", "title": "Integral definida"},
    {"group": "calculo", "latex": r"\int_{#?}^{#?} #? \, d#?", "label": "∫dx", "title": "Integral con variable"},
    {"group": "calculo", "latex": r"\partial #?", "label": "∂", "title": "Derivada parcial"},
    {"group": "calculo", "latex": r"\operatorname{diff}\left(#?,#?\right)", "label": "d/dx", "title": "Derivada"},
    {"group": "calculo", "latex": r"\sum_{i=1}^{#?} #?", "label": "∑", "title": "Suma"},
    {"group": "calculo", "latex": r"\prod_{i=1}^{#?} #?", "label": "∏", "title": "Producto"},
    {"group": "calculo", "latex": r"\lim_{x\to #?} #?", "label": "lím", "title": "Límite"},
    {"group": "calculo", "latex": r"\operatorname{series}\left(#?,#?,#?,#?\right)", "label": "series", "title": "Serie de Taylor"},
    {"group": "calculo", "latex": r"\operatorname{solve}\left(#?,#?\right)", "label": "solve", "title": "Resuelve una ecuación"},
    {"group": "calculo", "latex": r"\operatorname{simplify}\left(#?\right)", "label": "simplify"},
    {"group": "calculo", "latex": r"\operatorname{expand}\left(#?\right)", "label": "expand"},
    {"group": "calculo", "latex": r"\operatorname{factor}\left(#?\right)", "label": "factor"},
    {"group": "calculo", "latex": r"\operatorname{subs}\left(#?,#?,#?\right)", "label": "subs", "title": "Sustituye"},
    # --- conjuntos y lógica --------------------------------------------------
    {"group": "conjuntos", "latex": r"\in", "label": "∈"},
    {"group": "conjuntos", "latex": r"\notin", "label": "∉"},
    {"group": "conjuntos", "latex": r"\subset", "label": "⊂"},
    {"group": "conjuntos", "latex": r"\subseteq", "label": "⊆"},
    {"group": "conjuntos", "latex": r"\cup", "label": "∪"},
    {"group": "conjuntos", "latex": r"\cap", "label": "∩"},
    {"group": "conjuntos", "latex": r"\emptyset", "label": "∅"},
    {"group": "conjuntos", "latex": r"\left\{#?,#?\right\}", "label": "{a,b}", "title": "Conjunto"},
    {"group": "conjuntos", "latex": r"\left\{#?\mid #?\right\}", "label": "{x | x>0}", "title": "Conjunto por propiedad"},
    {"group": "conjuntos", "latex": r"\mathbb{R}", "label": "ℝ"},
    {"group": "conjuntos", "latex": r"\mathbb{N}", "label": "ℕ"},
    {"group": "conjuntos", "latex": r"\mathbb{Z}", "label": "ℤ"},
    {"group": "conjuntos", "latex": r"\mathbb{Q}", "label": "ℚ"},
    {"group": "conjuntos", "latex": r"\mathbb{C}", "label": "ℂ"},
    {"group": "conjuntos", "latex": r"\land", "label": "∧", "title": "Y lógico"},
    {"group": "conjuntos", "latex": r"\lor", "label": "∨", "title": "O lógico"},
    {"group": "conjuntos", "latex": r"\neg", "label": "¬", "title": "No"},
    {"group": "conjuntos", "latex": r"\implies", "label": "⇒"},
    {"group": "conjuntos", "latex": r"\iff", "label": "⇔"},
    {"group": "conjuntos", "latex": r"\exists #?", "label": "∃", "title": "Existe"},
    {"group": "conjuntos", "latex": r"\forall #?", "label": "∀", "title": "Para todo"},
    # --- griego --------------------------------------------------------------
    *[
        {"group": "griego", "latex": f"\\{name}", "label": label}
        for name, label in (
            ("alpha", "α"), ("beta", "β"), ("gamma", "γ"), ("delta", "δ"),
            ("epsilon", "ε"), ("zeta", "ζ"), ("eta", "η"), ("theta", "θ"),
            ("iota", "ι"), ("kappa", "κ"), ("lambda", "λ"), ("mu", "μ"),
            ("nu", "ν"), ("xi", "ξ"), ("rho", "ρ"), ("sigma", "σ"),
            ("tau", "τ"), ("upsilon", "υ"), ("varphi", "φ"), ("chi", "χ"),
            ("psi", "ψ"), ("omega", "ω"), ("Gamma", "Γ"), ("Delta", "Δ"),
            ("Theta", "Θ"), ("Lambda", "Λ"), ("Xi", "Ξ"), ("Pi", "Π"),
            ("Sigma", "Σ"), ("Phi", "Φ"), ("Psi", "Ψ"), ("Omega", "Ω"),
        )
    ],
    # --- constantes ----------------------------------------------------------
    {"group": "constantes", "latex": r"\pi", "label": "π"},
    {"group": "constantes", "latex": "e", "label": "e", "title": "Número de Euler"},
    {"group": "constantes", "latex": r"\tau", "label": "τ"},
    {"group": "constantes", "latex": r"\varphi", "label": "φ", "title": "Razón áurea"},
    {"group": "constantes", "latex": "i", "label": "i", "title": "Unidad imaginaria"},
    {"group": "constantes", "latex": r"\infty", "label": "∞"},
    {"group": "constantes", "latex": r"\operatorname{Catalan}", "label": "Catalan"},
    {"group": "constantes", "latex": r"\operatorname{EulerGamma}", "label": "γE"},
    {"group": "constantes", "latex": r"180\degree", "label": "180°", "title": "Grados"},
    {"group": "constantes", "latex": r"50\%", "label": "50%"},
    # --- estructuras ---------------------------------------------------------
    {"group": "estructuras", "latex": r"\binom{#?}{#?}", "label": "(n k)", "title": "Coeficiente binomial"},
    {"group": "estructuras", "latex": r"\begin{pmatrix}#?&#?\\#?&#?\end{pmatrix}", "label": "[ ]", "title": "Matriz 2×2"},
    {"group": "estructuras", "latex": r"\vec{#?}", "label": "v⃗", "title": "Vector"},
    {"group": "estructuras", "latex": r"\hat{#?}", "label": "ĥ", "title": "Unitario"},
    {"group": "estructuras", "latex": r"\overline{#?}", "label": "z̄", "title": "Complejo conjugado"},
    {"group": "estructuras", "latex": r"\ldots", "label": "…"},
]


def palette() -> dict:
    """Datos que consume el frontend para pintar la barra de símbolos."""
    return {
        "groups": [{"id": key, "label": label} for key, label in GROUP_LABELS.items()],
        "symbols": SYMBOLS,
    }