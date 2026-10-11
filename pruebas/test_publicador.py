"""Pruebas del publicador.

No levantan ningun servidor: reemplazan el metodo que habla por la red
por uno de mentira. Asi se verifica que el cuerpo que arma cumple el
contrato y que los errores se manejan como corresponde.
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from vision.publicador import ErrorPublicacion, Publicador, armar_lugares

ESPACIOS = ["P01", "P02", "P03"]


class AsignacionFalsa:
    """Imita a una Asignacion: solo lo que el publicador le pide."""

    def __init__(self, confianza: float, cobertura: float) -> None:
        self.confianza = confianza
        self.cobertura = cobertura


def test_un_lugar_ocupado_lleva_confianza_y_cobertura():
    lugares = armar_lugares(
        ESPACIOS,
        {"P01": True, "P02": False, "P03": False},
        {"P01": AsignacionFalsa(0.9312, 0.87648)},
    )
    assert lugares[0] == {
        "espacio": "P01", "ocupado": True,
        "confianza": 0.931, "cobertura": 0.876,
    }


def test_un_lugar_libre_los_deja_en_nulo():
    lugares = armar_lugares(ESPACIOS, {"P02": False}, {})
    assert lugares[1]["ocupado"] is False
    assert lugares[1]["confianza"] is None
    assert lugares[1]["cobertura"] is None


def test_vienen_todos_los_lugares_y_en_orden():
    lugares = armar_lugares(ESPACIOS, {}, {})
    assert [lugar["espacio"] for lugar in lugares] == ESPACIOS


def test_el_instante_viaja_sin_microsegundos():
    publicador = Publicador()
    enviados = []
    publicador._pedir = lambda ruta, cuerpo: enviados.append(cuerpo) or {"transiciones": []}

    publicador.publicar(datetime(2026, 10, 10, 9, 12, 0, 123456), 20100, [])

    assert enviados[0]["instante"] == "2026-10-10T09:12:00"


def test_el_cuadro_viaja_como_entero():
    publicador = Publicador()
    enviados = []
    publicador._pedir = lambda ruta, cuerpo: enviados.append(cuerpo) or {"transiciones": []}

    publicador.publicar(datetime(2026, 10, 10, 9, 12), 20100.0, [])

    assert enviados[0]["cuadro"] == 20100
    assert isinstance(enviados[0]["cuadro"], int)


def test_publicar_devuelve_las_transiciones_y_cuenta():
    publicador = Publicador()
    publicador._pedir = lambda ruta, cuerpo: {
        "recibido": 3, "corrida": 1,
        "transiciones": [{"espacio": "P07", "estado": "ocupado"}],
    }

    transiciones = publicador.publicar(datetime(2026, 10, 10, 9, 12), 1, [])

    assert len(transiciones) == 1
    assert publicador.enviadas == 1
    assert publicador.fallidas == 0


def test_si_falla_publicar_no_levanta_y_cuenta_el_fallo():
    """Perder una muestra no justifica perder media hora de procesamiento."""
    publicador = Publicador()

    def romper(ruta, cuerpo):
        raise ErrorPublicacion("el backend no responde")

    publicador._pedir = romper

    assert publicador.publicar(datetime(2026, 10, 10, 9, 12), 1, []) == []
    assert publicador.fallidas == 1
    assert publicador.enviadas == 0
    assert "no responde" in publicador.ultimo_error


def test_reiniciar_si_levanta_cuando_falla():
    """Al arrancar conviene cortar: casi seguro falta levantar el backend."""
    publicador = Publicador()

    def romper(ruta, cuerpo):
        raise ErrorPublicacion("el backend no responde")

    publicador._pedir = romper

    with pytest.raises(ErrorPublicacion):
        publicador.reiniciar()


def test_reiniciar_devuelve_el_numero_de_corrida():
    publicador = Publicador()
    publicador._pedir = lambda ruta, cuerpo: {"corrida": 7}
    assert publicador.reiniciar() == 7


def test_el_resumen_avisa_cuando_hubo_fallos():
    publicador = Publicador()
    publicador.enviadas, publicador.fallidas = 10, 2
    publicador.ultimo_error = "tiempo agotado"
    assert "2 fallaron" in publicador.resumen()


def test_el_resumen_es_breve_cuando_no_hubo_fallos():
    publicador = Publicador()
    publicador.enviadas = 10
    assert publicador.resumen() == "Publicadas 10 muestras, sin fallos."