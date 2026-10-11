"""Publica en el backend el estado de los lugares, por REST.

Usa urllib, que viene incluido en Python: el servicio de vision no suma
ninguna dependencia nueva para hablar con la API.

La politica de errores es deliberada y conviene entenderla. Si el
backend no responde al arrancar, el programa corta con un mensaje
claro, porque casi seguro alguien se olvido de levantarlo. Si en cambio
falla a mitad de camino, se cuenta el fallo y el recorrido sigue:
perder una muestra no justifica perder media hora de procesamiento, y
como cada publicacion lleva el estado completo, la siguiente corrige
sola lo que la anterior no pudo enviar.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from datetime import datetime

URL_BASE = os.environ.get("VIGIA_API", "http://127.0.0.1:8000/api/v1")
CLAVE = os.environ.get("VIGIA_CLAVE", "clave-de-desarrollo")


class ErrorPublicacion(Exception):
    """No se pudo hablar con el backend."""


def armar_lugares(espacios, estado, asignaciones) -> list[dict]:
    """Arma la lista `lugares` del contrato con lo que hay en memoria.

    `estado` es el estado ya estabilizado por la histeresis; `asignaciones`
    trae la deteccion que ocupa cada lugar, para la confianza y la cobertura.
    """
    lugares = []
    for espacio in espacios:
        ocupado = bool(estado.get(espacio, False))
        asignacion = asignaciones.get(espacio) if ocupado else None
        lugares.append({
            "espacio": espacio,
            "ocupado": ocupado,
            "confianza": round(float(asignacion.confianza), 3) if asignacion else None,
            "cobertura": round(float(asignacion.cobertura), 3) if asignacion else None,
        })
    return lugares


class Publicador:
    """Un cliente minimo de los dos endpoints de escritura del contrato."""

    def __init__(self, url_base: str = URL_BASE, clave: str = CLAVE,
                 espera_s: float = 5.0) -> None:
        self.url_base = url_base.rstrip("/")
        self.clave = clave
        self.espera_s = espera_s
        self.enviadas = 0
        self.fallidas = 0
        self.ultimo_error: str | None = None

    def _pedir(self, ruta: str, cuerpo: dict) -> dict:
        pedido = urllib.request.Request(
            f"{self.url_base}{ruta}",
            data=json.dumps(cuerpo).encode("utf-8"),
            method="POST",
            headers={
                "Content-Type": "application/json",
                "X-Clave-Servicio": self.clave,
            },
        )
        try:
            with urllib.request.urlopen(pedido, timeout=self.espera_s) as respuesta:
                return json.loads(respuesta.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            detalle = error.read().decode("utf-8", errors="replace")[:200]
            raise ErrorPublicacion(
                f"El backend rechazo el pedido a {ruta}: HTTP {error.code}. {detalle}"
            ) from error
        except urllib.error.URLError as error:
            raise ErrorPublicacion(
                f"No pude conectar con {self.url_base}. Esta levantado el "
                f"backend? Detalle: {error.reason}"
            ) from error

    def reiniciar(self) -> int:
        """Abre una corrida nueva. Si falla, levanta: es el arranque."""
        return self._pedir("/reinicio", {})["corrida"]

    def publicar(self, instante: datetime, cuadro: int,
                 lugares: list[dict]) -> list[dict]:
        """Publica el estado completo. Nunca levanta: cuenta y sigue."""
        cuerpo = {
            "instante": instante.replace(microsecond=0).isoformat(),
            "cuadro": int(cuadro),
            "lugares": lugares,
        }
        try:
            respuesta = self._pedir("/estado", cuerpo)
        except ErrorPublicacion as error:
            self.fallidas += 1
            self.ultimo_error = str(error)
            return []
        self.enviadas += 1
        self.ultimo_error = None
        return respuesta.get("transiciones", [])

    def resumen(self) -> str:
        """Una linea para el final del recorrido."""
        if not self.fallidas:
            return f"Publicadas {self.enviadas} muestras, sin fallos."
        return (f"Publicadas {self.enviadas} muestras, {self.fallidas} fallaron. "
                f"Ultimo error: {self.ultimo_error}")