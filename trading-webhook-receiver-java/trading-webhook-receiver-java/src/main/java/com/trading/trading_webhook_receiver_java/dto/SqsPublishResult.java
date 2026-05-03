package com.trading.trading_webhook_receiver_java.dto;

/*
 * Resultado interno de publicación en SQS.
 *
 * Funcionalidad:
 * - Encapsula la respuesta relevante de AWS SQS.
 * - Permite separar la lógica AWS del controller.
 *
 * Conceptos Java aplicados:
 * - Record inmutable.
 * - Separación entre capa de servicio y capa HTTP.
 */
public record SqsPublishResult(
        boolean ok,
        String messageId,
        String sequenceNumber,
        String publishedAt
) {
}