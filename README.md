# TradingView Validation Layer API

## 1. Descripción general

Esta API es una **Validation Layer** para un sistema de trading algorítmico basado en alertas de TradingView.

Su objetivo principal es recibir señales generadas por Pine Script, normalizarlas, fusionar eventos complementarios, enriquecerlas con datos de mercado externos, validar entradas operativas y persistir información completa para análisis, dashboard, métricas y futuros modelos de Machine Learning.

El flujo general es:

```text
TradingView Pine Script
        ↓
Alertas JSON
        ↓
FastAPI Backend / Validation Layer
        ↓
Normalización + Merge CORE/EXTRA
        ↓
Validación de entradas con Binance + scoring + probabilidad TP/SL
        ↓
Supabase + Memoria local + Telegram
        ↓
Dashboard / Streamlit / Análisis histórico / ML futuro
```

Esta API no reemplaza la lógica de Pine Script. La API actúa como una capa posterior de validación, persistencia y enriquecimiento.

---

## 2. Responsabilidades del sistema

El sistema está dividido en dos grandes responsabilidades:

```text
1. TradingView / Pine Script
2. Backend FastAPI / Validation Layer
```

---

## 3. Responsabilidad de Pine Script / TradingView

Pine Script es responsable de detectar el contexto técnico inicial y enviar alertas estructuradas.

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
- Información de Hull / SuperTrend / Setup Engine
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

