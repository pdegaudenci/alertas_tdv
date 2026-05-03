package com.trading.trading_webhook_receiver_java.controller;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.trading.trading_webhook_receiver_java.dto.SqsPublishResult;
import com.trading.trading_webhook_receiver_java.dto.WebhookAckResponse;
import com.trading.trading_webhook_receiver_java.security.WebhookSecretValidator;
import com.trading.trading_webhook_receiver_java.service.JsonPayloadInspector;
import com.trading.trading_webhook_receiver_java.service.SqsPublisherService;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.UUID;

/*
 * Controller HTTP del webhook TradingView.
 *
 * Funcionalidad:
 * - Expone POST /api/webhook y POST /.
 * - Recibe el JSON crudo de TradingView.
 * - Valida el secret desde header o payload.
 * - Extrae campos mínimos para trazabilidad.
 * - Publica el JSON completo en AWS SQS.
 * - Responde 200 OK rápido si el mensaje fue encolado.
 *
 * Qué NO hace:
 * - No consulta Binance.
 * - No valida señales.
 * - No persiste en Supabase.
 * - No exporta a S3.
 * - No ejecuta Databricks.
 * - No fusiona CORE/EXTRA.
 *
 * Conceptos Java/Spring aplicados:
 * - REST Controller.
 * - Constructor injection.
 * - Separación de responsabilidades.
 * - Structured logging.
 * - DTOs inmutables.
 * - Fast ACK pattern para webhooks.
 */
@RestController
public class WebhookController {

    private static final Logger log = LoggerFactory.getLogger(WebhookController.class);

    private final ObjectMapper objectMapper;
    private final WebhookSecretValidator secretValidator;
    private final SqsPublisherService sqsPublisherService;
    private final JsonPayloadInspector payloadInspector;

    public WebhookController(
            ObjectMapper objectMapper,
            WebhookSecretValidator secretValidator,
            SqsPublisherService sqsPublisherService,
            JsonPayloadInspector payloadInspector
    ) {
        this.objectMapper = objectMapper;
        this.secretValidator = secretValidator;
        this.sqsPublisherService = sqsPublisherService;
        this.payloadInspector = payloadInspector;
    }

    @PostMapping(
            path = {"/api/webhook", "/"},
            consumes = "application/json",
            produces = "application/json"
    )
    public ResponseEntity<WebhookAckResponse> receiveWebhook(
            @RequestBody byte[] body,
            @RequestHeader(value = "x-webhook-secret", required = false) String headerSecret
    ) {
        long startNs = System.nanoTime();
        String traceId = buildTraceId();

        try {
            String rawJson = new String(body, StandardCharsets.UTF_8);
            JsonNode payload = objectMapper.readTree(rawJson);

            String eventUid = payloadInspector.extractText(payload, "event_uid");
            String messageType = payloadInspector.extractText(payload, "message_type");
            String event = payloadInspector.extractNestedText(payload, "signal", "event");
            String side = payloadInspector.extractNestedText(payload, "signal", "side");
            String symbol = payloadInspector.extractNestedText(payload, "signal", "symbol");

            if (!secretValidator.isValid(headerSecret, payload)) {
                long processingMs = elapsedMs(startNs);

                log.warn(
                        "webhook_secret_invalid trace_id={} event_uid={} message_type={} processing_ms={}",
                        traceId,
                        eventUid,
                        messageType,
                        processingMs
                );

                return ResponseEntity
                        .status(HttpStatus.UNAUTHORIZED)
                        .body(new WebhookAckResponse(
                                false,
                                "Invalid webhook secret",
                                traceId,
                                processingMs,
                                eventUid,
                                messageType,
                                event,
                                side,
                                symbol,
                                null,
                                "sqs",
                                "java_receiver_secret_rejected"
                        ));
            }

            SqsPublishResult publishResult = sqsPublisherService.publishRawAlert(
                    rawJson,
                    traceId,
                    eventUid,
                    messageType
            );

            long processingMs = elapsedMs(startNs);

            log.info(
                    "webhook_queued trace_id={} event_uid={} message_type={} event={} side={} symbol={} sqs_message_id={} processing_ms={}",
                    traceId,
                    eventUid,
                    messageType,
                    event,
                    side,
                    symbol,
                    publishResult.messageId(),
                    processingMs
            );

            return ResponseEntity.ok(
                    new WebhookAckResponse(
                            true,
                            "Alert queued",
                            traceId,
                            processingMs,
                            eventUid,
                            messageType,
                            event,
                            side,
                            symbol,
                            publishResult.messageId(),
                            "sqs",
                            "java_sync_sqs_fast_ack"
                    )
            );

        } catch (Exception e) {
            long processingMs = elapsedMs(startNs);

            log.error(
                    "webhook_receiver_error trace_id={} processing_ms={} error={}",
                    traceId,
                    processingMs,
                    e.getMessage(),
                    e
            );

            return ResponseEntity
                    .status(HttpStatus.INTERNAL_SERVER_ERROR)
                    .body(new WebhookAckResponse(
                            false,
                            "Webhook receiver error",
                            traceId,
                            processingMs,
                            null,
                            null,
                            null,
                            null,
                            null,
                            null,
                            "sqs",
                            "java_receiver_error"
                    ));
        }
    }

    @GetMapping(path = "/healthz", produces = "application/json")
    public ResponseEntity<String> healthz() {
        return ResponseEntity.ok("{\"ok\":true,\"service\":\"trading-webhook-receiver-java\"}");
    }

    private String buildTraceId() {
        return "java_" + Instant.now().toEpochMilli() + "_" + UUID.randomUUID();
    }

    private long elapsedMs(long startNs) {
        return Math.round((System.nanoTime() - startNs) / 1_000_000.0);
    }
}