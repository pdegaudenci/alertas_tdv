# TradingView Validation Layer API

## 1. Descripción general

Esta API es una **Validation Layer** para un sistema de trading algorítmico basado en alertas de TradingView.

Su objetivo principal es recibir señales generadas por Pine Script, normalizarlas, fusionar eventos complementarios, enriquecerlas con datos de mercado externos, validar entradas operativas y persistir información completa para análisis, dashboard, métricas y futuros modelos de Machine Learning.

El sistema queda dividido en dos aplicaciones principales:

```text
1. Backend FastAPI / Validation Layer
2. Panel Streamlit / UI Layer
```

Flujo general:

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
Panel Streamlit / Dashboard / Análisis histórico / ML futuro
```

Esta API no reemplaza la lógica de Pine Script. La API actúa como una capa posterior de validación, persistencia y enriquecimiento.

---

## 2. Responsabilidades del sistema

El sistema está dividido en tres grandes responsabilidades:

```text
1. TradingView / Pine Script
2. Backend FastAPI / Validation Layer
3. Panel Streamlit / UI Layer
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

## 8. Capas de la aplicación Backend

La aplicación backend quedó dividida en capas siguiendo un patrón modular.

```text
API Layer
Core Layer
Service Layer
Repository Layer
Utils Layer
External Integrations
```

---

## 9. Patrón aplicado en la refactorización del Backend

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

## 10. UI Layer / Panel Streamlit

Además del backend, el sistema cuenta con un **Panel Streamlit** que actúa como capa visual para consultar, interpretar y monitorear las alertas, validaciones y estados persistidos.

El patrón aplicado al panel es equivalente al del backend, pero adaptado a una aplicación visual:

```text
UI Layer → Services Layer → Clients / Repositories Layer → Utils / Config
```

Equivalencia conceptual con el backend:

```text
Backend routes.py        → Streamlit views/pages
Backend services/*.py    → Streamlit services/*.py
Backend repositories/*.py → Streamlit clients/*.py / repositories/*.py
Backend core/*.py        → Streamlit core/*.py
Backend utils/*.py       → Streamlit utils/*.py
```

---

## 11. Responsabilidad general del Panel Streamlit

El panel de Streamlit no debe contener lógica pesada ni lógica de negocio mezclada con visualización.

Su responsabilidad es:

```text
- Consultar endpoints del backend
- Mostrar última alerta recibida
- Mostrar última validación
- Mostrar histórico local
- Mostrar histórico desde Supabase
- Mostrar market_snapshot
- Mostrar structure_snapshot
- Mostrar validation_steps
- Mostrar analysis_trace
- Mostrar analysis_summary
- Mostrar estado del setup
- Mostrar métricas visuales
- Facilitar debugging operativo
- Servir como dashboard para monitoreo del sistema
```

---

## 12. Patrón aplicado en el Panel Streamlit

El patrón recomendado para el panel es:

```text
app.py
        ↓
views/
        ↓
services/
        ↓
clients/
        ↓
backend FastAPI
```

Flujo conceptual:

```text
Streamlit app.py
        ↓
views/sidebar.py
        ↓
clients/backend_client.py
        ↓
FastAPI Backend
        ↓
Respuesta JSON
        ↓
services/*
        ↓
components/*
        ↓
Streamlit UI
```

Ejemplo concreto:

```text
GET /api/validation/latest
        ↓
backend_client.get_latest_validation()
        ↓
validation_service.extract_validation_summary()
        ↓
validation_view.render_latest_validation()
        ↓
components.cards.render_metric_card()
```

---

## 13. Estructura propuesta para el Panel Streamlit

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

## 14. Función de cada capa del Panel Streamlit

### 14.1 `app.py`

Archivo principal de Streamlit.

Responsabilidad:

```text
- Configurar la página Streamlit
- Definir layout global
- Cargar configuración
- Renderizar sidebar
- Orquestar las vistas principales
- Controlar refresh
- No contener lógica pesada
- No hacer requests HTTP directamente si puede delegarlo a clients/
```

Ejemplo de responsabilidad:

```text
Configurar página
Renderizar sidebar
Renderizar últimas alertas
Renderizar validación
Renderizar histórico
Renderizar secciones técnicas
```

---

### 14.2 `core/`

Capa de configuración y estado.

Responsabilidad:

```text
- Definir BACKEND_BASE_URL
- Definir URLs del backend
- Definir valores por defecto del dashboard
- Definir constantes visuales
- Gestionar session_state
- Centralizar configuración reutilizable
```

Archivos sugeridos:

```text
core/config.py
core/constants.py
core/session_state.py
```

Ejemplo:

