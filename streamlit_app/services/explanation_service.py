"""
Explanation Service del panel Streamlit.

Este archivo contiene todos los textos explicativos usados por el dashboard.

Responsabilidad:
- Centralizar explicaciones de mercado, entrada, liquidez, TP, rentabilidad y calidad del setup.
- Evitar que app.py tenga bloques largos de texto.
- Mantener los textos originales sin cambiar comportamiento.


"""

from typing import Dict


# ============================================================
# EXPLICACIONES - CONTEXTO / MERCADO
# ============================================================

def explicacion_prob_mercado(prob_mercado: float, score_market: float, contexto: Dict) -> str:
    return f"""
**Qué significa este porcentaje**

La **probabilidad de entorno favorable** mide si el mercado actual tiene condiciones suficientes para que el trade
nazca en un contexto sano. No evalúa todavía el punto exacto de entrada, sino la calidad del entorno.

**Cómo se calcula en esta sección**
- Se parte de un score inicial de **0**.
- **ADX 5m**:
  - Si ADX > 25: se suman **30 puntos**.
  - Si ADX > 22: se suman **20 puntos**.
  - Si ADX es bajo: no suma y se considera entorno más débil.
- **Fase estructural**:
  - Si la fase NO es `RANGO`: se suman **20 puntos**.
  - Si la fase es `RANGO`: no suma porque el contexto es menos fiable.
- **Señales de agotamiento**:
  - `vela_extendida = True` no suma; se interpreta como posible clímax.
  - `adx_cayendo = True` no suma; se interpreta como pérdida de fuerza.

**Resultado actual**
- Score bruto de mercado: **{score_market}**
- Probabilidad entorno favorable mostrada: **{prob_mercado}%**
- ADX 5m actual: **{contexto['adx_5m']:.2f}**
- Fase actual: **{contexto['fase']}**
- Vela extendida: **{contexto['vela_extendida']}**
- ADX cayendo: **{contexto['adx_cayendo']}**

**Interpretación**
- Cuanto más alto es este porcentaje, mejor es el entorno general para operar.
- Un porcentaje bajo suele indicar mercado flojo, lateral o con síntomas de agotamiento.
""".strip()


def explicacion_mercado_fuerza() -> str:
    return """
**Mercado con fuerza (ADX > 25)**

El ADX mide la **intensidad** de la tendencia, no su dirección.

Cuando el ADX está por encima de 25, normalmente significa que:
- el mercado se está moviendo con decisión,
- hay mayor probabilidad de continuidad,
- hay menos ruido que en un rango débil.

**Importante:**  
ADX alto no significa automáticamente LONG o SHORT.  
Solo indica que el movimiento actual tiene fuerza.
La dirección la definen otros elementos como:
- DI+ / DI-
- fase
- VWAP
- estructura
""".strip()


