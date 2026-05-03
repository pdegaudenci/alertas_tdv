# trading-webhook-receiver-java

Microservicio Spring Boot para recibir alertas de TradingView y publicarlas en AWS SQS con ACK rápido.

## Responsabilidad

Este servicio solo hace:

- Recibir `POST /api/webhook`
- Validar `WEBHOOK_SECRET`
- Publicar el JSON crudo en AWS SQS
- Responder rápido a TradingView

No hace:

- Validación de trading
- Binance
- Supabase
- S3
- Databricks
- Merge CORE/EXTRA

## Arquitectura

```text
TradingView
   ↓
trading-webhook-receiver-java
   ↓
AWS SQS
   ↓
Lambda Consumer Python
   ↓
Supabase + S3
   ↓
Databricks Bronze/Silver/Gold