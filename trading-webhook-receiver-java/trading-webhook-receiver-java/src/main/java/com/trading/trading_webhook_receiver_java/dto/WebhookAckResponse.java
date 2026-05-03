package com.trading.trading_webhook_receiver_java.dto;

/*
 * DTO de respuesta HTTP para TradingView.
 *
 * Funcionalidad:
 * - Devuelve un ACK claro al webhook caller.
 * - Incluye información mínima para trazabilidad:
 *   traceId, eventUid, messageType, event, side, symbol y sqsMessageId.
 * - No expone secretos ni payload completo.
 *
 * Conceptos Java aplicados:
 * - Record inmutable.
 * - DTO explícito.
 * - Contrato de respuesta estable.
 */
public record WebhookAckResponse(
        boolean ok,
        String message,
        String traceId,
        Long processingMs,
        String eventUid,
        String messageType,
        String event,
        String side,
        String symbol,
        String sqsMessageId,
        String queueBackend,
        String processingMode
) {
}