package com.trading.trading_webhook_receiver_java.service;

import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.stereotype.Service;

/*
 * Servicio utilitario para inspeccionar payloads JSON de TradingView.
 *
 * Funcionalidad:
 * - Extrae campos básicos para logging y ACK:
 *   event_uid, message_type, signal.event, signal.side, signal.symbol.
 * - Soporta payload directo y payload envuelto:
 *   {"payload": {...}}.
 * - No modifica el JSON, no canonicaliza, no valida trading logic.
 *
 * Conceptos Java/Spring aplicados:
 * - Single Responsibility Principle.
 * - Separación de parsing liviano respecto al controller.
 * - Null-safety defensiva con JsonNode.
 */
@Service
public class JsonPayloadInspector {

    public String extractText(JsonNode payload, String fieldName) {
        if (payload == null || payload.isNull() || fieldName == null || fieldName.isBlank()) {
            return null;
        }

        JsonNode value = payload.get(fieldName);
        if (value != null && !value.isNull()) {
            return value.asText(null);
        }

        JsonNode nestedPayload = payload.get("payload");
        if (nestedPayload != null && nestedPayload.isObject()) {
            JsonNode nestedValue = nestedPayload.get(fieldName);
            if (nestedValue != null && !nestedValue.isNull()) {
                return nestedValue.asText(null);
            }
        }

        return null;
    }

    public String extractNestedText(JsonNode payload, String objectName, String fieldName) {
        if (
                payload == null
                        || payload.isNull()
                        || objectName == null
                        || objectName.isBlank()
                        || fieldName == null
                        || fieldName.isBlank()
        ) {
            return null;
        }

        JsonNode parent = payload.get(objectName);
        if (parent != null && parent.isObject()) {
            JsonNode value = parent.get(fieldName);
            if (value != null && !value.isNull()) {
                return value.asText(null);
            }
        }

        JsonNode nestedPayload = payload.get("payload");
        if (nestedPayload != null && nestedPayload.isObject()) {
            JsonNode nestedParent = nestedPayload.get(objectName);
            if (nestedParent != null && nestedParent.isObject()) {
                JsonNode nestedValue = nestedParent.get(fieldName);
                if (nestedValue != null && !nestedValue.isNull()) {
                    return nestedValue.asText(null);
                }
            }
        }

        return null;
    }
}