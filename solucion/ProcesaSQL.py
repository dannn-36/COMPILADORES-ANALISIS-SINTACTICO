"""
ProcesaSQL.py - Procesador de sentencias SQL con Analizador Estático (ANTLR)
Compiladores - Laboratorio A7 - Análisis Semántico - Universidad El Bosque

Versión modificada del script entregado. Antes de ejecutar cada sentencia
del archivo CSV sobre MySQL, la evalúa con el analizador estático
(analizador.py, construido con ANTLR a partir de MiniSQL.g4):

  * Solo se ejecutan las sentencias VÁLIDAS.
  * Las válidas se guardan en      salida/<archivo>_validas.csv
  * Las inválidas (con motivo) en  salida/<archivo>_invalidas.csv
  * El detalle de todas las líneas salida/<archivo>_reporte.csv

Uso (desde la consola CMD, en la carpeta 'solucion'):
    python ProcesaSQL.py <archivo.csv>
    python ProcesaSQL.py <archivo.csv> --sin-bd          (solo análisis, sin MySQL)
    python ProcesaSQL.py <archivo.csv> --clave 12345678 --usuario root --host localhost
    python ProcesaSQL.py --ayuda
"""

import argparse
import csv
import os
import sys
import time
from collections import Counter

from analizador import (EJECUCION, LEXICO, NO_SOPORTADA, PELIGROSA, SEMANTICO, SINTACTICO,
                        AnalizadorSQL)

# Parámetros de conexión por defecto (los del script original)
HOST = "localhost"
PUERTO = 3306
USUARIO = "root"
CLAVE = "12345678"
BASE_DATOS = "ubosquebd"

# Mismo sql_mode por defecto de MySQL 8: el analizador asume estas reglas
SQL_MODE = ("ONLY_FULL_GROUP_BY,STRICT_TRANS_TABLES,NO_ZERO_IN_DATE,NO_ZERO_DATE,"
            "ERROR_FOR_DIVISION_BY_ZERO,NO_ENGINE_SUBSTITUTION")

SEPARADOR = "=" * 78


def leer_lineas(ruta: str) -> list[str]:
    """Lee el archivo CSV (UTF-8, con o sin BOM; si falla, Windows-1252)."""
    for codificacion in ("utf-8-sig", "cp1252"):
        try:
            with open(ruta, "r", encoding=codificacion, newline="") as archivo:
                return archivo.read().splitlines()
        except UnicodeDecodeError:
            continue
    raise SystemExit(f"No se pudo leer el archivo '{ruta}' (codificación desconocida).")


def conectar(args):
    """Abre la conexión a MySQL. Si no es posible, el proceso sigue solo con el análisis."""
    try:
        import mysql.connector
        conexion = mysql.connector.connect(host=args.host, port=args.puerto, user=args.usuario,
                                           password=args.clave, database=args.bd)
        cursor = conexion.cursor(buffered=True)
        try:
            cursor.execute(f"SET SESSION sql_mode = '{SQL_MODE}'")
        except Exception:
            pass
        print(f"Conectado a MySQL: {args.usuario}@{args.host}:{args.puerto}/{args.bd}")
        return conexion, cursor
    except Exception as error:
        print(f"[AVISO] No fue posible conectar a MySQL: {error}")
        print("[AVISO] Se realizará SOLO el análisis estático (ninguna sentencia se ejecutará).")
        return None, None


def ejecutar(conexion, cursor, resultado, max_filas: int):
    """Ejecuta una sentencia ya validada (igual que el script original)."""
    try:
        cursor.execute(resultado.sentencia)
        if cursor.description is not None:  # SELECT: mostrar resultados
            filas = cursor.fetchall()
            for fila in filas[:max_filas]:
                print(f"      {fila}")
            if len(filas) > max_filas:
                print(f"      ... ({len(filas)} filas en total, se muestran {max_filas})")
            elif not filas:
                print("      (la consulta no devolvió filas)")
            resultado.ejecucion = f"OK: {len(filas)} fila(s) consultada(s)"
        else:
            conexion.commit()
            print(f"      Filas afectadas: {cursor.rowcount}")
            resultado.ejecucion = f"OK: {cursor.rowcount} fila(s) afectada(s)"
    except Exception as error:
        try:
            conexion.rollback()
        except Exception:
            pass
        resultado.errores.append((EJECUCION, f"MySQL rechazó la sentencia al ejecutarla: {error}"))
        resultado.ejecucion = "ERROR"
        print(f"      [ERROR DE EJECUCIÓN] {error}")


