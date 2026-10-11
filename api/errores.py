"""El error del dominio, con la forma que define el contrato.

Vive en su propio archivo para que cualquier capa pueda levantarlo sin
importar la aplicacion. Si estuviera en principal.py, el almacen tendria
que importar principal y principal al almacen: un ciclo que Python
rechaza.
"""

from __future__ import annotations


class ErrorVigia(Exception):
    """Un error previsto, que el cliente recibe con el cuerpo del contrato."""

    def __init__(self, estado: int, error: str, detalle: str) -> None:
        super().__init__(detalle)
        self.estado = estado
        self.error = error
        self.detalle = detalle