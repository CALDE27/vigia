"""Geometria de poligonos. Sin dependencias de OpenCV ni del modelo.

Todo lo de este archivo es matematica pura: recibe numeros y devuelve
numeros. Esa es la razon por la que se puede probar sin levantar nada.
"""

from __future__ import annotations

Punto = tuple[float, float]
Poligono = list[Punto]
Caja = tuple[float, float, float, float]


def area_poligono(poligono: Poligono) -> float:
    """Area por la formula del cordon del zapatero."""
    if len(poligono) < 3:
        return 0.0
    total = 0.0
    for i in range(len(poligono)):
        x1, y1 = poligono[i]
        x2, y2 = poligono[(i + 1) % len(poligono)]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def punto_en_poligono(punto: Punto, poligono: Poligono) -> bool:
    """True si el punto cae adentro (algoritmo del rayo)."""
    x, y = punto
    dentro = False
    n = len(poligono)
    for i in range(n):
        x1, y1 = poligono[i]
        x2, y2 = poligono[(i - 1) % n]
        # ¿el lado cruza la altura del punto?
        if (y1 > y) != (y2 > y):
            corte_x = (x2 - x1) * (y - y1) / (y2 - y1) + x1
            if x < corte_x:
                dentro = not dentro
    return dentro


def _recortar(poligono: Poligono, dentro, cruce) -> Poligono:
    """Un paso de Sutherland-Hodgman: corta el poligono por una recta."""
    salida: Poligono = []
    n = len(poligono)
    for i in range(n):
        actual = poligono[i]
        previo = poligono[i - 1]
        if dentro(actual):
            if not dentro(previo):
                salida.append(cruce(previo, actual))
            salida.append(actual)
        elif dentro(previo):
            salida.append(cruce(previo, actual))
    return salida


def interseccion_area(caja: Caja, poligono: Poligono) -> float:
    """Area de la parte del poligono que cae dentro de la caja."""
    x1, y1, x2, y2 = caja
    recortado = list(poligono)

    def cruce_vertical(cx):
        def f(p, a):
            t = (cx - p[0]) / (a[0] - p[0])
            return (cx, p[1] + t * (a[1] - p[1]))
        return f

    def cruce_horizontal(cy):
        def f(p, a):
            t = (cy - p[1]) / (a[1] - p[1])
            return (p[0] + t * (a[0] - p[0]), cy)
        return f

    recortado = _recortar(recortado, lambda p: p[0] >= x1, cruce_vertical(x1))
    if not recortado:
        return 0.0
    recortado = _recortar(recortado, lambda p: p[0] <= x2, cruce_vertical(x2))
    if not recortado:
        return 0.0
    recortado = _recortar(recortado, lambda p: p[1] >= y1, cruce_horizontal(y1))
    if not recortado:
        return 0.0
    recortado = _recortar(recortado, lambda p: p[1] <= y2, cruce_horizontal(y2))
    return area_poligono(recortado)


def cobertura(caja: Caja, poligono: Poligono) -> float:
    """Que fraccion del poligono cubre la caja. Entre 0 y 1."""
    area = area_poligono(poligono)
    if area <= 0:
        return 0.0
    return interseccion_area(caja, poligono) / area