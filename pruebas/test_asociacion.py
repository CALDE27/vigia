"""Pruebas de la asociacion. No usan YOLO: cada caja esta armada a mano.

Escenario: dos cuadrados de 100x100 uno al lado del otro.
P01 va de x=0 a 100 y P02 de x=100 a 200, ambos de y=0 a 100.
"""

import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vision.asociacion import Region, asignar, estado_de_espacios

P01 = Region("P01", [(0, 0), (100, 0), (100, 100), (0, 100)])
P02 = Region("P02", [(100, 0), (200, 0), (200, 100), (100, 100)])
REGIONES = [P01, P02]


@dataclass(frozen=True)
class DeteccionFalsa:
    """Doble de prueba: solo tiene lo que asignar usa, caja y punto_apoyo."""

    caja: tuple[float, float, float, float]

    @property
    def punto_apoyo(self) -> tuple[float, float]:
        x1, _, x2, y2 = self.caja
        return ((x1 + x2) / 2.0, y2)


def test_auto_centrado():
    # Apoyo (50, 90), dentro de P01.
    resultado = asignar([DeteccionFalsa((10, 10, 90, 90))], REGIONES)
    assert list(resultado) == ["P01"]
    assert resultado["P01"].por_apoyo is True


def test_caja_que_invade_al_vecino_se_queda_en_su_lugar():
    # La caja tapa la mitad de P02, pero el auto apoya en P01 (80, 90).
    # Gana P01 por el punto de apoyo, no por cuanto tapa la caja.
    resultado = asignar([DeteccionFalsa((10, 10, 150, 90))], REGIONES)
    assert list(resultado) == ["P01"]
    assert resultado["P01"].por_apoyo is True


def test_respaldo_por_cobertura():
    # Apoyo (52.5, 150), fuera de todo. Cobertura de P01 = 85*90/10000 = 0.765.
    resultado = asignar([DeteccionFalsa((10, 10, 95, 150))], REGIONES)
    assert list(resultado) == ["P01"]
    assert resultado["P01"].por_apoyo is False
    assert abs(resultado["P01"].cobertura - 0.765) < 1e-9


def test_se_descarta_si_no_llega_al_umbral():
    # Apoyo (20, 150), fuera de todo. Cobertura de P01 = 20*90/10000 = 0.18 < 0.35.
    resultado = asignar([DeteccionFalsa((10, 10, 30, 150))], REGIONES)
    assert resultado == {}


def test_dos_en_el_mismo_lugar_gana_la_de_mayor_cobertura():
    chica = DeteccionFalsa((20, 40, 80, 80))  # 60*40/10000 = 0.24
    grande = DeteccionFalsa((5, 5, 95, 95))  # 90*90/10000 = 0.81
    resultado = asignar([chica, grande], REGIONES)
    assert list(resultado) == ["P01"]
    assert resultado["P01"].indice == 1
    assert abs(resultado["P01"].cobertura - 0.81) < 1e-9


def test_sin_detecciones_todo_libre():
    asignaciones = asignar([], REGIONES)
    assert estado_de_espacios(REGIONES, asignaciones) == {"P01": False, "P02": False}


def test_un_auto_en_cada_lugar():
    detecciones = [DeteccionFalsa((10, 10, 90, 90)), DeteccionFalsa((110, 10, 190, 90))]
    asignaciones = asignar(detecciones, REGIONES)
    assert estado_de_espacios(REGIONES, asignaciones) == {"P01": True, "P02": True}
