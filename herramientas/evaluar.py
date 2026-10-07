"""Puntua el sistema contra la verdad de campo, sin contar a mano.

Lee datos/verdad_de_campo.json, que dice para cada cuadro que lugares
estan realmente ocupados, corre el sistema sobre esos mismos cuadros y
compara. Imprime la planilla y la matriz de confusion.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Permite correr esto como "python herramientas\evaluar.py".
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2

from vision.asociacion import asignar, cargar_regiones
from vision.detector import DetectorVehiculos


def leer_cuadro(captura, numero: int):
    """Posiciona la captura en un cuadro y lo devuelve, o None si falla."""
    captura.set(cv2.CAP_PROP_POS_FRAMES, numero)
    ok, cuadro = captura.read()
    return cuadro if ok else None


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fuente", required=True)
    parser.add_argument("--verdad", default="datos/verdad_de_campo.json")
    parser.add_argument("--regiones", default="config/regiones.json")
    args = parser.parse_args()

    verdad = json.loads(Path(args.verdad).read_text(encoding="utf-8"))
    cuadros = {int(k): set(v) for k, v in verdad["cuadros"].items()}

    captura = cv2.VideoCapture(args.fuente)
    if not captura.isOpened():
        raise SystemExit(f"No se pudo abrir el video: {args.fuente}")
    ancho = int(captura.get(cv2.CAP_PROP_FRAME_WIDTH))
    alto = int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT))
    regiones = cargar_regiones(Path(args.regiones), ancho, alto)
    espacios = [r.espacio for r in regiones]
    detector = DetectorVehiculos()

    print(f"\n{'Cuadro':<9}{'Reales':>7}{'Sistema':>9}{'VP':>5}{'FP':>5}"
          f"{'FN':>5}{'VN':>5}{'Aciertos':>11}   Errores")
    print("-" * 82)

    totales = {"VP": 0, "FP": 0, "FN": 0, "VN": 0}
    aciertos_total = 0
    observaciones = 0

    for numero in sorted(cuadros):
        imagen = leer_cuadro(captura, numero)
        if imagen is None:
            print(f"{numero:<9}  no se pudo leer este cuadro")
            continue

        reales = cuadros[numero]
        marcados = set(asignar(detector.detectar(imagen), regiones))

        vp = len(reales & marcados)
        fp = len(marcados - reales)
        fn = len(reales - marcados)
        vn = len(espacios) - vp - fp - fn

        totales["VP"] += vp; totales["FP"] += fp
        totales["FN"] += fn; totales["VN"] += vn
        aciertos_total += vp + vn
        observaciones += len(espacios)

        errores = []
        if fn: errores.append("libre y no lo esta: " + ", ".join(sorted(reales - marcados)))
        if fp: errores.append("ocupado y no lo esta: " + ", ".join(sorted(marcados - reales)))

        print(f"{numero:<9}{len(reales):>7}{len(marcados):>9}{vp:>5}{fp:>5}"
              f"{fn:>5}{vn:>5}{f'{vp + vn}/{len(espacios)}':>11}   "
              f"{' | '.join(errores) if errores else '-'}")

    captura.release()

    print("-" * 82)
    print(f"{'TOTAL':<9}{'':>7}{'':>9}{totales['VP']:>5}{totales['FP']:>5}"
          f"{totales['FN']:>5}{totales['VN']:>5}"
          f"{f'{aciertos_total}/{observaciones}':>11}")

    vp, fp, fn = totales["VP"], totales["FP"], totales["FN"]
    exactitud = aciertos_total / observaciones if observaciones else 0.0
    precision = vp / (vp + fp) if vp + fp else 0.0
    exhaustividad = vp / (vp + fn) if vp + fn else 0.0

    print(f"\nExactitud      {exactitud:.1%}   (aciertos sobre el total de observaciones)")
    print(f"Precision      {precision:.1%}   (de lo que marco ocupado, cuanto lo estaba)")
    print(f"Exhaustividad  {exhaustividad:.1%}   (de lo realmente ocupado, cuanto encontro)\n")


if __name__ == "__main__":
    main()