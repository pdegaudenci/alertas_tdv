"""
Constantes operativas del panel Streamlit.

Este archivo contiene parámetros de trading, riesgo y configuración fija usada
por el dashboard analítico.

No contiene lógica de cálculo.
"""

# ============================================================
# TRADE CONFIG
# ============================================================

TP_BASE = 0.35          # %
SL_BASE = 0.15         # %
RISK_REWARD_WEIGHT = 0.4


# ============================================================
# POSITION / CAPITAL CONFIG
# ============================================================

CAPITAL_EUR = 170.0
RIESGO_POR_TRADE = 0.01
APALANCAMIENTO = 3.0


# ============================================================
# REAL EXECUTION ASSUMPTIONS
# ============================================================

TP_REAL = 0.006        # 0.6%
SL_REAL = 0.0035       # 0.35%
COMISION = 0.0008      # 0.08% por lado aprox


# ============================================================
# UI DEFAULTS
# ============================================================

DEFAULT_HISTORY_LIMIT = 50
HISTORY_LIMIT_OPTIONS = [10, 20, 50, 100]

DEFAULT_AUTO_REFRESH = True
DEFAULT_REFRESH_SECONDS = 10
MIN_REFRESH_SECONDS = 5
MAX_REFRESH_SECONDS = 60