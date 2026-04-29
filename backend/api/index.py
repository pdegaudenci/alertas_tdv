"""
Wrapper de entrada para Vercel.

Vercel suele esperar un archivo api/index.py como entrypoint.
Este archivo no contiene lógica propia: solo expone la app FastAPI real definida
en app/main.py.
"""

from app.main import app