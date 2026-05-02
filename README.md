# TradingView Validation Layer API

## 1. Descripción general

Esta API es una **Validation Layer** para un sistema de trading algorítmico basado en alertas de TradingView.

Su objetivo principal es recibir señales generadas por Pine Script, normalizarlas, fusionar eventos complementarios, desacoplar el procesamiento pesado mediante cola, enriquecerlas con datos de mercado externos, validar entradas operativas y persistir información completa para análisis, dashboard, métricas y futuros modelos de Machine Learning.

El sistema queda dividido en **cuatro bloques principales**:

```text
1. TradingView / Pine Script
2. Backend FastAPI / Validation Layer
3. Storage + Cola + Persistencia
4. Panel Streamlit / UI Layer
```

Arquitectura lógica actual:

```text
TradingView Pine Script
        ↓
Alertas JSON CORE / EXTRA
        ↓
FastAPI Backend / Vercel
        ↓
Validación secret + parse + merge CORE/EXTRA
        ↓
Encolado rápido a AWS SQS
        ↓
Respuesta rápida a TradingView
        ↓
Worker lógico / endpoint de procesamiento SQS
        ↓
Validación + Binance + scoring + probabilidad TP/SL
        ├────────────→ Supabase
        ├────────────→ Telegram
        └────────────→ AWS S3 (Data Lake Bronze)
                                ↓
                          Databricks / Autoloader
                                ↓
                        Bronze / Silver / Gold
                                ↓
                     Analytics / ML / Backtesting
```

Este backend **no reemplaza** la lógica de Pine Script. Actúa como una capa posterior de:

```text
- recepción
- normalización
- encolado
- procesamiento desacoplado
- validación
- persistencia operacional
- exportación analítica
```

---

## 2. Responsabilidades del sistema

El sistema queda dividido en las siguientes responsabilidades:

```text
1. TradingView / Pine Script
2. Backend FastAPI / Validation Layer
3. AWS SQS / AWS S3 / IAM
4. Supabase
5. Databricks
6. Panel Streamlit / UI Layer
```

---

## 3. Flujo de datos actual

### 3.1 Flujo resumido

```text
TradingView
  ↓
POST /api/webhook
  ↓
FastAPI valida secreto, parsea JSON y ensambla CORE + EXTRA
  ↓
Si el payload está completo:
  ↓
Se encola en AWS SQS
  ↓
TradingView recibe ACK rápido
  ↓
Un proceso posterior consume desde SQS
  ↓
Ejecuta validación y enriquecimiento
  ↓
Guarda en Supabase
  ↓
Guarda en S3
  ↓
Opcionalmente envía Telegram
  ↓
Databricks consume desde S3
```

### 3.2 Flujo detallado

```text
1. Pine Script detecta una señal.
2. Pine Script envía JSON logical_event_core y/o logical_event_extra.
3. FastAPI recibe el webhook en /api/webhook.
4. Se valida el secret del webhook.
5. Se parsea el JSON.
6. Se ensambla el evento por event_uid.
7. Si aún falta el par CORE/EXTRA:
   - se deja estado parcial
   - se responde OK esperando el complemento
8. Si el evento ya está completo:
   - se actualiza estado rápido en memoria
   - se inserta en SQS
   - se responde rápido a TradingView
9. Un endpoint/worker de procesamiento consume mensajes desde SQS.
10. Se ejecuta run_validation() si aplica.
11. Se actualiza LAST_VALIDATION / LAST_ALERT.
12. Si validation.approve == true:
    - se construye mensaje Telegram
    - se envía a Telegram
13. Se persiste en Supabase.
14. Se exporta evento raw + validación a S3.
15. Databricks consume desde S3 con Auto Loader / file events.
16. Se construyen capas Bronze / Silver / Gold para analytics y ML.
```

---

## 4. Arquitectura actual de alto nivel

```text
┌──────────────────────────────┐
│ TradingView / Pine Script    │
│ - señales INIT / IMP / ENTRY │
│ - JSON schema v2.0           │
└──────────────┬───────────────┘
               │ Webhook POST
               ▼
┌──────────────────────────────────────────┐
│ FastAPI Backend en Vercel                │
│ /api/webhook                             │
│ - validate_secret                        │
│ - parse_payload                          │
│ - assemble_event_payload                 │
│ - assemble_core_extra_by_event_uid       │
│ - fast ack                               │
│ - enqueue to SQS                         │
└──────────────┬───────────────────────────┘
               │
               ▼
┌──────────────────────────────────────────┐
│ AWS SQS                                  │
│ - trading-alerts-queue                   │
│ - trading-alerts-dlq                     │
└──────────────┬───────────────────────────┘
               │ Consume / process
               ▼
┌──────────────────────────────────────────┐
│ Procesamiento desacoplado                │
│ - validation_service                     │
│ - telegram_service                       │
│ - supabase_repo                          │
│ - databricks_export_service              │
│ - error_log_service                      │
└───────┬────────────────┬─────────────────┘
        │                │
        ▼                ▼
┌───────────────┐   ┌──────────────────────┐
│ Supabase      │   │ AWS S3               │
│ Operacional   │   │ Data Lake Bronze     │
└───────┬───────┘   └──────────┬───────────┘
        │                      │
        ▼                      ▼
┌───────────────┐   ┌──────────────────────┐
│ Streamlit     │   │ Databricks           │
│ Dashboard     │   │ Bronze/Silver/Gold   │
└───────────────┘   └──────────────────────┘
```

---

## 5. Responsabilidad de Pine Script / TradingView

Pine Script sigue siendo responsable de detectar el contexto técnico inicial y enviar alertas estructuradas.

### Pine Script calcula y envía

```text
- Evento lógico detectado
- Tipo de señal
- Dirección long / short
- Estado del setup
- Precio de referencia
- OHLC de la vela
- Contexto de régimen
- Contexto de fase
- Bias HTF
- Estados de liquidez
- Estados de movimiento
- Estados de estructura
- Calidad del setup
- Trigger técnico
- Plan de trade TP/SL
- Información de Adaptive SuperTrend
- Información de ML tracking para labeling
```

### Tipos de alertas esperadas

```text
logical_event_core
logical_event_extra
logical_event_full
executed_event
```

### Eventos lógicos principales

```text
LONG_INIT
SHORT_INIT
LONG_INIT_AFTER_ADAPTIVE
SHORT_INIT_AFTER_ADAPTIVE
IMP_UP_AFTER_ADAPTIVE
IMP_DN_AFTER_ADAPTIVE
LONG_ENTRY
SHORT_ENTRY
LONG_WATCH
SHORT_WATCH
LONG_ARMED
SHORT_ARMED
LONG_CANCEL
SHORT_CANCEL
```

### Eventos reales de estrategia

```text
REAL_LONG_ENTRY
REAL_SHORT_ENTRY
REAL_LONG_EXIT
REAL_SHORT_EXIT
EXECUTED_EXIT
```

---

## 6. Información recibida en cada alerta

Cada alerta de TradingView puede enviar un JSON con estructura rica.

### Campos principales

```json
{
  "schema_version": "2.0",
  "message_type": "logical_event_core",
  "event_uid": "BTCUSDC_1m_...",
  "secret": "MI_SECRET",
  "source": {},
  "signal": {},
  "context": {},
  "trigger": {},
  "quality": {},
  "trade_plan": {},
  "ml_tracking": {}
}
```

---

## 7. Bloques de información de la alerta

### 7.1 `source`

```json
{
  "platform": "tradingview",
  "engine": "pine_indicator",
  "script": "SETUP_CLASSIFIER_MASTER_v7_3_FULL_API_ALERTS"
}
```

Responsabilidad:

```text
- Saber qué script envió la alerta
- Diferenciar indicador vs strategy
- Filtrar persistencia por tipo de script
- Mantener trazabilidad
```

---

### 7.2 `signal`

```json
{
  "event": "LONG_INIT",
  "side": "long",
  "setup": "INIT_LONG",
  "entry_type": "INIT",
  "candidate_type": "INIT",
  "track_for_outcome": true,
  "setup_state": "LONG_INIT",
  "setup_side": "long",
  "symbol": "BTCUSDC",
  "tf": "1m",
  "timestamp": "...",
  "bar_time": 123456789,
  "bar_index": 1000,
  "price": 90000,
  "entry_price": 90000,
  "close": 90000,
  "open": 89900,
  "high": 90100,
  "low": 89800
}
```

Responsabilidad:

```text
- Identificar evento
- Identificar lado long / short
- Identificar símbolo y timeframe
- Registrar precio y vela
- Alimentar normalización y lifecycle
- Servir de base para tracking de outcome futuro
```

