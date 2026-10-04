import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from vision.histeresis import Estabilizador

T0 = datetime(2026, 1, 1, 7, 0)
ESPACIOS = ["P01", "P02"]


def instante(minutos):
    return T0 + timedelta(minutes=minutos)


def test_una_sola_observacion_distinta_no_confirma():
    e = Estabilizador(ESPACIOS, instante_inicial=T0, k=3)
    assert e.observar({"P01": True, "P02": False}, instante(2)) == []
    assert e.estado["P01"] is False
    assert e.pendientes == {"P01": 1}


def test_volver_al_estado_anterior_reinicia_el_contador():
    e = Estabilizador(ESPACIOS, instante_inicial=T0, k=3)
    e.observar({"P01": True, "P02": False}, instante(2))
    e.observar({"P01": False, "P02": False}, instante(4))
    assert e.pendientes == {}


def test_tres_observaciones_seguidas_confirman():
    e = Estabilizador(ESPACIOS, instante_inicial=T0, k=3)
    for minuto in (2, 4):
        assert e.observar({"P01": True, "P02": False}, instante(minuto)) == []
    transiciones = e.observar({"P01": True, "P02": False}, instante(6))
    assert len(transiciones) == 1
    assert transiciones[0].espacio == "P01"
    assert transiciones[0].etiqueta == "OCUPADO"
    assert e.estado["P01"] is True


def test_la_alternancia_pura_no_confirma_nunca():
    """Lo que pasaria con una persona caminando ida y vuelta."""
    e = Estabilizador(["P01"], instante_inicial=T0, k=3)
    confirmadas = []
    for i in range(10):
        confirmadas += e.observar({"P01": i % 2 == 0}, instante(i * 2))
    assert confirmadas == []
    assert e.estado["P01"] is False


def test_con_k_igual_a_uno_confirma_de_inmediato():
    e = Estabilizador(["P01"], instante_inicial=T0, k=1)
    assert len(e.observar({"P01": True}, instante(2))) == 1


def test_la_transicion_informa_cuanto_duro_el_estado_anterior():
    e = Estabilizador(["P01"], instante_inicial=T0, k=2)
    for minuto in (10, 20):
        e.observar({"P01": True}, instante(minuto))
    transiciones = []
    for minuto in (30, 40):
        transiciones += e.observar({"P01": False}, instante(minuto))
    assert transiciones[0].duracion_anterior_s == 20 * 60


def test_k_invalido_es_un_error():
    with pytest.raises(ValueError):
        Estabilizador(["P01"], instante_inicial=T0, k=0)


def test_un_espacio_desconocido_se_ignora():
    e = Estabilizador(["P01"], instante_inicial=T0, k=1)
    assert e.observar({"P99": True}, instante(2)) == []
    assert e.estado == {"P01": False}