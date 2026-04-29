"""
Helpers JSON para el panel Streamlit.

Permiten leer estructuras anidadas, limpiar valores y evitar errores cuando
el backend devuelve None, errores o payloads incompletos.
"""

from typing import Any, Dict


def nested_get(data: Dict[str, Any], *keys: str, default: Any = None) -> Any:
    """
    Obtiene un valor anidado de un diccionario.

    Ejemplo:
    nested_get(payload, "validation", "approve", default=False)
    """

    current = data

    for key in keys:
        if not isinstance(current, dict):
            return default
        current = current.get(key)

    return current if current is not None else default


def ensure_dict(value: Any) -> Dict[str, Any]:
    """
    Devuelve value si es dict, si no devuelve {}.
    """

    return value if isinstance(value, dict) else {}


def ensure_list(value: Any) -> list:
    """
    Devuelve value si es list, si no devuelve [].
    """

    return value if isinstance(value, list) else []


def coalesce(*values: Any, default: Any = "-") -> Any:
    """
    Devuelve el primer valor no vacío.
    """

    for value in values:
        if value is not None and value != "":
            return value

    return default