---

### 7.3 `context`

```json
{
  "regime": "TREND",
  "raw_regime": "TREND",
  "regime_score": 7,
  "regime_strength": "VALID",
  "regime_dir": "BULL",
  "regime_gap": 0,
  "regime_age": 12,
  "phase": "IMP_UP",
  "raw_phase": "IMP_UP",
  "phase_score": 75,
  "phase_strength": "NORMAL",
  "phase_bias": "EARLY_BULL",
  "phase_gap": 2,
  "ctx_state": "TREND",
  "dir_state": "BULL"
}
```

Responsabilidad:

```text
- Dar contexto de mercado
- Informar fase y régimen
- Permitir validación posterior por dirección
- Alimentar dashboard y persistencia
```

---

### 7.4 `trigger`

```json
{
  "trigger_long": true,
  "trigger_short": false,
  "ast_bull": true,
  "ast_bear": false,
  "hull_bull": false,
  "hull_bear": false,
  "init_long_aligned": true,
  "init_short_aligned": false,
  "impulse_long": true,
  "impulse_short": false,
  "aa_color": "GREEN_BULL",
  "aa_dir": -1,
  "aa_st": 89500,
  "aa_bull_shift": true,
  "aa_bear_shift": false,
  "aa_bars_since_bull_shift": 1,
  "aa_bars_since_bear_shift": null
}
```

Responsabilidad:

```text
- Informar si el trigger apoya long o short
- Informar alineación con Adaptive SuperTrend
- Enviar color/estado del Adaptive ST como dato extra
- Permitir que el backend decida prioridad o validación posterior
```

---

### 7.5 `quality`

```json
{
  "quality_score": 75,
  "quality_class": "VALID",
  "quality_approved": true,
  "setup_points": 7,
  "setup_validated_for_state": true,
  "phase_correct": true,
  "too_extended": false,
  "too_extended_block": false,
  "late_trend": false
}
```

Responsabilidad:

```text
- Enviar score calculado por Pine
- Indicar si el setup es válido según lógica local
- Informar si está extendido o tarde
- Alimentar validación y persistencia
```

---

### 7.6 `trade_plan`

```json
{
  "tp_sl_mode": "Percent",
  "entry_price": 90000,
  "tp_price": 90450,
  "sl_price": 89820,
  "tp_perc": 0.50,
  "sl_perc": 0.20,
  "rr_ratio": 2.5,
  "tp_atr_mult": null,
  "sl_atr_mult": null
}
```

Responsabilidad:

```text
- Informar entry / TP / SL
- Permitir cálculo de probabilidad TP antes que SL
- Permitir cálculo de RR
- Permitir futuro labeling de outcomes
```

---

### 7.7 `ml_tracking`

```json
{
  "track_for_outcome": true,
  "candidate_type": "INIT",
  "labeling_profile": "tp_sl_20bars_v1",
  "labeling_window_bars": 20,
  "ambiguous_rule": "AMBIGUOUS_SAME_BAR",
  "timeout_rule": "NO_HIT_EXPIRED",
  "entry_reference": "payload_entry_price_else_close",
  "tp_sl_source": "payload_trade_plan",
  "ml_target": "tp_before_sl",
  "exclude_ambiguous_from_binary": true,
  "created_from": "tradingview_alert_engine"
}
```

Responsabilidad:

```text
- Definir contrato de labeling
- Permitir separar señales trackeables
- Preparar datasets para ML posterior
```

---

### 7.8 `movement`

Contiene estado de movimiento, impulso y calidad de vela.

Responsabilidad:

```text
- Describir calidad del movimiento
- Medir impulso y eficiencia
- Detectar extensión o agotamiento
- Alimentar scoring y validación
```

---

### 7.9 `liquidity`

Responsabilidad:

```text
- Informar barridas de liquidez
- Informar absorciones
- Validar si hay liquidez reciente que apoye la entrada
```

---

### 7.10 `structure`

Responsabilidad:

```text
- Informar edad de estructura
- Confirmar micro breaks
- Detectar cambios de dirección
- Alimentar dashboard y validación
```

---

### 7.11 `htf_context`

Responsabilidad:

```text
- Usar fase HTF como contexto superior
- Filtrar o ponderar setups
- Detectar coherencia entre 1m y 5m
```

---

### 7.12 `execution`

Disponible para eventos reales de strategy.

Responsabilidad:

```text
- Registrar entradas y salidas reales
- Conectar alertas lógicas con operaciones ejecutadas
- Permitir análisis posterior de performance
```

---

## 8. Responsabilidad del Backend / Validation Layer

El backend ya no procesa todo dentro del webhook síncrono. Ahora su responsabilidad queda dividida en **dos fases**:

```text
Fase A: Ingesta rápida
Fase B: Procesamiento desacoplado
```

### Fase A — Ingesta rápida

```text
- Recibir alertas
- Validar secreto del webhook
- Parsear JSON
- Normalizar payloads
- Fusionar logical_event_core + logical_event_extra
- Guardar estado rápido en memoria
- Detectar payload parcial o completo
- Encolar payload completo en AWS SQS
- Responder rápido a TradingView
```

### Fase B — Procesamiento desacoplado

```text
- Consumir mensajes desde SQS
- Ejecutar validación cuando aplica
- Consultar Binance
- Calcular indicadores backend
- Analizar order book
- Analizar aggTrades
- Calcular scoring externo
- Estimar probabilidad TP antes que SL
- Persistir alertas y resultados en Supabase
- Enviar Telegram si una entrada es aprobada
- Exportar payload raw + validación a AWS S3
- Registrar errores en tabla de logs
- Exponer datos al dashboard
```

---

## 9. Tres niveles / módulos de validación

La validación sigue organizada en **tres niveles principales**.

```text
Nivel 1: Validación del payload y del evento
Nivel 2: Validación técnica con información de Pine Script
Nivel 3: Validación externa con mercado real, score y probabilidad TP/SL
```

---

### 9.1 Nivel 1 — Validación del payload y del evento

Responsabilidades:

```text
- Validar webhook secret
- Parsear el body recibido
- Verificar JSON válido
- Normalizar estructura base
- Identificar message_type
- Identificar event_uid
- Identificar signal.event
- Identificar signal.side
- Identificar symbol y timeframe
- Fusionar logical_event_core + logical_event_extra si aplica
- Decidir si el evento debe validarse o solo persistirse
- Decidir si debe encolarse
```

Eventos que pueden pasar a validación completa:

```text
LONG_ENTRY
SHORT_ENTRY
REAL_LONG_ENTRY
REAL_SHORT_ENTRY
```

Eventos que se reciben y se pueden persistir sin validación completa:

```text
LONG_INIT
SHORT_INIT
IMP_UP_AFTER_ADAPTIVE
IMP_DN_AFTER_ADAPTIVE
LONG_WATCH
SHORT_WATCH
LONG_ARMED
SHORT_ARMED
LONG_CANCEL
SHORT_CANCEL
```

---

### 9.2 Nivel 2 — Validación técnica con datos de Pine Script

Responsabilidades:

```text
- Evaluar quality_score_alert
- Evaluar quality_class_alert
- Evaluar quality_approved_alert
- Evaluar trigger_long / trigger_short
- Evaluar Adaptive SuperTrend
- Evaluar fase y régimen
- Evaluar HTF context
- Evaluar liquidez enviada por Pine
- Evaluar flags de extensión o late trend
- Evaluar setup_validation y setup_context
```

---

### 9.3 Nivel 3 — Validación externa con mercado real, score y probabilidad TP/SL

Responsabilidades:

```text
- Descargar klines 1m
- Descargar klines 5m
- Descargar order book
- Descargar aggTrades
- Calcular indicadores backend
- Analizar spread
- Analizar imbalance
- Analizar aggression
- Analizar delta_qty
- Analizar walls / vacuums
- Calcular score_external
- Calcular probability_tp_before_sl
- Generar validation_steps
- Aprobar o rechazar entrada
```

---

## 10. Arquitectura por capas del Backend

La aplicación backend quedó dividida siguiendo un patrón modular.

```text
API Layer
Core Layer
Service Layer
Repository Layer
AWS Integration Layer
Utils Layer
External Integrations
```

Patrón aplicado:

```text
API Layer → Service Layer → Repository Layer
```

Capas transversales:

```text
Core Layer
Utils Layer
AWS Integration Layer
External Services
```

---

## 11. Estructura actual del proyecto Backend

