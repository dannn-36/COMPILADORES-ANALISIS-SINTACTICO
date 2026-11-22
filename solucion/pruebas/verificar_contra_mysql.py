"""
verificar_contra_mysql.py - Validación cruzada del analizador contra MySQL real.

Toma las sentencias que el analizador rechazó por error LÉXICO, SINTÁCTICO o
SEMÁNTICO (un ejemplo por cada patrón distinto), las envía directamente a
MySQL dentro de una transacción y la REVIERTE (ROLLBACK). Así se comprueba
que MySQL también las rechaza y con qué código de error.

Las sentencias PELIGROSAS (DROP, DELETE masivo, ...) NO se envían nunca.

Uso (desde la carpeta 'solucion', después de procesar los archivos):
    python pruebas\\verificar_contra_mysql.py salida\\casos_extra_invalidas.csv salida\\dataset_sql_usuarios_invalidas.csv
"""

import csv
import re
import sys

import mysql.connector

SQL_MODE = ("ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,"
            "ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION")
CATEGORIAS = ("LEXICO", "SINTACTICO", "SEMANTICO")


def main(archivos):
    conexion = mysql.connector.connect(host="localhost", user="root", password="12345678",
                                       database="ubosquebd", autocommit=False)
    cursor = conexion.cursor(buffered=True)
    cursor.execute(f"SET SESSION sql_mode = '{SQL_MODE}'")
    vistos, rechazadas, aceptadas = set(), 0, []
    print(f"{'CATEGORÍA':<11}| {'RESULTADO EN MySQL':<62}| SENTENCIA")
    print("-" * 130)
    for archivo in archivos:
        with open(archivo, encoding="utf-8-sig") as f:
            for fila in csv.DictReader(f):
                if fila["categoria"] not in CATEGORIAS:
                    continue
                patron = re.sub(r"'[^']*'", "'?'", fila["sentencia"])
                if patron in vistos:
                    continue
                vistos.add(patron)
                sentencia = fila["sentencia"].rstrip("; ")
                try:
                    cursor.execute(sentencia)
                    if cursor.description:
                        cursor.fetchall()
                    resultado = "LA ACEPTA (decisión de diseño del analizador)"
                    aceptadas.append(sentencia)
                except mysql.connector.Error as error:
                    resultado = f"rechaza: error {error.errno} {error.msg[:45]}"
                    rechazadas += 1
                finally:
                    conexion.rollback()  # nada queda guardado
                print(f"{fila['categoria']:<11}| {resultado:<62}| {sentencia[:60]}")
    conexion.close()
    print("-" * 130)
    print(f"Patrones distintos probados: {len(vistos)} | MySQL los rechaza: {rechazadas} | "
          f"MySQL los acepta: {len(aceptadas)}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    main(sys.argv[1:])
