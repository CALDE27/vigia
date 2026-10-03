"""Junta todo: detecta vehiculos en un cuadro y dice que lugares estan ocupados.

Uso, desde la raiz del proyecto y con el entorno activado:

    python herramientas\\ver_ocupacion.py
    python herramientas\\ver_ocupacion.py --fuente datos\\videos\\prueba.mp4 --frame 300
    python herramientas\\ver_ocupacion.py --umbral 0.5 --sin-cajas

Si no se pasan --fuente o --frame, se usan los de config/regiones.json.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import cv2
import numpy as np

# Permite importar "vision" aunque este script viva dentro de herramientas/:
# agrega la carpeta raiz del proyecto al camino de busqueda de Python.
RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from vision.asociacion import (  # noqa: E402
    UMBRAL_COBERTURA,
    Asignacion,
    Region,
    asignar,
    cargar_regiones,
    estado_de_espacios,
)
from vision.detector import Deteccion, DetectorVehiculos  # noqa: E402

REGIONES_JSON = RAIZ / "config" / "regiones.json"

# OpenCV usa BGR, no RGB: el ultimo numero es el rojo.
ROJO = (70, 70, 200)
VERDE = (120, 200, 120)
CIAN = (177, 190, 51)
AMARILLO = (102, 209, 255)
BLANCO = (245, 245, 245)
NEGRO = (25, 25, 25)


def cargar_cuadro(ruta: Path, numero: int) -> np.ndarray:
    """Devuelve un cuadro puntual del video como array de numpy."""
    if not ruta.exists():
        raise SystemExit(f"No existe el archivo: {ruta}")
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


def _texto_con_borde(imagen: np.ndarray, texto: str, origen: tuple[int, int], escala: float) -> None:
    """Escribe el texto dos veces, negro grueso y blanco fino, para que se lea sobre cualquier fondo."""
    cv2.putText(imagen, texto, origen, cv2.FONT_HERSHEY_SIMPLEX, escala, NEGRO, 4, cv2.LINE_AA)
    cv2.putText(imagen, texto, origen, cv2.FONT_HERSHEY_SIMPLEX, escala, BLANCO, 1, cv2.LINE_AA)


def anotar(
    imagen: np.ndarray,
    regiones: list[Region],
    estado: dict[str, bool],
    detecciones: list[Deteccion],
    dibujar_cajas: bool = True,
) -> np.ndarray:
    """Dibuja regiones, nombres, cajas y la barra de totales sobre una copia."""
    salida = imagen.copy()

    # 1. Regiones rojas (ocupadas) o verdes (libres), semitransparentes:
    #    se pintan sobre una copia y se mezclan 30/70 con el original.
    capa = salida.copy()
    for region in regiones:
        puntos = np.array(region.poligono, dtype=np.int32)
        color = ROJO if estado[region.espacio] else VERDE
        cv2.fillPoly(capa, [puntos], color)
    salida = cv2.addWeighted(capa, 0.3, salida, 0.7, 0)
    for region in regiones:
        puntos = np.array(region.poligono, dtype=np.int32)
        color = ROJO if estado[region.espacio] else VERDE
        cv2.polylines(salida, [puntos], True, color, 2, cv2.LINE_AA)

    # 2. Nombre de cada lugar en el centro del poligono.
    for region in regiones:
        cx = sum(x for x, _ in region.poligono) / len(region.poligono)
        cy = sum(y for _, y in region.poligono) / len(region.poligono)
        (ancho_texto, alto_texto), _ = cv2.getTextSize(
            region.espacio, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2
        )
        origen = (int(cx - ancho_texto / 2), int(cy + alto_texto / 2))
        _texto_con_borde(salida, region.espacio, origen, 0.7)

    # 3. Cajas de YOLO en cian y punto de apoyo en amarillo.
    if dibujar_cajas:
        for deteccion in detecciones:
            x1, y1, x2, y2 = (int(v) for v in deteccion.caja)
            cv2.rectangle(salida, (x1, y1), (x2, y2), CIAN, 2)
            px, py = (int(v) for v in deteccion.punto_apoyo)
            cv2.circle(salida, (px, py), 5, AMARILLO, -1)
            cv2.circle(salida, (px, py), 5, NEGRO, 1)

    # 4. Barra negra arriba con los totales.
    ocupados = sum(estado.values())
    libres = len(estado) - ocupados
    cv2.rectangle(salida, (0, 0), (salida.shape[1], 40), NEGRO, -1)
    resumen = f"Ocupados: {ocupados}   Libres: {libres}   Total: {len(estado)}"
    cv2.putText(salida, resumen, (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.8, BLANCO, 2, cv2.LINE_AA)

    return salida


def imprimir_tabla(
    regiones: list[Region], estado: dict[str, bool], asignaciones: dict[str, Asignacion]
) -> None:
    print(f"\n{'lugar':<6} {'estado':<8} {'clase':<11} {'conf.':>5} {'cob.':>5}  criterio")
    print("-" * 52)
    for region in regiones:
        asignacion = asignaciones.get(region.espacio)
        if asignacion is None:
            print(f"{region.espacio:<6} {'libre':<8}")
            continue
        criterio = "apoyo" if asignacion.por_apoyo else "cobertura"
        print(
            f"{region.espacio:<6} {'ocupado':<8} {asignacion.deteccion.clase:<11} "
            f"{asignacion.deteccion.confianza:>5.2f} {asignacion.cobertura:>5.2f}  {criterio}"
        )
    ocupados = sum(estado.values())
    print(f"\nOcupados: {ocupados} de {len(estado)}")


def main() -> None:
    analizador = argparse.ArgumentParser(description="Ocupacion de lugares en un cuadro.")
    analizador.add_argument("--fuente", help="video a analizar (por defecto, el de regiones.json)")
    analizador.add_argument("--frame", type=int, help="cuadro (por defecto, el de regiones.json)")
    analizador.add_argument("--conf", type=float, default=0.35, help="confianza minima de YOLO")
    analizador.add_argument(
        "--umbral", type=float, default=UMBRAL_COBERTURA, help="cobertura minima del respaldo"
    )
    analizador.add_argument("--sin-cajas", action="store_true", help="no dibujar las cajas de YOLO")
    argumentos = analizador.parse_args()

    if not REGIONES_JSON.exists():
        raise SystemExit(
            f"No existe {REGIONES_JSON}. Corre primero herramientas\\calibrar.py"
        )
    configuracion = json.loads(REGIONES_JSON.read_text(encoding="utf-8"))
    fuente = argumentos.fuente or configuracion.get("fuente")
    if not fuente:
        raise SystemExit("Falta --fuente y regiones.json no indica ninguna.")
    numero = argumentos.frame
    if numero is None:
        numero = int(configuracion.get("cuadro_referencia", 0))

    ruta = Path(fuente)
    if not ruta.is_absolute():
        ruta = RAIZ / ruta
    imagen = cargar_cuadro(ruta, numero)
    alto, ancho = imagen.shape[:2]
    print(f"Cuadro {numero} de {ruta.name}: {ancho} x {alto} px")

    # Las regiones estan guardadas entre 0 y 1: se pasan a pixeles con el
    # tamano real de esta imagen.
    regiones = cargar_regiones(REGIONES_JSON, ancho, alto)
    print(f"Regiones cargadas: {len(regiones)}")

    print("Cargando modelo ...")
    detector = DetectorVehiculos(umbral_confianza=argumentos.conf)

    inicio = time.perf_counter()
    detecciones = detector.detectar(imagen)
    ms_deteccion = (time.perf_counter() - inicio) * 1000

    inicio = time.perf_counter()
    asignaciones = asignar(detecciones, regiones, umbral=argumentos.umbral)
    estado = estado_de_espacios(regiones, asignaciones)
    ms_asignacion = (time.perf_counter() - inicio) * 1000

    print(f"\nVehiculos detectados: {len(detecciones)}")
    print(f"Deteccion: {ms_deteccion:.0f} ms   Asignacion: {ms_asignacion:.2f} ms")
    imprimir_tabla(regiones, estado, asignaciones)

    carpeta_salidas = RAIZ / "datos" / "salidas"
    carpeta_salidas.mkdir(parents=True, exist_ok=True)
    destino = carpeta_salidas / "ocupacion.jpg"
    cv2.imwrite(
        str(destino),
        anotar(imagen, regiones, estado, detecciones, dibujar_cajas=not argumentos.sin_cajas),
    )
    print(f"\nImagen anotada guardada en: {destino}")


if __name__ == "__main__":
    main()
