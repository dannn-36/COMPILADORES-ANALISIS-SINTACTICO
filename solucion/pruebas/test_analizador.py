"""
test_analizador.py - Pruebas automáticas del Analizador Estático de SQL.

Ejecutar desde la carpeta 'solucion':
    python -m unittest pruebas.test_analizador -v
"""

import os
import re
import sys
import unittest
from collections import Counter

AQUI = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(AQUI))

from analizador import AnalizadorSQL  # noqa: E402

# (sentencia, categoría esperada)
CASOS = [
    # ---------------- válidas
    ("select login, estado from usuarios where login = 'ana_g';", "VALIDA"),
    ("SELECT * FROM usuarios;", "VALIDA"),
    ("SELECT COUNT(*) FROM usuarios;", "VALIDA"),
    ("SELECT estado, COUNT(*) FROM usuarios GROUP BY estado;", "VALIDA"),
    ("SELECT login FROM usuarios ORDER BY login DESC LIMIT 5;", "VALIDA"),
    ("SELECT login AS usuario FROM usuarios WHERE estado = 'activo';", "VALIDA"),
    ("SELECT * FROM usuarios WHERE login LIKE 'juan%';", "VALIDA"),
    ("SELECT login FROM ubosquebd.usuarios WHERE login = 'user1';", "VALIDA"),
    ("SELECT u.login FROM usuarios u WHERE u.estado = 'activo';", "VALIDA"),
    ("SELECT * FROM usuarios WHERE login = \"ana_g\";", "VALIDA"),
    ("SELECT * FROM usuarios WHERE login = 'ana_g' AND password = 'pass123';", "VALIDA"),
    ("  SELECT login FROM usuarios WHERE login = 'user1' ;  ", "VALIDA"),
    ("INSERT INTO usuarios VALUES ('pedro', '123', 'activo');", "VALIDA"),
    ("INSERT INTO usuarios VALUES ('ana_x', 'b', 'activo'), ('dani', 'e', 'activo');", "VALIDA"),
    ("INSERT INTO usuarios SET login = 'zoe', password = '1', estado = 'activo';", "VALIDA"),
    ("INSERT INTO usuarios VALUES ('o''brien', 'x', 'activo');", "VALIDA"),
    ("UPDATE usuarios SET estado = 'activo' WHERE login IN ('ana_g', 'user1');", "VALIDA"),
    ("UPDATE usuarios SET estado = 'activo' WHERE login = 'ana_g' AND estado = 'inactivo';", "VALIDA"),
    ("DELETE FROM usuarios WHERE login = 'guest' LIMIT 1;", "VALIDA"),
    ("DELETE FROM usuarios WHERE login = 'guest'", "VALIDA"),
    ("\"INSERT INTO usuarios VALUES ('q', 'w', 'activo');\"", "VALIDA"),
    # ---------------- léxicas
    ("SELECT * FROM usuarios WHERE login = 'ana_g;", "LEXICO"),
    ("SELECT * FROM usuarios WHERE login = ?;", "LEXICO"),
    # ---------------- sintácticas
    ("SELECT login, FROM usuarios;", "SINTACTICO"),
    ("SELCT * FROM usuarios;", "SINTACTICO"),
    ("SELECT * FROM usuarios WHERE estado = 'activo' AND;", "SINTACTICO"),
    ("UPDATE usuarios SET estado 'activo' WHERE login = 'ana_g';", "SINTACTICO"),
    ("INSERT INTO usuarios VALUES ('a' 'b', 'c');", "SINTACTICO"),
    # ---------------- semánticas
    ("SELECT * FROM clientes WHERE id = 1;", "SEMANTICO"),
    ("SELECT nombre FROM usuarios;", "SEMANTICO"),
    ("SELECT login, COUNT(*) FROM usuarios;", "SEMANTICO"),
    ("SELECT x.login FROM usuarios u;", "SEMANTICO"),
    ("INSERT INTO usuarios VALUES ('pedro', '123');", "SEMANTICO"),
    ("INSERT INTO usuarios (login, clave, estado) VALUES ('pedro', '1', 'activo');", "SEMANTICO"),
    ("INSERT INTO usuarios VALUES ('usuario_con_nombre_largo', '123', 'activo');", "SEMANTICO"),
    ("INSERT INTO usuarios VALUES ('pedro', NULL, 'activo');", "SEMANTICO"),
    ("INSERT INTO usuarios (login, login, estado) VALUES ('a', 'b', 'c');", "SEMANTICO"),
    ("INSERT INTO usuarios VALUES ('a', 'b', 'c'), ('d', 'e');", "SEMANTICO"),
    ("UPDATE usuarios SET nombre = 'x' WHERE login = 'ana_g';", "SEMANTICO"),
    ("UPDATE usuarios SET password = 'una_clave_demasiado_larga' WHERE login = 'ana_g';", "SEMANTICO"),
    ("UPDATE usuarios SET estado = NULL WHERE login = 'ana_g';", "SEMANTICO"),
    ("UPDATE usuarios SET estado = 'activo', estado = 'inactivo' WHERE login = 'ana_g';", "SEMANTICO"),
    # ---------------- válidas pero peligrosas (no se ejecutan)
    ("SELECT * FROM usuarios WHERE login = 'admin' OR '1'='1';", "PELIGROSA"),
    ("SELECT * FROM usuarios WHERE login = 'admin' OR 1=1;", "PELIGROSA"),
    ("SELECT * FROM usuarios; DROP TABLE usuarios;", "PELIGROSA"),
    ("SELECT * FROM usuarios WHERE login = 'x' AND SLEEP(5);", "PELIGROSA"),
    ("INSERT INTO usuarios VALUES ('admin', 'x', 'activo') /*! , ('h','h','h') */;", "PELIGROSA"),
    ("UPDATE usuarios SET estado = 'activo';", "PELIGROSA"),
    ("UPDATE usuarios SET estado = 'activo' WHERE 1=1;", "PELIGROSA"),
    ("UPDATE usuarios SET estado = 'activo' WHERE login = 'ana_g' OR 1=1;", "PELIGROSA"),
    ("UPDATE usuarios SET estado = 'activo' WHERE login LIKE '%';", "PELIGROSA"),
    ("UPDATE usuarios SET estado = 'activo' WHERE estado = 'inactivo';", "PELIGROSA"),
    ("DELETE FROM usuarios;", "PELIGROSA"),
    ("DELETE FROM usuarios WHERE login != 'admin';", "PELIGROSA"),
    ("DELETE FROM usuarios WHERE login = 'guest' OR estado = 'inactivo';", "PELIGROSA"),
    ("TRUNCATE TABLE usuarios;", "PELIGROSA"),
    ("ALTER TABLE usuarios ADD COLUMN edad INT;", "PELIGROSA"),
    ("CREATE TABLE prueba (id INT);", "PELIGROSA"),
    ("DROP DATABASE ubosquebd;", "PELIGROSA"),
    ("GRANT ALL ON *.* TO 'x'@'%';", "PELIGROSA"),
    # ---------------- otras
    ("SHOW TABLES;", "NO_SOPORTADA"),
    ("-- solo un comentario", "OMITIDA"),
    ("", "OMITIDA"),
]

