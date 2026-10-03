"""Asociacion de detecciones con espacios de estacionamiento.

Decide que vehiculo ocupa que lugar. No sabe nada de YOLO ni de OpenCV:
recibe detecciones y regiones, y devuelve a quien le toco cada espacio.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from vision.geometria import Poligono, cobertura, punto_en_poligono

if TYPE_CHECKING:
    from vision.detector import Deteccion

# Fraccion minima del lugar que debe cubrir la caja cuando el punto de
# apoyo no cae en ningun lugar.
UMBRAL_COBERTURA = 0.35


@dataclass(frozen=True)
class Region:
    """Un espacio de estacionamiento, con su poligono en pixeles."""

    espacio: str
    poligono: Poligono


@dataclass(frozen=True)
class Asignacion:
    """Un vehiculo asignado a un espacio."""

    espacio: str
    indice: int  # posicion de la deteccion en la lista recibida
    deteccion: Deteccion
    cobertura: float
    por_apoyo: bool  # True si gano por el punto de apoyo, False por cobertura


def cargar_regiones(ruta: str | Path, ancho: float, alto: float) -> list[Region]:
    """Lee el JSON de calibracion y pasa los poligonos de 0..1 a pixeles."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    regiones: list[Region] = []
    for item in datos.get("regiones", []):
        poligono = [(x * ancho, y * alto) for x, y in item["poligono"]]
        regiones.append(Region(espacio=item["espacio"], poligono=poligono))
    return regiones


def asignar(
    detecciones: list[Deteccion],
    regiones: list[Region],
    umbral: float = UMBRAL_COBERTURA,
) -> dict[str, Asignacion]:
    """Asigna cada deteccion a un espacio como mucho.

    1. Si el punto de apoyo cae dentro de uno o mas lugares, gana ese
       (si hay dos por error de calibracion, desempata la cobertura).
    2. Si no, gana el lugar con mayor cobertura, si llega al umbral.
    3. Si ninguno llega, la deteccion se descarta (auto del pasillo o
       del fondo del predio).

    Si dos detecciones caen en el mismo espacio, se queda la de mayor
    cobertura.
    """
    resultado: dict[str, Asignacion] = {}
    for indice, deteccion in enumerate(detecciones):
        caja = deteccion.caja
        apoyo = deteccion.punto_apoyo

        contenedores = [r for r in regiones if punto_en_poligono(apoyo, r.poligono)]
        if contenedores:
            elegida = max(contenedores, key=lambda r: cobertura(caja, r.poligono))
            por_apoyo = True
        else:
            candidatas = [(r, cobertura(caja, r.poligono)) for r in regiones]
            candidatas = [(r, c) for r, c in candidatas if c >= umbral]
            if not candidatas:
                continue
            elegida = max(candidatas, key=lambda par: par[1])[0]
            por_apoyo = False

        cob = cobertura(caja, elegida.poligono)
        previa = resultado.get(elegida.espacio)
        if previa is None or cob > previa.cobertura:
            resultado[elegida.espacio] = Asignacion(
                espacio=elegida.espacio,
                indice=indice,
                deteccion=deteccion,
                cobertura=cob,
                por_apoyo=por_apoyo,
            )
    return resultado


def estado_de_espacios(
    regiones: list[Region], asignaciones: dict[str, Asignacion]
) -> dict[str, bool]:
    """True si el espacio esta ocupado, False si esta libre."""
    return {r.espacio: r.espacio in asignaciones for r in regiones}
