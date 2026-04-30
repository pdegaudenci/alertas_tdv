"""
MTF View del panel Streamlit.

Este archivo contiene el tab "Validación MTF" del dashboard.

Responsabilidad:
- Mostrar validación multi-timeframe para LONG y SHORT.
- Mostrar distancia entre EMAs 5m.
- Mostrar checks por 1H, 15M y 5M.

"""

import pandas as pd
import streamlit as st

from services.mtf_service import (
    evaluar_mtf,
    emas_abiertas_5m,
)


def render_mtf_tab(
    df_1m: pd.DataFrame,
    df_5m: pd.DataFrame,
    df_15m: pd.DataFrame,
    df_1h: pd.DataFrame,
) -> None:
    """
    Renderiza el tab Validación MTF.

    Equivale al bloque original:

    with tab3:
        ...
    """

    st.subheader("🧠 Validación MTF")

    for direccion in ["LONG", "SHORT"]:
        st.markdown(f"## {direccion}")

        mtf_valido, detalle = evaluar_mtf(
            direccion,
            df_1h,
            df_15m,
            df_5m,
            df_1m,
        )

        if mtf_valido:
            st.success(f"{direccion} VÁLIDO")
        else:
            st.error(f"{direccion} INVÁLIDO")

        ema9_5m = df_5m["ema9"].iloc[-1]
        ema20_5m = df_5m["ema20"].iloc[-1]
        ema50_5m = df_5m["ema50"].iloc[-1]
        price5m = df_5m["close"].iloc[-1]

        emas_ok, d1, d2 = emas_abiertas_5m(
            direccion,
            ema9_5m,
            ema20_5m,
            ema50_5m,
            price5m,
        )

        ca, cb, cc = st.columns(3)
        ca.metric("EMA9-EMA20 distancia", f"{d1 * 100:.3f}%")
        cb.metric("EMA20-EMA50 distancia", f"{d2 * 100:.3f}%")
        cc.metric("EMAs abiertas", "SI" if emas_ok else "NO")

        for tf, (valido_tf, checks) in detalle.items():
            st.subheader(f"{tf} ({'VÁLIDO' if valido_tf else 'INVÁLIDO'})")

            for c in checks:
                if c["ok"]:
                    st.success(f"✔ {c['texto']} : {c['valor']}")
                else:
                    st.error(f"✖ {c['texto']} : {c['valor']}")

        st.markdown("---")