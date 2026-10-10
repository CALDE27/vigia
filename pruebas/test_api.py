"""Pruebas del stub de la API.

No hace falta levantar el servidor: TestClient habla con la aplicacion
directamente en memoria, asi que corren igual de rapido que las demas.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from api.configuracion import CLAVE_SERVICIO
from api.principal import ESPACIOS, app, memoria

cliente = TestClient(app)
CABECERA = {"X-Clave-Servicio": CLAVE_SERVICIO}


@pytest.fixture(autouse=True)
def memoria_limpia():
    """Cada prueba arranca con una corrida nueva y vacia."""
    memoria.reiniciar()
    yield


def publicar(hora_minuto: str, cuadro: int, ocupados: set[str]):
    """Publica un estado completo, como lo hara el servicio de vision."""
    cuerpo = {
        "instante": f"2026-10-09T{hora_minuto}:00",
        "cuadro": cuadro,
        "lugares": [
            {
                "espacio": espacio,
                "ocupado": espacio in ocupados,
                "confianza": 0.93 if espacio in ocupados else None,
                "cobertura": 0.88 if espacio in ocupados else None,
            }
            for espacio in ESPACIOS
        ],
    }
    return cliente.post("/api/v1/estado", json=cuerpo, headers=CABECERA)


def test_salud_responde_ok():
    cuerpo = cliente.get("/api/v1/salud").json()
    assert cuerpo["estado"] == "ok"
    assert cuerpo["lugares_configurados"] == len(ESPACIOS)


def test_el_estado_trae_todos_los_lugares():
    cuerpo = cliente.get("/api/v1/estado").json()
    assert [lugar["espacio"] for lugar in cuerpo["lugares"]] == ESPACIOS
    assert cuerpo["resumen"]["total"] == len(ESPACIOS)
    assert (cuerpo["resumen"]["libres"] + cuerpo["resumen"]["ocupados"]
            == len(ESPACIOS))


def test_publicar_sin_clave_da_401():
    respuesta = cliente.post("/api/v1/estado", json={
        "instante": "2026-10-09T09:12:00", "cuadro": 1, "lugares": []})
    assert respuesta.status_code == 401
    assert respuesta.json()["error"] == "clave_invalida"


def test_la_primera_publicacion_no_anota_transiciones():
    """El primer estado es el punto de partida, no un cambio."""
    respuesta = publicar("09:12", 100, {ESPACIOS[0], ESPACIOS[2]})
    assert respuesta.status_code == 200
    assert respuesta.json()["transiciones"] == []
    assert respuesta.json()["recibido"] == len(ESPACIOS)


def test_un_cambio_anota_una_sola_transicion():
    publicar("09:12", 100, {ESPACIOS[0]})
    respuesta = publicar("10:00", 1600, {ESPACIOS[0], ESPACIOS[6]})
    transiciones = respuesta.json()["transiciones"]
    assert len(transiciones) == 1
    assert transiciones[0]["espacio"] == ESPACIOS[6]
    assert transiciones[0]["estado"] == "ocupado"


def test_publicar_lo_mismo_no_anota_nada():
    publicar("09:12", 100, {ESPACIOS[0]})
    assert publicar("09:13", 130, {ESPACIOS[0]}).json()["transiciones"] == []


def test_un_instante_anterior_da_409():
    publicar("10:00", 1600, {ESPACIOS[0]})
    respuesta = publicar("09:00", 10, {ESPACIOS[0]})
    assert respuesta.status_code == 409
    assert respuesta.json()["error"] == "instante_anterior"


def test_un_lugar_desconocido_da_422():
    respuesta = cliente.post("/api/v1/estado", headers=CABECERA, json={
        "instante": "2026-10-09T09:12:00",
        "cuadro": 1,
        "lugares": [{"espacio": "ZZZ", "ocupado": True,
                     "confianza": None, "cobertura": None}],
    })
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "cuerpo_invalido"


def test_un_cuerpo_sin_instante_da_422():
    respuesta = cliente.post("/api/v1/estado", headers=CABECERA,
                             json={"cuadro": 1, "lugares": []})
    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "cuerpo_invalido"


def test_el_limite_recorta_el_historial():
    publicar("09:00", 10, set())
    publicar("09:30", 20, {ESPACIOS[0]})
    publicar("10:00", 30, {ESPACIOS[0], ESPACIOS[1]})
    publicar("10:30", 40, {ESPACIOS[0], ESPACIOS[1], ESPACIOS[2]})
    cuerpo = cliente.get("/api/v1/transiciones?limite=2").json()
    assert cuerpo["total"] == 3
    assert len(cuerpo["transiciones"]) == 2
    assert cuerpo["limite"] == 2


def test_las_transiciones_vienen_de_la_mas_nueva_a_la_mas_vieja():
    publicar("09:00", 10, set())
    publicar("09:30", 20, {ESPACIOS[0]})
    publicar("10:00", 30, {ESPACIOS[0], ESPACIOS[1]})
    instantes = [t["instante"] for t in
                 cliente.get("/api/v1/transiciones").json()["transiciones"]]
    assert instantes == sorted(instantes, reverse=True)


def test_filtrar_por_un_lugar_inexistente_da_404():
    respuesta = cliente.get("/api/v1/transiciones?espacio=ZZZ")
    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "no_encontrado"


def test_el_reinicio_abre_una_corrida_nueva():
    antes = cliente.get("/api/v1/salud").json()["corrida"]
    respuesta = cliente.post("/api/v1/reinicio", headers=CABECERA)
    assert respuesta.status_code == 200
    assert respuesta.json()["corrida"] == antes + 1


def test_el_reinicio_sin_clave_da_401():
    assert cliente.post("/api/v1/reinicio").status_code == 401