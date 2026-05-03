package com.trading.trading_webhook_receiver_java.security;

import com.fasterxml.jackson.databind.JsonNode;
import com.trading.trading_webhook_receiver_java.config.TradingReceiverProperties;
import org.springframework.stereotype.Component;

import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;

/*
 * Validador del secret del webhook.
 *
 * Funcionalidad:
 * - Valida el secret recibido desde header x-webhook-secret o desde payload.secret.
 * - Soporta payloads envueltos dentro de {"payload": {...}}.
 * - Evita comparación simple con equals usando comparación constant-time.
 *
 * Conceptos Java/Security aplicados:
 * - Comparación constant-time con MessageDigest.isEqual.
 * - Inyección de configuración tipada.
 * - Encapsulamiento de seguridad fuera del controller.
 */
@Component
public class WebhookSecretValidator {

    private final String expectedSecret;

    public WebhookSecretValidator(TradingReceiverProperties properties) {
        this.expectedSecret = properties.webhook().secret();
    }

    public boolean isValid(String headerSecret, JsonNode payload) {
        String payloadSecret = extractPayloadSecret(payload);

        return constantTimeEquals(expectedSecret, headerSecret)
                || constantTimeEquals(expectedSecret, payloadSecret);
    }

    private String extractPayloadSecret(JsonNode payload) {
        if (payload == null || payload.isNull()) {
            return null;
        }

        JsonNode directSecret = payload.get("secret");
        if (directSecret != null && !directSecret.isNull()) {
            return directSecret.asText(null);
        }

        JsonNode nestedPayload = payload.get("payload");
        if (nestedPayload != null && nestedPayload.isObject()) {
            JsonNode nestedSecret = nestedPayload.get("secret");
            if (nestedSecret != null && !nestedSecret.isNull()) {
                return nestedSecret.asText(null);
            }
        }

        return null;
    }

    private boolean constantTimeEquals(String expected, String candidate) {
        if (expected == null || candidate == null) {
            return false;
        }

        byte[] expectedBytes = expected.getBytes(StandardCharsets.UTF_8);
        byte[] candidateBytes = candidate.getBytes(StandardCharsets.UTF_8);

        return MessageDigest.isEqual(expectedBytes, candidateBytes);
    }
}