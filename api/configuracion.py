"""Ajustes del backend y carga de los lugares calibrados.

Todo lo configurable vive aca, en un solo lugar, leido del entorno con
un valor por defecto que sirve para desarrollar sin configurar nada.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

# La raiz del proyecto: la carpeta que contiene a api/.
RAIZ = Path(__file__).resolve().parent.parent

VERSION = "1.0.0"

# Clave compartida con el servicio de vision. En desarrollo alcanza con
# el valor por defecto; en una maquina real se define la variable de
# entorno VIGIA_CLAVE antes de levantar el servidor.
CLAVE_SERVICIO = os.environ.get("VIGIA_CLAVE", "clave-de-desarrollo")

RUTA_REGIONES = Path(os.environ.get("VIGIA_REGIONES", RAIZ / "config" / "regiones.json"))

# Cuantos segundos reales dura un ciclo completo del guion de prueba.
CICLO_S = 120

# El archivo de la base de datos.
RUTA_BASE = Path(os.environ.get("VIGIA_BASE", RAIZ / "datos" / "vigia.db"))

# Con VIGIA_FALSOS=1 el backend vuelve al guion del tramo 6 en lugar de
# usar la base. Sirve para que el frontend trabaje sin publicaciones.
USAR_FALSOS = os.environ.get("VIGIA_FALSOS", "") == "1"

def leer_espacios() -> list[str]:
    """Devuelve los identificadores de lugares de la calibracion."""
    if not RUTA_REGIONES.exists():
        raise SystemExit(
            f"No encuentro {RUTA_REGIONES}. El backend necesita la "
            "calibracion para saber cuantos lugares hay."
        )
    datos = json.loads(RUTA_REGIONES.read_text(encoding="utf-8"))
    espacios = [region["espacio"] for region in datos.get("regiones", [])]
    if not espacios:
        raise SystemExit(f"{RUTA_REGIONES} no tiene ninguna region.")
    return espacios