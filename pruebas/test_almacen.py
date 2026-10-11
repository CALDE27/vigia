"""Pruebas de la persistencia.

Cada prueba trabaja sobre una base nueva, en una carpeta temporal que
pytest borra sola al terminar. Nunca tocan datos/vigia.db.
"""

import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from api import esquemas
from api.almacen import Almacen
from api.errores import ErrorVigia

ESPACIOS = ["P01", "P02", "P03"]


@pytest.fixture
def almacen(tmp_path):
    """Una base vacia por prueba."""
    return Almacen(ESPACIOS, tmp_path / "prueba.db")


def publicar(almacen, hora_minuto: str, cuadro: int, ocupados: set[str]):
    """Publica un estado completo, como lo hara el servicio de vision."""
    hora, minuto = (int(parte) for parte in hora_minuto.split(":"))
    cuerpo = esquemas.EstadoPublicado(
        instante=datetime(2026, 10, 10, hora, minuto),
        cuadro=cuadro,
        lugares=[
            esquemas.LugarPublicado(
                espacio=espacio,
                ocupado=espacio in ocupados,
                confianza=0.93 if espacio in ocupados else None,
                cobertura=0.88 if espacio in ocupados else None,
            )
            for espacio in ESPACIOS
        ],
    )
    return almacen.publicar(cuerpo)


def test_una_base_nueva_no_tiene_estado(almacen):
    with pytest.raises(ErrorVigia) as excepcion:
        almacen.estado_actual()
    assert excepcion.value.estado == 503
    assert excepcion.value.error == "sin_datos"


def test_la_primera_publicacion_no_anota_transiciones(almacen):
    assert publicar(almacen, "09:12", 100, {"P01"}) == []
    assert almacen.listar_transiciones().total == 0


def test_un_cambio_anota_una_transicion_con_su_duracion(almacen):
    publicar(almacen, "09:12", 100, {"P01"})
    nuevas = publicar(almacen, "10:00", 1600, {"P01", "P03"})
    assert len(nuevas) == 1
    assert nuevas[0]["espacio"] == "P03"
    assert nuevas[0]["estado"] == "ocupado"
    assert nuevas[0]["duracion_anterior_s"] == 48 * 60


def test_publicar_lo_mismo_no_anota_nada(almacen):
    publicar(almacen, "09:12", 100, {"P01"})
    assert publicar(almacen, "09:13", 130, {"P01"}) == []


def test_el_estado_refleja_la_ultima_publicacion(almacen):
    publicar(almacen, "09:12", 100, {"P01"})
    publicar(almacen, "10:30", 3200, {"P01", "P02"})
    estado = almacen.estado_actual()
    assert estado.instante == datetime(2026, 10, 10, 10, 30)
    assert estado.cuadro == 3200
    assert estado.resumen.ocupados == 2
    assert estado.resumen.libres == 1


def test_los_lugares_vienen_completos_y_en_orden(almacen):
    publicar(almacen, "09:12", 100, {"P01"})
    estado = almacen.estado_actual()
    assert [lugar.espacio for lugar in estado.lugares] == ESPACIOS


def test_la_duracion_se_mide_en_tiempo_simulado(almacen):
    publicar(almacen, "09:00", 10, {"P01"})
    publicar(almacen, "11:00", 20, {"P01"})
    lugar = almacen.estado_actual().lugares[0]
    assert lugar.duracion_s == 2 * 3600


def test_el_filtro_por_lugar(almacen):
    publicar(almacen, "09:00", 10, set())
    publicar(almacen, "09:30", 20, {"P01"})
    publicar(almacen, "10:00", 30, {"P01", "P02"})
    assert almacen.listar_transiciones().total == 2
    assert almacen.listar_transiciones(espacio="P02").total == 1


def test_el_limite_y_el_desplazamiento(almacen):
    publicar(almacen, "09:00", 10, set())
    publicar(almacen, "09:30", 20, {"P01"})
    publicar(almacen, "10:00", 30, {"P01", "P02"})
    pagina = almacen.listar_transiciones(limite=1)
    assert pagina.total == 2 and len(pagina.transiciones) == 1
    segunda = almacen.listar_transiciones(limite=1, desplazamiento=1)
    assert segunda.transiciones[0].id != pagina.transiciones[0].id


def test_las_transiciones_vienen_de_la_mas_nueva_a_la_mas_vieja(almacen):
    publicar(almacen, "09:00", 10, set())
    publicar(almacen, "09:30", 20, {"P01"})
    publicar(almacen, "10:00", 30, {"P01", "P02"})
    instantes = [t.instante for t in almacen.listar_transiciones().transiciones]
    assert instantes == sorted(instantes, reverse=True)


def test_el_reinicio_abre_corrida_y_deja_sin_estado(almacen):
    publicar(almacen, "09:12", 100, {"P01"})
    assert almacen.reiniciar() == 2
    assert almacen.publicado is False
    with pytest.raises(ErrorVigia):
        almacen.estado_actual()


def test_el_reinicio_no_borra_el_historial_anterior(almacen):
    publicar(almacen, "09:00", 10, set())
    publicar(almacen, "09:30", 20, {"P01"})
    almacen.reiniciar()
    assert almacen.listar_transiciones().total == 0
    assert almacen.listar_transiciones(corrida=1).total == 1


def test_los_datos_sobreviven_a_cerrar_y_abrir(tmp_path):
    ruta = tmp_path / "prueba.db"
    primero = Almacen(ESPACIOS, ruta)
    publicar(primero, "09:00", 10, set())
    publicar(primero, "09:30", 20, {"P01"})
    del primero

    segundo = Almacen(ESPACIOS, ruta)
    assert segundo.listar_transiciones().total == 1
    assert segundo.estado_actual().resumen.ocupados == 1