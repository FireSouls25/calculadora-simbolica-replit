"""Calculadora simbólica «forma»: LaTeX -> SymPy -> JSON."""

from __future__ import annotations

from .calculator import calculate
from .errors import CalculationError, EvaluationTimeout
from .evaluator import Evaluator, evaluate
from .latex import parse
from .palette import palette
from .units import convert

__version__ = "1.0.0"

__all__ = [
    "CalculationError",
    "EvaluationTimeout",
    "Evaluator",
    "calculate",
    "convert",
    "evaluate",
    "palette",
    "parse",
]