def explicacion_fase(fase: str) -> str:
    mapa = {
        "ALCISTA": """
**Fase ALCISTA**

Indica que el contexto dominante favorece movimientos hacia arriba.

**Cómo se clasifica en este panel**
La fase se calcula con esta lógica:

- `st_dir == 1`  → el **Supertrend 5m** está alcista
- `adx_5m > 22` → el **ADX 5m** indica fuerza suficiente
- `di_plus > di_minus` → en el **DMI 5m**, los compradores dominan

Es decir, para que el panel etiquete una fase como **ALCISTA** deben alinearse:
1. **Dirección**: Supertrend 5m
2. **Fuerza**: ADX 5m
3. **Dominancia**: DI+ frente a DI-

**Interpretación**
No significa que debas comprar inmediatamente, sino que el sesgo estructural favorece LONG.
""",
        "BAJISTA": """
**Fase BAJISTA**

Indica que el contexto dominante favorece movimientos hacia abajo.

**Cómo se clasifica en este panel**
La fase se calcula con esta lógica:

- `st_dir == -1` → el **Supertrend 5m** está bajista
- `adx_5m > 22` → el **ADX 5m** indica fuerza suficiente
- `di_minus > di_plus` → en el **DMI 5m**, los vendedores dominan

Es decir, para que el panel etiquete una fase como **BAJISTA** deben alinearse:
1. **Dirección**: Supertrend 5m
2. **Fuerza**: ADX 5m
3. **Dominancia**: DI- frente a DI+

**Método usado**
El panel no clasifica la fase solo por precio o por una EMA.  
Usa una combinación de:
- **Supertrend 5m** para detectar dirección estructural
- **ADX 5m** para medir fuerza de tendencia
- **DI+ / DI-** para saber qué lado del mercado domina

**Interpretación**
No significa que debas vender inmediatamente, sino que el sesgo estructural favorece SHORT.
""",
        "TRANSICIÓN": """
**Fase TRANSICIÓN**

El mercado no está completamente definido.

**Cómo se clasifica en este panel**
Se considera transición cuando el **ADX 5m** está en una zona intermedia:
- `15 <= adx_5m <= 22`

Eso sugiere que el mercado:
- puede estar cambiando de dirección,
- perdiendo fuerza en la tendencia previa,
- o preparándose para expansión.

**Método usado**
Aquí el panel usa principalmente el **ADX 5m** como medidor de fuerza insuficiente o intermedia.

**Interpretación**
En transición suele haber más incertidumbre y más falsas señales.
""",
        "RANGO": """
**Fase RANGO**

El mercado está lateral o sin impulso claro.

**Cómo se clasifica en este panel**
Si no se cumplen las condiciones de fase alcista, bajista o transición,
el panel clasifica el entorno como **RANGO**.

En la práctica suele ocurrir cuando:
- el **Supertrend** no da una lectura sólida,
- el **ADX 5m** no muestra suficiente fuerza,
- o no hay dominancia clara entre **DI+ y DI-**.

**Método usado**
La clasificación sale por descarte:
- no hay tendencia clara,
- no hay fuerza suficiente,
- o no hay dominancia limpia.

**Interpretación**
En rango aumenta el riesgo de ruido, barridas y falsas rupturas.
"""
    }

    return mapa.get(fase, "Fase no reconocida.")


def explicacion_climax() -> str:
    return """
**Vela 1m extendida (posible clímax)**

Una vela extendida es una vela cuyo rango es claramente mayor que el promedio reciente.

Esto puede significar:
- aceleración final del movimiento,
- compras o ventas tardías,
- posible agotamiento justo antes de pausa o retroceso.

Se le llama **clímax** porque muchas veces aparece cuando gran parte del impulso ya ocurrió.
Entrar justo después de un clímax suele aumentar el riesgo de llegar tarde.
""".strip()


def explicacion_adx_cayendo() -> str:
    return """
**ADX cayendo (pérdida de fuerza)**

Si el ADX empieza a bajar, significa que la tendencia sigue existiendo quizá en precio,
pero su **fuerza interna** se está debilitando.

Eso puede traducirse en:
- menor continuidad,
- más dificultad para alcanzar TP,
- más probabilidad de pausa, retroceso o rango.

No siempre implica giro inmediato, pero sí alerta de que el impulso es menos sólido.
""".strip()


# ============================================================
# EXPLICACIONES - VALIDACIÓN DE ENTRADA
# ============================================================

def explicacion_prob_entry(prob_entry: float, score_entry: float, direccion: str) -> str:
    return f"""
**Qué significa este porcentaje**

La **Calidad de la entrada** evalúa si este momento concreto es bueno para ejecutar el trade.

A diferencia de la condición del mercado (entorno general), aquí se analiza el
**timing inmediato** de entrada.

**Cómo se calcula**
Se parte de una base de **50 puntos** y luego se suman o restan factores:

1. Momentum inmediato (ROC)
2. RSI
3. Microtendencia (EMA stack)
4. Posición respecto al VWAP
5. Energía del movimiento (ATR vs TP)
6. Compresión de volatilidad (Bollinger Width)

**Resultado actual**
- Dirección evaluada: **{direccion}**
- Score final: **{score_entry}**
- Calidad de entrada mostrada: **{prob_entry}%**

**Interpretación**
- Alto % = buen timing
- Medio % = entrada aceptable con cautela
- Bajo % = mala sincronización o condiciones pobres
""".strip()


def explicacion_momentum_bajista() -> str:
    return """
**Momentum inmediato bajista**

Se mide con el indicador **ROC (Rate of Change)**.

En SHORT, si el ROC es claramente negativo, significa que el precio ya está acelerando hacia abajo.

Eso aporta:
- confirmación de presión vendedora,
- continuidad inmediata,
- menor probabilidad de entrar contra el impulso.

No mide tendencia global, solo velocidad reciente.
""".strip()


