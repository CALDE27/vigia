"""Confirma los cambios de estado solo cuando se repiten K veces seguidas."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

K_POR_DEFECTO = 3


@dataclass(frozen=True)
class Transicion:
    """Un cambio de estado confirmado."""
    espacio: str
    estado: bool                  # True = paso a ocupado
    instante: datetime
    duracion_anterior_s: float    # cuanto duro el estado que termina

    @property
    def etiqueta(self) -> str:
        return "OCUPADO" if self.estado else "LIBRE"


class Estabilizador:
    """Mantiene una maquina de estados por cada lugar."""

    def __init__(self, espacios, instante_inicial: datetime,
                 k: int = K_POR_DEFECTO, estado_inicial: bool = False) -> None:
        if k < 1:
            raise ValueError("K tiene que ser 1 o mas.")
        self.k = k
        self._confirmado = {e: estado_inicial for e in espacios}
        self._contador = {e: 0 for e in espacios}
        self._desde = {e: instante_inicial for e in espacios}

    def observar(self, observaciones: dict, instante: datetime) -> list[Transicion]:
        """Recibe el estado observado en un cuadro y devuelve lo que se confirmo."""
        transiciones = []
        for espacio, observado in observaciones.items():
            if espacio not in self._confirmado:
                continue

            if observado == self._confirmado[espacio]:
                self._contador[espacio] = 0      # la racha se corta
                continue

            self._contador[espacio] += 1
            if self._contador[espacio] >= self.k:
                duracion = (instante - self._desde[espacio]).total_seconds()
                self._confirmado[espacio] = observado
                self._contador[espacio] = 0
                self._desde[espacio] = instante
                transiciones.append(
                    Transicion(espacio, observado, instante, duracion))
        return transiciones

    @property
    def estado(self) -> dict:
        """{espacio: True si ocupado}, segun lo confirmado."""
        return dict(self._confirmado)

    @property
    def pendientes(self) -> dict:
        """{espacio: cuantas muestras lleva contradiciendo}. Util para el tablero."""
        return {e: c for e, c in self._contador.items() if c > 0}