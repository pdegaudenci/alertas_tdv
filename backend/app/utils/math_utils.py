"""
Utilidades matemáticas básicas.

Contiene funciones auxiliares usadas en normalización, scoring, validación y
cálculos de probabilidad.
"""

from typing import Any, Dict


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None or value == "":
            return default
        return int(float(value))
    except Exception:
        return default


def clip(value: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, value))


def pct(a: float, b: float) -> float:
    if b == 0:
        return 0.0
    return (a / b) * 100.0


def sign_for_side(side: str) -> int:
    return 1 if str(side).lower() == "long" else -1


def nested_get(d: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    cur = d
    for k in keys:
        if not isinstance(cur, dict):
            return default
        cur = cur.get(k)
    return cur if cur is not None else default


def strength_to_score(value: Any) -> float:
    txt = str(value or "").upper()
    if txt == "STRONG":
        return 90.0
    if txt == "VALID":
        return 75.0
    if txt == "NORMAL":
        return 70.0
    if txt == "TRANSITION":
        return 50.0
    if txt == "WEAK":
        return 30.0
    if txt == "INVALID":
        return 0.0
    return safe_float(value, 0.0)