## 4. Información recibida en cada alerta

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
  "trade_plan": {}
}
```

---

## 5. Bloques de información de la alerta

### 5.1 `source`

Identifica el origen de la alerta.

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

### 5.2 `signal`

Contiene la información principal de la señal.

```json
{
  "event": "LONG_INIT",
  "side": "long",
  "setup": "INIT_LONG",
  "entry_type": "INIT",
  "setup_state": "LONG_INIT",
  "setup_side": "long",
  "symbol": "BTCUSDC",
  "tf": "1m",
  "timestamp": "...",
  "bar_time": 123456789,
  "bar_index": 1000,
  "price": 90000,
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
```

---

### 5.3 `context`

Contiene el contexto macro/lógico del setup.

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
- Alimentar dashboard y Supabase
```

---

### 5.4 `trigger`

Contiene la información del disparador técnico.

```json
{
  "trigger_long": true,
  "trigger_short": false,
  "ast_bull": true,
  "ast_bear": false,
  "hull_bull": true,
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
- No eliminar INIT aunque Adaptive no esté alineado
- Permitir que backend decida prioridad o validación posterior
```

---

### 5.5 `quality`

Contiene la evaluación interna de Pine Script.

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
- Indicar si el setup es válido según la lógica local
- Informar si está extendido o tarde
- Alimentar validación y Supabase
```

---

### 5.6 `trade_plan`

Contiene el plan de operación sugerido por Pine Script.

```json
{
  "tp_sl_mode": "Percent",
  "tp_price": 90450,
  "sl_price": 89820,
  "tp_perc": 0.50,
  "sl_perc": 0.20,
  "tp_atr_mult": null,
  "sl_atr_mult": null
}
```

Responsabilidad:

```text
- Informar TP y SL
- Permitir cálculo de probabilidad TP antes que SL
- Permitir cálculo de RR
- Alimentar validación y dashboard
```

---

### 5.7 `movement`

Contiene estado de movimiento, impulso y calidad de vela.

```json
{
  "mov_state": "IMPULSE",
  "efficiency_local": 0.7,
  "efficiency_global": 0.6,
  "impulse": 1.1,
  "expand_ctx": true,
  "compress_ctx": false,
  "dist_atr_now": 1.2,
  "atr": 100,
  "range": 150,
  "body_pct": 0.6,
  "adx": 24,
  "plus_di": 28,
  "minus_di": 14,
  "ema_spread_atr": 0.2,
  "ema_slope": 1,
  "too_extended_long_warn": false,
  "too_extended_short_warn": false,
  "too_extended_long_block": false,
  "too_extended_short_block": false,
  "late_long_trend": false,
  "late_short_trend": false,
  "up_extended": false,
  "down_extended": false,
  "exh_bull": false,
  "exh_bear": false
}
```

Responsabilidad:

```text
- Describir calidad del movimiento
- Medir impulso y eficiencia
- Detectar extensión o agotamiento
- Alimentar scoring y validación
```

---

### 5.8 `liquidity`

Contiene eventos de liquidez detectados por Pine.

```json
{
  "liq_state": "BULLISH",
  "sweep_high": false,
  "sweep_low": true,
  "absorb_bull": true,
  "absorb_bear": false,
  "bars_since_sweep_low": 2,
  "bars_since_sweep_high": 999,
  "bars_since_absorb_bull": 3,
  "bars_since_absorb_bear": 999
}
```

Responsabilidad:

```text
- Informar barridas de liquidez
- Informar absorciones
- Validar si hay liquidez reciente que apoye la entrada
```

---

### 5.9 `structure`

Contiene información estructural del setup.

```json
{
  "fresh_struct": true,
  "alive_struct": true,
  "stale_struct": false,
  "bull_flip": true,
  "bear_flip": false,
  "bull_micro_break": true,
  "bear_micro_break": false,
  "str_age": 5,
  "structure_dir": "BULL",
  "bull_break": true,
  "bear_break": false
}
```

Responsabilidad:

```text
- Informar edad de estructura
- Confirmar micro breaks
- Detectar cambios de dirección
- Alimentar dashboard y validación
```

---

### 5.10 `htf_context`

Contiene contexto de timeframe superior.

```json
{
  "htf_tf": "5",
  "htf_phase": "IMP_UP",
  "htf_phase_strength": "NORMAL",
  "htf_phase_bias": "EARLY_BULL",
  "htf_raw_phase": "IMP_UP",
  "htf_raw_score": 70,
  "htf_phase_gap": 2,
  "htf_adx": 22,
  "allow_long_init_5m": true,
  "allow_short_init_5m": false,
  "allow_long_cont_5m": true,
  "allow_short_cont_5m": false,
  "allow_long_rev_5m": false,
  "allow_short_rev_5m": false
}
```

Responsabilidad:

```text
- Usar fase 5m como contexto superior
- Filtrar o ponderar setups
- Detectar coherencia entre 1m y 5m
```

---

### 5.11 `execution`

Disponible para eventos reales de strategy.

```json
{
  "position_size_before": 0,
  "position_size_now": 1,
  "avg_price_before": null,
  "avg_price_now": 90000,
  "exit_reason": null,
  "tp_price": 90450,
  "sl_price": 89820,
  "pnl_pct": null,
  "distance_to_tp_pct": 0.5,
  "distance_to_sl_pct": 0.2,
  "rr_ratio": 2.5
}
```

Responsabilidad:

```text
- Registrar entradas y salidas reales
- Conectar alertas lógicas con operaciones ejecutadas
- Permitir análisis posterior de performance
```

---

## 6. Responsabilidad del Backend / Validation Layer

El backend no debe recalcular toda la lógica de Pine Script. Su responsabilidad es:

```text
- Recibir alertas
- Validar secreto del webhook
- Parsear JSON
- Normalizar payloads
- Fusionar logical_event_core + logical_event_extra
- Guardar estado en memoria
- Ejecutar validación solo para eventos ENTRY
- Consultar datos externos de Binance
- Calcular indicadores backend
- Analizar order book
- Analizar aggTrades
- Calcular scoring externo
- Estimar probabilidad TP antes que SL
- Persistir alertas y resultados en Supabase
- Enviar Telegram si una entrada es aprobada
- Exponer endpoints para dashboard
```

---

## 7. Tres niveles / módulos de validación

La validación se organiza en **tres niveles principales**. Cada nivel tiene una responsabilidad distinta y se ejecuta dentro de la Validation Layer.

```text
Nivel 1: Validación del payload y del evento
Nivel 2: Validación técnica con información de Pine Script
Nivel 3: Validación externa con mercado real, score y probabilidad TP/SL
```

---

### 7.1 Nivel 1 — Validación del payload y del evento

Este nivel verifica que la alerta recibida sea procesable.

Responsabilidades:

```text
- Validar el webhook secret
- Parsear el body recibido
- Verificar que sea JSON válido
- Normalizar estructura base
- Identificar message_type
- Identificar event_uid
- Identificar signal.event
- Identificar signal.side
- Identificar symbol y timeframe
- Fusionar logical_event_core + logical_event_extra si aplica
- Decidir si el evento debe validarse completamente o solo persistirse
```

Eventos que pasan a validación completa:

```text
LONG_ENTRY
SHORT_ENTRY
REAL_LONG_ENTRY
REAL_SHORT_ENTRY
```

Eventos que se reciben y se pueden persistir, pero no ejecutan validación completa:

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

Módulos relacionados:

```text
app.core.security
app.services.alert_service
app.api.routes
```

Funciones relacionadas:

```text
validate_secret()
parse_payload()
ensure_canonical_schema()
assemble_event_payload()
assemble_core_extra_by_event_uid()
should_validate_payload()
```

---

### 7.2 Nivel 2 — Validación técnica con datos de Pine Script

Este nivel reutiliza la información técnica que ya fue calculada por TradingView.

Responsabilidades:

```text
- Evaluar quality_score_alert
- Evaluar quality_class_alert
- Evaluar quality_approved_alert
- Evaluar trigger_long / trigger_short
- Evaluar ast_bull / ast_bear
- Evaluar hull_bull / hull_bear
- Evaluar aa_color del Adaptive SuperTrend
- Evaluar fase y régimen
- Evaluar HTF context
- Evaluar liquidez enviada por Pine
- Evaluar flags de extensión o late trend
- Evaluar setup_validation y setup_context
```

Datos reutilizados desde la alerta:

```text
context
trigger
quality
movement
liquidity
structure
setup_timing
setup_validation
setup_context
sequence
htf_context
trade_plan
execution
```

Módulos relacionados:

```text
app.services.alert_service
app.services.scoring_service
app.services.validation_service
```

Funciones relacionadas:

```text
normalize_alert()
compute_external_scores()
run_validation()
```

---

### 7.3 Nivel 3 — Validación externa con mercado real, score y probabilidad TP/SL

Este nivel enriquece la alerta con datos externos actuales desde Binance.

Responsabilidades:

```text
- Descargar klines 1m
- Descargar klines 5m
- Descargar order book
- Descargar aggTrades
- Calcular indicadores backend
- Calcular estructura / swings
- Analizar spread
- Analizar book imbalance
- Analizar buy/sell aggression
- Analizar delta_qty
- Analizar bid/ask walls
- Analizar vacuum above/below
- Calcular score_external
- Calcular probability_tp_before_sl
- Generar validation_steps
- Aprobar o rechazar entrada
```

Datos externos usados:

```text
Binance 1m klines
Binance 5m klines
Binance depth
Binance aggTrades
```

Indicadores calculados en backend:

```text
EMA20
EMA50
EMA200
ATR14
ADX
+DI
-DI
VWAP
RVOL20
Body %
Wicks
Returns
Impulse ATR
Compression ratio
Swing high / swing low
Order book imbalance
Spread bps
Bid wall
Ask wall
Vacuum above / below
Buy aggression
Sell aggression
Delta qty
```

Módulos relacionados:

```text
app.services.binance_service
app.services.market_features_service
app.services.scoring_service
app.services.probability_service
app.services.validation_service
```

Funciones relacionadas:

```text
collect_market_data()
compute_candle_features()
detect_swings()
analyze_order_book()
analyze_agg_trades()
compute_external_scores()
estimate_tp_before_sl_probability()
run_validation()
```

---

## 8. Capas de la aplicación

La aplicación quedó dividida en capas siguiendo un patrón modular.

```text
API Layer
Core Layer
Service Layer
Repository Layer
Utils Layer
External Integrations
```

---

## 9. Patrón aplicado en la refactorización

El patrón aplicado es:

```text
API Layer → Service Layer → Repository Layer
```

También se separaron responsabilidades transversales:

```text
Core Layer
Utils Layer
External Services
```

### Antes

```text
index.py
 ├── FastAPI app
 ├── rutas
 ├── configuración
 ├── logging
 ├── Telegram
 ├── Supabase
 ├── Binance
 ├── validación
 ├── scoring
 ├── probabilidad
 ├── normalización
 └── estado global
```

### Después

```text
backend/
├── api/
│   └── index.py
├── app/
│   ├── main.py
│   ├── api/
│   │   └── routes.py
│   ├── core/
│   ├── services/
│   ├── repositories/
│   └── utils/
```

---

## 10. Objetivo de la refactorización

La refactorización tuvo como objetivo dividir un archivo monolítico `index.py` de más de 2000 líneas en módulos mantenibles.

### Reglas aplicadas

```text
- No quitar lógica
- No simplificar comportamiento
- No optimizar cambiando reglas
- No alterar endpoints existentes
- Separar responsabilidades por archivo
- Mantener compatibilidad con Vercel
- Mantener compatibilidad con TradingView
- Mantener Supabase
- Mantener Telegram
- Mantener validación Binance
```

---

## 11. Fases de la refactorización

### Fase 1 — Core y utilidades base

Se extrajeron:

```text
core/config.py
core/state.py
core/logging.py
core/security.py
utils/time_utils.py
utils/json_utils.py
utils/math_utils.py
```

Responsabilidad:

```text
- Variables de entorno
- Estado global
- Logging JSON
- Seguridad webhook
- Fechas UTC
- Sanitización JSON
- Funciones matemáticas auxiliares
```

---

### Fase 2 — Servicio de alertas

Archivo:

```text
services/alert_service.py
```

Responsabilidad:

```text
- parse_payload
- ensure_canonical_schema
- assemble_event_payload
- should_validate_payload
- normalize_alert
- build_history_item
- merge_core_extra_payloads
- assemble_core_extra_by_event_uid
```

---

### Fase 3 — Binance y features de mercado

Archivos:

```text
services/binance_service.py
services/market_features_service.py
```

Responsabilidad:

```text
- Consultar klines
- Consultar depth
- Consultar aggTrades
- Convertir klines a DataFrame
- Calcular EMA
- Calcular ATR
- Calcular ADX / DI
- Calcular VWAP
- Calcular features de vela
- Detectar swings
- Analizar order book
- Analizar flujo de trades
```

---

### Fase 4 — Scoring y probabilidad

Archivos:

```text
services/scoring_service.py
services/probability_service.py
```

Responsabilidad:

```text
- Calcular score externo
- Evaluar contexto HTF
- Evaluar EMA / ADX / DI
- Evaluar VWAP
- Evaluar volumen
- Evaluar order book
- Evaluar flujo
- Evaluar liquidez
- Evaluar room hacia TP
- Calcular probabilidad TP antes SL
- Integrar modelo sklearn opcional
```

---

### Fase 5 — Validation Service

Archivo:

```text
services/validation_service.py
```

Responsabilidad:

```text
- Ejecutar validación completa
- Omitir validación para eventos no-entry
- Crear validation_steps
- Crear analysis_trace
- Crear analysis_summary
- Calcular aprobación final
- Devolver normalized_alert
- Devolver market_snapshot
- Devolver structure_snapshot
- Devolver alert_reused
```

---

### Fase 6 — Rutas API

Archivo:

```text
app/api/routes.py
```

Responsabilidad:

```text
- Healthcheck
- Latest alert
- Latest validation
- Webhook TradingView
- Validate manual
- Alert history
- Supabase history
- Supabase health
- Binance health
```

---

### Fase 7 — Telegram y Supabase

Archivos:

```text
services/telegram_service.py
repositories/supabase_repo.py
```

Responsabilidad Telegram:

```text
- Construir mensaje ENTRY VALIDADA OK
- Enviar mensaje a Telegram
- Loguear éxito o error
```

Responsabilidad Supabase:

```text
- Inicializar cliente Supabase
- Filtrar payloads persistibles
- Guardar alert_events
- Actualizar trade_setups
- Guardar validation_results
- Leer histórico de alertas
- Leer setups
```

---

### Fase 8 — Main final y wrapper Vercel

Archivos:

```text
app/main.py
api/index.py
vercel.json
```

Responsabilidad:

```text
- Crear FastAPI app
- Configurar CORS
- Incluir router
- Exponer app para Vercel
```

---

## 12. Estructura final del proyecto

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
│   │   └── routes.py
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
│   │   ├── binance_service.py
│   │   ├── market_features_service.py
│   │   ├── probability_service.py
│   │   ├── scoring_service.py
│   │   ├── telegram_service.py
│   │   └── validation_service.py
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

---

## 13. Función de cada capa

### 13.1 API Layer

Ubicación:

```text
app/api/routes.py
```

Responsabilidad:

```text
- Recibir requests HTTP
- Exponer endpoints
- Delegar lógica a servicios
- No contener lógica pesada
```

Endpoints:

```text
GET  /
GET  /api/latest
GET  /api/validation/latest
GET  /api/alerts
GET  /api/health/binance
GET  /api/health/supabase
GET  /api/alerts/supabase
GET  /api/setups/supabase
POST /api/webhook
POST /api/validate
POST /
```

---

### 13.2 Core Layer

Ubicación:

```text
app/core/
```

Responsabilidad:

```text
- Configuración
- Estado global
- Logging
- Seguridad
```

Archivos:

```text
config.py
state.py
logging.py
security.py
```

---

### 13.3 Service Layer

Ubicación:

```text
app/services/
```

Responsabilidad:

```text
- Lógica de negocio
- Normalización
- Validación
- Scoring
- Probabilidad
- Features de mercado
- Integraciones externas funcionales
```

Archivos principales:

```text
alert_service.py
binance_service.py
market_features_service.py
scoring_service.py
probability_service.py
validation_service.py
telegram_service.py
```

---

### 13.4 Repository Layer

Ubicación:

```text
app/repositories/
```

Responsabilidad:

```text
- Acceso a base de datos
- Persistencia Supabase
- Lectura de histórico
- Upserts e inserts
```

Archivo:

```text
supabase_repo.py
```

---

### 13.5 Utils Layer

Ubicación:

```text
app/utils/
```

Responsabilidad:

```text
- Funciones auxiliares reutilizables
- Sanitización JSON
- Fechas
- Conversión numérica
- Helpers matemáticos
```

Archivos:

```text
time_utils.py
json_utils.py
math_utils.py
```

---

## 14. Validation Layer

La Validation Layer es la parte central del backend.

Su función es decidir si una entrada enviada por TradingView merece ser aprobada o rechazada.

### La Validation Layer usa

```text
- Payload recibido desde Pine Script
- Datos de Binance 1m
- Datos de Binance 5m
- Order book
- AggTrades
- Indicadores backend
- Scoring externo
- Probabilidad TP antes que SL
- Reglas de extensión / late trend
- Espacio estructural hacia TP
```

---

## 15. Eventos que se validan completamente

Actualmente la validación completa se ejecuta para:

```text
LONG_ENTRY
SHORT_ENTRY
REAL_LONG_ENTRY
REAL_SHORT_ENTRY
```

Eventos como:

```text
LONG_INIT
SHORT_INIT
IMP_UP_AFTER_ADAPTIVE
IMP_DN_AFTER_ADAPTIVE
```

se reciben, se normalizan y se pueden persistir, pero no ejecutan validación completa de entrada.

Esto es intencional porque INIT representa señal temprana o potencial, no entrada final.

---

## 16. Persistencia de INIT

La persistencia fue ajustada para no perder INIT.

Ahora se permite guardar:

```text
LONG_INIT
SHORT_INIT
LONG_INIT_AFTER_ADAPTIVE
SHORT_INIT_AFTER_ADAPTIVE
IMP_UP_AFTER_ADAPTIVE
IMP_DN_AFTER_ADAPTIVE
LONG_ENTRY
SHORT_ENTRY
REAL_LONG_ENTRY
REAL_SHORT_ENTRY
REAL_LONG_EXIT
REAL_SHORT_EXIT
EXECUTED_EXIT
LONG_CANCEL
SHORT_CANCEL
CANCEL
```

Esto permite construir dataset histórico aunque la señal no esté aprobada.

---

## 17. Lifecycle de eventos

El backend asigna un estado lógico a cada evento.

```text
WATCH          → señal observada
ARMED          → señal armada
INIT_RECEIVED  → INIT recibida, pero no aprobada como entrada
VALIDATED      → señal aprobada
REJECTED       → señal rechazada
ENTRY_PENDING  → entrada pendiente de validación
OPEN           → operación real abierta
CLOSED         → operación cerrada
CANCELLED      → setup cancelado
```

---

## 18. Flujo del dato completo

### Paso 1 — Pine Script detecta señal

TradingView detecta una señal como:

```text
LONG_INIT
SHORT_INIT
LONG_ENTRY
SHORT_ENTRY
REAL_LONG_ENTRY
REAL_LONG_EXIT
```

### Paso 2 — Pine Script construye JSON

El script genera un JSON con:

```text
source
signal
context
trigger
quality
trade_plan
movement
liquidity
structure
setup_timing
setup_validation
setup_context
sequence
htf_context
execution
```

### Paso 3 — TradingView envía alerta

TradingView envía la alerta al endpoint:

```http
POST /api/webhook
```

### Paso 4 — FastAPI recibe alerta

La API ejecuta:

```text
validate_secret()
parse_payload()
assemble_event_payload()
assemble_core_extra_by_event_uid()
```

### Paso 5 — Merge CORE + EXTRA

Si la alerta llega en dos partes:

```text
logical_event_core
logical_event_extra
```

el backend espera ambas y las fusiona en:

```text
logical_event_full
```

Esto evita guardar señales incompletas.

### Paso 6 — Actualización de memoria local

El backend actualiza:

```text
LAST_ALERT
LAST_VALIDATION
ALERT_HISTORY
```

Esto permite consultar:

```http
GET /api/latest
GET /api/validation/latest
GET /api/alerts
```

### Paso 7 — Respuesta rápida al webhook

El backend responde rápido a TradingView:

```json
{
  "ok": true,
  "message": "Alert received quickly. Validation, Supabase and Telegram queued in background."
}
```

### Paso 8 — Background task

Después de responder a TradingView, se ejecuta en background:

```text
process_alert_background()
```

Responsabilidades:

```text
- Validar si aplica
- Persistir en Supabase
- Enviar Telegram si la entrada es aprobada
- Actualizar LAST_ALERT con resultado final
```

### Paso 9 — Validación de entrada

Si el evento es entrada:

```text
LONG_ENTRY
SHORT_ENTRY
REAL_LONG_ENTRY
REAL_SHORT_ENTRY
```

se ejecuta:

```text
run_validation()
```

### Paso 10 — Recolección de mercado

La API consulta Binance:

```text
GET /api/v3/klines 1m
GET /api/v3/klines 5m
GET /api/v3/depth
GET /api/v3/aggTrades
```

### Paso 11 — Features backend

El backend calcula:

```text
EMA20
EMA50
EMA200
ATR14
ADX
+DI
-DI
VWAP
RVOL20
Body %
Wicks
Returns
Impulse ATR
Compression ratio
Swing high / swing low
Order book imbalance
Spread bps
Bid wall
Ask wall
Vacuum above / below
Buy aggression
Sell aggression
Delta qty
```

### Paso 12 — Scoring externo

El backend calcula un score externo usando:

```text
Trigger
Quality alert
HTF alignment
EMA trend
ADX / DI
VWAP
RVOL
Flow
Order book
Liquidity
Extension
TP room
```

Resultado:

```json
{
  "score_external": 72.5,
  "reasons": [],
  "penalties": [],
  "backend_feature_pack": {}
}
```

### Paso 13 — Probabilidad TP antes SL

El backend calcula:

```text
probability_tp_before_sl
barrier_component
technical_component
ml_component
mu_per_bar
sigma_per_bar
```

Modelo usado:

```text
hybrid_barrier_logit
```

Si hay modelo sklearn cargado:

```text
hybrid_barrier_logit_sklearn
```

### Paso 14 — Validation Steps

Se generan pasos explícitos:

```text
event_gate
context_validation
microstructure_validation
flow_validation
tp_room_validation
extension_validation
tp_probability_validation
score_validation
```

Cada paso tiene:

```json
{
  "ok": true,
  "status": "OK",
  "reason": "...",
  "details": {}
}
```

### Paso 15 — Decisión final

La entrada se aprueba si:

```text
probability_tp_before_sl >= VALIDATION_THRESHOLD
score_external >= MIN_SCORE_THRESHOLD
too_extended_block_alert == false
```

Variables de entorno:

```text
VALIDATION_THRESHOLD=0.62
MIN_SCORE_THRESHOLD=55
```

### Paso 16 — Resultado de validación

La respuesta incluye:

```text
approve
confidence
side
symbol
event
entry_price
tp
sl
rr
probability_tp_before_sl
probability_model
barrier_component
technical_component
ml_component
score_external
quality_score_alert
reason
penalties
validation_steps
analysis_trace
analysis_summary
market_snapshot
structure_snapshot
alert_reused
normalized_alert
```

### Paso 17 — Persistencia en Supabase

Se guarda en:

```text
alert_events
trade_setups
validation_results
```

### Paso 18 — Telegram

Si:

```text
validation.approve == true
```

se envía mensaje Telegram:

```text
ENTRY VALIDADA OK
```

con:

```text
symbol
side
event
entry
tp
sl
rr
confidence
probabilidad
score
razones
penalizaciones
```

---

## 19. Endpoints disponibles

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

---

## 20. Variables de entorno

Crear estas variables tanto en local como en Vercel.

### 20.1 Seguridad del webhook

```env
WEBHOOK_SECRET=MI_SECRET
```

Uso:

```text
- Valida el header x-webhook-secret enviado al backend
- Si está vacío, no se aplica validación por header
- Recomendado configurarlo siempre en producción
```

Header esperado:

```http
x-webhook-secret: MI_SECRET
```

---

### 20.2 Validación

```env
VALIDATION_THRESHOLD=0.62
MIN_SCORE_THRESHOLD=55
REQUEST_TIMEOUT_SEC=8.0
VALIDATION_MODEL_VERSION=rules_v1
```

Uso:

```text
VALIDATION_THRESHOLD:
- Umbral mínimo de probability_tp_before_sl para aprobar una entrada

MIN_SCORE_THRESHOLD:
- Score externo mínimo requerido para aprobar una entrada

REQUEST_TIMEOUT_SEC:
- Timeout para requests HTTP hacia Binance

VALIDATION_MODEL_VERSION:
- Versión lógica del modelo/reglas guardada en validation_results
```

---

### 20.3 Supabase

```env
SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxxxx
```

Uso:

```text
SUPABASE_URL:
- URL del proyecto Supabase

SUPABASE_SERVICE_ROLE_KEY:
- Key con permisos para insertar/upsert/leer tablas
- No usar anon key para persistencia backend
```

Tablas usadas:

```text
alert_events
trade_setups
validation_results
```

---

### 20.4 Telegram

```env
TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

Uso:

```text
TELEGRAM_ENABLED:
- true para activar notificaciones
- false para desactivarlas

TELEGRAM_BOT_TOKEN:
- Token del bot creado con BotFather

TELEGRAM_CHAT_ID:
- Chat o grupo donde se enviarán las señales aprobadas
```

El mensaje se envía solo si:

```text
validation.approve == true
```

---

### 20.5 Machine Learning opcional

```env
ML_MODEL_PATH=
ML_FEATURES_JSON=
```

Uso:

```text
ML_MODEL_PATH:
- Ruta local o del entorno al modelo sklearn/joblib

ML_FEATURES_JSON:
- JSON con el orden de features esperado por el modelo
```

Si no están configuradas, la API funciona igual usando:

```text
hybrid_barrier_logit
```

Si están configuradas correctamente, puede usar:

```text
hybrid_barrier_logit_sklearn
```

---

### 20.6 CORS

```env
ALLOWED_ORIGINS=*
```

Uso:

```text
- Permite definir qué frontends pueden consumir la API
- Para desarrollo puede usarse *
- Para producción conviene restringirlo al dominio del dashboard
```

Ejemplo producción:

```env
ALLOWED_ORIGINS=https://mi-dashboard.vercel.app,https://mi-streamlit-app.streamlit.app
```

---

### 20.7 Ejemplo `.env` local

```env
WEBHOOK_SECRET=MI_SECRET

VALIDATION_THRESHOLD=0.62
MIN_SCORE_THRESHOLD=55
REQUEST_TIMEOUT_SEC=8.0
VALIDATION_MODEL_VERSION=rules_v1

SUPABASE_URL=https://xxxxx.supabase.co
SUPABASE_SERVICE_ROLE_KEY=xxxxx

TELEGRAM_ENABLED=false
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

ML_MODEL_PATH=
ML_FEATURES_JSON=

ALLOWED_ORIGINS=*
```

---

### 20.8 Variables a crear en Vercel

En Vercel:

```text
Project Settings
        ↓
Environment Variables
        ↓
Add
```

Crear:

```text
WEBHOOK_SECRET
VALIDATION_THRESHOLD
MIN_SCORE_THRESHOLD
REQUEST_TIMEOUT_SEC
VALIDATION_MODEL_VERSION
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
TELEGRAM_ENABLED
TELEGRAM_BOT_TOKEN
TELEGRAM_CHAT_ID
ML_MODEL_PATH
ML_FEATURES_JSON
ALLOWED_ORIGINS
```

Mínimas obligatorias para operar con Supabase:

```text
WEBHOOK_SECRET
SUPABASE_URL
SUPABASE_SERVICE_ROLE_KEY
```

Mínimas para validar sin Supabase:

```text
WEBHOOK_SECRET
VALIDATION_THRESHOLD
MIN_SCORE_THRESHOLD
REQUEST_TIMEOUT_SEC
```

---

## 21. Compatibilidad con Vercel

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
  ]
}
```

---

## 22. Ejecución local

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

## 23. Pruebas básicas

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/api/latest
curl http://127.0.0.1:8000/api/validation/latest
curl http://127.0.0.1:8000/api/health/binance
curl http://127.0.0.1:8000/api/health/supabase
```