```python
import os

BACKEND_BASE_URL = os.getenv(
    "BACKEND_BASE_URL",
    "https://alertas-tdv-67cu-two.vercel.app"
)

BACKEND_LATEST_URL = f"{BACKEND_BASE_URL}/api/latest"
BACKEND_ALERTS_URL = f"{BACKEND_BASE_URL}/api/alerts"
BACKEND_VALIDATION_URL = f"{BACKEND_BASE_URL}/api/validation/latest"
BACKEND_SUPABASE_ALERTS_URL = f"{BACKEND_BASE_URL}/api/alerts/supabase"
BACKEND_SUPABASE_SETUPS_URL = f"{BACKEND_BASE_URL}/api/setups/supabase"
```

---

### 14.3 `clients/`

Capa de comunicación externa.

Responsabilidad:

```text
- Hacer requests HTTP al backend
- Manejar timeouts
- Manejar errores HTTP
- Devolver JSON crudo o estructura segura
- No renderizar componentes Streamlit
- No calcular métricas visuales
```

Archivo principal:

```text
clients/backend_client.py
```

Funciones esperadas:

```text
get_latest_alert()
get_latest_validation()
get_alerts_history()
get_supabase_alerts()
get_supabase_setups()
health_backend()
health_binance()
health_supabase()
```

Responsabilidad opcional de `clients/supabase_client.py`:

```text
- Leer Supabase directamente si en el futuro el panel decide no pasar por la API
- Mantener la opción desacoplada del backend
```

---

### 14.4 `services/`

Capa de transformación y lógica visual.

Responsabilidad:

```text
- Transformar respuestas crudas del backend
- Extraer validation_steps
- Extraer market_snapshot
- Extraer structure_snapshot
- Preparar DataFrames para tablas
- Calcular KPIs visuales del dashboard
- Clasificar estados OK / KO / WARNING
- Preparar datos para charts
- Formatear valores numéricos
```

Archivos sugeridos:

```text
services/alert_service.py
services/validation_service.py
services/market_snapshot_service.py
services/metrics_service.py
services/formatting_service.py
```

Ejemplos de responsabilidades por archivo:

```text
alert_service.py:
- Extraer event, side, symbol, price, phase, regime
- Preparar resumen de última alerta
- Preparar historial de alertas

validation_service.py:
- Extraer approve, confidence, probability, score
- Preparar validation_steps como tabla
- Preparar analysis_trace y summary

market_snapshot_service.py:
- Extraer close, EMA, ADX, DI, VWAP, RVOL
- Preparar métricas de order book y flow

metrics_service.py:
- Calcular conteos de alertas
- Calcular aprobadas/rechazadas
- Calcular distribución por side/event/status

formatting_service.py:
- Formatear porcentajes
- Formatear precios
- Formatear booleanos
- Formatear estados visuales
```

---

### 14.5 `views/`

Capa visual de secciones del dashboard.

Responsabilidad:

```text
- Renderizar pantallas Streamlit
- Organizar columnas, tabs y secciones
- Llamar clients/ para obtener datos
- Llamar services/ para preparar datos
- Llamar components/ para mostrar UI
- No contener lógica de negocio pesada
```

Archivos sugeridos:

```text
views/sidebar.py
views/latest_alert_view.py
views/validation_view.py
views/alerts_history_view.py
views/supabase_history_view.py
views/market_snapshot_view.py
views/technical_context_view.py
views/setup_detail_view.py
```

Responsabilidad por vista:

```text
sidebar.py:
- Auto refresh
- Selector de backend URL
- Botón de recarga
- Parámetros visuales

latest_alert_view.py:
- Mostrar última alerta recibida
- Mostrar payload resumido
- Mostrar JSON expandible

validation_view.py:
- Mostrar última validación
- Mostrar approve/confidence/probability/score
- Mostrar validation_steps
- Mostrar razones y penalizaciones

alerts_history_view.py:
- Mostrar historial en memoria desde /api/alerts

supabase_history_view.py:
- Mostrar histórico persistido desde /api/alerts/supabase
- Mostrar setups desde /api/setups/supabase

market_snapshot_view.py:
- Mostrar datos de mercado usados en validación
- Mostrar order book / flow / indicadores

technical_context_view.py:
- Mostrar contexto Pine: regime, phase, HTF, movement, liquidity

setup_detail_view.py:
- Mostrar detalle de un setup seleccionado
```

---

### 14.6 `components/`

Capa de componentes visuales reutilizables.

Responsabilidad:

```text
- Cards
- Badges
- Métricas
- Tablas
- Gráficos
- Expansores JSON
- Componentes de estado
```

Archivos sugeridos:

```text
components/cards.py
components/tables.py
components/badges.py
components/charts.py
```

Ejemplos:

