"""
Validation View Service del panel Streamlit.

Este archivo prepara datos de validación para visualización.

Responsabilidad:
- Extraer validation.validation de la respuesta del backend.
- Preparar métricas globales.
- Extraer razones, penalizaciones y snapshots.
- Separar bloques Pine / Backend / Probabilidad.
- Evitar lógica repetida dentro de app.py.

"""

from typing import Any, Dict, List


def extract_validation_container(data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrae el objeto validation completo desde /api/latest.

    En el panel actual:
    validation = data.get("validation", {}) or {}
    """

    if not isinstance(data, dict):
        return {}

    validation = data.get("validation", {}) or {}

    return validation if isinstance(validation, dict) else {}


def extract_validation_block(data_or_validation: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrae el bloque interno validation.validation.

    Soporta dos entradas:
    1. /api/latest completo.
    2. Objeto validation ya extraído.
    """

    if not isinstance(data_or_validation, dict):
        return {}

    if "validation" in data_or_validation and isinstance(data_or_validation.get("validation"), dict):
        inner = data_or_validation.get("validation", {})
        if any(k in inner for k in ["approve", "confidence", "probability_tp_before_sl", "score_external"]):
            return inner

    validation_container = extract_validation_container(data_or_validation)
    inner = validation_container.get("validation", {}) if isinstance(validation_container, dict) else {}

    return inner if isinstance(inner, dict) else {}


def format_probability_value(prob_tp: Any) -> Any:
    """
    Formatea probabilidad TP antes SL igual que app.py.

    Lógica original:
    - Si es float/int y <= 1, mostrar round(prob_tp * 100, 2)%
    - Si ya viene como valor, devolverlo
    - Si no existe, "-"
    """

    if isinstance(prob_tp, (float, int)) and prob_tp <= 1:
        return f"{round(prob_tp * 100, 2)}%"

    if prob_tp is not None:
        return prob_tp

    return "-"


def build_validation_metrics(validation_block: Dict[str, Any]) -> Dict[str, Any]:
    """
    Prepara métricas globales de validación.
    """

    if not isinstance(validation_block, dict):
        validation_block = {}

    approve = validation_block.get("approve")
    confidence = validation_block.get("confidence")
    prob_tp = validation_block.get("probability_tp_before_sl")
    score_external = validation_block.get("score_external")

    return {
        "approve": approve,
        "approve_label": "YES" if approve is True else "NO" if approve is False else "-",
        "confidence": confidence,
        "confidence_label": f"{confidence}%" if confidence is not None else "-",
        "prob_tp": prob_tp,
        "prob_tp_label": format_probability_value(prob_tp),
        "score_external": score_external,
        "score_external_label": score_external if score_external is not None else "-",
        "tp": validation_block.get("tp", "-"),
        "sl": validation_block.get("sl", "-"),
        "rr": validation_block.get("rr", "-"),
    }


def extract_validation_sections(validation_block: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrae secciones internas usadas por el panel.
    """

    if not isinstance(validation_block, dict):
        validation_block = {}

    return {
        "validation_steps": validation_block.get("validation_steps", {}) or {},
        "analysis_trace": validation_block.get("analysis_trace", []) or [],
        "analysis_summary": validation_block.get("analysis_summary", {}) or {},
        "alert_reused": validation_block.get("alert_reused", {}) or {},
        "market_snapshot": validation_block.get("market_snapshot", {}) or {},
        "structure_snapshot": validation_block.get("structure_snapshot", {}) or {},
        "reasons": validation_block.get("reason", []) or [],
        "penalties": validation_block.get("penalties", []) or [],
    }


def get_step(validation_steps: Dict[str, Any], step_name: str) -> Dict[str, Any]:
    """
    Obtiene un step de validación.
    """

    if not isinstance(validation_steps, dict):
        return {}

    step = validation_steps.get(step_name, {})

    return step if isinstance(step, dict) else {}


def build_step_title(step_name: str, step_data: Dict[str, Any]) -> str:
    """
    Construye título visual del step.

    Mantiene formato:
    step_name → STATUS
    """

    if not isinstance(step_data, dict):
        step_data = {}

    return f"{step_name} → {step_data.get('status', '-')}"


def get_pine_step_names() -> List[str]:
    """
    Steps relacionados con contexto técnico Pine.

    Mantiene lista original.
    """

    return [
        "event_gate",
        "context_validation",
        "extension_validation",
        "score_validation",
    ]


def get_backend_step_names() -> List[str]:
    """
    Steps relacionados con Binance / backend.

    Mantiene lista original.
    """

    return [
        "microstructure_validation",
        "flow_validation",
        "tp_room_validation",
    ]


def extract_probability_model_summary(validation_block: Dict[str, Any]) -> Dict[str, Any]:
    """
    Extrae información del modelo probabilístico.
    """

    if not isinstance(validation_block, dict):
        validation_block = {}

    return {
        "probability_model": validation_block.get("probability_model", "-"),
        "barrier_component": validation_block.get("barrier_component", "-"),
        "technical_component": validation_block.get("technical_component", "-"),
        "ml_component": validation_block.get("ml_component", "-"),
        "probability_tp_before_sl": validation_block.get("probability_tp_before_sl"),
        "confidence": validation_block.get("confidence"),
        "approve": validation_block.get("approve"),
        "score_external": validation_block.get("score_external"),
    }


def get_approve_status_message(approve: Any) -> Dict[str, str]:
    """
    Devuelve estado visual y mensaje para approve.

    Mantiene la semántica actual:
    - approve True => success
    - approve False => error
    - None/otro => warning
    """

    if approve is True:
        return {
            "status": "success",
            "message": "✅ Señal aprobada por Validation Layer",
        }

    if approve is False:
        return {
            "status": "error",
            "message": "⛔ Señal rechazada por Validation Layer",
        }

    return {
        "status": "warning",
        "message": "⚠ Validación no disponible",
    }