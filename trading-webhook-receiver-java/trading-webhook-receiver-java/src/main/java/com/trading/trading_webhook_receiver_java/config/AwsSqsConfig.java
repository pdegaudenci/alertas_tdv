package com.trading.trading_webhook_receiver_java.config;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import software.amazon.awssdk.auth.credentials.DefaultCredentialsProvider;
import software.amazon.awssdk.http.urlconnection.UrlConnectionHttpClient;
import software.amazon.awssdk.regions.Region;
import software.amazon.awssdk.services.sqs.SqsClient;

/*
 * Configuración del cliente AWS SQS.
 *
 * Funcionalidad:
 * - Crea un único bean SqsClient reutilizable por toda la aplicación.
 * - Usa DefaultCredentialsProvider, compatible con:
 *   - aws configure local
 *   - variables de entorno
 *   - IAM Role en AWS App Runner / ECS / EC2
 * - Usa UrlConnectionHttpClient para reducir dependencias y mantener el receiver ligero.
 *
 * Conceptos Java/Spring aplicados:
 * - Dependency Injection.
 * - Bean singleton gestionado por Spring.
 * - Configuración externa desacoplada del código.
 */
@Configuration
public class AwsSqsConfig {

    @Bean
    public SqsClient sqsClient(TradingReceiverProperties properties) {
        return SqsClient.builder()
                .region(Region.of(properties.aws().region()))
                .credentialsProvider(DefaultCredentialsProvider.create())
                .httpClientBuilder(UrlConnectionHttpClient.builder())
                .build();
    }
}