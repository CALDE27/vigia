"""Pruebas de la geometria. Todos los valores esperados se calculan a mano."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vision.geometria import area_poligono, cobertura, punto_en_poligono

CUADRADO = [(0, 0), (10, 0), (10, 10), (0, 10)]
TRAPECIO = [(2, 0), (8, 0), (10, 10), (0, 10)]


def test_area_cuadrado():
    assert area_poligono(CUADRADO) == 100.0


def test_area_trapecio():
    # (base mayor + base menor) / 2 * altura = (10 + 6) / 2 * 10 = 80
    assert area_poligono(TRAPECIO) == 80.0


def test_area_no_depende_del_sentido():
    assert area_poligono(CUADRADO[::-1]) == area_poligono(CUADRADO)


def test_area_degenerada():
    assert area_poligono([(0, 0), (1, 1)]) == 0.0


def test_punto_adentro():
    assert punto_en_poligono((5, 5), CUADRADO) is True


def test_punto_afuera():
    assert punto_en_poligono((15, 5), CUADRADO) is False
    assert punto_en_poligono((5, -1), CUADRADO) is False


def test_punto_en_zona_inclinada_del_trapecio():
    # (5, 1) esta adentro; (1, 1) queda fuera del lado inclinado
    assert punto_en_poligono((5, 1), TRAPECIO) is True
    assert punto_en_poligono((1, 1), TRAPECIO) is False


def test_cobertura_total():
    assert cobertura((-5, -5, 15, 15), CUADRADO) == 1.0


def test_cobertura_mitad():
    assert cobertura((0, 0, 5, 10), CUADRADO) == 0.5


def test_cobertura_un_cuarto():
    assert cobertura((0, 0, 5, 5), CUADRADO) == 0.25


def test_cobertura_nula():
    assert cobertura((20, 20, 30, 30), CUADRADO) == 0.0


def test_cobertura_caja_que_solo_toca_el_borde():
    assert cobertura((10, 0, 20, 10), CUADRADO) == 0.0