# Patrón del dataset (literales reemplazados por '?') -> categoría esperada
PATRONES_DATASET = {
    "INSERT INTO usuarios VALUES ('?', '?', '?');": "VALIDA",
    "INSERT INTO usuarios (login, password, estado) VALUES ('?', '?', '?');": "VALIDA",
    "SELECT login, estado FROM usuarios WHERE login = '?';": "VALIDA",
    "SELECT * FROM usuarios WHERE estado = '?' AND login != '?';": "VALIDA",
    "SELECT login FROM usuarios WHERE password = '?';": "VALIDA",
    "UPDATE usuarios SET estado = '?' WHERE login = '?';": "VALIDA",
    "UPDATE usuarios SET password = '?', estado = '?' WHERE login = '?';": "VALIDA",
    "DELETE FROM usuarios WHERE login = '?';": "VALIDA",
    "DROP TABLE IF EXISTS usuarios;": "PELIGROSA",
    "DROP TABLE usuarios;": "PELIGROSA",
    "DELETE FROM usuarios WHERE estado = '?';": "PELIGROSA",
    "SELECT FROM usuarios WHERE login = '?';": "SINTACTICO",
    "SELECT * FROM usuarios WHERE;": "SINTACTICO",
    "SELECT login estado FROM usuarios WHERE login = '?';": "SINTACTICO",
    "DELETE FROM WHERE estado = '?';": "SINTACTICO",
    "DELETE usuarios WHERE login = '?';": "SINTACTICO",
    "UPDATE SET password = '?' WHERE login = '?';": "SINTACTICO",
    "UPDATE usuarios SET password = '?' '?' WHERE login = '?';": "SINTACTICO",
    "DROP TABLE;": "SINTACTICO",
    "DROP usuarios;": "SINTACTICO",
    "INSERT usuarios VALUES ('?', '?', '?');": "SINTACTICO",
    "INSERT INTO usuarios (login, password) VALUES ('?');": "SEMANTICO",
}


class PruebasAnalizador(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.analizador = AnalizadorSQL()

    def test_casos_puntuales(self):
        for i, (sentencia, esperado) in enumerate(CASOS, start=1):
            with self.subTest(sentencia=sentencia):
                r = self.analizador.analizar(sentencia, i)
                self.assertEqual(esperado, r.categoria, r.motivo)
                if esperado not in ("VALIDA", "OMITIDA"):
                    self.assertTrue(r.motivo, "toda sentencia inválida debe tener motivo")

    def test_dataset_completo(self):
        ruta = os.path.join(AQUI, "..", "..", "dataset_sql_usuarios.csv")
        if not os.path.exists(ruta):
            self.skipTest("no se encontró dataset_sql_usuarios.csv")
        conteo = Counter()
        with open(ruta, encoding="utf-8-sig") as archivo:
            for n, linea in enumerate(archivo, start=1):
                patron = re.sub(r"'[^']*'", "'?'", linea.strip())
                r = self.analizador.analizar(linea, n)
                with self.subTest(linea=n):
                    self.assertIn(patron, PATRONES_DATASET, f"patrón no previsto: {linea}")
                    self.assertEqual(PATRONES_DATASET[patron], r.categoria, f"línea {n}: {linea}")
                conteo[r.categoria] += 1
        self.assertEqual(10000, sum(conteo.values()))
        self.assertEqual(3644, conteo["VALIDA"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
