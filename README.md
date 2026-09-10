# Vigia

Sistema de gestion de estacionamientos mediante vision por computadora.
Proyecto final de la catedra de SEMINARIO II.

Detecta vehiculos en el video de una camara fija con YOLO y determina
automaticamente que espacios estan libres y cuales ocupados.

## Requisitos

- Python 3.12 (no 3.13 ni 3.14: faltan paquetes de PyTorch)
- Sin GPU: todo corre en CPU

## Puesta en marcha

```powershell
py -3.12 -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Uso

```powershell
python herramientas\probar_deteccion.py --fuente datos\videos\prueba.mp4 --frame 300
```

## Estructura

- `vision/` paquete de vision por computadora, sin dependencias del backend
- `herramientas/` scripts de linea de comandos
- `config/` configuracion y regiones calibradas
- `datos/videos/` videos de entrada (no se versionan: pesan demasiado)
- `datos/salidas/` imagenes anotadas que genera el sistema

## Nota sobre los videos

Los videos no estan en el repositorio. Se comparten aparte y cada integrante
los guarda en su propia carpeta `datos/videos/`.

La camara debe estar elevada y en angulo oblicuo: en la imagen tienen que
verse los laterales y parabrisas de los vehiculos, no solo los techos. Con
vista cenital el modelo no detecta ningun vehiculo.
