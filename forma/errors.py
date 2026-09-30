"""Errores de dominio de la calculadora."""

from __future__ import annotations


class CalculationError(ValueError):
    """Error causado por la expresión escrita por la persona usuaria.

    Es seguro mostrarlo en la interfaz: el mensaje está pensado para leerse.
    """


class EvaluationTimeout(CalculationError):
    """El cálculo superó el tiempo máximo permitido."""

    def __init__(self, seconds: float) -> None:
        super().__init__(f"El cálculo tardó más de {seconds:g} s. Prueba a simplificarlo.")