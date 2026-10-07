"""Asigna cada deteccion a lo sumo a un lugar de estacionamiento.

Regla v4: la cobertura admite, el area de interseccion decide.

Las dos correcciones anteriores, las dos medidas sobre el predio real:

v1 elegia por punto de apoyo (centro del borde inferior de la caja). Ese
punto se corre un lugar HACIA LA CAMARA, porque la caja que devuelve el
modelo esta alineada a los ejes y los autos estan en diagonal.

v2 y v3 elegian por cobertura (interseccion / area del lugar). Esa
fraccion se corre un lugar HACIA EL FONDO, porque por perspectiva los
lugares lejanos se ven mucho mas chicos -- P01 mide 200.000 px2 y P07
solo 14.000 -- y dividir por un area menor infla su fraccion.

v4 conserva la cobertura como filtro de admision, que es lo que descarta
el estacionamiento del fondo, pero elige por superficie superpuesta en
pixeles, que no depende de cuan lejos este el lugar.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from vision.geometria import Poligono, area_poligono, interseccion_area

UMBRAL_COBERTURA = 0.35


@dataclass(frozen=True)
class Region:
    """Un lugar de estacionamiento, en pixeles de la imagen."""
    espacio: str
    poligono: Poligono


@dataclass(frozen=True)
class Asignacion:
    """El resultado de asignar una deteccion a un lugar."""
    espacio: str
    deteccion: object
    indice_deteccion: int
    cobertura: float       # fraccion del lugar que tapa la caja
    interseccion: float    # la misma superposicion, en pixeles cuadrados
    criterio: str          # "interseccion"

    # Nombres que usaban versiones anteriores. Se conservan para no tener
    # que tocar las herramientas; hoy siempre devuelven False.
    @property
    def por_punto_apoyo(self) -> bool:
        return self.criterio == "desempate"

    @property
    def por_apoyo(self) -> bool:
        return self.criterio == "desempate"

    @property
    def confianza(self) -> float:
        """Atajo a la confianza de la deteccion asignada."""
        return getattr(self.deteccion, "confianza", 0.0)

    @property
    def clase(self) -> str:
        """Atajo a la clase de la deteccion asignada."""
        return getattr(self.deteccion, "clase", "-")


def cargar_regiones(ruta: Path, ancho: int, alto: int) -> list[Region]:
    """Lee regiones.json y devuelve los poligonos en pixeles."""
    datos = json.loads(Path(ruta).read_text(encoding="utf-8"))
    return [
        Region(espacio=item["espacio"],
               poligono=[(x * ancho, y * alto) for x, y in item["poligono"]])
        for item in datos.get("regiones", [])
    ]


def asignar(detecciones, regiones, umbral: float = UMBRAL_COBERTURA):
    """Devuelve {espacio: Asignacion} para los espacios que quedan ocupados."""
    resultado: dict[str, Asignacion] = {}

    for indice, deteccion in enumerate(detecciones):
        caja = deteccion.caja

        # 1. Admision: solo son candidatas las regiones que la caja tapa en
        #    mas de `umbral`. Esto descarta el estacionamiento del fondo.
        candidatas = []
        for region in regiones:
            area = area_poligono(region.poligono)
            if area <= 0:
                continue
            interseccion = interseccion_area(caja, region.poligono)
            if interseccion / area >= umbral:
                candidatas.append((region, interseccion / area, interseccion))
        if not candidatas:
            continue

        # 2. Eleccion: gana la mayor superposicion EN PIXELES, no la mayor
        #    fraccion. Por perspectiva los lugares del fondo son hasta 14
        #    veces mas chicos, y dividir por su area inflaba su fraccion:
        #    un auto que pisaba dos lugares se asignaba siempre al de atras.
        elegida, cob, inter = max(candidatas, key=lambda t: t[2])

        # 3. Si dos detecciones caen en el mismo lugar, gana la que mas tapa.
        previa = resultado.get(elegida.espacio)
        if previa is None or inter > previa.interseccion:
            resultado[elegida.espacio] = Asignacion(
                espacio=elegida.espacio,
                deteccion=deteccion,
                indice_deteccion=indice,
                cobertura=cob,
                interseccion=inter,
                criterio="interseccion",
            )
    return resultado


def estado_de_espacios(regiones, asignaciones) -> dict[str, bool]:
    """{espacio: True si ocupado}. Incluye todos los espacios."""
    return {r.espacio: r.espacio in asignaciones for r in regiones}