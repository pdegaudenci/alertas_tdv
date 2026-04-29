"""
Entrada principal de FastAPI.

Este archivo crea la instancia principal de FastAPI, configura CORS y registra
las rutas del backend mediante include_router.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import ALLOWED_ORIGINS
from app.api.routes import router


app = FastAPI(
    title="TradingView Validation Layer",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)