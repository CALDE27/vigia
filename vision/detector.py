"""Envoltorio del modelo de detección de objetos.

Este módulo es la ÚNICA parte del sistema que sabe que existe YOLO. Todo
lo demás trabaja con la clase Deteccion, que es nuestra. Si mañana
cambiamos de modelo, se reescribe este archivo y ningún otro.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Clases del dataset COCO que consideramos vehículo.
CLASES_VEHICULO: frozenset[str] = frozenset({"car", "motorcycle", "bus", "truck"})


@dataclass(frozen=True)
class Deteccion:
    """Un vehículo detectado en un cuadro.

    Coordenadas en píxeles, origen (0,0) arriba a la izquierda,
    eje Y creciendo hacia abajo.
    """

    clase: str
    confianza: float
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def ancho(self) -> float:
        return self.x2 - self.x1

    @property
    def alto(self) -> float:
        return self.y2 - self.y1

    @property
    def area(self) -> float:
        return self.ancho * self.alto

    @property
    def caja(self) -> tuple[float, float, float, float]:
        return (self.x1, self.y1, self.x2, self.y2)

    @property
    def punto_apoyo(self) -> tuple[float, float]:
        """Centro del borde inferior: aproxima dónde el vehículo toca el piso."""
        return ((self.x1 + self.x2) / 2.0, self.y2)


class DetectorVehiculos:
    """Carga el modelo una vez y detecta vehículos en los cuadros que reciba."""

    def __init__(
        self,
        modelo: str = "yolo11n.pt",
        umbral_confianza: float = 0.35,
        tamano_entrada: int = 640,
    ) -> None:
        from ultralytics import YOLO  # import perezoso: ultralytics tarda en cargar

        self.umbral_confianza = float(umbral_confianza)
        self.tamano_entrada = int(tamano_entrada)
        self._modelo = YOLO(modelo)
        self._nombres: dict[int, str] = self._modelo.names

    def detectar(self, imagen: np.ndarray) -> list[Deteccion]:
        """Corre el modelo sobre un cuadro y devuelve sólo los vehículos."""
        resultados = self._modelo.predict(
            source=imagen,
            imgsz=self.tamano_entrada,
            conf=self.umbral_confianza,
            device="cpu",
            verbose=False,
        )

        detecciones: list[Deteccion] = []
        for resultado in resultados:
            if resultado.boxes is None:
                continue
            for caja in resultado.boxes:
                clase = self._nombres[int(caja.cls[0])]
                if clase not in CLASES_VEHICULO:
                    continue
                x1, y1, x2, y2 = (float(v) for v in caja.xyxy[0])
                detecciones.append(
                    Deteccion(
                        clase=clase,
                        confianza=float(caja.conf[0]),
                        x1=x1,
                        y1=y1,
                        x2=x2,
                        y2=y2,
                    )
                )
        return detecciones