```text
cards.py:
- render_metric_card()
- render_status_card()
- render_validation_card()

badges.py:
- render_ok_badge()
- render_ko_badge()
- render_warning_badge()
- render_side_badge()

tables.py:
- render_dataframe()
- render_validation_steps_table()
- render_alerts_table()

charts.py:
- render_probability_chart()
- render_score_distribution()
- render_alerts_by_event()
```

---

### 14.7 `utils/`

Capa auxiliar.

Responsabilidad:

```text
- Helpers de JSON
- Helpers de DataFrame
- Conversión de fechas
- Safe get
- Safe float
- Limpieza de valores nulos
- Funciones reutilizables sin dependencia directa de Streamlit
```

Archivos sugeridos:

```text
utils/json_utils.py
utils/time_utils.py
utils/dataframe_utils.py
```

---

## 15. Fases recomendadas para refactorizar el Panel Streamlit

### Fase 1 — Base modular

Crear:

```text
core/config.py
core/session_state.py
utils/json_utils.py
utils/dataframe_utils.py
```

Objetivo:

```text
Centralizar configuración, helpers y estado.
```

---

### Fase 2 — Backend client

Extraer todas las llamadas `requests.get()` o `requests.post()` a:

```text
clients/backend_client.py
```

Objetivo:

```text
Que Streamlit no haga llamadas HTTP directamente desde la UI.
```

---

### Fase 3 — Servicios de transformación

Crear:

```text
services/alert_service.py
services/validation_service.py
services/market_snapshot_service.py
services/metrics_service.py
```

Objetivo:

```text
Separar datos crudos del backend de datos listos para visualizar.
```

---

### Fase 4 — Componentes visuales

Crear:

```text
components/cards.py
components/tables.py
components/badges.py
components/charts.py
```

Objetivo:

```text
Evitar duplicar st.metric, st.dataframe, st.json, st.columns y estilos.
```

---

### Fase 5 — Vistas

Crear:

```text
views/sidebar.py
views/latest_alert_view.py
views/validation_view.py
views/alerts_history_view.py
views/supabase_history_view.py
views/market_snapshot_view.py
```

Objetivo:

```text
Cada bloque visual del dashboard queda aislado y mantenible.
```

---

### Fase 6 — `app.py` limpio

Dejar `app.py` solo como orquestador:

```text
- Configurar página
- Renderizar sidebar
- Renderizar vistas
- Controlar refresh
```

---

## 16. Objetivo de la refactorización del Panel Streamlit

El objetivo es evitar que el panel crezca como un archivo monolítico.

Reglas:

```text
- No quitar visualizaciones
- No cambiar endpoints
- No eliminar lógica existente
- No mezclar requests con UI
- No mezclar transformación de datos con renderizado
- Mantener compatibilidad con el backend actual
- Mantener el panel como herramienta de monitoreo operativo
```

---

## 17. Estructura final del proyecto Backend

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

## 18. Endpoints disponibles

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

## 19. Variables de entorno

Crear estas variables tanto en local como en Vercel.

### 19.1 Seguridad del webhook

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

### 19.2 Validación

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

### 19.3 Supabase

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

### 19.4 Telegram

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

### 19.5 Machine Learning opcional

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

### 19.6 CORS

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

### 19.7 Ejemplo `.env` local

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

### 19.8 Variables a crear en Vercel

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

## 20. Compatibilidad con Vercel

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

## 21. Ejecución local Backend

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

## 22. Pruebas básicas Backend

```bash
curl http://127.0.0.1:8000/
curl http://127.0.0.1:8000/api/latest
curl http://127.0.0.1:8000/api/validation/latest
curl http://127.0.0.1:8000/api/health/binance
curl http://127.0.0.1:8000/api/health/supabase
```

---

## 23. Ejecución local Panel Streamlit

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

## 24. Estado final de la refactorización

La refactorización separó un backend monolítico en una arquitectura modular basada en capas y deja definido el patrón equivalente para el panel Streamlit.

### Resultado Backend

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

### Resultado esperado Panel Streamlit

```text
- UI más mantenible
- Requests aislados en clients/
- Transformación de datos aislada en services/
- Renderizado aislado en views/
- Componentes visuales reutilizables
- Configuración centralizada
- Dashboard preparado para crecer
- Menor riesgo al agregar nuevas visualizaciones
```

---

## 25. Commit representativo Backend

```bash
git add .
git commit -m "refactor trading validation backend into modular services" -m "Split monolithic index.py into FastAPI routes, core config/state/logging/security, alert parsing, Binance market data, market features, scoring, TP/SL probability, validation service, Telegram service and Supabase repository. Preserve original behavior while improving maintainability and Vercel deployment structure."
```

---

## 26. Commit representativo Panel Streamlit

