"""La persistencia: las tres tablas y el acceso a ellas.

Expone exactamente los mismos metodos que api.falsos.Memoria, asi que
principal.py no necesita saber cual de los dos esta usando. Esa es la
razon por la que el acceso a los datos vivia en un archivo aparte desde
el tramo anterior.

Las fechas se guardan como texto ISO 8601: SQLite no tiene un tipo de
fecha propio, y el texto ISO se ordena alfabeticamente en el mismo orden
en que se ordenan las fechas, asi que los ORDER BY funcionan.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from pathlib import Path

from api import esquemas
from api.errores import ErrorVigia

ESQUEMA = """
CREATE TABLE IF NOT EXISTS lugares (
    espacio  TEXT PRIMARY KEY,
    activo   INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS corridas (
    numero              INTEGER PRIMARY KEY,
    iniciada_en         TEXT NOT NULL,
    ultimo_instante     TEXT,
    ultimo_cuadro       INTEGER,
    ultimo_recibido_en  TEXT
);

CREATE TABLE IF NOT EXISTS estado_actual (
    espacio         TEXT NOT NULL,
    corrida         INTEGER NOT NULL,
    ocupado         INTEGER NOT NULL,
    desde           TEXT NOT NULL,
    confianza       REAL,
    cobertura       REAL,
    actualizado_en  TEXT NOT NULL,
    PRIMARY KEY (espacio, corrida),
    FOREIGN KEY (espacio) REFERENCES lugares (espacio)
);

CREATE TABLE IF NOT EXISTS transiciones (
    id                   INTEGER PRIMARY KEY AUTOINCREMENT,
    corrida              INTEGER NOT NULL,
    espacio              TEXT NOT NULL,
    estado               TEXT NOT NULL,
    instante             TEXT NOT NULL,
    duracion_anterior_s  INTEGER,
    recibido_en          TEXT NOT NULL,
    FOREIGN KEY (espacio) REFERENCES lugares (espacio)
);

CREATE INDEX IF NOT EXISTS idx_transiciones_busqueda
    ON transiciones (corrida, instante DESC);
"""


def _a_texto(momento: datetime) -> str:
    """Una fecha, como la guarda la base: ISO 8601 sin microsegundos."""
    return momento.replace(microsecond=0).isoformat()


def _a_fecha(texto: str | None) -> datetime | None:
    return datetime.fromisoformat(texto) if texto else None


class Almacen:
    """Lee y escribe las tres tablas. Misma interfaz que falsos.Memoria."""

    def __init__(self, espacios: list[str], ruta: str | Path) -> None:
        self.espacios = list(espacios)
        self.ruta = Path(ruta)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False porque uvicorn atiende los pedidos en
        # varios hilos. Es seguro aca: cada operacion es una transaccion
        # corta y SQLite las serializa por su cuenta.
        self.conexion = sqlite3.connect(self.ruta, check_same_thread=False)
        self.conexion.row_factory = sqlite3.Row
        self.conexion.execute("PRAGMA foreign_keys = ON")
        self.conexion.executescript(ESQUEMA)
        self._sembrar_lugares()
        self._asegurar_corrida()

    # --- Arranque -------------------------------------------------------

    def _sembrar_lugares(self) -> None:
        """Deja en la tabla los lugares de la calibracion, sin duplicar."""
        with self.conexion:
            self.conexion.executemany(
                "INSERT OR IGNORE INTO lugares (espacio) VALUES (?)",
                [(espacio,) for espacio in self.espacios],
            )

    def _asegurar_corrida(self) -> None:
        """Si la base es nueva, abre la corrida 1."""
        fila = self.conexion.execute(
            "SELECT MAX(numero) AS numero FROM corridas"
        ).fetchone()
        if fila["numero"] is None:
            with self.conexion:
                self.conexion.execute(
                    "INSERT INTO corridas (numero, iniciada_en) VALUES (1, ?)",
                    (_a_texto(datetime.now()),),
                )

    # --- Lo que principal.py lee directamente ---------------------------

    @property
    def corrida(self) -> int:
        return self.conexion.execute(
            "SELECT MAX(numero) AS numero FROM corridas"
        ).fetchone()["numero"]

    def _corrida_abierta(self) -> sqlite3.Row:
        return self.conexion.execute(
            "SELECT * FROM corridas ORDER BY numero DESC LIMIT 1"
        ).fetchone()

    @property
    def publicado(self) -> bool:
        """True si esta corrida ya recibio al menos una publicacion."""
        return self._corrida_abierta()["ultimo_instante"] is not None

    @property
    def instante(self) -> datetime | None:
        return _a_fecha(self._corrida_abierta()["ultimo_instante"])

    # --- Lectura --------------------------------------------------------

    def estado_actual(self) -> esquemas.RespuestaEstado:
        abierta = self._corrida_abierta()
        if abierta["ultimo_instante"] is None:
            raise ErrorVigia(
                503,
                "sin_datos",
                "El backend todavia no recibio ningun estado en esta corrida.",
            )

        corrida = abierta["numero"]
        instante = _a_fecha(abierta["ultimo_instante"])
        hace = round(
            (datetime.now() - _a_fecha(abierta["ultimo_recibido_en"])).total_seconds(), 1
        )

        filas = {
            fila["espacio"]: fila
            for fila in self.conexion.execute(
                "SELECT * FROM estado_actual WHERE corrida = ?", (corrida,)
            )
        }

        lugares = []
        for espacio in self.espacios:
            fila = filas.get(espacio)
            if fila is None:
                lugares.append(esquemas.LugarEstado(espacio=espacio, ocupado=False))
                continue
            desde = _a_fecha(fila["desde"])
            lugares.append(esquemas.LugarEstado(
                espacio=espacio,
                ocupado=bool(fila["ocupado"]),
                desde=desde,
                duracion_s=int((instante - desde).total_seconds()),
                confianza=fila["confianza"],
            ))

        ocupados = sum(1 for lugar in lugares if lugar.ocupado)
        return esquemas.RespuestaEstado(
            instante=instante,
            cuadro=abierta["ultimo_cuadro"] or 0,
            corrida=corrida,
            actualizado_hace_s=max(hace, 0.0),
            resumen=esquemas.Resumen(
                total=len(lugares),
                libres=len(lugares) - ocupados,
                ocupados=ocupados,
            ),
            lugares=lugares,
        )

    def listar_transiciones(self, espacio=None, desde=None, hasta=None,
                            corrida=None, limite=100, desplazamiento=0):
        condiciones = ["corrida = ?"]
        valores: list = [corrida if corrida is not None else self.corrida]
        if espacio:
            condiciones.append("espacio = ?")
            valores.append(espacio)
        if desde:
            condiciones.append("instante >= ?")
            valores.append(_a_texto(desde))
        if hasta:
            condiciones.append("instante < ?")
            valores.append(_a_texto(hasta))
        donde = " AND ".join(condiciones)

        total = self.conexion.execute(
            f"SELECT COUNT(*) AS cuantas FROM transiciones WHERE {donde}", valores
        ).fetchone()["cuantas"]

        filas = self.conexion.execute(
            f"SELECT * FROM transiciones WHERE {donde} "
            "ORDER BY instante DESC, id DESC LIMIT ? OFFSET ?",
            valores + [limite, desplazamiento],
        ).fetchall()

        return esquemas.RespuestaTransiciones(
            total=total,
            limite=limite,
            desplazamiento=desplazamiento,
            transiciones=[
                esquemas.Transicion(
                    id=fila["id"],
                    espacio=fila["espacio"],
                    estado=fila["estado"],
                    instante=_a_fecha(fila["instante"]),
                    duracion_anterior_s=fila["duracion_anterior_s"],
                )
                for fila in filas
            ],
        )

    # --- Escritura ------------------------------------------------------

    def publicar(self, cuerpo: esquemas.EstadoPublicado) -> list[dict]:
        corrida = self.corrida
        recibido_en = _a_texto(datetime.now())
        instante = _a_texto(cuerpo.instante)
        nuevas: list[dict] = []

        with self.conexion:
            for lugar in cuerpo.lugares:
                previo = self.conexion.execute(
                    "SELECT ocupado, desde FROM estado_actual "
                    "WHERE espacio = ? AND corrida = ?",
                    (lugar.espacio, corrida),
                ).fetchone()

                if previo is None:
                    # Primera publicacion de la corrida: punto de partida,
                    # no un cambio. No se anota transicion.
                    self.conexion.execute(
                        "INSERT INTO estado_actual (espacio, corrida, ocupado, "
                        "desde, confianza, cobertura, actualizado_en) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (lugar.espacio, corrida, int(lugar.ocupado), instante,
                         lugar.confianza, lugar.cobertura, recibido_en),
                    )
                    continue

                if bool(previo["ocupado"]) == lugar.ocupado:
                    self.conexion.execute(
                        "UPDATE estado_actual SET confianza = ?, cobertura = ?, "
                        "actualizado_en = ? WHERE espacio = ? AND corrida = ?",
                        (lugar.confianza, lugar.cobertura, recibido_en,
                         lugar.espacio, corrida),
                    )
                    continue

                duracion = int(
                    (cuerpo.instante - _a_fecha(previo["desde"])).total_seconds()
                )
                cursor = self.conexion.execute(
                    "INSERT INTO transiciones (corrida, espacio, estado, instante, "
                    "duracion_anterior_s, recibido_en) VALUES (?, ?, ?, ?, ?, ?)",
                    (corrida, lugar.espacio,
                     "ocupado" if lugar.ocupado else "libre",
                     instante, duracion, recibido_en),
                )
                self.conexion.execute(
                    "UPDATE estado_actual SET ocupado = ?, desde = ?, confianza = ?, "
                    "cobertura = ?, actualizado_en = ? WHERE espacio = ? AND corrida = ?",
                    (int(lugar.ocupado), instante, lugar.confianza,
                     lugar.cobertura, recibido_en, lugar.espacio, corrida),
                )
                nuevas.append({
                    "id": cursor.lastrowid,
                    "espacio": lugar.espacio,
                    "estado": "ocupado" if lugar.ocupado else "libre",
                    "instante": cuerpo.instante,
                    "duracion_anterior_s": duracion,
                })

            self.conexion.execute(
                "UPDATE corridas SET ultimo_instante = ?, ultimo_cuadro = ?, "
                "ultimo_recibido_en = ? WHERE numero = ?",
                (instante, cuerpo.cuadro, recibido_en, corrida),
            )

        return nuevas

    def reiniciar(self) -> int:
        """Abre una corrida nueva. No borra nada de las anteriores."""
        nueva = self.corrida + 1
        with self.conexion:
            self.conexion.execute(
                "INSERT INTO corridas (numero, iniciada_en) VALUES (?, ?)",
                (nueva, _a_texto(datetime.now())),
            )
        return nueva