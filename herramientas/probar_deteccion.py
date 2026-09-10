"""Prueba del tramo 1: corre el detector sobre una imagen o un cuadro de video.

Uso, desde la raíz del proyecto y con el entorno activado:

    python herramientas\\probar_deteccion.py --fuente URL_O_RUTA
    python herramientas\\probar_deteccion.py --fuente datos\\videos\\prueba.mp4 --frame 120
"""
    
from __future__ import annotations

import argparse
import sys
import time
import urllib.request
from pathlib import Path

import cv2
import numpy as np

# Permite ejecutar este script directamente sin instalar el proyecto como
# paquete: agrega la carpeta raíz (la de arriba) al camino de búsqueda de
# Python, para que "from vision.detector import ..." encuentre el módulo.
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from vision.detector import DetectorVehiculos  # noqa: E402

EXTENSIONES_IMAGEN = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def cargar_cuadro(fuente: str, numero_cuadro: int) -> np.ndarray:
    """Devuelve un cuadro como array de numpy, venga de donde venga."""
    if fuente.startswith("http://") or fuente.startswith("https://"):
        with urllib.request.urlopen(fuente) as respuesta:
            crudo = np.frombuffer(respuesta.read(), dtype=np.uint8)
        imagen = cv2.imdecode(crudo, cv2.IMREAD_COLOR)
        if imagen is None:
            raise SystemExit(f"No pude decodificar la imagen de {fuente}")
        return imagen

    ruta = Path(fuente)
    if not ruta.exists():
        raise SystemExit(f"No existe el archivo: {ruta}")

    if ruta.suffix.lower() in EXTENSIONES_IMAGEN:
        imagen = cv2.imread(str(ruta))
        if imagen is None:
            raise SystemExit(f"No pude leer la imagen: {ruta}")
        return imagen

    # Es un video: nos posicionamos en el cuadro pedido y leemos uno solo.
    captura = cv2.VideoCapture(str(ruta))
    if not captura.isOpened():
        raise SystemExit(f"No pude abrir el video: {ruta}")
    total = int(captura.get(cv2.CAP_PROP_FRAME_COUNT))
    if numero_cuadro >= total > 0:
        print(f"[aviso] El video tiene {total} cuadros; uso el último.")
        numero_cuadro = max(0, total - 1)
    captura.set(cv2.CAP_PROP_POS_FRAMES, numero_cuadro)
    ok, imagen = captura.read()
    captura.release()
    if not ok:
        raise SystemExit(f"No pude leer el cuadro {numero_cuadro}")
    return imagen


def anotar(imagen: np.ndarray, detecciones: list) -> np.ndarray:
    """Dibuja las cajas, las etiquetas y el punto de apoyo sobre una copia."""
    salida = imagen.copy()
    # OpenCV usa BGR, no RGB. (177, 190, 51) es un cian.
    cian = (177, 190, 51)
    amarillo = (102, 209, 255)

    for deteccion in detecciones:
        x1, y1, x2, y2 = (int(v) for v in deteccion.caja)
        cv2.rectangle(salida, (x1, y1), (x2, y2), cian, 2)

        etiqueta = f"{deteccion.clase} {deteccion.confianza:.2f}"
        (ancho_texto, alto_texto), _ = cv2.getTextSize(
            etiqueta, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1
        )
        cv2.rectangle(
            salida,
            (x1, max(0, y1 - alto_texto - 8)),
            (x1 + ancho_texto + 8, y1),
            cian,
            -1,  # -1 rellena el rectángulo
        )
        cv2.putText(
            salida,
            etiqueta,
            (x1 + 4, max(11, y1 - 5)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (30, 30, 30),
            1,
            cv2.LINE_AA,
        )

        px, py = (int(v) for v in deteccion.punto_apoyo)
        cv2.circle(salida, (px, py), 5, amarillo, -1)
        cv2.circle(salida, (px, py), 5, (30, 30, 30), 1)

    return salida


def main() -> None:
    analizador = argparse.ArgumentParser(description="Prueba del detector de vehículos.")
    analizador.add_argument("--fuente", required=True, help="URL, imagen o video")
    analizador.add_argument("--frame", type=int, default=0, help="cuadro del video a analizar")
    analizador.add_argument("--modelo", default="yolo11n.pt")
    analizador.add_argument("--conf", type=float, default=0.35)
    analizador.add_argument("--imgsz", type=int, default=640)
    argumentos = analizador.parse_args()

    print(f"Cargando modelo {argumentos.modelo} ...")
    detector = DetectorVehiculos(
        modelo=argumentos.modelo,
        umbral_confianza=argumentos.conf,
        tamano_entrada=argumentos.imgsz,
    )

    imagen = cargar_cuadro(argumentos.fuente, argumentos.frame)
    alto, ancho = imagen.shape[:2]
    print(f"Cuadro cargado: {ancho} x {alto} px")

    inicio = time.perf_counter()
    detecciones = detector.detectar(imagen)
    milisegundos = (time.perf_counter() - inicio) * 1000

    print(f"\nInferencia: {milisegundos:.0f} ms")
    print(f"Vehículos detectados: {len(detecciones)}\n")

    if detecciones:
        print(f"{'#':>2}  {'clase':<12} {'conf.':>6}  {'punto de apoyo':>16}")
        print("-" * 44)
        for indice, deteccion in enumerate(detecciones, start=1):
            px, py = deteccion.punto_apoyo
            print(
                f"{indice:>2}  {deteccion.clase:<12} "
                f"{deteccion.confianza:>6.2f}  ({px:>6.0f}, {py:>6.0f})"
            )

    carpeta_salidas = RAIZ / "datos" / "salidas"
    carpeta_salidas.mkdir(parents=True, exist_ok=True)
    destino = carpeta_salidas / "deteccion.jpg"
    cv2.imwrite(str(destino), anotar(imagen, detecciones))
    print(f"\nImagen anotada guardada en: {destino}")


if __name__ == "__main__":
    main()