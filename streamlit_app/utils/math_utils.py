"""
Helpers matemáticos y conversión numérica para el panel Streamlit.

"""

from typing import Any, Optional

import pandas as pd


def safe_float(value: Any, default: float = 0.0) -> float:
    """
    Convierte un valor a float de forma segura.

    Si el valor es None, NaN, vacío o no convertible, devuelve default.
    """

    try:
        if value is None or pd.isna(value):
            return default
        return float(value)
    except Exception:
        return default


def safe_int(value: Any, default: int = 0) -> int:
    """
    Convierte un valor a int de forma segura.
    """

    try:
        if value is None or pd.isna(value):
            return default
        return int(float(value))
    except Exception:
        return default


def clamp(value: float, min_value: float, max_value: float) -> float:
    """
    Limita un número dentro de un rango.
    """

    return max(min_value, min(max_value, value))


def pct_to_display(value: Any, decimals: int = 2) -> str:
    """
    Formatea una probabilidad como porcentaje.

    Si el valor viene entre 0 y 1, lo multiplica por 100.
    Si ya viene en escala 0-100, lo deja como está.
    """

    try:
        v = float(value)
    except Exception:
        return "-"

    if v <= 1:
        v = v * 100

    return f"{round(v, decimals)}%"


def calcular_trailing(adx: float) -> Optional[float]:
    """
    Calcula trailing stop sugerido según ADX.

    Mantiene la lógica original del panel:
    - ADX > 32 → 0.15
    - ADX > 26 → 0.18
    - ADX > 22 → 0.22
    - Caso contrario → None
    """

    if adx > 32:
        return 0.15
    elif adx > 26:
        return 0.18
    elif adx > 22:
        return 0.22
    return None


def rating_score(score: float) -> str:
    """
    Clasifica un score operativo.

    Mantiene la lógica original:
    - <55  → INVÁLIDO
    - <65  → MARGINAL
    - <72  → OPERABLE
    - <82  → BUENO
    - >=82 → ÓPTIMO
    """

    if score < 55:
        return "INVÁLIDO"
    elif score < 65:
        return "MARGINAL"
    elif score < 72:
        return "OPERABLE"
    elif score < 82:
        return "BUENO"
    return "ÓPTIMO"