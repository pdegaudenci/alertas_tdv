"""
Backtest View del panel Streamlit.

Este archivo contiene el tab "Backtest / Histórico" del dashboard.

Responsabilidad:
- Mostrar backtest rápido 1M.
- Mostrar resultados LONG / SHORT.
- Mostrar probabilidad histórica por condiciones similares.

"""

import pandas as pd
import streamlit as st

from services.backtest_service import (
    backtest,
    probabilidad_historica,
)


def render_backtest_tab(df_1m: pd.DataFrame) -> None:
    """
    Renderiza el tab Backtest / Histórico.

    Equivale al bloque original:

    with tab5:
        ...
    """

    st.subheader("Backtest rápido 1M")

    wins_l, losses_l, winrate_l, final_capital_l = backtest(df_1m, "long")
    wins_s, losses_s, winrate_s, final_capital_s = backtest(df_1m, "short")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("### LONG")
        st.write("Wins:", wins_l)
        st.write("Losses:", losses_l)
        st.write("Winrate:", round(winrate_l, 2), "%")
        st.write("Capital final simulado:", round(final_capital_l, 2))

    with c2:
        st.markdown("### SHORT")
        st.write("Wins:", wins_s)
        st.write("Losses:", losses_s)
        st.write("Winrate:", round(winrate_s, 2), "%")
        st.write("Capital final simulado:", round(final_capital_s, 2))

    st.markdown("---")
    st.subheader("Probabilidad histórica por condiciones similares")

    hist_long = probabilidad_historica(df_1m, "LONG")
    hist_short = probabilidad_historica(df_1m, "SHORT")

    st.write(f"LONG histórico: {hist_long:.2f}%")
    st.write(f"SHORT histórico: {hist_short:.2f}%")