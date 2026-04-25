from __future__ import annotations

import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "movemove_api_client.py"
SPEC = importlib.util.spec_from_file_location("movemove_api_client", MODULE_PATH)
if SPEC is None or SPEC.loader is None:
    raise ImportError(f"Unable to load MoveMove client from {MODULE_PATH}")

MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

MoveMoveClient = MODULE.MoveMoveClient
MoveMoveCredentials = MODULE.MoveMoveCredentials
MoveMoveError = MODULE.MoveMoveError
