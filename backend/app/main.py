"""
Entrada principal de FastAPI.

Este archivo crea la instancia principal de FastAPI, configura CORS y registra
las rutas del backend mediante include_router.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import ALLOWED_ORIGINS
from app.api.health_routes import router as health_router
from app.api.dashboard_routes import router as dashboard_router
from app.api.validation_routes import router as validation_router
from app.api.webhook_routes import router as webhook_router
from app.api.processing_sqs_routes import router as processing_sqs_router


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

app.include_router(health_router)
app.include_router(dashboard_router)
app.include_router(validation_router)
app.include_router(webhook_router)
app.include_router(processing_sqs_router)