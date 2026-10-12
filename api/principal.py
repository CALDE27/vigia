"""La aplicacion FastAPI: los cinco endpoints del contrato.

Esta capa no sabe de donde salen los datos: se los pide a `memoria`.
Hoy esa memoria los inventa; en el tramo siguiente se reemplaza por la
base de datos y estos endpoints no se tocan. Esa es la razon de que el
acceso a los datos este en otro archivo.
"""

from __future__ import annotations

from datetime import datetime

from fastapi import Depends, FastAPI, Header, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api import almacen, esquemas, falsos
from api.configuracion import (CLAVE_SERVICIO, RAIZ, RUTA_BASE, USAR_FALSOS,
                               VERSION, leer_espacios)
from api.errores import ErrorVigia

ESPACIOS = leer_espacios()

# Por omision el backend usa la base de datos. Con VIGIA_FALSOS=1 vuelve
# al guion del tramo 6, que es como el frontend puede trabajar sin que
# nadie este publicando estados reales.
memoria = (falsos.Memoria(ESPACIOS) if USAR_FALSOS
           else almacen.Almacen(ESPACIOS, RUTA_BASE))

app = FastAPI(
    title="Vigia - API",
    version=VERSION,
    description=(
        "Backend del sistema de gestion de estacionamientos. "
        "Esta version responde datos inventados: sirve para que el "
        "frontend se construya sin esperar la base de datos."
    ),
)

# En desarrollo el tablero se abre desde otro origen (un archivo local o
# el servidor de Live Server), y el navegador bloquea esos pedidos salvo
# que el backend los autorice. En produccion esta lista se recorta a los
# origenes reales.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)




@app.exception_handler(ErrorVigia)
async def manejar_error_vigia(_, excepcion: ErrorVigia) -> JSONResponse:
    return JSONResponse(
        status_code=excepcion.estado,
        content={"error": excepcion.error, "detalle": excepcion.detalle},
    )


@app.exception_handler(RequestValidationError)
async def manejar_validacion(_, excepcion: RequestValidationError) -> JSONResponse:
    """FastAPI rechaza los cuerpos mal formados con su propio formato.

    Lo traducimos al del contrato para que el cliente tenga una sola
    forma de error que manejar.
    """
    primero = excepcion.errors()[0]
    campo = ".".join(str(parte) for parte in primero.get("loc", []))
    return JSONResponse(
        status_code=422,
        content={
            "error": "cuerpo_invalido",
            "detalle": f"{campo}: {primero.get('msg', 'valor invalido')}",
        },
    )


def exigir_clave(x_clave_servicio: str | None = Header(default=None)) -> None:
    """Protege los endpoints de escritura con la clave compartida."""
    if x_clave_servicio != CLAVE_SERVICIO:
        raise ErrorVigia(
            401,
            "clave_invalida",
            "La cabecera X-Clave-Servicio falta o no coincide con la configurada.",
        )


# --- Lo que usa el servicio de vision ----------------------------------

@app.post(
    "/api/v1/estado",
    response_model=esquemas.RespuestaPublicacion,
    dependencies=[Depends(exigir_clave)],
    tags=["vision"],
    summary="Publicar el estado completo de los lugares",
)
def publicar_estado(cuerpo: esquemas.EstadoPublicado) -> esquemas.RespuestaPublicacion:
    desconocidos = [l.espacio for l in cuerpo.lugares if l.espacio not in ESPACIOS]
    if desconocidos:
        raise ErrorVigia(
            422,
            "cuerpo_invalido",
            f"Lugares que no estan en la calibracion: {', '.join(desconocidos)}.",
        )
    if memoria.publicado and cuerpo.instante < memoria.instante:
        raise ErrorVigia(
            409,
            "instante_anterior",
            "El instante publicado es anterior al ultimo recibido. Si el "
            "video volvio a empezar, llama primero a POST /api/v1/reinicio.",
        )

    nuevas = memoria.publicar(cuerpo)
    return esquemas.RespuestaPublicacion(
        recibido=len(cuerpo.lugares),
        corrida=memoria.corrida,
        transiciones=[
            esquemas.TransicionBreve(
                espacio=fila["espacio"],
                estado=fila["estado"],
                instante=fila["instante"],
            )
            for fila in nuevas
        ],
    )


@app.post(
    "/api/v1/reinicio",
    response_model=esquemas.RespuestaReinicio,
    dependencies=[Depends(exigir_clave)],
    tags=["vision"],
    summary="Abrir una corrida nueva",
)
def reiniciar() -> esquemas.RespuestaReinicio:
    return esquemas.RespuestaReinicio(corrida=memoria.reiniciar())


# --- Lo que usa el tablero ---------------------------------------------

@app.get(
    "/api/v1/estado",
    response_model=esquemas.RespuestaEstado,
    tags=["tablero"],
    summary="Estado actual de todos los lugares",
)
def obtener_estado() -> esquemas.RespuestaEstado:
    return memoria.estado_actual()


@app.get(
    "/api/v1/transiciones",
    response_model=esquemas.RespuestaTransiciones,
    tags=["tablero"],
    summary="Historial de cambios de estado",
)
def obtener_transiciones(
    espacio: str | None = Query(default=None),
    desde: datetime | None = Query(default=None),
    hasta: datetime | None = Query(default=None),
    corrida: int | None = Query(default=None),
    limite: int = Query(default=100, ge=1, le=500),
    desplazamiento: int = Query(default=0, ge=0),
) -> esquemas.RespuestaTransiciones:
    if espacio is not None and espacio not in ESPACIOS:
        raise ErrorVigia(
            404, "no_encontrado", f"El lugar {espacio} no esta en la calibracion."
        )
    return memoria.listar_transiciones(
            espacio=espacio,
            desde=desde,
            hasta=hasta,
            corrida=corrida,
            limite=limite,
    )


# --- Servicio -----------------------------------------------------------

@app.get(
    "/api/v1/salud",
    response_model=esquemas.Salud,
    tags=["servicio"],
    summary="Estado del propio backend",
)
def salud() -> esquemas.Salud:
    return esquemas.Salud(
        estado="ok",
        version=VERSION,
        corrida=memoria.corrida,
        ultimo_estado_hace_s=memoria.estado_actual().actualizado_hace_s,
        lugares_configurados=len(ESPACIOS),
    )

# --- El frontend ---------------------------------------------------------

# La misma aplicacion sirve el tablero y el historial. Va al final a
# proposito: un montaje en "/" atiende cualquier ruta, asi que tiene que
# registrarse despues de los endpoints de /api/v1 para no taparlos.
app.mount("/", StaticFiles(directory=RAIZ / "web", html=True), name="web")