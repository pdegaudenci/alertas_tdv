package com.trading.trading_webhook_receiver_java.service;

import com.trading.trading_webhook_receiver_java.config.TradingReceiverProperties;
import com.trading.trading_webhook_receiver_java.dto.SqsPublishResult;
import org.springframework.stereotype.Service;
import software.amazon.awssdk.services.sqs.SqsClient;
import software.amazon.awssdk.services.sqs.model.MessageAttributeValue;
import software.amazon.awssdk.services.sqs.model.SendMessageRequest;
import software.amazon.awssdk.services.sqs.model.SendMessageResponse;

import java.time.Instant;
import java.util.HashMap;
import java.util.Map;

/*
 * Servicio responsable de publicar alertas crudas en AWS SQS.
 *
 * Funcionalidad:
 * - Recibe el JSON original de TradingView.
 * - Publica el mensaje completo en SQS sin modificarlo.
 * - Agrega message attributes para trazabilidad:
 *   trace_id, event_uid, message_type y source.
 * - Devuelve el messageId de SQS al controller.
 *
 * Conceptos Java/Spring/AWS aplicados:
 * - Service layer.
 * - Inyección por constructor.
 * - AWS SDK v2.
 * - Mensajería desacoplada mediante SQS.
 * - Uso de Map tipado para message attributes.
 */
@Service
public class SqsPublisherService {

    private static final String SOURCE_NAME = "trading-webhook-receiver-java";

    private final SqsClient sqsClient;
    private final String queueUrl;

    public SqsPublisherService(
            SqsClient sqsClient,
            TradingReceiverProperties properties
    ) {
        this.sqsClient = sqsClient;
        this.queueUrl = properties.aws().sqs().queueUrl();
    }

    public SqsPublishResult publishRawAlert(
            String rawJson,
            String traceId,
            String eventUid,
            String messageType
    ) {
        SendMessageRequest request = SendMessageRequest.builder()
                .queueUrl(queueUrl)
                .messageBody(rawJson)
                .messageAttributes(buildMessageAttributes(traceId, eventUid, messageType))
                .build();

        SendMessageResponse response = sqsClient.sendMessage(request);

        return new SqsPublishResult(
                true,
                response.messageId(),
                response.sequenceNumber(),
                Instant.now().toString()
        );
    }

    private Map<String, MessageAttributeValue> buildMessageAttributes(
            String traceId,
            String eventUid,
            String messageType
    ) {
        Map<String, MessageAttributeValue> attributes = new HashMap<>();

        putStringAttribute(attributes, "trace_id", traceId);
        putStringAttribute(attributes, "event_uid", eventUid);
        putStringAttribute(attributes, "message_type", messageType);
        putStringAttribute(attributes, "source", SOURCE_NAME);

        return Map.copyOf(attributes);
    }

    private void putStringAttribute(
            Map<String, MessageAttributeValue> attributes,
            String key,
            String value
    ) {
        if (key == null || key.isBlank() || value == null || value.isBlank()) {
            return;
        }

        attributes.put(
                key,
                MessageAttributeValue.builder()
                        .dataType("String")
                        .stringValue(value)
                        .build()
        );
    }
}