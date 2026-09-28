"""Herramienta de calibracion de las regiones de interes.

Abre un cuadro del video y permite marcar los lugares de estacionamiento
con cuatro clics cada uno. Guarda el resultado en config/regiones.json
con coordenadas normalizadas entre 0 y 1.

Uso:
    python herramientas\\calibrar.py --fuente datos\\videos\\prueba.mp4 --frame 300
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import cv2
import numpy as np

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

VENTANA = "Calibracion de regiones - Vigia"
DESTINO = RAIZ / "config" / "regiones.json"

VERDE = (120, 200, 120)
AMARILLO = (102, 209, 255)
BLANCO = (245, 245, 245)
NEGRO = (25, 25, 25)


def cargar_cuadro(ruta: Path, numero: int) -> np.ndarray:
    """Devuelve un cuadro puntual del video como array de numpy."""
    captura = cv2.VideoCapture(str(ruta))
    if not captura.isOpened():
        raise SystemExit(f"No pude abrir el video: {ruta}")
    total = int(captura.get(cv2.CAP_PROP_FRAME_COUNT))
    if total and numero >= total:
        print(f"[aviso] El video tiene {total} cuadros; uso el ultimo.")
        numero = total - 1
    captura.set(cv2.CAP_PROP_POS_FRAMES, numero)
    ok, imagen = captura.read()
    captura.release()
    if not ok:
        raise SystemExit(f"No pude leer el cuadro {numero}")
    return imagen


class Calibrador:
    """Mantiene los poligonos marcados y dibuja el estado actual."""

    def __init__(self, imagen: np.ndarray, escala: float) -> None:
        self.imagen = imagen
        self.alto, self.ancho = imagen.shape[:2]
        self.escala = escala
        self.poligonos: list[list[tuple[int, int]]] = []
        self.parcial: list[tuple[int, int]] = []

    def al_hacer_clic(self, evento, x, y, flags, parametros) -> None:
        """Agrega un vertice. Divide por la escala para volver a pixeles reales."""
        if evento != cv2.EVENT_LBUTTONDOWN:
            return
        self.parcial.append((int(x / self.escala), int(y / self.escala)))
        if len(self.parcial) == 4:
            self.poligonos.append(self.parcial)
            self.parcial = []

    def deshacer(self) -> None:
        """Quita un vertice; si no hay ninguno en curso, reabre el ultimo lugar."""
        if self.parcial:
            self.parcial.pop()
        elif self.poligonos:
            self.parcial = self.poligonos.pop()
            self.parcial.pop()

    def borrar_ultimo(self) -> None:
        """Elimina el lugar en curso, o el ultimo terminado."""
        if self.parcial:
            self.parcial = []
        elif self.poligonos:
            self.poligonos.pop()

    def render(self) -> np.ndarray:
        """Dibuja todo sobre una copia y la devuelve ya escalada para mostrar."""
        lienzo = self.imagen.copy()
        for indice, poligono in enumerate(self.poligonos):
            puntos = np.array(poligono, dtype=np.int32)
            capa = lienzo.copy()
            cv2.fillPoly(capa, [puntos], VERDE)
            cv2.addWeighted(capa, 0.25, lienzo, 0.75, 0, lienzo)
            cv2.polylines(lienzo, [puntos], True, VERDE, 2)
            centro = puntos.mean(axis=0).astype(int)
            etiqueta = f"P{indice + 1:02d}"
            for color, grosor in ((NEGRO, 3), (BLANCO, 1)):
                cv2.putText(lienzo, etiqueta, (centro[0] - 18, centro[1] + 6),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, grosor, cv2.LINE_AA)

        if len(self.parcial) > 1:
            cv2.polylines(lienzo, [np.array(self.parcial, np.int32)], False, AMARILLO, 2)
        for punto in self.parcial:
            cv2.circle(lienzo, punto, 6, AMARILLO, -1)
            cv2.circle(lienzo, punto, 6, NEGRO, 1)

        cv2.rectangle(lienzo, (0, 0), (self.ancho, 36), NEGRO, -1)
        texto = (f"lugares: {len(self.poligonos)}  |  vertices: {len(self.parcial)}/4"
                 "   [z] deshacer   [d] borrar   [g] guardar   [q] salir")
        cv2.putText(lienzo, texto, (12, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55,
                    BLANCO, 1, cv2.LINE_AA)

        if self.escala != 1.0:
            lienzo = cv2.resize(lienzo, None, fx=self.escala, fy=self.escala,
                                interpolation=cv2.INTER_AREA)
        return lienzo

    def a_json(self, fuente: str, cuadro: int) -> dict:
        """Convierte los poligonos a coordenadas normalizadas entre 0 y 1."""
        return {
            "fuente": str(fuente).replace("\\", "/"),
            "cuadro_referencia": cuadro,
            "resolucion": [self.ancho, self.alto],
            "regiones": [
                {
                    "espacio": f"P{i + 1:02d}",
                    "poligono": [[round(x / self.ancho, 5), round(y / self.alto, 5)]
                                 for x, y in poligono],
                }
                for i, poligono in enumerate(self.poligonos)
            ],
        }

    def desde_json(self, datos: dict) -> None:
        """Recupera una calibracion anterior y la vuelve a pixeles."""
        for region in datos.get("regiones", []):
            self.poligonos.append([
                (int(round(x * self.ancho)), int(round(y * self.alto)))
                for x, y in region["poligono"]
            ])


def main() -> None:
    analizador = argparse.ArgumentParser(description="Calibra las regiones de interes.")
    analizador.add_argument("--fuente", required=True)
    analizador.add_argument("--frame", type=int, default=0)
    analizador.add_argument("--ancho-ventana", type=int, default=1280)
    argumentos = analizador.parse_args()

    imagen = cargar_cuadro(Path(argumentos.fuente), argumentos.frame)
    escala = min(1.0, argumentos.ancho_ventana / imagen.shape[1])
    calibrador = Calibrador(imagen, escala)

    if DESTINO.exists():
        calibrador.desde_json(json.loads(DESTINO.read_text(encoding="utf-8")))
        print(f"Cargadas {len(calibrador.poligonos)} regiones ya calibradas.")

    print("Marca cada lugar con 4 clics. [z] deshacer  [d] borrar  [g] guardar  [q] salir")
    cv2.namedWindow(VENTANA)
    cv2.setMouseCallback(VENTANA, calibrador.al_hacer_clic)

    while True:
        cv2.imshow(VENTANA, calibrador.render())
        tecla = cv2.waitKey(20) & 0xFF
        if tecla == ord("q"):
            break
        if tecla == ord("z"):
            calibrador.deshacer()
        elif tecla == ord("d"):
            calibrador.borrar_ultimo()
        elif tecla == ord("g"):
            DESTINO.parent.mkdir(parents=True, exist_ok=True)
            DESTINO.write_text(
                json.dumps(calibrador.a_json(argumentos.fuente, argumentos.frame),
                           indent=2, ensure_ascii=False),
                encoding="utf-8")
            print(f"Guardado: {DESTINO}  ({len(calibrador.poligonos)} regiones)")
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()