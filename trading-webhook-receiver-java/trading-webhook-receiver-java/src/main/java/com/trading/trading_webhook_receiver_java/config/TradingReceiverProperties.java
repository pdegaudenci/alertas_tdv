package com.trading.trading_webhook_receiver_java.config;

import jakarta.validation.Valid;
import jakarta.validation.constraints.NotBlank;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

/*
 * Configuración tipada del microservicio.
 *
 * Funcionalidad:
 * - Mapea propiedades desde application.yml / variables de entorno.
 * - Evita usar strings sueltos con @Value distribuidos por todo el código.
 * - Falla temprano si faltan variables obligatorias como WEBHOOK_SECRET o AWS_SQS_QUEUE_URL.
 *
 * Conceptos Java/Spring aplicados:
 * - Records inmutables.
 * - @ConfigurationProperties.
 * - Validación con Bean Validation.
 * - Configuración jerárquica y strongly typed.
 */
@Validated
@ConfigurationProperties(prefix = "trading")
public record TradingReceiverProperties(
        @Valid Webhook webhook,
        @Valid Aws aws
) {

    public record Webhook(
            @NotBlank(message = "trading.webhook.secret / WEBHOOK_SECRET is required")
            String secret
    ) {
    }

    public record Aws(
            @NotBlank(message = "trading.aws.region / AWS_REGION is required")
            String region,

            @Valid Sqs sqs
    ) {
    }

    public record Sqs(
            @NotBlank(message = "trading.aws.sqs.queue-url / AWS_SQS_QUEUE_URL is required")
            String queueUrl
    ) {
    }
}