"""Datos inventados, para que el tablero tenga algo que dibujar.

Mientras nadie publique un estado real, el backend reproduce un guion
fijo: una jornada de 07:00 a 21:00 comprimida en dos minutos, con
entradas y salidas en momentos prefijados. Apenas llega la primera
publicacion del servicio de vision, el guion se apaga y el backend
pasa a responder lo que le publicaron.

Nada de esto sobrevive a un reinicio del servidor: es memoria y se
pierde. La persistencia es el tramo siguiente.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from time import monotonic

from api import esquemas
from api.configuracion import CICLO_S

HORA_INICIO = time(7, 0)
SEGUNDOS_JORNADA = 14 * 3600          # de 07:00 a 21:00
FACTOR = SEGUNDOS_JORNADA / CICLO_S   # cuantos segundos simulados por segundo real
CUADROS_POR_SEGUNDO = 30

# Que lugares arrancan ocupados, por posicion en la lista de la calibracion.
OCUPADOS_AL_INICIO = (0, 2, 3, 6)

# El guion: (segundo del ciclo, posicion del lugar, queda ocupado).
PAUTA = (
    (12, 1, True),
    (24, 4, True),
    (36, 2, False),
    (48, 5, True),
    (60, 0, False),
    (72, 2, True),
    (84, 1, False),
    (96, 4, False),
    (108, 6, False),
)


def _instante(dia: date, segundo_del_ciclo: float) -> datetime:
    """Convierte un segundo del ciclo en la hora simulada que representa."""
    base = datetime.combine(dia, HORA_INICIO)
    return base + timedelta(seconds=int(segundo_del_ciclo * FACTOR))


class Memoria:
    """El estado del backend mientras no haya base de datos."""

    def __init__(self, espacios: list[str]) -> None:
        self.espacios = list(espacios)
        self.dia = date.today()
        self.corrida = 1
        self.arranque = monotonic()
        self.publicado = False
        self.ultima_publicacion: float | None = None
        self.estado: dict[str, dict] = {}
        self.transiciones: list[dict] = []
        self.cuadro = 0
        self.instante = _instante(self.dia, 0)

    # --- El guion -------------------------------------------------------

    def _guion(self) -> list[tuple[int, str, bool]]:
        return [
            (segundo, self.espacios[posicion], ocupado)
            for segundo, posicion, ocupado in PAUTA
            if posicion < len(self.espacios)
        ]

    def _simular(self) -> None:
        """Recalcula el estado desde cero segun el momento del ciclo."""
        transcurrido = (monotonic() - self.arranque) % CICLO_S

        ocupados = {
            self.espacios[posicion]
            for posicion in OCUPADOS_AL_INICIO
            if posicion < len(self.espacios)
        }
        cambio_en = {espacio: 0 for espacio in self.espacios}
        historia: list[dict] = []

        for segundo, espacio, ocupado in self._guion():
            if segundo > transcurrido:
                break
            if (espacio in ocupados) == ocupado:
                continue          # no cambia nada, no es una transicion
            anterior = cambio_en[espacio]
            historia.append({
                "id": len(historia) + 1,
                "espacio": espacio,
                "estado": "ocupado" if ocupado else "libre",
                "instante": _instante(self.dia, segundo),
                "duracion_anterior_s": int((segundo - anterior) * FACTOR) or None,
            })
            ocupados = ocupados | {espacio} if ocupado else ocupados - {espacio}
            cambio_en[espacio] = segundo

        self.instante = _instante(self.dia, transcurrido)
        self.cuadro = int(transcurrido * CUADROS_POR_SEGUNDO)
        self.transiciones = historia
        self.estado = {
            espacio: {
                "ocupado": espacio in ocupados,
                "desde": _instante(self.dia, cambio_en[espacio]),
                "confianza": 0.88 if espacio in ocupados else None,
                "cobertura": 0.85 if espacio in ocupados else None,
            }
            for espacio in self.espacios
        }

    # --- Lo que leen los endpoints --------------------------------------

    def estado_actual(self) -> esquemas.RespuestaEstado:
        if not self.publicado:
            self._simular()
            hace = 0.0
        else:
            hace = round(monotonic() - (self.ultima_publicacion or 0.0), 1)

        lugares = []
        for espacio in self.espacios:
            fila = self.estado.get(espacio, {})
            desde = fila.get("desde")
            lugares.append(esquemas.LugarEstado(
                espacio=espacio,
                ocupado=bool(fila.get("ocupado", False)),
                desde=desde,
                duracion_s=int((self.instante - desde).total_seconds()) if desde else None,
                confianza=fila.get("confianza"),
            ))

        ocupados = sum(1 for lugar in lugares if lugar.ocupado)
        return esquemas.RespuestaEstado(
            instante=self.instante,
            cuadro=self.cuadro,
            corrida=self.corrida,
            actualizado_hace_s=hace,
            resumen=esquemas.Resumen(
                total=len(lugares),
                libres=len(lugares) - ocupados,
                ocupados=ocupados,
            ),
            lugares=lugares,
        )

    def listar_transiciones(self, espacio=None, desde=None, hasta=None,
                            limite=100, desplazamiento=0):
        if not self.publicado:
            self._simular()
        filas = list(self.transiciones)
        if espacio:
            filas = [f for f in filas if f["espacio"] == espacio]
        if desde:
            filas = [f for f in filas if f["instante"] >= desde]
        if hasta:
            filas = [f for f in filas if f["instante"] < hasta]
        filas.sort(key=lambda f: (f["instante"], f["id"]), reverse=True)
        recorte = filas[desplazamiento:desplazamiento + limite]
        return esquemas.RespuestaTransiciones(
            total=len(filas),
            limite=limite,
            desplazamiento=desplazamiento,
            transiciones=[esquemas.Transicion(**f) for f in recorte],
        )

    # --- Lo que escriben los endpoints ----------------------------------

    def publicar(self, cuerpo: esquemas.EstadoPublicado) -> list[dict]:
        """Aplica una publicacion real y devuelve las transiciones anotadas."""
        if not self.publicado:
            self.transiciones = []     # se descarta lo que invento el guion
            self.estado = {}

        nuevas = []
        for lugar in cuerpo.lugares:
            previo = self.estado.get(lugar.espacio)

            if previo is None:
                # Primera publicacion de la corrida: esto es el punto de
                # partida, no un cambio. Se guarda el estado y no se anota
                # ninguna transicion.
                self.estado[lugar.espacio] = {
                    "ocupado": lugar.ocupado,
                    "desde": cuerpo.instante,
                    "confianza": lugar.confianza,
                    "cobertura": lugar.cobertura,
                }
                continue

            if previo["ocupado"] == lugar.ocupado:
                previo["confianza"] = lugar.confianza
                previo["cobertura"] = lugar.cobertura
                continue

            fila = {
                "id": len(self.transiciones) + len(nuevas) + 1,
                "espacio": lugar.espacio,
                "estado": "ocupado" if lugar.ocupado else "libre",
                "instante": cuerpo.instante,
                "duracion_anterior_s": int(
                    (cuerpo.instante - previo["desde"]).total_seconds()
                ),
            }
            nuevas.append(fila)
            self.estado[lugar.espacio] = {
                "ocupado": lugar.ocupado,
                "desde": cuerpo.instante,
                "confianza": lugar.confianza,
                "cobertura": lugar.cobertura,
            }

        self.transiciones.extend(nuevas)

        self.publicado = True
        self.ultima_publicacion = monotonic()
        self.instante = cuerpo.instante
        self.cuadro = cuerpo.cuadro
        return nuevas

    def reiniciar(self) -> int:
        self.corrida += 1
        self.publicado = False
        self.ultima_publicacion = None
        self.estado = {}
        self.transiciones = []
        self.arranque = monotonic()
        self.dia = date.today()
        return self.corrida