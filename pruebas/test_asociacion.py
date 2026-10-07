"""Pruebas de la regla de asignacion v4: admite por cobertura, elige por area."""

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vision.asociacion import Region, asignar, estado_de_espacios


@dataclass(frozen=True)
class DeteccionFalsa:
    """Imita a Deteccion sin necesitar YOLO."""
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def caja(self):
        return (self.x1, self.y1, self.x2, self.y2)

    @property
    def punto_apoyo(self):
        return ((self.x1 + self.x2) / 2, self.y2)


# Dos lugares lado a lado, del mismo tamano.
P01 = Region("P01", [(0, 0), (100, 0), (100, 100), (0, 100)])
P02 = Region("P02", [(100, 0), (200, 0), (200, 100), (100, 100)])
REGIONES = [P01, P02]


def test_auto_centrado_ocupa_su_lugar():
    resultado = asignar([DeteccionFalsa(10, 10, 90, 90)], REGIONES)
    assert list(resultado) == ["P01"]
    assert resultado["P01"].criterio == "interseccion"


def test_caja_que_invade_al_vecino_no_lo_ocupa():
    """Cubre la mitad de P02, pero cubre mucho mas P01."""
    resultado = asignar([DeteccionFalsa(10, 10, 150, 90)], REGIONES)
    assert list(resultado) == ["P01"]


def test_deteccion_fuera_de_toda_region_se_descarta():
    assert asignar([DeteccionFalsa(10, 10, 30, 150)], REGIONES) == {}


def test_dos_detecciones_en_el_mismo_lugar_gana_la_de_mayor_cobertura():
    chica = DeteccionFalsa(10, 10, 40, 90)
    grande = DeteccionFalsa(5, 5, 95, 95)
    resultado = asignar([chica, grande], REGIONES)
    assert resultado["P01"].indice_deteccion == 1


def test_sin_detecciones_todo_libre():
    assert estado_de_espacios(REGIONES, asignar([], REGIONES)) == {
        "P01": False, "P02": False
    }


def test_un_auto_en_cada_lugar():
    resultado = asignar(
        [DeteccionFalsa(10, 10, 90, 90), DeteccionFalsa(110, 10, 190, 90)],
        REGIONES,
    )
    assert estado_de_espacios(REGIONES, resultado) == {"P01": True, "P02": True}


# --- Lugares apilados en profundidad, como la fila real del predio ---
# CERCA esta mas abajo en la imagen (y mayor), LEJOS mas arriba.
CERCA = Region("CERCA", [(0, 100), (300, 100), (300, 200), (0, 200)])
LEJOS = Region("LEJOS", [(0, 0), (300, 0), (300, 100), (0, 100)])
FILA = [LEJOS, CERCA]


def test_apoyo_corrido_una_ranura_no_roba_el_lugar():
    """El primer error medido en el predio.

    El auto esta en LEJOS, pero su caja baja hasta CERCA porque esta
    alineada a los ejes y el auto esta en diagonal. El punto de apoyo
    cae en CERCA. La asignacion tiene que dar LEJOS igual.
    """
    auto = DeteccionFalsa(20, 10, 280, 120)
    assert auto.punto_apoyo == (150, 120)          # cae dentro de CERCA
    resultado = asignar([auto], FILA)
    assert list(resultado) == ["LEJOS"]
    assert resultado["LEJOS"].criterio == "interseccion"


# --- Perspectiva: el lugar del fondo se ve mas chico ---
# CERCANO tiene 40.000 px2; LEJANO, 10.000. Es el caso real del predio,
# donde P01 es catorce veces mas grande que P07 en la imagen.
CERCANO = Region("CERCANO", [(0, 0), (200, 0), (200, 200), (0, 200)])
LEJANO = Region("LEJANO", [(200, 0), (300, 0), (300, 100), (200, 100)])
PERSPECTIVA = [CERCANO, LEJANO]


def test_la_perspectiva_no_corre_el_auto_al_lugar_del_fondo():
    """El segundo error medido en el predio.

    La caja tapa 20.000 px2 de CERCANO y 6.000 de LEJANO: esta mucho mas
    en CERCANO. Pero como fraccion da 0,50 contra 0,60, porque LEJANO es
    cuatro veces mas chico. Dividir por el area del lugar premiaba al del
    fondo; comparar superficies en pixeles lo corrige.
    """
    auto = DeteccionFalsa(0, 0, 260, 100)
    resultado = asignar([auto], PERSPECTIVA)
    assert list(resultado) == ["CERCANO"]
    assert resultado["CERCANO"].interseccion == 20000
    assert resultado["CERCANO"].cobertura == 0.50


# --- Cobertura pareja: ahora decide la superficie ---
ANGOSTA = Region("ANGOSTA", [(0, 0), (60, 0), (60, 100), (0, 100)])
ANCHA = Region("ANCHA", [(60, 0), (200, 0), (200, 100), (60, 100)])
PAR = [ANGOSTA, ANCHA]


def test_con_cobertura_pareja_gana_la_de_mayor_superficie():
    """Empate exacto en fracciones, resuelto por area de interseccion.

    El auto tapa 2.700 de los 6.000 px2 de ANGOSTA y 6.300 de los 14.000
    de ANCHA: 0,45 y 0,45. La fraccion no distingue; la superficie si.
    """
    auto = DeteccionFalsa(30, 0, 130, 90)
    resultado = asignar([auto], PAR)
    assert list(resultado) == ["ANCHA"]
    assert resultado["ANCHA"].interseccion == 6300


def test_cobertura_clara_ignora_el_punto_de_apoyo():
    auto = DeteccionFalsa(0, 0, 100, 90)           # 0,90 contra 0,26
    resultado = asignar([auto], PAR)
    assert list(resultado) == ["ANGOSTA"]
    assert resultado["ANGOSTA"].criterio == "interseccion"