def explicacion_momentum_alcista() -> str:
    return """
**Momentum inmediato alcista**

Se mide con el indicador **ROC (Rate of Change)**.

En LONG, si el ROC es positivo y suficiente, significa aceleración reciente al alza.

Eso aporta:
- confirmación compradora,
- timing más agresivo,
- mayor probabilidad de continuación inmediata.
""".strip()


def explicacion_rsi_saludable(direction: str) -> str:
    if direction == "LONG":
        return """
**RSI saludable para LONG**

El RSI está en una zona alcista sana:
- no demasiado débil,
- no sobrecomprado.

Eso sugiere que aún puede quedar recorrido al alza sin estar excesivamente extendido.
""".strip()

    return """
**RSI saludable para SHORT**

El RSI está en una zona bajista sana:
- hay debilidad,
- pero no sobreventa extrema.

Eso sugiere que el precio puede seguir cayendo sin estar demasiado agotado.
""".strip()


def explicacion_microtendencia_contraria() -> str:
    return """
**Microtendencia contraria (EMA stack)**

Se comparan las EMAs rápidas del marco 1m:

- LONG busca: EMA20 > EMA50
- SHORT busca: EMA20 < EMA50

Si no se cumple, la estructura corta del precio no acompaña la dirección elegida.

Eso aumenta el riesgo de:
- retroceso,
- entrada prematura,
- señal sin continuidad.
""".strip()


def explicacion_vwap() -> str:
    return """
**Precio control institucional (VWAP)**

El VWAP representa el precio promedio ponderado por volumen.

Se usa como referencia institucional:

- LONG: mejor si el precio está por encima del VWAP
- SHORT: mejor si el precio está por debajo del VWAP

Operar a favor del VWAP suele mejorar la probabilidad de continuidad.
""".strip()


def explicacion_sin_energia() -> str:
    return """
**Movimiento sin energía**

Se mide con la relación:

**ATR actual / distancia al TP**

Si el ATR es demasiado pequeño respecto al objetivo, el mercado puede no tener
volatilidad suficiente para alcanzar el TP.

En resumen:
- poco desplazamiento,
- movimiento lento,
- trade con peor expectativa.
""".strip()


def explicacion_compresion_extrema() -> str:
    return """
**Compresión extrema**

Se detecta usando el ancho de las Bollinger Bands (`bb_width`).

Cuando la compresión es muy baja:
- el mercado está apretado,
- hay poca expansión real,
- aumentan falsos breakouts.

Una ruptura desde compresión puede funcionar, pero necesita confirmación extra.
""".strip()


# ============================================================
# EXPLICACIONES - TP / RENTABILIDAD / CALIDAD DEL SETUP
# ============================================================

def explicacion_prob_tp_real(
    prob_tp: float,
    prob_mercado: float,
    prob_entry: float,
    rr: float,
    atr_ratio: float,
    adx: float,
    rsi: float,
    lrs: float,
    market_regime: str,
    liquidity_attraction: str
) -> str:
    base = (prob_mercado * 0.55 + prob_entry * 0.45)

    return f"""
**Qué significa esta probabilidad**

La **Probabilidad real de alcanzar TP** intenta estimar qué tan probable es que el precio llegue al take profit
propuesto, combinando contexto de mercado, calidad de entrada y penalizaciones/bonificaciones adicionales.

**Cómo se calcula**
Primero se construye una base:

- **55% peso** → `prob_mercado`
- **45% peso** → `prob_entry`

Base actual:
- Probabilidad de entorno: **{prob_mercado:.1f}%**
- Calidad de entrada: **{prob_entry:.1f}%**
- Base combinada: **{base:.1f}**

Después esa base se ajusta con estos factores:

1. **R:R**
   - Mejor relación beneficio/riesgo suma puntos
   - Mala relación R:R resta puntos

2. **ATR ratio**
   - Evalúa si la volatilidad actual puede alcanzar el TP
   - Muy poca energía resta
   - Demasiada volatilidad también puede penalizar

3. **ADX**
   - Mide fuerza de tendencia
   - ADX alto favorece continuidad
   - ADX bajo penaliza

4. **RSI**
   - Sirve como timing complementario
   - A favor suma
   - En contra resta

5. **Liquidity Risk Score (LRS)**
   - Penaliza trades con alta probabilidad de sweep o entorno sucio

6. **Atracción de liquidez**
   - Si la liquidez tira en contra del trade, se resta

7. **Estructura institucional**
   - EMA stack + VWAP a favor pueden sumar

8. **Régimen de mercado**
   - TENDENCIA y EXPANSIÓN suman
   - RANGO resta bastante

**Estado actual**
- R:R: **{rr:.2f}**
- ATR ratio: **{atr_ratio:.2f}**
- ADX: **{adx:.2f}**
- RSI: **{rsi:.2f}**
- LRS: **{lrs:.1f}**
- Régimen: **{market_regime}**
- Atracción de liquidez: **{liquidity_attraction}**
- Probabilidad final mostrada: **{prob_tp:.1f}%**

**Interpretación**
- Porcentaje alto: mayor probabilidad de que el precio alcance el TP
- Porcentaje bajo: el setup puede existir, pero la probabilidad de completar el recorrido es débil
""".strip()


