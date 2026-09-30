"""Ejecución aislada con límite de tiempo.

SymPy puede quedarse calculando indefinidamente con algunas expresiones, así que
el cálculo se lanza en un proceso hijo y, si no termina a tiempo, se mata. Si el
entorno no permite crear procesos, se cae al cálculo en línea.
"""

from __future__ import annotations

import multiprocessing as mp
import threading
from typing import Any

from .calculator import calculate
from .errors import CalculationError, EvaluationTimeout

#: Segundos máximos por cálculo antes de cortarlo.
DEFAULT_TIMEOUT = 12.0

#: Como mucho dos cálculos a la vez: la máquina de Replit es pequeña.
_SLOTS = threading.Semaphore(2)

_CONTEXT: Any = None


def _worker(connection: Any, expression: str) -> None:
    try:
        connection.send(calculate(expression))
    except BaseException as exception:  # noqa: BLE001 - el hijo solo devuelve diccionarios
        message = str(exception).strip() or "No se pudo completar el cálculo."
        connection.send({"ok": False, "error": message})
    finally:
        connection.close()


def _context() -> Any:
    """Contexto de multiprocesos: forkserver si existe, si no fork o spawn.

    ``fork`` dentro de un servidor con hilos avisa en Python 3.12+, y ``spawn``
    tarda un segundo en arrancar SymPy; ``forkserver`` evita ambos problemas.
    """
    global _CONTEXT
    if _CONTEXT is None:
        available = mp.get_all_start_methods()
        method = next((name for name in ("forkserver", "fork", "spawn") if name in available), "spawn")
        _CONTEXT = mp.get_context(method)
        if method == "forkserver":
            try:
                _CONTEXT.set_forkserver_preload(["forma.calculator"])
            except (RuntimeError, ValueError):  # pragma: no cover - depende del SO
                pass
    return _CONTEXT


def calculate_safely(expression: str, timeout: float = DEFAULT_TIMEOUT) -> dict:
    """Calcula ``expression`` en un proceso aparte con tiempo máximo."""
    if not _SLOTS.acquire(timeout=timeout + 1):
        raise CalculationError("Hay demasiados cálculos en marcha; inténtalo en un momento.")
    try:
        return _run_isolated(expression, timeout)
    finally:
        _SLOTS.release()


def _run_isolated(expression: str, timeout: float) -> dict:
    context = _context()
    try:
        parent, child = context.Pipe(duplex=False)
        process = context.Process(target=_worker, args=(child, expression), daemon=True)
        process.start()
    except (OSError, ValueError, RuntimeError, ImportError):
        # Sin procesos disponibles: al menos que funcione en línea.
        return _inline(expression)
    child.close()
    try:
        if parent.poll(timeout):
            return parent.recv()
        raise EvaluationTimeout(timeout)
    except (EOFError, OSError):
        raise CalculationError("El cálculo se interrumpió; prueba con algo más sencillo.") from None
    finally:
        parent.close()
        if process.is_alive():
            process.terminate()
            process.join(timeout=1)
        if process.is_alive():  # pragma: no cover - sólo en máquinas muy lentas
            process.kill()
            process.join(timeout=1)


def _inline(expression: str) -> dict:
    try:
        return calculate(expression)
    except CalculationError:
        raise
    except Exception:  # noqa: BLE001 - nunca queremos filtrar excepciones crudas
        raise CalculationError("No se pudo completar el cálculo.") from None