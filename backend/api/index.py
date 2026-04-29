"""
Entrypoint de Vercel para FastAPI.

Este archivo expone una variable global llamada `app`, requerida por Vercel.
La app real está definida en app/main.py.
"""

from app.main import app as fastapi_app

app = fastapi_app