def explicacion_prob_rentable(prob_profit: float, prob_tp: float, rr: float) -> str:
    return f"""
**Qué significa esta probabilidad**

La **Probabilidad de rentabilidad** no mide solo si el TP puede alcanzarse.
Mide si, combinando la probabilidad de éxito con el R:R del trade, el resultado esperado es favorable.

**Cómo se calcula**
Se usa:
- `prob_tp = {prob_tp:.1f}%`
- `rr = {rr:.2f}`

Primero:
- `p = prob_tp / 100`

Luego se calcula un EV normalizado:
- `ev = (p * rr) - (1 - p)`

Y después ese EV se transforma a una escala 0–100 para mostrarlo como probabilidad visual de rentabilidad.

**Qué pondera realmente**
- La **probabilidad de alcanzar TP**
- La **relación beneficio/riesgo (R:R)**

**Interpretación**
- Puede ocurrir que un trade tenga **baja probabilidad de TP** pero **alta rentabilidad esperada**
  si el R:R compensa suficientemente.
- También puede pasar lo contrario:
  mucha probabilidad de acierto, pero poco beneficio relativo.

**Resultado actual**
- Probabilidad de TP: **{prob_tp:.1f}%**
- R:R real: **{rr:.2f}**
- Probabilidad de rentabilidad mostrada: **{prob_profit:.1f}%**
""".strip()


def explicacion_calidad_setup(
    final_score: float,
    rating: str,
    prob_mercado: float,
    prob_entry: float,
    lrs_score: float
) -> str:
    base_score = (prob_mercado * 0.55 + prob_entry * 0.45)
    liquidity_penalty = lrs_score * 0.35

    return f"""
**Qué significa este score**

La **Calidad Técnica del Setup** resume si el trade tiene permiso operativo suficiente
antes incluso de decidir si es ideal, marginal o inválido.

**Cómo se calcula**
1. Se construye una base:
   - **55% peso** → probabilidad de entorno (`prob_mercado`)
   - **45% peso** → calidad de entrada (`prob_entry`)

2. Después se aplica una penalización por liquidez:
   - `Liquidity penalty = LRS * 0.35`

**Valores actuales**
- Probabilidad de entorno: **{prob_mercado:.1f}%**
- Calidad de entrada: **{prob_entry:.1f}%**
- Base combinada: **{base_score:.1f}%**
- Liquidity Risk Score: **{lrs_score:.1f}**
- Penalización por liquidez: **{liquidity_penalty:.1f}**
- Score final: **{final_score:.1f}%**
- Rating: **{rating}**

**Qué factores pondera indirectamente**
A través de `prob_mercado` y `prob_entry`, este score incorpora:
- ADX
- fase estructural
- agotamiento
- ROC
- RSI
- EMA stack
- VWAP
- ATR ratio
- compresión de volatilidad

Y además, aparte, resta por:
- riesgo de liquidez
- entorno con probable sweep
- estructura sucia

**Interpretación**
- Score bajo: el mercado o la entrada no son suficientemente buenos
- Score medio: trade operable pero con cautela
- Score alto: el setup tiene buena calidad técnica
""".strip()