---

## 24. Estado final de la refactorización

La refactorización separó un backend monolítico en una arquitectura modular basada en capas.

### Resultado

```text
- Backend más mantenible
- Menor riesgo al modificar lógica
- Rutas separadas de servicios
- Persistencia aislada
- Validación aislada
- Scoring aislado
- Probabilidad aislada
- Telegram aislado
- Configuración centralizada
- Estado global centralizado
- Compatible con Vercel
- Compatible con TradingView
- Compatible con Supabase
```

---

## 25. Commit representativo

```bash
git add .
git commit -m "refactor trading validation backend into modular services" -m "Split monolithic index.py into FastAPI routes, core config/state/logging/security, alert parsing, Binance market data, market features, scoring, TP/SL probability, validation service, Telegram service and Supabase repository. Preserve original behavior while improving maintainability and Vercel deployment structure."
```

---

## 26. Resumen ejecutivo

Esta API es la capa de validación y persistencia del sistema de trading algorítmico.

TradingView se encarga de detectar señales, contexto, fases, triggers y setups.

El backend se encarga de:

```text
- Recibir alertas
- Fusionar mensajes CORE/EXTRA
- Normalizar datos
- Guardar historial
- Validar entradas reales
- Enriquecer con Binance
- Calcular score externo
- Calcular probabilidad TP antes SL
- Persistir en Supabase
- Notificar por Telegram
- Servir datos al dashboard
```

La arquitectura final sigue el patrón:

```text
API Layer → Service Layer → Repository Layer
```

con capas auxiliares:

```text
Core Layer
Utils Layer
External Integrations
```

La validación queda organizada en tres niveles:

```text
Nivel 1: Validación del payload y evento
Nivel 2: Validación técnica con datos de Pine Script
Nivel 3: Validación externa con mercado real, score y probabilidad TP/SL
```

Esta estructura permite continuar el desarrollo agregando dashboard, ML, LLM explanation, métricas de performance y automatización sin seguir creciendo sobre un único `index.py` monolítico.