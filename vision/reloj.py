"""Relojes del sistema. El tiempo es una dependencia, no una llamada global."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta


@dataclass(frozen=True)
class RelojSimulado:
    """Traduce el tiempo del video a una linea de tiempo comprimida."""

    origen: datetime
    factor: float = 24.0

    @classmethod
    def para_abarcar(cls, origen: datetime, fin: datetime,
                     duracion_video_s: float) -> "RelojSimulado":
        """Calcula el factor para que el video entero cubra ese rango horario."""
        if duracion_video_s <= 0:
            raise ValueError("La duracion del video tiene que ser mayor que cero.")
        span = (fin - origen).total_seconds()
        return cls(origen=origen, factor=span / duracion_video_s)

    def instante(self, segundo_de_video: float) -> datetime:
        return self.origen + timedelta(seconds=segundo_de_video * self.factor)


class RelojReal:
    """Para cuando la fuente sea una camara en vivo."""

    def instante(self, segundo_de_video: float = 0.0) -> datetime:
        return datetime.now()