```bash
git add .
git commit -m "define modular Streamlit dashboard architecture" -m "Document UI Layer architecture for the trading validation dashboard, separating app orchestration, views, components, services, backend clients, core configuration and utilities."
```

---

## 27. Resumen ejecutivo

Esta solución está compuesta por:

```text
TradingView / Pine Script
Backend FastAPI / Validation Layer
Panel Streamlit / UI Layer
Supabase
Telegram
Binance
```

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

El panel Streamlit se encarga de:

```text
- Consultar el backend
- Mostrar alertas
- Mostrar validaciones
- Mostrar histórico
- Mostrar snapshots técnicos
- Mostrar métricas
- Facilitar debugging y monitoreo
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
## Panel Streamlit — Arquitectura UI y responsabilidades

El panel Streamlit es la capa visual operativa del sistema de trading. Su función principal es mostrar, interpretar y organizar la información generada por TradingView, el backend FastAPI, Supabase, Binance y los cálculos locales del propio dashboard.

El panel no reemplaza la lógica de señales de TradingView ni la Validation Layer del backend. Su responsabilidad es actuar como interfaz de análisis, monitoreo y evaluación manual.

---

## Objetivos del panel Streamlit

El panel permite:

1. Visualizar la última alerta recibida desde TradingView.
2. Consultar la última validación generada por el backend.
3. Mostrar histórico de alertas persistidas en Supabase.
4. Analizar contexto de mercado local con datos de Binance.
5. Evaluar liquidez cercana, zonas institucionales y riesgo de barrida.
6. Validar condiciones multi-timeframe en 1H, 15M y 5M.
7. Evaluar manualmente una entrada LONG o SHORT.
8. Calcular TP, SL, break even, trailing, R:R, riesgo y tamaño de posición.
9. Estimar probabilidad de alcanzar TP y probabilidad de rentabilidad.
10. Ejecutar backtest rápido e histórico por condiciones similares.

---

## Patrón aplicado en la refactorización UI

La refactorización del panel aplica un patrón por capas:

App Orchestrator
↓
Views
↓
Components
↓
Services
↓
Clients
↓
Core / Utils

El objetivo del patrón es separar responsabilidades:

- `app.py` orquesta.
- `views/` renderiza pantallas.
- `components/` renderiza piezas visuales reutilizables.
- `services/` calcula, transforma y prepara datos.
- `clients/` consume APIs externas.
- `core/` centraliza configuración y constantes.
- `utils/` contiene helpers genéricos.

---

## Flujo general del panel

Streamlit `app.py`
↓  
Carga configuración desde `core/config.py`
↓  
Consulta datos de Binance mediante `services/market_data_service.py`
↓  
Prepara indicadores con `services/indicators_service.py`
↓  
Construye contexto con `services/context_service.py`
↓  
Construye liquidez con `services/liquidity_service.py`
↓  
Renderiza vistas desde `views/`
↓  
Consulta backend mediante `clients/backend_client.py`
↓  
Prepara datos visuales con `alert_view_service.py` y `validation_view_service.py`
↓  
Muestra dashboard operativo al usuario

---

## Capas del panel Streamlit

---

### 1. `app.py` — Orquestador principal

Archivo principal del panel.

Responsabilidades:

- Configurar la página Streamlit.
- Cargar configuración global.
- Descargar datos de mercado.
- Preparar dataframes.
- Construir contexto operativo.
- Construir mapa de liquidez.
- Renderizar sidebar.
- Renderizar métricas principales.
- Renderizar señal actual.
- Renderizar tabs principales.
- Controlar auto-refresh.

No debe contener:

- lógica pesada de indicadores,
- llamadas HTTP directas,
- cálculos de liquidez,
- cálculos de probabilidad,
- backtest,
- textos largos de explicación,
- lógica completa de tabs.

Ejemplo de responsabilidad de `app.py`:

Inicializar → cargar datos → construir contexto → renderizar views

---

### 2. `core/` — Configuración y constantes

Contiene configuración global del panel.

Archivos principales:

- `core/config.py`
- `core/constants.py`

#### `core/config.py`

Responsabilidades:

- Leer variables de entorno.
- Definir URL base del backend.
- Construir endpoints del backend.
- Definir timeouts.
- Definir configuración de página Streamlit.
- Definir símbolo por defecto.
- Definir endpoints Binance.
- Definir configuración de cache y auto-refresh.

Ejemplos:

- `BACKEND_BASE_URL`
- `BACKEND_LATEST_URL`
- `BACKEND_ALERTS_URL`
- `BACKEND_VALIDATION_URL`
- `BACKEND_ALERTS_SUPABASE_URL`
- `BACKEND_SETUPS_SUPABASE_URL`
- `PAGE_TITLE`
- `PAGE_ICON`
- `PAGE_LAYOUT`
- `DEFAULT_SYMBOL`
- `CACHE_TTL_SECONDS`
- `DEFAULT_REQUEST_TIMEOUT`

#### `core/constants.py`

Responsabilidades:

- Centralizar constantes operativas del sistema de trading.
- Evitar valores hardcodeados dispersos.

Ejemplos:

- `TP_BASE`
- `SL_BASE`
- `RISK_REWARD_WEIGHT`
- `CAPITAL_EUR`
- `RIESGO_POR_TRADE`
- `APALANCAMIENTO`
- `TP_REAL`
- `SL_REAL`
- `COMISION`

---

### 3. `utils/` — Helpers genéricos

Contiene funciones auxiliares reutilizables que no pertenecen a una vista ni a un servicio específico.

Archivo principal:

- `utils/math_utils.py`

Responsabilidades:

- Conversión segura a float.
- Clasificación de ratings.
- Cálculo auxiliar de trailing.
- Helpers matemáticos simples.

Funciones principales:

- `safe_float()`
- `rating_score()`
- `calcular_trailing()`

Ejemplo de uso:

- `trade_evaluator_view.py` usa `rating_score()`.
- `context_service.py` usa `safe_float()`.
- `trade_engine_service.py` usa `calcular_trailing()`.

---

### 4. `clients/` — Clientes externos

Contiene conectores HTTP hacia APIs externas o servicios propios.

Archivo principal:

- `clients/backend_client.py`

Responsabilidades:

- Centralizar todas las llamadas HTTP al backend FastAPI.
- Evitar `requests.get()` dispersos dentro de las vistas.
- Manejar timeouts.
- Manejar errores de conexión.
- Devolver respuestas seguras.
- Aplicar cache de Streamlit cuando corresponde.

Funciones principales:

- `fetch_backend_json()`
- `get_latest_backend_data()`
- `get_latest_validation_data()`
- `get_alerts_history()`
- `get_alerts_history_supabase()`
- `get_setups_supabase()`
- `health_backend()`
- `health_binance()`
- `health_supabase()`

Endpoints consumidos:

- `GET /api/latest`
- `GET /api/validation/latest`
- `GET /api/alerts`
- `GET /api/alerts/supabase`
- `GET /api/setups/supabase`
- `GET /api/health/binance`
- `GET /api/health/supabase`

---

### 5. `services/` — Lógica de negocio y preparación de datos

La capa `services/` contiene cálculos, transformaciones y preparación de datos. No debe renderizar interfaz Streamlit directamente.

#### `services/market_data_service.py`

Responsabilidad:

- Descargar datos OHLCV desde Binance.
- Construir dataframes base por timeframe.

Funciones:

- `get_klines()`
- `obtener_datos_binance()`

Timeframes usados:

- `1m`
- `5m`
- `15m`
- `1h`

---

#### `services/indicators_service.py`

Responsabilidad:

- Calcular indicadores técnicos propios.
- Preparar dataframes enriquecidos para cada timeframe.

Indicadores incluidos:

- EMA
- RSI
- ATR
- ROC
- Bollinger Bands
- VWAP
- ADX / DMI
- Supertrend
- Volumen relativo
- Volatilidad
- Swing high / swing low

Funciones:

- `ema()`
- `rsi()`
- `atr()`
- `roc()`
- `bbands()`
- `vwap()`
- `adx_dmi()`
- `supertrend()`
- `preparar_tf()`
- `preparar_1m()`
- `preparar_5m_contexto()`

---

#### `services/context_service.py`

Responsabilidad:

- Construir el contexto operativo general del mercado.
- Clasificar régimen.
- Clasificar fase.
- Evaluar estructura LONG / SHORT.
- Evaluar agotamiento.
- Calcular probabilidad base.
- Calcular EV base.

Función principal:

- `construir_contexto()`

Salida principal:

- `price_1m`
- `price_5m`
- `fase`
- `market_regime`
- `adx_5m`
- `rsi_1m`
- `roc`
- `atr`
- `bb_width`
- `above_vwap`
- `above_ema200`
- `ema_bullish_stack`
- `ema_bearish_stack`
- `long_valido`
- `short_valido`
- `probabilidad`
- `EV`

---

#### `services/liquidity_service.py`

Responsabilidad:

- Construir el motor de liquidez local.
- Detectar pivots.
- Identificar liquidez por encima y por debajo del precio.
- Agrupar zonas.
- Calcular riesgo de liquidez.
- Explicar riesgo de liquidez para LONG o SHORT.

Funciones:

- `detectar_pivots()`
- `contar_toques()`
- `agrupar_zonas()`
- `market_liquidity_risk()`
- `liquidity_risk_explained()`
- `construir_liquidity_engine()`

Salida principal:

- `nearest_resistance`
- `nearest_support`
- `dist_up`
- `dist_down`
- `dist_up_pct`
- `dist_down_pct`
- `strong_resistances`
- `strong_supports`
- `liquidity_attraction`
- `market_clean`
- `market_lrs`
- `resistance_zones`
- `support_zones`

---

#### `services/mtf_service.py`

Responsabilidad:

- Validar condiciones multi-timeframe.
- Evaluar LONG y SHORT en 1H, 15M y 5M.
- Medir apertura de EMAs en 5M.

Funciones:

- `emas_abiertas_5m()`
- `evaluar_mtf()`

Validaciones principales:

1H:

- EMA50 vs EMA200
- DI+ / DI-
- ADX
- RSI
- ATR no decreciente

15M:

- Precio vs EMA20
- ADX subiendo
- RSI
- DI+ / DI-

5M:

- Abanico EMA9 / EMA20 / EMA50
- ADX
- DI+ / DI-

---

#### `services/trade_engine_service.py`

Responsabilidad:

- Calcular niveles de trade.
- Calcular TP, SL, break even y trailing.
- Calcular riesgo, beneficio y R:R.
- Calcular tamaño de posición real.

Funciones:

- `compute_trade_levels()`
- `calcular_posicion_real()`

Salida principal:

- `tp`
- `sl`
- `be`
- `trailing`
- `risk_pct`
- `reward_pct`
- `rr`
- `risk_label`
- `reward_label`
- `rr_label`
- `posicion`
- `margen`
- `riesgo`
- `beneficio`
- `comisiones`

---

#### `services/probability_service.py`

Responsabilidad:

- Calcular probabilidad real de alcanzar TP.
- Calcular probabilidad de rentabilidad.
- Generar debug de factores ponderados.

Funciones:

- `probabilidad_tp_real()`
- `probabilidad_rentable()`

Factores considerados:

- `prob_mercado`
- `prob_entry`
- R:R
- ATR ratio
- ADX
- RSI
- Liquidity Risk Score
- Atracción de liquidez
- EMA stack
- VWAP
- `market_regime`

---

#### `services/backtest_service.py`

Responsabilidad:

- Registrar señales locales.
- Buscar condiciones históricas similares.
- Calcular probabilidad histórica.
- Ejecutar backtest rápido 1M.

Funciones:

- `log_signal()`
- `condiciones_similares()`
- `probabilidad_historica()`
- `backtest()`

Salidas:

- wins
- losses
- winrate
- capital final simulado
- probabilidad histórica LONG
- probabilidad histórica SHORT

---

#### `services/explanation_service.py`

Responsabilidad:

- Centralizar textos explicativos largos.
- Evitar que `app.py` o las views contengan bloques extensos de documentación textual.

Funciones:

- `explicacion_prob_mercado()`
- `explicacion_mercado_fuerza()`
- `explicacion_fase()`
- `explicacion_climax()`
- `explicacion_adx_cayendo()`
- `explicacion_prob_entry()`
- `explicacion_momentum_bajista()`
- `explicacion_momentum_alcista()`
- `explicacion_rsi_saludable()`
- `explicacion_microtendencia_contraria()`
- `explicacion_vwap()`
- `explicacion_sin_energia()`
- `explicacion_compresion_extrema()`
- `explicacion_prob_tp_real()`
- `explicacion_prob_rentable()`
- `explicacion_calidad_setup()`

---

#### `services/alert_view_service.py`

Responsabilidad:

- Preparar datos de alertas para visualización.
- Extraer resumen de última alerta.
- Preparar histórico de alertas en formato tabular.
- Extraer detalle de cada alerta para expanders.

Funciones:

- `unwrap_latest_response()`
- `extract_latest_alert_summary()`
- `build_latest_alert_metrics()`
- `build_alert_history_rows()`
- `build_alert_history_dataframe()`
- `build_alert_expander_title()`
- `extract_alert_detail()`

---

#### `services/validation_view_service.py`

Responsabilidad:

- Preparar datos de validación para visualización.
- Extraer métricas globales.
- Extraer pasos de validación.
- Extraer razones, penalizaciones y snapshots.
- Separar bloques Pine / Backend / Probabilidad.

Funciones:

- `extract_validation_container()`
- `extract_validation_block()`
- `format_probability_value()`
- `build_validation_metrics()`
- `extract_validation_sections()`
- `get_step()`
- `build_step_title()`
- `get_pine_step_names()`
- `get_backend_step_names()`
- `extract_probability_model_summary()`
- `get_approve_status_message()`

---

### 6. `components/` — Componentes visuales reutilizables

La capa `components/` contiene piezas visuales pequeñas y reutilizables. No contiene lógica de negocio.

Archivos:

- `components/ui_helpers.py`
- `components/cards.py`
- `components/badges.py`
- `components/tables.py`

#### `components/ui_helpers.py`

Responsabilidad:

- Renderizar helpers visuales comunes.
- Mostrar bloques de explicación.
- Mostrar JSON en expanders.
- Mostrar listas de textos.
- Renderizar divisores visuales.

Funciones:

- `render_info_item()`
- `render_json_expander()`
- `render_text_list()`
- `render_section_divider()`

#### `components/cards.py`

Responsabilidad:

- Renderizar cards y métricas reutilizables.

Funciones:

- `render_metric_card()`
- `render_four_metrics()`
- `render_status_message()`

#### `components/badges.py`

Responsabilidad:

- Renderizar badges visuales de estado.

Funciones:

- `render_approve_badge()`
- `render_boolean_badge()`
- `render_direction_badge()`

#### `components/tables.py`

Responsabilidad:

- Renderizar dataframes y diccionarios como tablas.

Funciones:

- `render_dataframe()`
- `render_dict_as_dataframe()`

---

### 7. `views/` — Vistas completas del dashboard

La capa `views/` contiene pantallas o secciones completas. Las views renderizan UI consumiendo datos ya preparados por `services/`.

Archivos:

- `views/sidebar.py`
- `views/current_signal_view.py`
- `views/backend_monitor_view.py`
- `views/context_view.py`
- `views/liquidity_view.py`
- `views/mtf_view.py`
- `views/trade_evaluator_view.py`
- `views/backtest_view.py`

#### `views/sidebar.py`

Responsabilidad:

- Renderizar sidebar de auto-refresh.
- Renderizar configuración del símbolo.
- Mostrar endpoints Binance.

Funciones:

- `render_initial_backend_sidebar()`
- `render_market_sidebar()`

#### `views/current_signal_view.py`

Responsabilidad:

- Mostrar la señal actual del entorno.
- Mostrar LONG válido, SHORT válido, esperar o contexto ambiguo.
- Calcular niveles de trade del entorno actual.
- Registrar señal local si corresponde.

Función:

- `render_current_signal_view()`

#### `views/backend_monitor_view.py`

Responsabilidad:

- Mostrar monitor del backend.
- Mostrar última alerta recibida.
- Mostrar última validación.
- Mostrar razones y penalizaciones.
- Mostrar snapshot de mercado backend.
- Mostrar histórico Supabase.
- Mostrar payloads completos.

Función:

- `render_backend_monitor_tab()`

#### `views/context_view.py`

Responsabilidad:

- Mostrar régimen de mercado.
- Mostrar RSI, ROC y ATR.
- Mostrar contexto VWAP / EMA200 / EMAs.
- Mostrar compresión de volatilidad.
- Mostrar EV base.

Función:

- `render_context_tab()`

#### `views/liquidity_view.py`

Responsabilidad:

- Mostrar liquidez cercana.
- Mostrar distancia hacia soporte y resistencia.
- Mostrar intención probable del mercado.
- Mostrar zonas institucionales.
- Mostrar riesgo de liquidez.
- Mostrar estado operativo del mercado.

Función:

- `render_liquidity_tab()`

#### `views/mtf_view.py`

Responsabilidad:

- Mostrar validación MTF.
- Evaluar LONG y SHORT.
- Mostrar apertura de EMAs 5M.
- Mostrar checks por timeframe.

Función:

- `render_mtf_tab()`

#### `views/trade_evaluator_view.py`

Responsabilidad:

- Mostrar evaluador manual de entrada.
- Calcular condición de mercado.
- Calcular calidad de entrada.
- Mostrar gestión del trade.
- Mostrar probabilidad de TP.
- Mostrar probabilidad de rentabilidad.
- Mostrar calidad técnica.
- Mostrar decisión final.
- Mostrar gestión de posición.

Función:

- `render_trade_evaluator_tab()`

#### `views/backtest_view.py`

Responsabilidad:

- Mostrar backtest rápido 1M.
- Mostrar wins, losses, winrate y capital final.
- Mostrar probabilidad histórica por condiciones similares.

Función:

- `render_backtest_tab()`

---

## Estructura final del panel

streamlit_app/
├── app.py
├── .env
├── requirements.txt
│
├── core/
│   ├── __init__.py
│   ├── config.py
│   └── constants.py
│
├── utils/
│   ├── __init__.py
│   └── math_utils.py
│
├── clients/
│   ├── __init__.py
│   └── backend_client.py
│
├── services/
│   ├── __init__.py
│   ├── market_data_service.py
│   ├── indicators_service.py
│   ├── context_service.py
│   ├── liquidity_service.py
│   ├── mtf_service.py
│   ├── trade_engine_service.py
│   ├── probability_service.py
│   ├── backtest_service.py
│   ├── explanation_service.py
│   ├── alert_view_service.py
│   └── validation_view_service.py
│
├── components/
│   ├── __init__.py
│   ├── ui_helpers.py
│   ├── cards.py
│   ├── badges.py
│   └── tables.py
│
└── views/
    ├── __init__.py
    ├── sidebar.py
    ├── current_signal_view.py
    ├── backend_monitor_view.py
    ├── context_view.py
    ├── liquidity_view.py
    ├── mtf_view.py
    ├── trade_evaluator_view.py
    └── backtest_view.py

---

## Workflow interno de ejecución

1. `app.py` inicia Streamlit.
2. `core/config.py` carga variables de entorno.
3. `app.py` carga datos de Binance.
4. `indicators_service.py` prepara indicadores.
5. `context_service.py` construye contexto.
6. `liquidity_service.py` construye liquidez.
7. `sidebar.py` renderiza controles laterales.
8. `current_signal_view.py` muestra señal actual.
9. `backend_monitor_view.py` consulta backend/Supabase.
10. `context_view.py` muestra contexto.
11. `liquidity_view.py` muestra liquidez.
12. `mtf_view.py` muestra validación MTF.
13. `trade_evaluator_view.py` permite evaluación manual.
14. `backtest_view.py` muestra backtest rápido.
15. `app.py` ejecuta auto-refresh si está activo.

---

## Responsabilidades por fuente de datos

### TradingView

Responsable de:

- Generar señales.
- Enviar contexto técnico.
- Enviar trigger.
- Enviar quality score.
- Enviar estructura.
- Enviar liquidez detectada en Pine.
- Enviar HTF context.

### Backend FastAPI

Responsable de:

- Recibir alertas.
- Normalizar payloads.
- Ensamblar core + extra.
- Validar entradas.
- Consultar Binance.
- Calcular microestructura.
- Calcular score externo.
- Estimar probabilidad TP antes SL.
- Persistir en Supabase.
- Exponer endpoints al panel.

### Supabase

Responsable de:

- Guardar `alert_events`.
- Guardar `trade_setups`.
- Guardar `validation_results`.
- Servir histórico al dashboard.

### Binance

Responsable de:

- Proveer OHLCV.
- Proveer datos de mercado para indicadores locales.
- Alimentar contexto, liquidez y backtest local.

### Streamlit

Responsable de:

- Visualizar alertas.
- Visualizar validaciones.
- Visualizar histórico.
- Mostrar análisis local.
- Evaluar manualmente trades.
- Mostrar backtest y contexto operativo.

---

## Variables de entorno del panel

Archivo recomendado:

`streamlit_app/.env`

Ejemplo:

BACKEND_BASE_URL=http://localhost:8000
# BACKEND_BASE_URL=https://alertas-tdv-67cu-two.vercel.app

STREAMLIT_REQUEST_TIMEOUT=25
STREAMLIT_SHORT_REQUEST_TIMEOUT=10
STREAMLIT_CACHE_TTL_SECONDS=5

STREAMLIT_PAGE_TITLE=Panel Operativo BTC
STREAMLIT_PAGE_ICON=📊
STREAMLIT_PAGE_LAYOUT=wide

TRADING_SYMBOL=BTCUSDC

STREAMLIT_SIGNAL_LOG_FILE=signals_log.csv

STREAMLIT_DEFAULT_AUTO_REFRESH=true
STREAMLIT_DEFAULT_REFRESH_SECONDS=10
STREAMLIT_MIN_REFRESH_SECONDS=5
STREAMLIT_MAX_REFRESH_SECONDS=60

STREAMLIT_DEFAULT_HISTORY_LIMIT=50
STREAMLIT_DEBUG=false

---

## Ejecución local

Desde la carpeta del panel:

cd streamlit_app

Instalar dependencias:

pip install -r requirements.txt

Ejecutar:

streamlit run app.py

---

## Beneficios de esta arquitectura

La nueva arquitectura permite:

1. Mantener `app.py` limpio y fácil de leer.
2. Modificar una tab sin afectar el resto del panel.
3. Reutilizar cálculos en futuras vistas.
4. Reutilizar componentes visuales.
5. Cambiar endpoints desde `.env`.
6. Separar datos, lógica y presentación.
7. Reducir riesgo de errores al agregar funcionalidades.
8. Preparar el panel para tests unitarios.
9. Preparar el panel para despliegue en Streamlit Cloud u otra plataforma.
10. Facilitar mantenimiento futuro del sistema de trading.

Esta estructura permite continuar el desarrollo agregando dashboard avanzado, ML, LLM explanation, métricas de performance, automatización y análisis histórico sin seguir creciendo sobre archivos monolíticos.