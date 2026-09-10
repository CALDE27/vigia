"""Paquete de visión por computadora del sistema Vigía.

Regla de oro de este paquete (decisión AD-4 del documento de diseño):
ningún módulo de acá adentro puede importar FastAPI, SQLAlchemy ni nada
del backend. Sólo numpy, opencv y ultralytics. Así se puede probar
unitariamente sin levantar servidor ni base de datos.
"""