```text
backend/
│
├── api/
│   └── index.py
│
├── app/
│   ├── __init__.py
│   ├── main.py
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── health_routes.py
│   │   ├── dashboard_routes.py
│   │   ├── validation_routes.py
│   │   ├── webhook_routes.py
│   │   └── processing_sqs_routes.py
│   │
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py
│   │   ├── logging.py
│   │   ├── security.py
│   │   └── state.py
│   │
│   ├── repositories/
│   │   ├── __init__.py
│   │   └── supabase_repo.py
│   │
│   ├── services/
│   │   ├── __init__.py
│   │   ├── alert_service.py
│   │   ├── webhook_state_service.py
│   │   ├── queue_service.py
│   │   ├── sqs_processing_service.py
│   │   ├── webhook_background_service.py
│   │   ├── binance_service.py
│   │   ├── market_features_service.py
│   │   ├── probability_service.py
│   │   ├── scoring_service.py
│   │   ├── validation_service.py
│   │   ├── telegram_service.py
│   │   ├── databricks_export_service.py
│   │   └── error_log_service.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── json_utils.py
│       ├── math_utils.py
│       └── time_utils.py
│
├── requirements.txt
└── vercel.json
```

> Nota: los nombres exactos de algunos módulos pueden variar levemente según la refactorización real, pero esta es la arquitectura objetivo y documentada.

---

## 12. Flujo interno del webhook

### 12.1 `/api/webhook`

Responsabilidad:

```text
- Recibir alerta desde TradingView
- Validar secret
- Parsear raw body
- Construir payload
- Ensamblar CORE + EXTRA por event_uid
- Guardar estado rápido
- Si el payload está completo:
  - enviarlo a SQS
  - responder rápido
- Si el payload está incompleto:
  - marcar waiting_for_pair
  - responder OK esperando la otra parte
```

Flujo:

```text
POST /api/webhook
    ↓
validate_secret()
    ↓
parse_payload()
    ↓
assemble_event_payload()
    ↓
assemble_core_extra_by_event_uid()
    ↓
set_validation_queued()
    ↓
set_last_alert_fast_ack()
    ↓
enqueue_alert_to_sqs()
    ↓
return fast ack
```

---

## 13. Procesamiento desacoplado con AWS SQS

### 13.1 ¿Por qué se usa SQS?

SQS se usa para que TradingView no espere a que termine todo el procesamiento pesado.

Beneficios:

```text
- Evita timeouts del webhook
- Desacopla recepción y procesamiento
- Permite reintentos
- Hace más robusta la arquitectura
- Facilita escalado futuro
- Reduce riesgo de perder alertas por latencia
```

### 13.2 Cola principal y DLQ

Se recomiendan al menos estas colas:

```text
trading-alerts-queue
trading-alerts-dlq
```

### Cola principal

```text
- recibe alertas completas
- sirve como buffer operacional
```

### Dead Letter Queue

```text
- recibe mensajes que fallaron tras varios intentos
- sirve para troubleshooting y replay
```

### 13.3 Flujo de SQS

```text
FastAPI webhook
    ↓
SendMessage → trading-alerts-queue
    ↓
Proceso consumidor
    ↓
ReceiveMessage
    ↓
run_validation + persist_to_supabase + export_to_s3 + telegram
    ↓
DeleteMessage
```

---

## 14. AWS S3 como Data Lake

S3 se usa como almacenamiento analítico de eventos.

Responsabilidades:

```text
- Guardar payloads raw
- Guardar validaciones
- Guardar metadatos de ingesta
- Servir como Bronze para Databricks
- Permitir historización completa
- Permitir ML, analytics y backtesting posterior
```

Ejemplo de particionado lógico:

```text
s3://<bucket>/bronze/trading_alerts/
    processing_date=2026-05-02/
        symbol=btcusdc/
            tf=1m/
                message_type=logical_event_core/
                    event_<uid>.jsonl
```

La exportación actual construye eventos Bronze con campos como:

```text
- event_uid
- schema_version
- message_type
- trace_id
- symbol
- tf
- event
- side
- price
- validation_approve
- validation_confidence
- probability_tp_before_sl
- raw_payload
- raw_validation
- ingestion_ts
- processing_date
- source
- lakehouse_layer
```

---

## 15. Databricks / Lakehouse

Databricks consume desde S3 para análisis y ML.

### Responsabilidades

```text
- Leer Bronze desde S3
- Ingerir con Auto Loader
- Crear tablas Delta
- Limpiar y tipar datos
- Construir Silver
- Construir Gold
- Preparar datasets para entrenamiento
- Facilitar análisis histórico y backtesting
```

### Flujo analítico recomendado

```text
AWS S3 Bronze
    ↓
Databricks Auto Loader
    ↓
Tabla Bronze Delta
    ↓
Transformaciones / normalización
    ↓
Tabla Silver
    ↓
Agregaciones / features / labels / performance
    ↓
Tabla Gold
```

### Bronze

```text
- JSON raw
- mínima transformación
- máxima fidelidad al payload original
```

### Silver

```text
- campos tipados
- columnas normalizadas
- quality checks
- datasets unificados por event_uid / setup_id
```

### Gold

```text
- datasets de ML
- KPIs
- históricos de validación
- outcomes TP/SL
- performance operativa
```

---

## 16. IAM Roles, credenciales y permisos AWS

La arquitectura actual incluye o requiere permisos IAM para tres ámbitos:

```text
1. Backend / Vercel
2. Databricks
3. Gestión operativa AWS
```

### 16.1 Backend / Vercel

El backend desplegado en Vercel necesita credenciales para:

```text
- escribir en SQS
- leer y borrar de SQS si también consume
- escribir en S3
```

Permisos típicos necesarios:

### Para SQS

```text
sqs:SendMessage
sqs:ReceiveMessage
sqs:DeleteMessage
sqs:ChangeMessageVisibility
sqs:GetQueueAttributes
sqs:GetQueueUrl
```

### Para S3

```text
s3:PutObject
s3:GetObject
s3:ListBucket
s3:PutObjectAcl   (solo si se requiere)
```

### 16.2 Databricks

Databricks necesita un **Storage Credential** / IAM Role para:

```text
- leer del bucket S3
- gestionar external location
- usar file events si aplica
```

Permisos típicos:

```text
s3:GetObject
s3:ListBucket
s3:PutObject           (si Databricks también escribe checkpoints o tablas externas)
sns:CreateTopic        (si se usan file events)
sns:Subscribe
sns:SetTopicAttributes
sqs:CreateQueue        (si se usan file events)
sqs:SetQueueAttributes
sqs:ReceiveMessage
sqs:DeleteMessage
sqs:GetQueueAttributes
```

### 16.3 Recomendación de separación de identidades

Se recomienda separar:

```text
- IAM identity del backend
- IAM identity de Databricks
- IAM identity administrativa
```

Ejemplo lógico:

```text
BackendVercelAlertsUser / Role
DatabricksTradingLakehouseS3Role
AWSAdmin / IAM admin operator
```

---

## 17. Qué se guarda en Supabase y qué se guarda en Databricks

### 17.1 Regla práctica del proyecto

### Guardar en Supabase todo lo que necesite la aplicación en tiempo casi real

```text
- última alerta
- última validación
- estado del setup
- histórico reciente
- resultado aprobado/rechazado
- datos para Streamlit
- logs de errores backend
```

### Guardar en Databricks todo lo que quieras explotar analíticamente

```text
- todos los payloads
- todas las validaciones
- market snapshots
- features
- señales históricas
- resultados reales
- datasets para ML
- tablas Bronze/Silver/Gold
- backtesting
```

### 17.2 Supabase = storage operacional

Objetivo:

```text
- servir al dashboard
- mantener histórico consultable
- soportar estado operativo
- almacenar resultados de validación
- registrar errores
```

### 17.3 S3 + Databricks = storage analítico

Objetivo:

```text
- almacenar histórico completo y escalable
- permitir transformación masiva
- permitir ML y análisis offline
- separar operación y analítica
```

---

## 18. Persistencia en Supabase

Las tablas principales del sistema son:

```text
alert_events
trade_setups
validation_results
backend_error_logs
```

### 18.1 `alert_events`

Contiene cada evento persistido.

Responsabilidad:

```text
- guardar evento recibido
- guardar raw_payload
- guardar normalized_payload
- guardar technical_state
- guardar microstructure_state
- mantener trazabilidad por event_id / setup_id
```

### 18.2 `trade_setups`

Contiene el estado más reciente del setup.

Responsabilidad:

```text
- mantener lifecycle_state
- mantener última validación
- mantener contexto reciente
- facilitar lectura rápida por Streamlit
```

### 18.3 `validation_results`

Contiene el resultado de validación.

Responsabilidad:

```text
- accepted/rejected
- confidence
- probability_tp
- rr_estimate
- razones
- features
- decision_payload
```

