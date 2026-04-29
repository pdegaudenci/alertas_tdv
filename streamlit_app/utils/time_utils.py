"""
Helpers de fechas y zonas horarias para el panel Streamlit.
"""

from datetime import datetime

import pytz


def madrid_to_utc_timestamp(fecha_str: str) -> int:
    """
    Convierte una fecha en horario Europe/Madrid a timestamp UTC en milisegundos.

    Formato esperado:
    YYYY-MM-DD HH:MM
    """

    madrid = pytz.timezone("Europe/Madrid")
    dt_local = madrid.localize(datetime.strptime(fecha_str, "%Y-%m-%d %H:%M"))
    dt_utc = dt_local.astimezone(pytz.utc)
    return int(dt_utc.timestamp() * 1000)


def now_local_str() -> str:
    """
    Devuelve fecha/hora local como string legible.
    """

    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")