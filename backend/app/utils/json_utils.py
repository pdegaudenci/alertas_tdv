"""
Utilidades de serialización JSON.

Lógica original de limpieza/sanitización de datos
para evitar errores con NaN, infinitos, numpy, pandas.Timestamp, listas y dicts.
"""

from typing import Any
import math
import numpy as np
import pandas as pd


def sanitize_for_json(value: Any) -> Any:
    if value is None:
        return None

    if isinstance(value, (str, bool, int)):
        return value

    if isinstance(value, (float, np.floating)):
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return None
        return v

    if isinstance(value, (np.integer,)):
        return int(value)

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, dict):
        return {str(k): sanitize_for_json(v) for k, v in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_json(v) for v in value]

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    return value


def is_bad_number(value: Any) -> bool:
    try:
        if isinstance(value, (float, np.floating)):
            v = float(value)
            return math.isnan(v) or math.isinf(v)
        return False
    except Exception:
        return False