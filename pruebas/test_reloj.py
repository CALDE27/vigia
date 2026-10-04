import sys
from datetime import datetime
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vision.reloj import RelojSimulado

ORIGEN = datetime(2026, 1, 1, 7, 0)


def test_el_instante_cero_es_el_origen():
    reloj = RelojSimulado(origen=ORIGEN, factor=24.0)
    assert reloj.instante(0) == ORIGEN


def test_el_tiempo_avanza_segun_el_factor():
    reloj = RelojSimulado(origen=ORIGEN, factor=24.0)
    # 150 s de video x 24 = 3600 s simulados = 1 hora
    assert reloj.instante(150) == datetime(2026, 1, 1, 8, 0)


def test_para_abarcar_cubre_exactamente_el_rango():
    fin = datetime(2026, 1, 1, 21, 0)
    reloj = RelojSimulado.para_abarcar(ORIGEN, fin, 2127.0)
    assert reloj.instante(0) == ORIGEN
    assert abs((reloj.instante(2127) - fin).total_seconds()) < 1


def test_para_abarcar_rechaza_duracion_invalida():
    with pytest.raises(ValueError):
        RelojSimulado.para_abarcar(ORIGEN, ORIGEN, 0)