### 18.4 `backend_error_logs`

Contiene errores del backend.

Responsabilidad:

```text
- capturar stage del error
- guardar mensaje y traceback
- guardar payload relacionado si existe
- guardar trace_id y contexto
- facilitar troubleshooting
```

---

## 19. Logging de errores

El sistema contempla la necesidad de persistir errores de backend.

Responsabilidades del error log:

```text
- registrar errores del webhook
- registrar errores del procesamiento SQS
- registrar errores de Supabase
- registrar errores de S3
- registrar errores de Telegram
- registrar errores no controlados
```

Campos recomendados:

```text
- created_at
- stage
- error_message
- traceback
- trace_id
- route
- event_uid
- payload
- context
```

---

## 20. Endpoints disponibles

### Health principal

```http
GET /
```

Devuelve estado general de la API.

### Última alerta

```http
GET /api/latest
```

Devuelve `LAST_ALERT`.

### Última validación

```http
GET /api/validation/latest
```

Devuelve `LAST_VALIDATION`.

### Historial en memoria

```http
GET /api/alerts
```

Devuelve historial local en memoria.

### Webhook TradingView

```http
POST /api/webhook
```

Endpoint principal para recibir alertas.

### Validación manual

```http
POST /api/validate
```

Permite validar un payload manualmente.

### Health Binance

```http
GET /api/health/binance
```

Prueba conexión con Binance.

### Health Supabase

```http
GET /api/health/supabase
```

Prueba conexión con Supabase.

### Histórico Supabase

```http
GET /api/alerts/supabase
```

Lee alertas guardadas en Supabase.

### Setups Supabase

```http
GET /api/setups/supabase
```

Lee setups guardados en Supabase.

### Procesar cola SQS manualmente

```http
POST /api/process/sqs
```

Procesa mensajes de la cola SQS de forma manual o interna.

### Procesar cola SQS por cron

```http
GET /api/process/sqs/cron
Authorization: Bearer <CRON_SECRET>
```

Endpoint para ser llamado por Vercel Cron o un scheduler externo y consumir mensajes desde SQS.

> Si el nombre exacto del endpoint cambia en tu código, actualízalo en este README.

---

## 21. Variables de entorno

Crear estas variables tanto en local como en Vercel.

### 21.1 Seguridad del webhook

```env
WEBHOOK_SECRET=MI_SECRET
```

Uso:

```text
- valida el secreto del webhook
- protege el endpoint de entrada
```

Header esperado por el backend:

```http
x-webhook-secret: MI_SECRET
```

> Si TradingView no puede enviar ese header, el sistema puede también validar el `secret` incluido en el payload, según tu implementación.

---

### 21.2 Validación

```env
VALIDATION_THRESHOLD=0.62
MIN_SCORE_THRESHOLD=55
REQUEST_TIMEOUT_SEC=8.0
VALIDATION_MODEL_VERSION=rules_v1
```

Uso:

```text
VALIDATION_THRESHOLD:
- umbral mínimo de probability_tp_before_sl para aprobar

MIN_SCORE_THRESHOLD:
- score externo mínimo para aprobar

REQUEST_TIMEOUT_SEC:
- timeout HTTP hacia Binance u otros servicios externos

VALIDATION_MODEL_VERSION:
- versión lógica del modelo/reglas guardada en validation_results
```

---

### 21.3 Supabase

```env
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxxxx
SUPABASE_ENABLED=true
```

Uso:

```text
- persistencia operacional
- lectura para dashboard
- guardado de alert_events
- guardado de trade_setups
- guardado de validation_results
- guardado de backend_error_logs
```

---

### 21.4 Telegram

```env
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Uso:

```text
- envía notificaciones cuando validation.approve == true
```

---

### 21.5 Machine Learning opcional

```env
ML_MODEL_PATH=
ML_FEATURES_JSON=
```

Uso:

```text
- modelo opcional sklearn/joblib
- features esperadas por el modelo
```

Si no están configuradas, el backend funciona igual con reglas / modelo híbrido base.

---

### 21.6 CORS

```env
ALLOWED_ORIGINS=*
```

Uso:

```text
- controla qué frontends pueden consumir la API
```

Ejemplo de producción:

```env
ALLOWED_ORIGINS=https://mi-dashboard.vercel.app,https://mi-streamlit-app.streamlit.app
```

---

### 21.7 AWS SQS

```env
AWS_REGION=eu-west-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
SQS_ENABLED=true
SQS_QUEUE_URL=https://sqs.eu-west-1.amazonaws.com/<account-id>/trading-alerts-queue
SQS_DLQ_URL=https://sqs.eu-west-1.amazonaws.com/<account-id>/trading-alerts-dlq
```

Uso:

```text
AWS_REGION:
- región donde vive la cola

AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY:
- credenciales del backend en Vercel para acceder a AWS

SQS_ENABLED:
- activa el uso de la cola

SQS_QUEUE_URL:
- cola principal

SQS_DLQ_URL:
- dead-letter queue
```

---

### 21.8 AWS S3 / Data Lake

```env
ENABLE_DATABRICKS_EXPORT=true
DATABRICKS_EXPORT_MODE=s3
AWS_S3_BUCKET=<tu-bucket>
AWS_S3_PREFIX=bronze/trading_alerts
AWS_S3_REGION=eu-west-1
```

Uso:

```text
ENABLE_DATABRICKS_EXPORT:
- activa exportación analítica

DATABRICKS_EXPORT_MODE:
- modo de exportación, por ejemplo s3

AWS_S3_BUCKET:
- bucket destino del data lake

AWS_S3_PREFIX:
- prefijo base donde se escriben los archivos Bronze

AWS_S3_REGION:
- región del bucket
```

> Si tu implementación reutiliza `AWS_REGION`, puedes no duplicar `AWS_S3_REGION`.

---

### 21.9 Cron / scheduler

```env
CRON_SECRET=<valor-largo-y-seguro>
```

Uso:

```text
- protege el endpoint llamado por el scheduler
- evita que terceros llamen al endpoint de procesamiento
```

Header esperado:

```http
Authorization: Bearer <CRON_SECRET>
```

> **Nunca** hardcodear este valor en `vercel.json` ni subirlo a GitHub.

---

### 21.10 Ejemplo `.env` local

```env
WEBHOOK_SECRET=MI_SECRET

VALIDATION_THRESHOLD=0.62
MIN_SCORE_THRESHOLD=55
REQUEST_TIMEOUT_SEC=8.0
VALIDATION_MODEL_VERSION=rules_v1

SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxxxx
SUPABASE_ENABLED=true

TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

ML_MODEL_PATH=
ML_FEATURES_JSON=

ALLOWED_ORIGINS=*

AWS_REGION=eu-west-1
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
SQS_ENABLED=true
SQS_QUEUE_URL=https://sqs.eu-west-1.amazonaws.com/<account-id>/trading-alerts-queue
SQS_DLQ_URL=https://sqs.eu-west-1.amazonaws.com/<account-id>/trading-alerts-dlq

ENABLE_DATABRICKS_EXPORT=true
DATABRICKS_EXPORT_MODE=s3
AWS_S3_BUCKET=<tu-bucket>
AWS_S3_PREFIX=bronze/trading_alerts

CRON_SECRET=<valor-largo-y-seguro>
```

---

### 21.11 Variables a crear en Vercel

En Vercel:

```text
Project Settings
        ↓
Environment Variables
        ↓
Add
```

Crear al menos:

```text
WEBHOOK_SECRET
VALIDATION_THRESHOLD
MIN_SCORE_THRESHOLD
REQUEST_TIMEOUT_SEC
VALIDATION_MODEL_VERSION
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
SUPABASE_ENABLED
TELEGRAM_ENABLED
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
ML_MODEL_PATH
ML_FEATURES_JSON
ALLOWED_ORIGINS
AWS_REGION
AWS_ACCESS_KEY_ID
AWS_SECRET_ACCESS_KEY
SQS_ENABLED
SQS_QUEUE_URL
SQS_DLQ_URL
ENABLE_DATABRICKS_EXPORT
DATABRICKS_EXPORT_MODE
AWS_S3_BUCKET
AWS_S3_PREFIX
CRON_SECRET
```

> `CRON_SECRET` se configura en Vercel Environment Variables, **no** en el repositorio.

---

## 22. Compatibilidad con Vercel

La app está preparada para Vercel con:

```text
api/index.py
vercel.json
```

### `api/index.py`

```python
from app.main import app
```

### `vercel.json`

Ejemplo seguro conservando `builds`, `routes` y agregando `crons` sin exponer secretos:

```json
{
  "version": 2,
  "builds": [
    {
      "src": "api/index.py",
      "use": "@vercel/python"
    }
  ],
  "routes": [
    {
      "src": "/(.*)",
      "dest": "api/index.py"
    }
  ],
  "crons": [
    {
      "path": "/api/process/sqs/cron?limit=10",
      "schedule": "* * * * *"
    }
  ]
}
```

> No incluir secretos en `vercel.json`.

---

## 23. Scheduler / procesamiento de la cola

Para que la cola SQS se procese periódicamente, hay dos opciones habituales:

```text
1. Vercel Cron llamando a /api/process/sqs/cron
2. Un scheduler externo llamando a /api/process/sqs/cron
```

Flujo:

```text
Scheduler
   ↓
