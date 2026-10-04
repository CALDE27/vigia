"""Recorre el video completo e informa las transiciones de estado.

Uso, desde la raiz del proyecto y con el entorno activado:

    python herramientas\\correr_video.py --fuente datos\\videos\\prueba.mp4
"""

from __future__ import annotations

import argparse
import csv
import sys
import time
from datetime import datetime
from pathlib import Path

import cv2

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))

from vision.asociacion import asignar, cargar_regiones, estado_de_espacios  # noqa: E402
from vision.histeresis import Estabilizador  # noqa: E402
from vision.reloj import RelojSimulado  # noqa: E402

REGIONES = RAIZ / "config" / "regiones.json"
SALIDAS = RAIZ / "datos" / "salidas"


def muestras(captura, paso: int):
    """Genera (indice, imagen) cada `paso` cuadros, sin decodificar los demas.

    grab() avanza sin decodificar y es barato; retrieve() decodifica y es
    lo caro. Llamando grab() siempre y retrieve() solo cuando hace falta,
    el recorrido de un video largo tarda minutos en vez de media hora.
    """
    indice = 0
    while True:
        if not captura.grab():
            return
        if indice % paso == 0:
            ok, imagen = captura.retrieve()
            if not ok:
                return
            yield indice, imagen
        indice += 1


def hora(texto: str) -> datetime:
    """Convierte '07:00' en un datetime de hoy a esa hora."""
    h, m = (int(parte) for parte in texto.split(":"))
    return datetime.now().replace(hour=h, minute=m, second=0, microsecond=0)


def formatear_duracion(segundos: float) -> str:
    minutos = int(segundos // 60)
    if minutos < 60:
        return f"{minutos} min"
    return f"{minutos // 60} h {minutos % 60} min"


def main() -> None:
    analizador = argparse.ArgumentParser(description="Recorre el video y reporta transiciones.")
    analizador.add_argument("--fuente", required=True)
    analizador.add_argument("--intervalo", type=float, default=2.0,
                            help="segundos de video entre muestras")
    analizador.add_argument("--k", type=int, default=3,
                            help="muestras consecutivas para confirmar un cambio")
    analizador.add_argument("--conf", type=float, default=0.35)
    analizador.add_argument("--umbral", type=float, default=0.35)
    analizador.add_argument("--desde", default="07:00")
    analizador.add_argument("--hasta", default="21:00")
    analizador.add_argument("--max-muestras", type=int, default=0,
                            help="0 = sin limite. Util para una prueba rapida.")
    argumentos = analizador.parse_args()

    if not REGIONES.exists():
        raise SystemExit(f"Falta la calibracion: {REGIONES}")

    captura = cv2.VideoCapture(argumentos.fuente)
    if not captura.isOpened():
        raise SystemExit(f"No pude abrir el video: {argumentos.fuente}")
    fps = captura.get(cv2.CAP_PROP_FPS) or 30.0
    total = int(captura.get(cv2.CAP_PROP_FRAME_COUNT))
    ancho = int(captura.get(cv2.CAP_PROP_FRAME_WIDTH))
    alto = int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT))
    duracion = total / fps

    paso = max(1, int(round(fps * argumentos.intervalo)))
    reloj = RelojSimulado.para_abarcar(hora(argumentos.desde),
                                       hora(argumentos.hasta), duracion)
    regiones = cargar_regiones(REGIONES, ancho, alto)

    print(f"Video: {total} cuadros a {fps:.1f} fps  ·  {duracion / 60:.1f} min")
    print(f"Reloj: {argumentos.desde} a {argumentos.hasta}  ·  "
          f"factor {reloj.factor:.1f}x  ·  muestra cada {argumentos.intervalo} s")
    print(f"Regiones: {len(regiones)}\n")

    # Import tardio: ultralytics tarda en cargar y asi el error de
    # configuracion aparece antes que la espera.
    from vision.detector import DetectorVehiculos
    detector = DetectorVehiculos(umbral_confianza=argumentos.conf)

    estabilizador = Estabilizador([r.espacio for r in regiones],
                                  instante_inicial=reloj.instante(0),
                                  k=argumentos.k)

    transiciones = []
    por_hora: dict[int, list[int]] = {}
    contadas = 0
    comienzo = time.perf_counter()

    for indice, imagen in muestras(captura, paso):
        segundo = indice / fps
        instante = reloj.instante(segundo)

        detecciones = detector.detectar(imagen)
        asignaciones = asignar(detecciones, regiones, argumentos.umbral)
        observado = estado_de_espacios(regiones, asignaciones)

        for transicion in estabilizador.observar(observado, instante):
            transiciones.append(transicion)
            print(f"  {transicion.instante:%H:%M}   {transicion.espacio} -> "
                  f"{transicion.etiqueta:<8}  (estuvo "
                  f"{'ocupado' if not transicion.estado else 'libre'} "
                  f"{formatear_duracion(transicion.duracion_anterior_s)})")

        confirmado = estabilizador.estado
        ocupados = sum(1 for v in confirmado.values() if v)
        por_hora.setdefault(instante.hour, []).append(ocupados)

        contadas += 1
        if argumentos.max_muestras and contadas >= argumentos.max_muestras:
            break

    captura.release()
    segundos_reales = time.perf_counter() - comienzo

    print("\nOcupacion por hora")
    for h in sorted(por_hora):
        promedio = sum(por_hora[h]) / len(por_hora[h]) / len(regiones) * 100
        barra = "#" * round(promedio / 7)
        print(f"  {h:02d}   {promedio:3.0f}%  {barra}")

    todas = [o for lista in por_hora.values() for o in lista]
    media = sum(todas) / len(todas) / len(regiones) * 100 if todas else 0
    print(f"\n{contadas} muestras  ·  {len(transiciones)} transiciones  ·  "
          f"ocupacion media {media:.0f}%")
    print(f"Procesado en {segundos_reales:.0f} s  "
          f"({segundos_reales / contadas * 1000:.0f} ms por muestra)")

    SALIDAS.mkdir(parents=True, exist_ok=True)
    destino = SALIDAS / "transiciones.csv"
    with destino.open("w", newline="", encoding="utf-8") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["espacio", "estado", "instante", "duracion_anterior_s"])
        for t in transiciones:
            escritor.writerow([t.espacio, t.etiqueta, t.instante.isoformat(),
                               round(t.duracion_anterior_s)])
    print(f"Transiciones guardadas en: {destino}")


if __name__ == "__main__":
    main()