def escribir_salidas(resultados, carpeta: str, base: str) -> tuple[str, str, str]:
    os.makedirs(carpeta, exist_ok=True)
    ruta_validas = os.path.join(carpeta, f"{base}_validas.csv")
    ruta_invalidas = os.path.join(carpeta, f"{base}_invalidas.csv")
    ruta_reporte = os.path.join(carpeta, f"{base}_reporte.csv")

    # 1. Válidas: mismo formato del archivo de entrada (una sentencia por línea),
    #    de modo que el archivo puede volver a procesarse sin ningún error.
    with open(ruta_validas, "w", encoding="utf-8", newline="") as archivo:
        for r in resultados:
            if r.valida:
                archivo.write(r.sentencia + ";\n")

    # 2. Inválidas: línea, sentencia, categoría y motivo
    with open(ruta_invalidas, "w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["linea", "sentencia", "categoria", "motivo"])
        for r in resultados:
            if not r.valida and not r.omitida:
                escritor.writerow([r.linea, r.texto, r.categoria, r.motivo])

    # 3. Reporte completo de trazabilidad
    with open(ruta_reporte, "w", encoding="utf-8-sig", newline="") as archivo:
        escritor = csv.writer(archivo)
        escritor.writerow(["linea", "resultado", "categoria", "tipo", "motivo", "ejecucion", "sentencia"])
        for r in resultados:
            estado = "OMITIDA" if r.omitida else ("VALIDA" if r.valida else "INVALIDA")
            escritor.writerow([r.linea, estado, r.categoria, r.tipo, r.motivo, r.ejecucion, r.texto])
    return ruta_validas, ruta_invalidas, ruta_reporte


def imprimir_resumen(args, resultados, rutas, conectado: bool, segundos: float):
    total = len(resultados)
    omitidas = sum(r.omitida for r in resultados)
    validas = [r for r in resultados if r.valida]
    invalidas = [r for r in resultados if not r.valida and not r.omitida]
    por_categoria = Counter(r.categoria for r in invalidas)
    print()
    print(SEPARADOR)
    print("RESUMEN DEL ANÁLISIS ESTÁTICO".center(78))
    print(SEPARADOR)
    print(f"Archivo analizado                : {args.archivo}")
    print(f"Líneas leídas                    : {total}")
    print(f"Líneas vacías o comentarios      : {omitidas}")
    print(f"Sentencias VÁLIDAS               : {len(validas)}"
          + ("  (ejecutadas en MySQL)" if conectado else "  (no se ejecutaron: modo sin BD)"))
    print(f"Sentencias INVÁLIDAS             : {len(invalidas)}")
    descripciones = [
        (LEXICO, "error léxico"),
        (SINTACTICO, "error de sintaxis"),
        (SEMANTICO, "error semántico"),
        (NO_SOPORTADA, "instrucción no soportada"),
        (PELIGROSA, "válida pero peligrosa: bloqueada"),
        (EJECUCION, "rechazada por MySQL"),
    ]
    for categoria, descripcion in descripciones:
        if por_categoria[categoria] or categoria != NO_SOPORTADA:
            print(f"   - {categoria:<13} {por_categoria[categoria]:>6}   {descripcion}")
    print(SEPARADOR)
    print("Archivos generados:")
    for ruta in rutas:
        print(f"   {ruta}")
    print(f"Tiempo total: {segundos:.2f} s")
    print(SEPARADOR)


def main():
    parser = argparse.ArgumentParser(
        prog="ProcesaSQL.py", add_help=False,
        description="Analizador estático de sentencias SQL (ANTLR) + ejecución controlada en MySQL.")
    parser.add_argument("archivo", nargs="?", help="archivo CSV con una sentencia SQL por línea")
    parser.add_argument("--sin-bd", action="store_true", help="solo analiza, no se conecta a MySQL")
    parser.add_argument("--host", default=HOST)
    parser.add_argument("--puerto", type=int, default=PUERTO)
    parser.add_argument("--usuario", default=USUARIO)
    parser.add_argument("--clave", default=CLAVE)
    parser.add_argument("--bd", default=BASE_DATOS)
    parser.add_argument("--salida", default="salida", help="carpeta de los archivos generados")
    parser.add_argument("--max-filas", type=int, default=10, help="filas a mostrar por cada SELECT")
    parser.add_argument("--solo-resumen", action="store_true", help="no muestra el detalle por línea")
    parser.add_argument("--permisivo", action="store_true",
                        help="acepta lo que MySQL tolera: INSERT sin INTO y alias sin AS")
    parser.add_argument("--ayuda", "-h", action="help", help="muestra esta ayuda")
    args = parser.parse_args()

    if not args.archivo:
        parser.print_help()
        sys.exit(1)
    if not os.path.isfile(args.archivo):
        sys.exit(f"No existe el archivo '{args.archivo}'.")

    inicio = time.time()
    lineas = leer_lineas(args.archivo)
    analizador = AnalizadorSQL(estricto=not args.permisivo)
    conexion, cursor = (None, None) if args.sin_bd else conectar(args)
    if args.sin_bd:
        print("Modo --sin-bd: solo análisis estático, no se ejecuta nada en MySQL.")

    print(SEPARADOR)
    print(f"Procesando '{args.archivo}' ({len(lineas)} líneas)")
    print(SEPARADOR)

    resultados = []
    for num_linea, linea in enumerate(lineas, start=1):
        resultado = analizador.analizar(linea, num_linea)
        resultados.append(resultado)
        if resultado.omitida:
            continue
        if not args.solo_resumen:
            print(f"Línea {num_linea}: {resultado.texto}")
        if resultado.valida:
            if conexion is not None:
                if not args.solo_resumen:
                    print(f"   [VÁLIDA - {resultado.tipo}] Ejecutando en MySQL...")
                    ejecutar(conexion, cursor, resultado, args.max_filas)
                else:
                    ejecutar_silencioso(conexion, cursor, resultado)
            elif not args.solo_resumen:
                print(f"   [VÁLIDA - {resultado.tipo}] (no se ejecuta: sin conexión a MySQL)")
        elif not args.solo_resumen:
            print(f"   [RECHAZADA - {resultado.categoria}] {resultado.motivo}")

    if conexion is not None:
        cursor.close()
        conexion.close()

    base = os.path.splitext(os.path.basename(args.archivo))[0]
    rutas = escribir_salidas(resultados, args.salida, base)
    imprimir_resumen(args, resultados, rutas, conexion is not None, time.time() - inicio)


def ejecutar_silencioso(conexion, cursor, resultado):
    salida_original = sys.stdout
    try:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")
        ejecutar(conexion, cursor, resultado, 0)
    finally:
        sys.stdout.close()
        sys.stdout = salida_original


if __name__ == "__main__":
    main()
