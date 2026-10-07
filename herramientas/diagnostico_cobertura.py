"""Mide, para un cuadro, la cobertura de cada deteccion contra cada region.

No modifica nada ni escribe archivos: solo imprime. Sirve para responder
una pregunta concreta: por que un auto que esta en la foto no termina
marcando su lugar como ocupado.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Permite correr esto como "python herramientas\diagnostico_cobertura.py".
# Al hacerlo, Python pone la carpeta herramientas/ al frente de sys.path, no
# la raiz del proyecto, asi que el paquete vision/ no se ve. Esta linea agrega
# la raiz (la carpeta padre de este archivo) para que el import funcione.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import cv2

from vision.asociacion import UMBRAL_COBERTURA, asignar, cargar_regiones
from vision.detector import DetectorVehiculos
from vision.geometria import cobertura, punto_en_poligono


def leer_cuadro(ruta: str, numero: int):
    """Devuelve un cuadro concreto del video, o corta con un mensaje claro."""
    captura = cv2.VideoCapture(str(ruta))
    if not captura.isOpened():
        raise SystemExit(f"No se pudo abrir el video: {ruta}")
    captura.set(cv2.CAP_PROP_POS_FRAMES, numero)
    ok, cuadro = captura.read()
    captura.release()
    if not ok:
        raise SystemExit(f"No se pudo leer el cuadro {numero}")
    return cuadro


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fuente", required=True)
    parser.add_argument("--frame", type=int, required=True)
    parser.add_argument("--regiones", default="config/regiones.json")
    parser.add_argument("--umbral", type=float, default=UMBRAL_COBERTURA)
    args = parser.parse_args()

    cuadro = leer_cuadro(args.fuente, args.frame)
    alto, ancho = cuadro.shape[:2]
    regiones = cargar_regiones(Path(args.regiones), ancho, alto)
    detecciones = DetectorVehiculos().detectar(cuadro)

    print(f"\nCuadro {args.frame} | {ancho}x{alto} | "
          f"{len(regiones)} regiones | umbral {args.umbral:.2f}")
    print(f"Detecciones: {len(detecciones)}\n")

    # --- 1. Matriz de cobertura: filas = detecciones, columnas = regiones ---
    matriz = [
        [cobertura(d.caja, r.poligono) for r in regiones] for d in detecciones
    ]

    print("MATRIZ DE COBERTURA")
    encabezado = "  #  " + "".join(f"{r.espacio:>8}" for r in regiones) + "   apoyo en"
    print(encabezado)
    print("  " + "-" * (len(encabezado) - 2))
    for i, deteccion in enumerate(detecciones):
        fila = "".join(f"{c:>8.2f}" for c in matriz[i])
        dentro = [r.espacio for r in regiones
                  if punto_en_poligono(deteccion.punto_apoyo, r.poligono)]
        print(f" {i:>2}  {fila}   {', '.join(dentro) if dentro else '-'}")

    # --- 2. Que paso con cada deteccion ---
    asignaciones = asignar(detecciones, regiones, umbral=args.umbral)
    ganadoras = {a.indice_deteccion: a for a in asignaciones.values()}

    print("\nDESTINO DE CADA DETECCION")
    for i, deteccion in enumerate(detecciones):
        clase = getattr(deteccion, "clase", "-")
        conf = getattr(deteccion, "confianza", 0.0)
        etiqueta = f" {i:>2}  {clase:<10} conf {conf:.2f}  ->  "

        if i in ganadoras:
            a = ganadoras[i]
            print(f"{etiqueta}{a.espacio}  (cobertura {a.cobertura:.2f}, "
                  f"criterio {a.criterio})")
            continue

        pares = sorted(zip(regiones, matriz[i]), key=lambda p: p[1], reverse=True)
        mejor, cob = pares[0]
        if cob < args.umbral:
            print(f"{etiqueta}DESCARTADA: ninguna region llega al umbral "
                  f"(la mejor es {mejor.espacio} con {cob:.2f})")
        else:
            rival = asignaciones.get(mejor.espacio)
            if rival is not None:
                print(f"{etiqueta}DESCARTADA: perdio {mejor.espacio} "
                      f"(su {cob:.2f} contra el {rival.cobertura:.2f} "
                      f"de la deteccion #{rival.indice_deteccion})")
            else:
                print(f"{etiqueta}DESCARTADA: motivo no previsto "
                      f"(mejor {mejor.espacio} con {cob:.2f})")

    # --- 3. Que paso con cada region ---
    print("\nREGIONES")
    for j, region in enumerate(regiones):
        a = asignaciones.get(region.espacio)
        if a is not None:
            print(f"  {region.espacio:<6} OCUPADO  por #{a.indice_deteccion} "
                  f"cob {a.cobertura:.2f}  criterio {a.criterio}")
            continue
        recibidas = [(i, matriz[i][j]) for i in range(len(detecciones))]
        i_mejor, cob_mejor = max(recibidas, key=lambda par: par[1]) if recibidas else (None, 0.0)
        if cob_mejor <= 0.0:
            print(f"  {region.espacio:<6} LIBRE    ninguna deteccion la toca")
        else:
            print(f"  {region.espacio:<6} LIBRE    mejor cobertura recibida: "
                  f"{cob_mejor:.2f} (deteccion #{i_mejor}) -- falta "
                  f"{args.umbral - cob_mejor:.2f} para el umbral")
    print()


if __name__ == "__main__":
    main()