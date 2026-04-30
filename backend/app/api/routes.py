"""
Archivo legacy de rutas.

Las rutas fueron separadas en:
- health_routes.py
- dashboard_routes.py
- validation_routes.py
- webhook_routes.py

Se mantiene este archivo para compatibilidad temporal.
No registra endpoints.
"""

from fastapi import APIRouter


router = APIRouter()