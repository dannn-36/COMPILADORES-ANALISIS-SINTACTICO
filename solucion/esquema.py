"""
esquema.py - Tabla de símbolos del analizador semántico.

Describe la base de datos sobre la que se ejecutan las sentencias. Es un
reflejo exacto de ScriptBD_DSL.sql (script inicial de la base de datos):

    CREATE TABLE `usuarios` (
      `login`    varchar(15) NOT NULL,
      `password` varchar(15) NOT NULL,
      `estado`   varchar(15) NOT NULL
    )

El analizador consulta esta tabla de símbolos para saber qué tablas y
columnas existen, de qué tipo y longitud son, cuáles son obligatorias y
cuál es la columna que identifica a cada registro (necesaria para detectar
actualizaciones o eliminaciones masivas).

Si la base de datos cambia, basta con actualizar este archivo.
"""

from __future__ import annotations

from dataclasses import dataclass, field

BASE_DATOS = "ubosquebd"


@dataclass(frozen=True)
class Columna:
    nombre: str
    tipo: str
    longitud: int | None = None   # longitud máxima (varchar)
    admite_nulo: bool = False      # NULL / NOT NULL
    tiene_defecto: bool = False    # ¿tiene valor DEFAULT?

    @property
    def obligatoria(self) -> bool:
        """Debe indicarse siempre en un INSERT (NOT NULL y sin DEFAULT)."""
        return not self.admite_nulo and not self.tiene_defecto

    def describir(self) -> str:
        tipo = f"{self.tipo}({self.longitud})" if self.longitud else self.tipo
        return f"{tipo} {'NULL' if self.admite_nulo else 'NOT NULL'}"


@dataclass
class Tabla:
    nombre: str
    columnas: dict[str, Columna] = field(default_factory=dict)
    # Columnas que identifican un registro puntual. La tabla `usuarios` no
    # tiene PRIMARY KEY, pero `login` es el identificador lógico del usuario.
    claves: tuple[str, ...] = ()

    def nombres_columnas(self) -> list[str]:
        return [c.nombre for c in self.columnas.values()]


def _tabla(nombre: str, columnas: list[Columna], claves: tuple[str, ...]) -> Tabla:
    return Tabla(nombre, {c.nombre.lower(): c for c in columnas}, claves)


ESQUEMA: dict[str, Tabla] = {
    "usuarios": _tabla(
        "usuarios",
        [
            Columna("login", "varchar", 15),
            Columna("password", "varchar", 15),
            Columna("estado", "varchar", 15),
        ],
        claves=("login",),
    ),
}