GET /api/process/sqs/cron
Authorization: Bearer <CRON_SECRET>
   ↓
receive messages from SQS
   ↓
process each alert
   ├── run_validation()
   ├── persist_to_supabase()
   ├── export_event_for_databricks() → S3
   └── send_telegram_message() si aplica
   ↓
delete message from SQS
```

---

## 24. Servicios principales del Backend

### 24.1 `alert_service.py`

Responsabilidad:

```text
- parse_payload
- normalize_alert
- assemble_event_payload
- assemble_core_extra_by_event_uid
- build_history_item
- should_validate_payload
```

### 24.2 `webhook_state_service.py`

Responsabilidad:

```text
- actualizar LAST_VALIDATION como queued
- actualizar LAST_ALERT con fast ack
- marcar waiting_for_pair
```

### 24.3 `queue_service.py`

Responsabilidad:

```text
- enviar mensajes a SQS
- leer mensajes de SQS
- borrar mensajes procesados
```

### 24.4 `validation_service.py`

Responsabilidad:

```text
- ejecutar run_validation
- orquestar scoring y probabilidad
```

### 24.5 `telegram_service.py`

Responsabilidad:

```text
- construir mensaje Telegram
- enviar notificaciones solo si approve == true
```

### 24.6 `databricks_export_service.py`

Responsabilidad:

```text
- construir evento Bronze
- escribir JSONL al storage de destino
- actualmente orientado a S3 como storage final
```

### 24.7 `supabase_repo.py`

Responsabilidad:

```text
- decidir qué payload persistir
- insertar alert_events
- upsert trade_setups
- insertar validation_results
- leer histórico desde Supabase
```

### 24.8 `error_log_service.py`

Responsabilidad:

```text
- registrar errores backend en Supabase
- ayudar al troubleshooting
```

---

## 25. UI Layer / Panel Streamlit

Además del backend, el sistema cuenta con un **Panel Streamlit** que actúa como capa visual para consultar, interpretar y monitorear las alertas, validaciones y estados persistidos.

Patrón aplicado al panel:

```text
UI Layer → Services Layer → Clients / Repositories Layer → Utils / Config
```

Equivalencia conceptual con el backend:

```text
Backend API routes        → Streamlit views/pages
Backend services/*.py     → Streamlit services/*.py
Backend repositories/*.py → Streamlit clients/*.py / repositories/*.py
Backend core/*.py         → Streamlit core/*.py
Backend utils/*.py        → Streamlit utils/*.py
```

---

## 26. Responsabilidad general del Panel Streamlit

El panel de Streamlit no debe contener lógica pesada ni mezclar lógica de negocio con visualización.

Su responsabilidad es:

```text
- consultar endpoints del backend
- mostrar última alerta recibida
- mostrar última validación
- mostrar histórico local
- mostrar histórico desde Supabase
- mostrar market_snapshot
- mostrar structure_snapshot
- mostrar validation_steps
- mostrar analysis_trace
- mostrar analysis_summary
- mostrar estado del setup
- mostrar métricas visuales
- facilitar debugging operativo
- servir como dashboard para monitoreo del sistema
```

---

## 27. Estructura propuesta para el Panel Streamlit

```text
streamlit_app/
│
├── app.py
│
├── core/
│   ├── __init__.py
│   ├── config.py
│   ├── constants.py
│   └── session_state.py
│
├── clients/
│   ├── __init__.py
│   ├── backend_client.py
│   └── supabase_client.py
│
├── services/
│   ├── __init__.py
│   ├── alert_service.py
│   ├── validation_service.py
│   ├── market_snapshot_service.py
│   ├── metrics_service.py
│   └── formatting_service.py
│
├── views/
│   ├── __init__.py
│   ├── sidebar.py
│   ├── latest_alert_view.py
│   ├── validation_view.py
│   ├── alerts_history_view.py
│   ├── supabase_history_view.py
│   ├── market_snapshot_view.py
│   ├── technical_context_view.py
│   └── setup_detail_view.py
│
├── components/
│   ├── __init__.py
│   ├── cards.py
│   ├── tables.py
│   ├── badges.py
│   └── charts.py
│
├── utils/
│   ├── __init__.py
│   ├── json_utils.py
│   ├── time_utils.py
│   └── dataframe_utils.py
│
└── requirements.txt
```

---

## 28. Responsabilidades por fuente de datos

### TradingView

Responsable de:

```text
- generar señales
- enviar contexto técnico
- enviar trigger
- enviar quality score
- enviar estructura
- enviar liquidez detectada en Pine
- enviar HTF context
- enviar trade_plan
- enviar ml_tracking
```

### Backend FastAPI

Responsable de:

```text
- recibir alertas
- normalizar payloads
- ensamblar core + extra
- encolar a SQS
- procesar la cola
- validar entradas
- consultar Binance
- calcular microestructura
- calcular score externo
- estimar probabilidad TP antes SL
- persistir en Supabase
- exportar a S3
- notificar por Telegram
- exponer endpoints al panel
```

### AWS SQS

Responsable de:

```text
- desacoplar recepción y procesamiento
- actuar como buffer
- permitir reintentos
- evitar timeouts en TradingView
```

### AWS S3

Responsable de:

```text
- almacenar eventos analíticos
- servir como Bronze del lakehouse
- desacoplar operación y analítica
```

### Databricks

Responsable de:

```text
- ingerir Bronze desde S3
- construir Silver y Gold
- preparar datasets de ML
- facilitar analytics y backtesting
```

### Supabase

Responsable de:

```text
- guardar alert_events
- guardar trade_setups
- guardar validation_results
- guardar backend_error_logs
- servir histórico al dashboard
```

### Binance

Responsable de:

```text
- proveer OHLCV
- proveer datos de mercado para validación
- proveer depth y aggTrades
```

### Streamlit

Responsable de:

```text
- visualizar alertas
- visualizar validaciones
- visualizar histórico
- mostrar snapshots técnicos
- mostrar métricas
- facilitar debugging y monitoreo
```

---

## 29. Ejecución local Backend

Desde la carpeta `backend`:

```bash
python -m pip install -r requirements.txt
python -m uvicorn app.main:app --reload
```

URL local:

```text
http://127.0.0.1:8000/
```

---

## 30. Pruebas básicas Backend

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/api/latest
curl http://127.0.0.1:8000/api/validation/latest
curl http://127.0.0.1:8000/api/health/binance
curl http://127.0.0.1:8000/api/health/supabase
```

### Prueba webhook manual

```bash
curl -X POST "http://127.0.0.1:8000/api/webhook" \
  -H "Content-Type: application/json" \
  -H "x-webhook-secret: MI_SECRET" \
  -d '{"schema_version":"2.0","message_type":"logical_event_core","event_uid":"test_1","secret":"MI_SECRET","source":{"platform":"tradingview","engine":"pine_indicator","script":"SETUP_CLASSIFIER_MASTER_v7_3_FULL_API_ALERTS"},"signal":{"event":"LONG_INIT","side":"long","setup":"INIT_LONG","entry_type":"INIT","setup_state":"LONG_INIT","setup_side":"long","symbol":"BTCUSDC","tf":"1m","price":90000,"close":90000,"open":89900,"high":90100,"low":89800}}'
```

### Prueba procesamiento cron

```bash
curl "http://127.0.0.1:8000/api/process/sqs/cron?limit=10" \
  -H "Authorization: Bearer <CRON_SECRET>"
```

---

## 31. Ejecución local Panel Streamlit

Desde la carpeta del panel:

```bash
streamlit run app.py
```

Variables mínimas del panel:

```env
BACKEND_BASE_URL=http://127.0.0.1:8000
```

En producción:

```env
BACKEND_BASE_URL=https://TU_BACKEND.vercel.app
```

---

## 32. Estado final de la refactorización

La refactorización ya no es solo modularización del backend monolítico, sino evolución hacia una arquitectura **desacoplada y orientada a pipeline**.

### Resultado Backend

```text
- backend más mantenible
- menor riesgo al modificar lógica
- rutas separadas de servicios
- persistencia aislada
- validación aislada
- scoring aislado
- probabilidad aislada
- Telegram aislado
- configuración centralizada
- estado global centralizado
- compatible con Vercel
- compatible con TradingView
- compatible con Supabase
- compatible con AWS SQS
- compatible con AWS S3
- preparado para Databricks
```

### Resultado esperado Panel Streamlit

```text
- UI más mantenible
- requests aislados en clients/
- transformación de datos aislada en services/
- renderizado aislado en views/
- componentes visuales reutilizables
- configuración centralizada
- dashboard preparado para crecer
- menor riesgo al agregar nuevas visualizaciones
```

---

## 33. Commit representativo Backend

```bash
git add .
git commit -m "refactor trading validation backend into modular services and async queue pipeline" -m "Split monolithic backend into FastAPI routes, core config/state/logging/security, alert parsing, webhook state handling, AWS SQS queue integration, decoupled processing, Binance validation, Telegram notification, Supabase repository, Databricks/S3 export and backend error logging while preserving operational behavior."
```

---

## 34. Commit representativo Panel Streamlit

```bash
git add .
git commit -m "define modular Streamlit dashboard architecture" -m "Document UI Layer architecture for the trading validation dashboard, separating app orchestration, views, components, services, backend clients, core configuration and utilities."
```

---

## 35. Resumen ejecutivo

Esta solución está compuesta por:

```text
TradingView / Pine Script
Backend FastAPI / Validation Layer
AWS SQS
AWS S3
Supabase
Databricks
Telegram
Binance
Panel Streamlit / UI Layer
```

TradingView se encarga de detectar señales, contexto, fases, triggers y setups.

El backend se encarga de:

```text
- recibir alertas
- fusionar mensajes CORE/EXTRA
- normalizar datos
- responder rápido al webhook
- encolar eventos en SQS
- procesar eventos de forma desacoplada
- validar entradas reales
- enriquecer con Binance
- calcular score externo
- calcular probabilidad TP antes SL
- persistir en Supabase
- exportar a S3
- notificar por Telegram
- servir datos al dashboard
- registrar errores
```

AWS SQS se encarga de:

```text
- desacoplar recepción y procesamiento
- soportar reintentos
- evitar timeouts de TradingView
```

AWS S3 se encarga de:

```text
- almacenar datos del lakehouse
- servir de capa Bronze
- alimentar Databricks
```

Databricks se encarga de:

```text
- ingerir datos desde S3
- construir Bronze / Silver / Gold
- preparar datasets de ML y analytics
```

Supabase se encarga de:

```text
- servir almacenamiento operacional y de dashboard
```

El panel Streamlit se encarga de:

```text
- consultar el backend
- mostrar alertas
- mostrar validaciones
- mostrar histórico
- mostrar snapshots técnicos
- mostrar métricas
- facilitar debugging y monitoreo
```

La arquitectura backend sigue el patrón:

```text
API Layer → Service Layer → Repository Layer
```

La arquitectura Streamlit sigue el patrón:

```text
UI Layer → Services Layer → Clients / Repositories Layer → Utils / Config
```

La validación queda organizada en tres niveles:

```text
Nivel 1: Validación del payload y evento
Nivel 2: Validación técnica con datos de Pine Script
Nivel 3: Validación externa con mercado real, score y probabilidad TP/SL
```

La arquitectura de datos queda separada así:

```text
Supabase = operación y dashboard
S3 + Databricks = analítica, histórico masivo, ML y backtesting
```

## X. Nuevas funcionalidades y servicios AWS incorporados

### Problema que surgió

Durante la evolución del sistema apareció un problema operativo y arquitectónico importante: el webhook de TradingView no debía ejecutar procesamiento pesado dentro del mismo request.

TradingView envía alertas en tiempo real y espera una respuesta rápida. Si el backend intenta ejecutar validación, consultas externas, persistencia, notificaciones y exportación analítica dentro del mismo flujo síncrono, aumenta el riesgo de:

```text
- timeout del webhook
- pérdida de alertas
- latencia excesiva
- bloqueo del flujo si falla Supabase
- bloqueo del flujo si falla Telegram
- bloqueo del flujo si falla la exportación a S3
- acoplamiento excesivo entre recepción, validación, persistencia y analítica
```

El flujo anterior podía terminar mezclando demasiadas responsabilidades en una sola ejecución:

```text
recepción de alerta
  ↓
validación
  ↓
consulta a Binance
  ↓
scoring
  ↓
persistencia en Supabase
  ↓
notificación Telegram
  ↓
exportación analítica
```

Esto no era adecuado para señales de trading en temporalidad de 1 minuto, donde la prioridad es recibir la alerta, validar lo mínimo necesario, encolarla y responder rápido.

---

### Solución implementada

La solución fue evolucionar el sistema hacia una arquitectura desacoplada y orientada a eventos usando servicios AWS.

El flujo actualizado queda así:

```text
TradingView / Pine Script
        ↓
FastAPI / Vercel /api/webhook
        ↓
validación rápida + parseo + normalización
        ↓
AWS SQS
        ↓
AWS Lambda Consumer
        ↓
ensamblado CORE + EXTRA
        ↓
validación + Binance + scoring + probabilidad TP/SL
        ├────────────→ Supabase operacional
        ├────────────→ Telegram si approve=true
        └────────────→ AWS S3 Bronze
                                ↓
                         Databricks Auto Loader
                                ↓
                       Bronze / Silver / Gold
                                ↓
                     Analytics / ML / Backtesting
```

Con este cambio, el webhook deja de ser responsable del procesamiento pesado y se convierte en una capa rápida de ingesta.

---

## X.1 Objetivo de la nueva arquitectura AWS

La nueva arquitectura AWS incorporada tiene los siguientes objetivos:

```text
- evitar timeouts de TradingView
- desacoplar ingesta y procesamiento
- permitir reintentos automáticos
- conservar mensajes fallidos en DLQ
- ensamblar correctamente logical_event_core + logical_event_extra
- ejecutar validaciones pesadas fuera del webhook
- persistir resultados operativos en Supabase
- exportar eventos validados a S3
- alimentar Databricks desde S3
- preparar datos para analytics, ML y backtesting
```

---

## X.2 Servicios AWS incorporados

En esta fase se trabajaron e incorporaron los siguientes servicios AWS:

```text
1. AWS SQS
2. AWS SQS Dead Letter Queue
3. AWS Lambda
4. AWS S3
5. AWS IAM
6. AWS ECR / Lambda Container Image
```

---

## X.3 AWS SQS — Cola principal de alertas

### Problema resuelto

El backend necesitaba responder rápido a TradingView sin depender de la duración de la validación ni de servicios externos.

### Solución

Se incorporó AWS SQS como cola desacoplada entre el webhook y el procesamiento pesado.

Cola principal:

```text
trading-alerts-queue
```

### Responsabilidad de SQS

```text
- recibir mensajes generados por el webhook
- actuar como buffer de alertas
- desacoplar FastAPI del consumidor
- permitir reintentos
- absorber picos pequeños de tráfico
- evitar pérdida inmediata si el consumidor no está disponible
```

### Flujo con SQS

```text
FastAPI /api/webhook
        ↓
SendMessage
        ↓
trading-alerts-queue
        ↓
Lambda Consumer
```

### Beneficios obtenidos

```text
- el webhook responde rápido
- el procesamiento queda fuera del request de TradingView
- se reduce el riesgo de timeout
- se mejora la robustez
- se prepara el sistema para escalar consumidores
```

---

## X.4 AWS SQS DLQ — Dead Letter Queue

### Problema resuelto

Si un mensaje falla varias veces durante su procesamiento, no debe perderse ni bloquear indefinidamente el flujo principal.

### Solución

Se configuró una Dead Letter Queue asociada a la cola principal.

Cola DLQ:

```text
trading-alerts-dlq
```

### Responsabilidad de la DLQ

```text
- almacenar mensajes que fallan repetidamente
- permitir análisis posterior del error
- facilitar replay manual
- evitar que mensajes problemáticos bloqueen la cola principal
```

### Casos típicos que pueden terminar en DLQ

```text
- payload corrupto
- error persistente de schema
- fallo repetido de validación crítica
- fallo repetido de Supabase
- fallo repetido de S3
- error no controlado en Lambda
```

---

## X.5 AWS Lambda — Consumidor desacoplado de SQS

### Problema resuelto

Vercel Cron no era suficiente para consumir SQS con la frecuencia necesaria, ya que el plan actual limita las ejecuciones de cron y no sirve para señales de trading casi en tiempo real.

### Solución

Se incorporó AWS Lambda como consumidor nativo de SQS.

Lambda creada:

```text
trading-alerts-consumer
```

### Responsabilidad de Lambda

```text
- activarse automáticamente cuando llegan mensajes a SQS
- leer mensajes de la cola
- procesar cada record recibido
- fusionar fragmentos CORE y EXTRA si aplica
- ejecutar process_alert_background()
- persistir en Supabase
- exportar a S3
- enviar Telegram si corresponde
- devolver batchItemFailures si un mensaje falla
```

### Beneficios frente a Vercel Cron

```text
- ejecución automática por evento
- menor latencia
- no depende de cron cada minuto
- reintentos gestionados por AWS
- integración nativa con SQS
- escalado administrado
- mejor separación de responsabilidades
```

### Comportamiento validado

Se validó el siguiente flujo:

```text
logical_event_core recibido
        ↓
se guarda fragmento
        ↓
status = WAITING_PAIR
        ↓
logical_event_extra recibido
        ↓
se completa el par
        ↓
status = READY
        ↓
se construye logical_event_full
        ↓
se ejecuta validación
        ↓
se persiste en Supabase
        ↓
se exporta a S3
        ↓
status = PROCESSED
```

---

## X.6 Lambda Container Image

### Problema resuelto

El paquete ZIP de Lambda superó los límites prácticos de tamaño debido a dependencias pesadas como:

```text
numpy
pandas
scipy
scikit-learn
joblib
fastapi
supabase
httpx
boto3
```

Además, al empaquetar desde Windows aparecieron errores de compatibilidad binaria, por ejemplo con NumPy.

### Solución

Se migró el despliegue de Lambda hacia imagen Docker / Lambda Container Image.

### Beneficios

```text
- evita límite estricto del ZIP
- permite dependencias pesadas
- evita problemas de binarios Windows/Linux
- permite empaquetado reproducible
- facilita despliegue vía ECR
```

### Flujo de despliegue containerizado

```text
Docker build
        ↓
Docker tag
        ↓
Push a AWS ECR
        ↓
Lambda usa imagen desde ECR
```

### Resultado

Lambda quedó ejecutando el consumidor con dependencias compatibles con el runtime Linux de AWS.

---

## X.7 AWS ECR — Repositorio para imagen Lambda

### Problema resuelto

Para usar Lambda con imagen de contenedor, era necesario almacenar la imagen Docker en un registro compatible con AWS.

### Solución

Se usó AWS ECR como repositorio de imágenes.

### Responsabilidad de ECR

```text
- almacenar la imagen Docker del consumidor
- versionar imágenes por tag
- servir la imagen a Lambda
- permitir despliegues reproducibles
```

### Imagen objetivo

```text
trading-alerts-consumer
```

### Flujo conceptual

```text
local Docker image
        ↓
AWS ECR repository
        ↓
AWS Lambda function
```

---

## X.8 Fragment Store para CORE + EXTRA

### Problema resuelto

TradingView puede enviar `logical_event_core` y `logical_event_extra` como mensajes separados. Estos fragmentos pueden llegar:

```text
- en distinto orden
- en distintos mensajes SQS
- con segundos de diferencia
- incluso reintentados
```

Si se ejecuta la validación con solo CORE o solo EXTRA, faltan campos relevantes de contexto, movimiento, liquidez, estructura y HTF.

### Solución

Se incorporó un servicio de buffer de fragmentos:

```text
app/services/sqs_fragment_store_service.py
```

Tabla usada:

```text
sqs_alert_fragments
```

### Responsabilidad del fragment store

```text
- guardar logical_event_core
- guardar logical_event_extra
- correlacionar ambos por event_uid
- marcar WAITING_PAIR si falta un fragmento
- marcar READY si ambos existen
- construir logical_event_full
- marcar PROCESSED al completar el flujo
- marcar ERROR si falla el procesamiento
```

### Estados manejados

```text
WAITING_PAIR
READY
PROCESSED
ERROR
```

### Flujo de ensamblado

```text
CORE recibido
    ↓
guardar core_payload
    ↓
status = WAITING_PAIR

EXTRA recibido
    ↓
guardar extra_payload
    ↓
status = READY
    ↓
merge_core_extra_payloads()
    ↓
logical_event_full
    ↓
process_alert_background()
```

---

## X.9 Mejora de idempotencia con upsert

### Problema detectado

Durante las pruebas se observó un error de duplicado en Supabase:

```text
duplicate key value violates unique constraint "sqs_alert_fragments_event_uid_key"
```

Esto ocurría porque un `event_uid` podía existir ya en la tabla cuando el servicio intentaba hacer un insert nuevo.

### Solución aplicada

Se cambió el insert directo por un upsert usando `event_uid` como clave de conflicto.

Cambio conceptual:

```text
insert(row)
```

reemplazado por:

```text
upsert(row, on_conflict="event_uid")
```

### Resultado

```text
- se reducen errores por duplicados
- se mejora tolerancia a reintentos
- se soporta mejor concurrencia
- se evita que un fragmento repetido rompa el pipeline
```

---

## X.10 process_alert_background reutilizable fuera de FastAPI

### Problema resuelto

La función de procesamiento originalmente estaba asociada al flujo del backend. Para usar Lambda, era necesario que pudiera ejecutarse fuera de FastAPI.

### Solución

Se adaptó `process_alert_background()` para que sea reutilizable desde distintos contextos.

Ubicación:

```text
app/services/webhook_background_service.py
```

### Responsabilidades actuales

```text
- decidir si el payload debe validarse
- ejecutar run_validation()
- actualizar LAST_VALIDATION
- enviar Telegram si approve=true
- persistir en Supabase
- exportar a Databricks/S3
- actualizar LAST_ALERT
- registrar errores en backend_error_logs
- devolver estado ok / critical_error
```

### Contextos desde los que puede ejecutarse

```text
- FastAPI
- AWS Lambda
- script local
- tests unitarios
```

### Regla de errores aplicada

```text
Validación: crítico
Supabase: crítico
S3 / Databricks export: crítico
Telegram: no crítico
LAST_ALERT update: no crítico
```

---

## X.11 AWS S3 — Data Lake Bronze

### Problema resuelto

Supabase es útil para operación y dashboard, pero no es el lugar ideal para guardar histórico masivo, raw payloads completos y datasets futuros de ML.

### Solución

Se incorporó AWS S3 como almacenamiento analítico Bronze.

Bucket:

```text
trading-lakehouse-btc-s3
```

Prefijo base:

```text
bronze/trading_alerts
```

### Responsabilidad de S3

```text
- almacenar eventos procesados en formato JSONL
- conservar raw_payload completo
- conservar raw_validation completo
- servir como entrada para Databricks
- mantener histórico escalable
- separar operación y analítica
```

### Estructura de particionado

```text
s3://trading-lakehouse-btc-s3/bronze/trading_alerts/
    processing_date=YYYY-MM-DD/
        symbol=btcusdc/
            tf=1m/
                message_type=logical_event_full/
                    event_<event_uid>_<timestamp>.jsonl
```

### Ejemplo validado

```text
s3://trading-lakehouse-btc-s3/bronze/trading_alerts/processing_date=2026-05-02/symbol=btcusdc/tf=1m/message_type=logical_event_full/event_test_s3_final_010_20260502T211920389832.jsonl
```

---

## X.12 Servicio de exportación a Databricks / S3

### Servicio trabajado

```text
app/services/databricks_export_service.py
```

### Servicio de almacenamiento S3

```text
app/services/s3_storage_service.py
```

### Responsabilidad

```text
- construir evento Bronze
- serializar como JSONL
- construir ruta particionada
- subir archivo a S3
- devolver s3_uri
- registrar logs de éxito o error
```

### Contrato Bronze exportado

Cada evento exportado contiene:

```text
event_uid
schema_version
message_type
trace_id
symbol
tf
event
side
price
validation_approve
validation_confidence
probability_tp_before_sl
raw_payload
raw_validation
ingestion_ts
processing_date
source
lakehouse_layer
```

### Resultado validado

Se validó correctamente:

```text
- generación del JSONL
- escritura en S3
- path particionado
- log s3_upload_ok
- log databricks_export_s3_success
```

---

## X.13 Databricks Auto Loader desde S3

### Problema resuelto

Una vez los eventos estaban en S3, era necesario conectarlos con Databricks para construir el Lakehouse.

### Solución

Se usó Databricks Auto Loader para leer desde S3.

### Capa Bronze

Tabla:

```text
trading.bronze.alerts_raw
```

Fuente:

```text
s3://trading-lakehouse-btc-s3/bronze/trading_alerts/
```

### Funcionalidades de Bronze

```text
- lectura incremental desde S3
- uso de schemaLocation
- checkpoint externo
- evolución de schema
- lectura de _metadata.file_path
- ingestión hacia Delta Lake
```

### Resultado

Los archivos exportados por Lambda a S3 son ingeridos por Databricks como capa Bronze.

---

## X.14 Capas Bronze, Silver y Gold trabajadas

### Bronze

Responsabilidad:

```text
- ingesta raw desde S3
- mínima transformación
- trazabilidad de archivo origen
- conservación de raw_payload y raw_validation
```

Tabla:

```text
trading.bronze.alerts_raw
```

### Silver

Responsabilidad:

```text
- limpiar datos
- aplanar campos clave
- normalizar symbol / side
- extraer validation
- extraer trade_plan
- extraer market_snapshot
- extraer structure_snapshot
- extraer ml_tracking
- deduplicar por clave técnica
```

Tabla:

```text
trading.silver.alerts_clean
```

### Gold

Responsabilidad:

```text
- construir tablas de consumo final
- preparar señales validadas
- calcular métricas agregadas
- preparar candidatos para ML
```

Tablas:

```text
trading.gold.validated_trade_signals
trading.gold.signal_quality_metrics
trading.gold.ml_training_candidates
```

---

## X.15 AWS IAM — Permisos trabajados

### Problema resuelto

Lambda necesitaba permisos para escribir en S3, consumir SQS y escribir logs en CloudWatch.

### Rol Lambda

Rol usado:

```text
trading-alerts-lambda-role
```

### Permisos utilizados durante pruebas

```text
AWSLambdaBasicExecutionRole
AmazonSQSFullAccess
AmazonS3FullAccess
```

### Responsabilidades cubiertas

```text
AWSLambdaBasicExecutionRole:
- escribir logs en CloudWatch

AmazonSQSFullAccess:
- leer mensajes de SQS
- manejar reintentos
- consumir cola principal

AmazonS3FullAccess:
- escribir JSONL en el bucket Bronze
```

### Recomendación futura

Para producción, reemplazar políticas full access por políticas mínimas específicas:

```text
sqs:ReceiveMessage
sqs:DeleteMessage
sqs:GetQueueAttributes
sqs:ChangeMessageVisibility
s3:PutObject
s3:GetObject
s3:ListBucket
logs:CreateLogGroup
logs:CreateLogStream
logs:PutLogEvents
```

---

## X.16 Variables de entorno AWS incorporadas

Variables relevantes para el nuevo flujo:

```env
AWS_REGION=eu-west-1

SQS_QUEUE_URL=https://sqs.eu-west-1.amazonaws.com/<account-id>/trading-alerts-queue
SQS_DLQ_URL=https://sqs.eu-west-1.amazonaws.com/<account-id>/trading-alerts-dlq

ENABLE_DATABRICKS_EXPORT=true
DATABRICKS_EXPORT_TARGET=s3

S3_BUCKET_NAME=trading-lakehouse-btc-s3
S3_BASE_PREFIX=bronze/trading_alerts
```

Variables complementarias usadas por el consumidor:

```env
WEBHOOK_SECRET=MI_SECRET

SUPABASE_URL=https://<project-id>.supabase.co
SUPABASE_SERVICE_ROLE_KEY=<service-role-key>

TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

VALIDATION_THRESHOLD=0.62
MIN_SCORE_THRESHOLD=55
REQUEST_TIMEOUT_SEC=8.0
```

---

## X.17 Problemas detectados durante la implementación y correcciones

### 1. Paquete ZIP demasiado grande

Problema:

```text
El ZIP de Lambda superaba el tamaño permitido.
```

Solución:

```text
Migración a Lambda Container Image usando Docker + ECR.
```

---

### 2. Dependencias incompatibles generadas desde Windows

Problema:

```text
numpy/scipy podían empaquetarse con binarios no compatibles con Lambda Linux.
```

Solución:

```text
Construcción dentro de contenedor compatible con AWS Lambda.
```

---

### 3. Falta de dependencias en Lambda

Problema:

```text
No module named 'fastapi'
No module named 'scipy'
```

Solución:

```text
Revisión del empaquetado y uso de imagen containerizada con requirements completos.
```

---

### 4. Duplicate key en sqs_alert_fragments

Problema:

```text
duplicate key value violates unique constraint "sqs_alert_fragments_event_uid_key"
```

Solución:

```text
Cambio de insert a upsert con on_conflict="event_uid".
```

---

### 5. S3_BUCKET_NAME no configurado

Problema:

```text
S3_BUCKET_NAME is not configured
```

Solución:

```text
Agregar S3_BUCKET_NAME en variables de entorno de Lambda.
```

---

### 6. Supabase trigger con updated_at

Problema observado:

```text
record "new" has no field "updated_at"
```

Causa probable:

```text
Existía un trigger o función de update esperando una columna updated_at en una tabla que no la tenía.
```

Solución aplicada en la validación final:

```text
Se corrigió el estado de Supabase y las pruebas posteriores persistieron correctamente.
```

---

## X.18 Estado validado al final de esta fase

Al cierre de esta fase se validó correctamente:

```text
- Lambda recibe mensajes desde SQS
- CORE queda en WAITING_PAIR
- EXTRA completa el par
- se genera logical_event_full
- se ejecuta validación
- se consulta Binance
- se calculan validation_steps
- se persiste en Supabase
- se escribe JSONL en S3
- se genera s3_uri correcto
- Databricks lee Bronze desde S3
- Silver transforma correctamente
- Gold genera tablas analíticas
```

---

## X.19 Arquitectura actualizada con AWS

```text
┌──────────────────────────────┐
│ TradingView / Pine Script    │
│ JSON schema_version 2.0      │
│ CORE / EXTRA / EXECUTED      │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ FastAPI / Vercel             │
│ /api/webhook                 │
│ - valida secret              │
│ - parsea payload             │
│ - normaliza                  │
│ - encola rápido              │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ AWS SQS                      │
│ trading-alerts-queue         │
│ + DLQ                        │
└──────────────┬───────────────┘
               │
               ▼
┌──────────────────────────────┐
│ AWS Lambda Consumer          │
│ - consume SQS                │
│ - une CORE + EXTRA           │
│ - ejecuta validación         │
│ - persiste resultados        │
└───────┬──────────────┬───────┘
        │              │
        ▼              ▼
┌──────────────┐   ┌─────────────────────┐
│ Supabase     │   │ AWS S3 Bronze        │
│ Operacional  │   │ JSONL particionado   │
└──────┬───────┘   └──────────┬──────────┘
       │                      │
       ▼                      ▼
┌──────────────┐   ┌─────────────────────┐
│ Dashboard    │   │ Databricks           │
│ Streamlit    │   │ Bronze/Silver/Gold   │
└──────────────┘   └──────────┬──────────┘
                              │
                              ▼
                    ┌─────────────────────┐
                    │ Analytics / ML       │
                    │ Backtesting          │
                    └─────────────────────┘
```

---

## X.20 Resumen ejecutivo

En esta fase se incorporó una arquitectura AWS desacoplada para soportar mejor la recepción y procesamiento de señales de trading.

La mejora principal fue separar el webhook del procesamiento pesado:

```text
Antes:
TradingView → Webhook → Validación pesada → Persistencia → Export

Ahora:
TradingView → Webhook rápido → SQS → Lambda → Validación → Supabase + S3 → Databricks
```

Los servicios AWS añadidos permiten:

```text
- desacoplar ingesta y procesamiento
- evitar timeouts
- manejar reintentos
- conservar mensajes fallidos en DLQ
- procesar señales en Lambda
- escribir histórico analítico en S3
- alimentar Databricks para Lakehouse
```

El sistema queda preparado para evolucionar hacia una arquitectura de microservicios más clara, donde cada responsabilidad pueda separarse progresivamente:

```text
Webhook Service
Queue Service
Assembler Service
Validation Service
Persistence Service
Lakehouse Export Service
Notification Service
```

Estado final de esta fase:

```text
VALIDADO:
- SQS operativo
- Lambda consumer operativo
- fragment store operativo
- ensamblado CORE + EXTRA operativo
- validación ejecutándose desde Lambda
- Supabase operativo
- S3 Bronze operativo
- Databricks Bronze/Silver/Gold operativo

PENDIENTE / FUTURO:
- endurecer IAM con permisos mínimos
- separar Lambda assembler y Lambda validator si crece el volumen
- añadir monitoreo CloudWatch más formal
- definir alarmas sobre DLQ
- automatizar jobs Databricks
- construir labeling real de outcomes TP/SL
- entrenar modelos ML sobre Gold
```