#!/usr/bin/env python3
"""Punto de entrada de la aplicación (lo que ejecuta Replit).

    python main.py            # http://0.0.0.0:5000
    PORT=8080 python main.py  # otro puerto
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from forma.server import main  # noqa: E402  (necesita el path anterior)

if __name__ == "__main__":
    main()