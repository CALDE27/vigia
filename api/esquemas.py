"""El contrato de API, escrito como clases.

Cada clase es un cuerpo JSON del documento de contrato. FastAPI las usa
para tres cosas a la vez: validar lo que entra, dar forma a lo que sale
y generar la documentacion de /docs. Si el contrato cambia, se cambia
aca primero.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


# --- Lo que publica el servicio de vision -------------------------------

class LugarPublicado(BaseModel):
    espacio: str
    ocupado: bool
    confianza: float | None = None
    cobertura: float | None = None


class EstadoPublicado(BaseModel):
    instante: datetime
    cuadro: int
    lugares: list[LugarPublicado]


class TransicionBreve(BaseModel):
    espacio: str
    estado: str
    instante: datetime


class RespuestaPublicacion(BaseModel):
    recibido: int
    corrida: int
    transiciones: list[TransicionBreve]


# --- Lo que consume el tablero ------------------------------------------

class Resumen(BaseModel):
    total: int
    libres: int
    ocupados: int


class LugarEstado(BaseModel):
    espacio: str
    ocupado: bool
    desde: datetime | None = None
    duracion_s: int | None = None
    confianza: float | None = None


class RespuestaEstado(BaseModel):
    instante: datetime
    cuadro: int
    corrida: int
    actualizado_hace_s: float
    resumen: Resumen
    lugares: list[LugarEstado]


class Transicion(BaseModel):
    id: int
    espacio: str
    estado: str
    instante: datetime
    duracion_anterior_s: int | None = None


class RespuestaTransiciones(BaseModel):
    total: int
    limite: int
    desplazamiento: int
    transiciones: list[Transicion]


# --- Endpoints de servicio ----------------------------------------------

class Salud(BaseModel):
    estado: str
    version: str
    corrida: int
    ultimo_estado_hace_s: float | None = None
    lugares_configurados: int


class RespuestaReinicio(BaseModel):
    corrida: int


class Error(BaseModel):
    error: str
    detalle: str = Field(description="Texto para un humano. Puede cambiar.")