"""
bd_util.py - Utilidades de la base de datos del laboratorio.

    python bd_util.py reiniciar   Ejecuta bd/ScriptBD_DSL_inicial.sql: crea la base
                                  ubosquebd y deja la tabla usuarios con los datos
                                  iniciales (útil antes de cada prueba).
    python bd_util.py exportar    Genera bd/ScriptBD_DSL_final.sql con la estructura
                                  y los datos ACTUALES (script final de la base).

Acepta las mismas opciones de conexión de ProcesaSQL.py:
    --host  --puerto  --usuario  --clave  --bd
"""

import argparse
import datetime
import os
import sys

import mysql.connector

from ProcesaSQL import BASE_DATOS, CLAVE, HOST, PUERTO, USUARIO

AQUI = os.path.dirname(os.path.abspath(__file__))
SCRIPT_INICIAL = os.path.join(AQUI, "bd", "ScriptBD_DSL_inicial.sql")
SCRIPT_FINAL = os.path.join(AQUI, "bd", "ScriptBD_DSL_final.sql")


def sentencias_de_script(ruta: str):
    """Divide un script .sql en sentencias (una sentencia termina en ';' al final de línea)."""
    actual = []
    with open(ruta, encoding="utf-8") as archivo:
        for linea in archivo:
            limpia = linea.strip()
            if not limpia or limpia.startswith("--"):
                continue
            actual.append(linea.rstrip("\r\n"))
            if limpia.endswith(";"):
                yield "\n".join(actual).rstrip().rstrip(";")
                actual = []
    if actual:
        yield "\n".join(actual)


def reiniciar(args):
    conexion = mysql.connector.connect(host=args.host, port=args.puerto, user=args.usuario,
                                       password=args.clave)
    cursor = conexion.cursor()
    total = 0
    for sentencia in sentencias_de_script(SCRIPT_INICIAL):
        cursor.execute(sentencia)
        if cursor.description is not None:
            cursor.fetchall()
        total += 1
    conexion.commit()
    cursor.execute(f"SELECT COUNT(*) FROM `{args.bd}`.`usuarios`")
    filas = cursor.fetchone()[0]
    cursor.close()
    conexion.close()
    print(f"Base de datos '{args.bd}' reiniciada: {total} sentencias del script inicial ejecutadas.")
    print(f"La tabla usuarios quedó con {filas} registros.")


def literal_sql(valor) -> str:
    if valor is None:
        return "NULL"
    if isinstance(valor, (int, float)):
        return str(valor)
    if isinstance(valor, (bytes, bytearray)):
        valor = valor.decode("utf-8")
    return "'" + str(valor).replace("\\", "\\\\").replace("'", "''") + "'"


def exportar(args):
    conexion = mysql.connector.connect(host=args.host, port=args.puerto, user=args.usuario,
                                       password=args.clave, database=args.bd)
    cursor = conexion.cursor()
    cursor.execute("SELECT VERSION()")
    version = cursor.fetchone()[0]
    cursor.execute("SHOW TABLES")
    tablas = [fila[0] for fila in cursor.fetchall()]

    lineas = [
        "-- " + "=" * 76,
        "-- ScriptBD_DSL_final.sql - Script FINAL de la base de datos (Laboratorio A7)",
        "-- Estructura y datos de la base después de procesar el archivo CSV con",
        "-- ProcesaSQL.py (solo se ejecutaron las sentencias válidas).",
        f"-- Generado: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}   Servidor MySQL: {version}",
        "-- " + "=" * 76,
        "",
        f"CREATE DATABASE IF NOT EXISTS `{args.bd}` DEFAULT CHARACTER SET utf8mb4;",
        f"USE `{args.bd}`;",
        "",
    ]
    resumen = []
    for tabla in tablas:
        cursor.execute(f"SHOW CREATE TABLE `{tabla}`")
        crear = cursor.fetchone()[1]
        cursor.execute(f"SELECT * FROM `{tabla}`")
        columnas = [d[0] for d in cursor.description]
        filas = cursor.fetchall()
        resumen.append(f"{tabla}: {len(filas)} registros")
        lineas += [f"-- Estructura de la tabla `{tabla}`", f"DROP TABLE IF EXISTS `{tabla}`;",
                   crear + ";", "", f"-- Datos de la tabla `{tabla}` ({len(filas)} registros)"]
        nombres = ", ".join(f"`{c}`" for c in columnas)
        for i in range(0, len(filas), 500):
            bloque = filas[i:i + 500]
            valores = ",\n".join("(" + ", ".join(literal_sql(v) for v in fila) + ")" for fila in bloque)
            lineas.append(f"INSERT INTO `{tabla}` ({nombres}) VALUES\n{valores};")
        lineas.append("")
    cursor.close()
    conexion.close()

    with open(SCRIPT_FINAL, "w", encoding="utf-8", newline="\n") as archivo:
        archivo.write("\n".join(lineas) + "\n")
    print(f"Script final generado: {SCRIPT_FINAL}")
    for linea in resumen:
        print(f"   {linea}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("accion", choices=["reiniciar", "exportar"])
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--puerto", type=int, default=PUERTO)
    parser.add_argument("--usuario", default=USUARIO)
    parser.add_argument("--clave", default=CLAVE)
    parser.add_argument("--bd", default=BASE_DATOS)
    args = parser.parse_args()
    try:
        reiniciar(args) if args.accion == "reiniciar" else exportar(args)
    except mysql.connector.Error as error:
        sys.exit(f"Error de MySQL: {error}")


if __name__ == "__main__":
    main()
