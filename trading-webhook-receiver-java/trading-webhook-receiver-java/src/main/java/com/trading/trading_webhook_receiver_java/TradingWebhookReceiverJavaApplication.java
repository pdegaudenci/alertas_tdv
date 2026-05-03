package com.trading.trading_webhook_receiver_java;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.boot.context.properties.ConfigurationPropertiesScan;

/*
 * Clase principal del microservicio trading-webhook-receiver-java.
 *
 * Funcionalidad:
 * - Arranca la aplicación Spring Boot.
 * - Activa el escaneo de clases @ConfigurationProperties.
 * - Mantiene el microservicio enfocado en una sola responsabilidad:
 *   recibir alertas TradingView, validar secret, publicar en SQS y responder rápido.
 *
 * Conceptos Java/Spring aplicados:
 * - Bootstrapping con SpringApplication.
 * - ConfigurationPropertiesScan para configuración tipada.
 * - Separación por capas: controller, service, security, config y dto.
 */
@SpringBootApplication
@ConfigurationPropertiesScan
public class TradingWebhookReceiverJavaApplication {

	public static void main(String[] args) {
		SpringApplication.run(TradingWebhookReceiverJavaApplication.class, args);
	}
}