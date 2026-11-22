"""
analizador.py - Analizador Estático de sentencias SQL (ANTLR + Python)

Evalúa cada sentencia ANTES de enviarla a MySQL, en tres fases:

  1. Análisis LÉXICO     : MiniSQLLexer (generado por ANTLR desde MiniSQL.g4)
                           caracteres no válidos, cadenas sin cerrar, ...
  2. Análisis SINTÁCTICO : MiniSQLParser + EscuchaErroresSintacticos
                           estructura de la sentencia según la gramática.
  3. Análisis SEMÁNTICO  : AnalizadorSemantico (patrón Visitor generado por ANTLR)
                           recorre el árbol y lo valida contra la tabla de
                           símbolos (esquema.py): tablas/columnas existentes,
                           cantidad de valores, NOT NULL, longitudes, ...
                           y aplica las REGLAS DE SEGURIDAD: bloquea sentencias
                           válidas pero peligrosas (DROP, TRUNCATE, UPDATE o
                           DELETE masivos, inyección SQL, ...).

Cada sentencia termina con una de estas categorías:
    VALIDA        se puede ejecutar en MySQL sin inconvenientes
    LEXICO        error léxico
    SINTACTICO    error de sintaxis
    SEMANTICO     sintaxis correcta pero inconsistente con la base de datos
    NO_SOPORTADA  instrucción de consulta de metadatos (SHOW, DESCRIBE, ...)
    PELIGROSA     válida, pero NO debe ejecutarse (destructiva o masiva)
    EJECUCION     MySQL la rechazó al ejecutarla (asignada por ProcesaSQL.py)
"""

from __future__ import annotations

import csv
import difflib
import re
from dataclasses import dataclass, field

from antlr4 import CommonTokenStream, InputStream, Token
from antlr4.error.ErrorListener import ErrorListener

from esquema import BASE_DATOS, ESQUEMA, Columna, Tabla
from MiniSQLLexer import MiniSQLLexer
from MiniSQLParser import MiniSQLParser
from MiniSQLVisitor import MiniSQLVisitor

P = MiniSQLParser  # alias corto para los contextos del árbol

# ---------------------------------------------------------------------------
# Categorías de resultado
# ---------------------------------------------------------------------------
VALIDA = "VALIDA"
OMITIDA = "OMITIDA"
LEXICO = "LEXICO"
SINTACTICO = "SINTACTICO"
SEMANTICO = "SEMANTICO"
NO_SOPORTADA = "NO_SOPORTADA"
PELIGROSA = "PELIGROSA"
EJECUCION = "EJECUCION"

PRIORIDAD = {LEXICO: 0, SINTACTICO: 1, SEMANTICO: 2, NO_SOPORTADA: 3, PELIGROSA: 4, EJECUCION: 5}

# Funciones reconocidas
FUNCIONES_AGREGADAS = {"count", "sum", "avg", "min", "max", "group_concat"}
FUNCIONES_ESCALARES = {
    "upper", "lower", "ucase", "lcase", "length", "char_length", "character_length",
    "concat", "concat_ws", "trim", "ltrim", "rtrim", "substring", "substr", "left",
    "right", "reverse", "lpad", "rpad", "locate", "instr", "now", "curdate", "curtime",
    "current_date", "current_time", "current_timestamp", "date", "year", "month", "day",
    "md5", "sha1", "sha", "sha2", "coalesce", "ifnull", "nullif", "abs", "round",
    "floor", "ceil", "ceiling",
}
FUNCIONES_PELIGROSAS = {
    "sleep": "detiene el servidor (ataque de denegación de servicio / inyección a ciegas)",
    "benchmark": "consume CPU del servidor (denegación de servicio)",
    "load_file": "lee archivos del servidor",
    "get_lock": "bloquea recursos del servidor",
    "release_lock": "manipula bloqueos del servidor",
    "sys_exec": "ejecuta comandos del sistema operativo",
    "sys_eval": "ejecuta comandos del sistema operativo",
}

INSTRUCCIONES_DML = ["SELECT", "INSERT", "UPDATE", "DELETE", "DROP", "TRUNCATE"]

# Instrucciones que se reconocen solo para bloquearlas (sentenciaNoPermitida)
NO_PERMITIDAS = {
    "ALTER": "modifica la estructura de la tabla",
    "CREATE": "crea objetos en la base de datos",
    "RENAME": "renombra tablas",
    "GRANT": "otorga permisos a usuarios",
    "REVOKE": "retira permisos a usuarios",
    "REPLACE": "puede borrar y reinsertar registros",
    "LOAD": "carga archivos en el servidor",
    "CALL": "ejecuta procedimientos almacenados",
    "LOCK": "bloquea tablas",
    "UNLOCK": "libera bloqueos de tablas",
    "SHUTDOWN": "apaga el servidor de base de datos",
    "KILL": "termina conexiones del servidor",
    "USE": "cambia la base de datos de trabajo",
    "SET": "modifica variables de la sesión o del servidor",
    "BEGIN": "altera el control de transacciones del proceso",
    "START": "altera el control de transacciones del proceso",
    "COMMIT": "altera el control de transacciones del proceso",
    "ROLLBACK": "altera el control de transacciones del proceso",
    "HANDLER": "accede a la tabla saltándose el optimizador",
    "DO": "evalúa expresiones arbitrarias",
}
SOLO_METADATOS = {"SHOW", "DESCRIBE", "DESC", "EXPLAIN"}

TOKENS_INICIO = {
    MiniSQLLexer.SELECT, MiniSQLLexer.INSERT, MiniSQLLexer.UPDATE, MiniSQLLexer.DELETE,
    MiniSQLLexer.DROP, MiniSQLLexer.TRUNCATE,
} | {getattr(MiniSQLLexer, n) for n in list(NO_PERMITIDAS) + list(SOLO_METADATOS)}

TOKENS_IDENTIFICADOR = {
    MiniSQLLexer.ID, MiniSQLLexer.ID_COMILLAS, MiniSQLLexer.VALUE, MiniSQLLexer.OFFSET,
    MiniSQLLexer.TEMPORARY, MiniSQLLexer.BEGIN, MiniSQLLexer.START, MiniSQLLexer.COMMIT,
    MiniSQLLexer.ROLLBACK, MiniSQLLexer.HANDLER, MiniSQLLexer.DO, MiniSQLLexer.SHUTDOWN,
}
TOKENS_VALOR = {
    MiniSQLLexer.CADENA, MiniSQLLexer.NUMERO, MiniSQLLexer.NULL, MiniSQLLexer.TRUE,
    MiniSQLLexer.FALSE, MiniSQLLexer.MENOS,
}


# ---------------------------------------------------------------------------
# Resultado del análisis de una línea
# ---------------------------------------------------------------------------
@dataclass
class Resultado:
    linea: int
    texto: str                 # sentencia tal como viene (sin espacios extremos)
    sentencia: str = ""        # sentencia a ejecutar (sin ';' final)
    tipo: str = ""             # SELECT, INSERT, UPDATE, DELETE, DROP TABLE, ...
    errores: list[tuple[str, str]] = field(default_factory=list)
    omitida: bool = False      # línea vacía o solo comentario
    ejecucion: str = ""        # resultado de la ejecución en MySQL

    @property
    def valida(self) -> bool:
        return not self.omitida and not self.errores

    @property
    def es_consulta(self) -> bool:
        return self.tipo == "SELECT"

    @property
    def categoria(self) -> str:
        if self.omitida:
            return OMITIDA
        if not self.errores:
            return VALIDA
        return min((c for c, _ in self.errores), key=PRIORIDAD.__getitem__)

    @property
    def motivo(self) -> str:
        ordenados = sorted(self.errores, key=lambda e: PRIORIDAD[e[0]])
        if len(ordenados) == 1:
            return ordenados[0][1]
        return " | ".join(f"[{c}] {m}" for c, m in ordenados)


# ---------------------------------------------------------------------------
# Utilidades
# ---------------------------------------------------------------------------
_ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0", "b": "\b", "Z": "\x1a"}
_PREFIJO_NUMERICO = re.compile(r"^\s*[+-]?(\d+(\.\d*)?|\.\d+)([eE][+-]?\d+)?")


def decodificar_cadena(token: str) -> str:
    """Convierte el texto de un literal MySQL ('it''s', 'a\\'b') en su valor real."""
    comilla, cuerpo = token[0], token[1:-1]
    salida, i = [], 0
    while i < len(cuerpo):
        c = cuerpo[i]
        if c == "\\" and i + 1 < len(cuerpo):
            salida.append(_ESCAPES.get(cuerpo[i + 1], cuerpo[i + 1]))
            i += 2
        elif c == comilla and i + 1 < len(cuerpo) and cuerpo[i + 1] == comilla:
            salida.append(comilla)
            i += 2
        else:
            salida.append(c)
            i += 1
    return "".join(salida)


def a_numero(valor):
    """Conversión implícita de MySQL de un valor a número ('12abc' -> 12, 'abc' -> 0)."""
    if valor is None or isinstance(valor, (int, float)):
        return valor
    m = _PREFIJO_NUMERICO.match(str(valor))
    return float(m.group(0)) if m else 0


def texto_original(ctx) -> str:
    """Texto del fragmento del árbol tal como se escribió (con espacios)."""
    if ctx is None or ctx.start is None or ctx.stop is None:
        return ""
    return ctx.start.getInputStream().getText(ctx.start.start, ctx.stop.stop)


def nombre_identificador(ctx) -> str:
    texto = ctx.getText()
    if texto.startswith("`"):
        return texto[1:-1].replace("``", "`")
    return texto


def sugerir(palabra: str, opciones) -> str:
    cercanas = difflib.get_close_matches(palabra.lower(), list(opciones), n=1, cutoff=0.6)
    return f" (¿quiso decir '{cercanas[0]}'?)" if cercanas else ""


def operandos(ctx) -> list:
    return ctx.getTypedRuleContexts(P.OperandoContext)


def lista_texto(items) -> str:
    items = list(items)
    if len(items) <= 1:
        return "".join(items)
    return ", ".join(items[:-1]) + " o " + items[-1]


def constante(op):
    """(True, valor) si el operando es un literal; (False, None) en otro caso."""
    if isinstance(op, P.OperandoNegativoContext):
        es_const, valor = constante(op.operando())
        if es_const:
            return True, (None if valor is None else -a_numero(valor))
        return False, None
    if isinstance(op, P.OperandoLiteralContext):
        lit = op.literal()
        if lit.CADENA():
            return True, "".join(decodificar_cadena(c.getText()) for c in lit.CADENA())
        if lit.NUMERO():
            return True, a_numero(lit.getText())
        if lit.NULL():
            return True, None
        return True, 1 if lit.TRUE() else 0
    return False, None


def columna_de(op) -> str | None:
    if isinstance(op, P.OperandoColumnaContext):
        return nombre_identificador(op.columnaRef().columna).lower()
    return None


def comparar(a, b, operador: str):
    """Evalúa una comparación entre constantes con la semántica de MySQL."""
    if operador == "<=>":
        if a is None or b is None:
            return a is None and b is None
        operador = "="
    if a is None or b is None:
        return None  # comparar con NULL da NULL (desconocido)
    if isinstance(a, str) and isinstance(b, str):
        a, b = a.lower(), b.lower()  # cotejamiento *_ci: no distingue mayúsculas
    else:
        a, b = a_numero(a), a_numero(b)
    return {
        "=": a == b, "!=": a != b, "<>": a != b, "<": a < b,
        ">": a > b, "<=": a <= b, ">=": a >= b,
    }[operador]


def es_verdadero(valor) -> bool:
    return valor is not None and a_numero(valor) != 0


def like_a_regex(patron: str) -> re.Pattern:
    partes, i = [], 0
    while i < len(patron):
        c = patron[i]
        if c == "\\" and i + 1 < len(patron):
            partes.append(re.escape(patron[i + 1]))
            i += 2
            continue
        partes.append(".*" if c == "%" else "." if c == "_" else re.escape(c))
        i += 1
    return re.compile("".join(partes), re.IGNORECASE | re.DOTALL)


def siempre_verdadera(cond, tabla: Tabla | None) -> bool:
    """True si la condición es verdadera para TODOS los registros (tautología)."""
    if isinstance(cond, P.CondicionParentesisContext):
        return siempre_verdadera(cond.condicion(), tabla)
    if isinstance(cond, P.CondicionAndContext):
        return all(siempre_verdadera(c, tabla) for c in cond.condicion())
    if isinstance(cond, P.CondicionOrContext):
        return any(siempre_verdadera(c, tabla) for c in cond.condicion())
    if isinstance(cond, P.CondicionNotContext):
        return False
    if not isinstance(cond, P.CondicionPredicadoContext):
        return False

    pred = cond.predicado()
    ops = operandos(pred)
    consts = [constante(o) for o in ops]
    todos_constantes = all(es for es, _ in consts)
    valores = [v for _, v in consts]

    def columna_no_nula(op) -> bool:
        nombre = columna_de(op)
        col = tabla.columnas.get(nombre) if (tabla and nombre) else None
        return col is not None and not col.admite_nulo

    if isinstance(pred, P.PredicadoComparacionContext):
        operador = pred.operadorComparacion().getText()
        if todos_constantes:
            return comparar(valores[0], valores[1], operador) is True
        izq, der = columna_de(ops[0]), columna_de(ops[1])
        return izq is not None and izq == der and operador in ("=", "<=", ">=", "<=>")
    if isinstance(pred, P.PredicadoIsContext):
        negado = pred.NOT() is not None
        if pred.NULL():
            if todos_constantes:
                return (valores[0] is None) != negado
            return negado and columna_no_nula(ops[0])
        return False
    if isinstance(pred, P.PredicadoLikeContext):
        if pred.NOT() is None and consts[1][0] and isinstance(valores[1], str):
            if valores[1] and set(valores[1]) == {"%"}:
                return columna_no_nula(ops[0]) or (consts[0][0] and valores[0] is not None)
            if consts[0][0] and valores[0] is not None:
                return bool(like_a_regex(valores[1]).fullmatch(str(valores[0])))
        return False
    if isinstance(pred, P.PredicadoInContext):
        if todos_constantes and pred.NOT() is None:
            return any(comparar(valores[0], v, "=") is True for v in valores[1:])
        return False
    if isinstance(pred, P.PredicadoBetweenContext):
        if todos_constantes and pred.NOT() is None:
            return comparar(valores[0], valores[1], ">=") is True and comparar(valores[0], valores[2], "<=") is True
        return False
    if isinstance(pred, P.PredicadoSimpleContext):
        return todos_constantes and es_verdadero(valores[0])
    return False


def or_con_tautologia(cond, tabla) -> bool:
    """Detecta '... OR <siempre verdadero>' (patrón clásico de inyección SQL)."""
    if isinstance(cond, P.CondicionOrContext):
        a, b = cond.condicion()
        if siempre_verdadera(a, tabla) or siempre_verdadera(b, tabla):
            return True
        return or_con_tautologia(a, tabla) or or_con_tautologia(b, tabla)
    if isinstance(cond, P.CondicionAndContext):
        return any(or_con_tautologia(c, tabla) for c in cond.condicion())
    if isinstance(cond, (P.CondicionNotContext, P.CondicionParentesisContext)):
        return or_con_tautologia(cond.condicion(), tabla)
    return False


def es_selectiva(cond, claves: tuple[str, ...]) -> bool:
    """True si la condición limita la operación a registros puntuales, es decir,
    exige igualdad (= / IN) entre la columna identificadora y un valor."""
    if isinstance(cond, P.CondicionParentesisContext):
        return es_selectiva(cond.condicion(), claves)
    if isinstance(cond, P.CondicionAndContext):
        return any(es_selectiva(c, claves) for c in cond.condicion())
    if isinstance(cond, P.CondicionOrContext):
        return all(es_selectiva(c, claves) for c in cond.condicion())
    if not isinstance(cond, P.CondicionPredicadoContext):
        return False
    pred = cond.predicado()
    ops = operandos(pred)
    if isinstance(pred, P.PredicadoComparacionContext):
        if pred.operadorComparacion().getText() not in ("=", "<=>"):
            return False
        for col, val in ((ops[0], ops[1]), (ops[1], ops[0])):
            es_const, valor = constante(val)
            if columna_de(col) in claves and es_const and valor is not None:
                return True
        return False
    if isinstance(pred, P.PredicadoInContext) and pred.NOT() is None:
        return columna_de(ops[0]) in claves and all(constante(o)[0] for o in ops[1:])
    return False


# ---------------------------------------------------------------------------
# Fase 2: errores sintácticos (escucha de errores de ANTLR, en español)
# ---------------------------------------------------------------------------
class EscuchaErroresSintacticos(ErrorListener):
    """Reemplaza al ConsoleErrorListener de ANTLR: guarda el PRIMER error de
    sintaxis y lo traduce a un mensaje entendible en español."""

    def __init__(self):
        super().__init__()
        self.errores: list[str] = []

    def syntaxError(self, recognizer, offendingSymbol, line, column, msg, e):
        if self.errores:
            return  # los siguientes suelen ser consecuencia del primero
        encontrado = self._describir_token(offendingSymbol)
        try:
            esperado = self._describir_esperados(recognizer, recognizer.getExpectedTokens())
        except Exception:
            esperado = ""
        if msg.startswith("missing"):
            detalle = f"falta {esperado or 'un elemento'} antes de {encontrado}"
        elif msg.startswith("extraneous"):
            detalle = f"sobra {encontrado}" + (f"; se esperaba {esperado}" if esperado else "")
        elif msg.startswith("mismatched"):
            detalle = f"se encontró {encontrado} pero se esperaba {esperado or 'otro elemento'}"
        else:
            detalle = f"estructura no válida cerca de {encontrado}"
        self.errores.append(f"Error de sintaxis en la posición {column + 1}: {detalle}.")

    @staticmethod
    def _describir_token(token) -> str:
        if token is None or token.type == Token.EOF:
            return "el final de la sentencia"
        if token.type == MiniSQLLexer.CADENA:
            return f"el texto {token.text}"
        return f"'{token.text}'"

    @staticmethod
    def _describir_esperados(parser, conjunto) -> str:
        tipos = set(conjunto) if conjunto is not None else set()
        partes = []
        if tipos & TOKENS_IDENTIFICADOR:
            partes.append("un nombre de tabla o columna")
        if tipos & TOKENS_VALOR:
            partes.append("un valor")
        for t in sorted(tipos - TOKENS_IDENTIFICADOR - TOKENS_VALOR):
            if t == Token.EOF:
                partes.append("el final de la sentencia")
            elif 0 < t < len(parser.literalNames) and parser.literalNames[t] != "<INVALID>":
                literal = parser.literalNames[t].strip("'")
                partes.append(literal if literal.isalpha() else f"'{literal}'")
        if len(partes) > 8:
            partes = partes[:8] + ["..."]
        return lista_texto(partes)


# ---------------------------------------------------------------------------
# Fase 3: análisis semántico (Visitor sobre el árbol sintáctico)
# ---------------------------------------------------------------------------
@dataclass
class Valor:
    """Información semántica de un operando."""
    clase: str                      # cadena | numero | null | booleano | columna | funcion
    texto: str
    dato: object = None             # valor del literal
    columna: Columna | None = None
    agregada: bool = False          # contiene COUNT/SUM/...
    columnas_libres: list[str] = field(default_factory=list)  # columnas fuera de agregación
    cadenas: int = 1                # cadenas consecutivas ('a' 'b' -> 2)


class AnalizadorSemantico(MiniSQLVisitor):

    def __init__(self, esquema: dict[str, Tabla], base_datos: str, estricto: bool = True):
        super().__init__()
        self.esquema = esquema
        self.base_datos = base_datos
        self.estricto = estricto
        self.errores: list[tuple[str, str]] = []
        self.tipos: list[str] = []
        self._reiniciar()

    # ----------------------------------------------------------- utilidades
    def _reiniciar(self):
        self.tabla: Tabla | None = None
        self.calificadores: set[str] = set()
        self.alias_select: set[str] = set()
        self.sin_from = False
        self.tipo = "?"

    def error(self, categoria: str, mensaje: str):
        if (categoria, mensaje) not in self.errores:
            self.errores.append((categoria, mensaje))

    def _columnas_disponibles(self) -> str:
        return ", ".join(self.tabla.nombres_columnas()) if self.tabla else ""

    def resolver_tabla(self, ctx_nombre, exigir: bool = True) -> Tabla | None:
        if ctx_nombre.baseDatos is not None:
            bd = nombre_identificador(ctx_nombre.baseDatos)
            if bd.lower() != self.base_datos.lower():
                self.error(SEMANTICO, f"La base de datos '{bd}' no es la base de trabajo "
                                      f"('{self.base_datos}').")
                return None
        nombre = nombre_identificador(ctx_nombre.tabla)
        tabla = self.esquema.get(nombre.lower())
        if tabla is None and exigir:
            self.error(SEMANTICO, f"La tabla '{nombre}' no existe en la base de datos "
                                  f"'{self.base_datos}'{sugerir(nombre, self.esquema)}.")
        return tabla

    def fijar_tabla(self, ctx_tabla_ref):
        """Registra la tabla de la sentencia (y su alias) en el contexto."""
        self.tabla = self.resolver_tabla(ctx_tabla_ref.nombreTabla())
        alias = ctx_tabla_ref.aliasTabla if hasattr(ctx_tabla_ref, "aliasTabla") else None
        if alias is not None:
            self.calificadores = {nombre_identificador(alias).lower()}
        else:
            self.calificadores = {nombre_identificador(ctx_tabla_ref.nombreTabla().tabla).lower()}

    def resolver_columna(self, ctx_col, permitir_alias: bool = False) -> Columna | None:
        nombre = nombre_identificador(ctx_col.columna)
        if ctx_col.calificador is not None:
            calificador = nombre_identificador(ctx_col.calificador)
            if calificador.lower() not in self.calificadores:
                self.error(SEMANTICO, f"'{calificador}.{nombre}': '{calificador}' no corresponde "
                                      f"a la tabla (o alias) usada en la sentencia.")
                return None
        elif permitir_alias and nombre.lower() in self.alias_select:
            return None
        if self.sin_from:
            self.error(SEMANTICO, f"Se usa la columna '{nombre}' pero la consulta no tiene "
                                  f"cláusula FROM.")
            return None
        if self.tabla is None:
            return None  # la tabla no existe o falta: ya se reportó
        columna = self.tabla.columnas.get(nombre.lower())
        if columna is None:
            self.error(SEMANTICO, f"La columna '{nombre}' no existe en la tabla "
                                  f"'{self.tabla.nombre}'{sugerir(nombre, self.tabla.columnas)}. "
                                  f"Columnas disponibles: {self._columnas_disponibles()}.")
        return columna

    # ------------------------------------------------------------- operandos
    def analizar_operando(self, ctx, lugar: str, asignada_a: str | None = None) -> Valor:
        """lugar: SELECT | WHERE | HAVING | GROUP | ORDER | VALOR"""
        if isinstance(ctx, P.OperandoNegativoContext):
            v = self.analizar_operando(ctx.operando(), lugar, asignada_a)
            v.texto = "-" + v.texto
            if v.clase in ("cadena", "numero", "booleano"):
                v.clase, v.dato = "numero", -a_numero(v.dato)
            return v
        if isinstance(ctx, P.OperandoLiteralContext):
            return self.analizar_literal(ctx.literal(), asignada_a)
        if isinstance(ctx, P.OperandoFuncionContext):
            return self.analizar_funcion(ctx.llamadaFuncion(), lugar)
        ref = ctx.columnaRef()
        col = self.resolver_columna(ref, permitir_alias=lugar in ("ORDER", "HAVING", "GROUP"))
        nombre = nombre_identificador(ref.columna).lower()
        return Valor("columna", ref.getText(), columna=col, columnas_libres=[nombre])

    def analizar_literal(self, ctx, asignada_a: str | None = None) -> Valor:
        cadenas = ctx.CADENA()
        if cadenas:
            partes = [decodificar_cadena(c.getText()) for c in cadenas]
            valor = Valor("cadena", texto_original(ctx), "".join(partes), cadenas=len(cadenas))
            if len(cadenas) > 1:
                textos = " ".join(c.getText() for c in cadenas)
                if asignada_a:
                    pista = (f"en la asignación de '{asignada_a}' faltan la coma y el nombre de "
                             f"la siguiente columna (p. ej. \", estado = ...\")")
                else:
                    pista = "falta la coma que separa los valores"
                self.error(SINTACTICO, f"Textos consecutivos sin separador {textos}: {pista}. "
                                       f"MySQL los uniría en un solo texto ('{valor.dato}').")
            return valor
        if ctx.NUMERO():
            return Valor("numero", ctx.getText(), a_numero(ctx.getText()))
        if ctx.NULL():
            return Valor("null", "NULL", None)
        return Valor("booleano", ctx.getText().upper(), 1 if ctx.TRUE() else 0)

    def analizar_funcion(self, ctx, lugar: str) -> Valor:
        nombre = nombre_identificador(ctx.nombre).lower()
        argumentos = [self.analizar_operando(o, lugar) for o in operandos(ctx)]
        agregada = nombre in FUNCIONES_AGREGADAS
        if nombre in FUNCIONES_PELIGROSAS:
            self.error(PELIGROSA, f"La función {nombre.upper()}() no está permitida: "
                                  f"{FUNCIONES_PELIGROSAS[nombre]}.")
        elif not agregada and nombre not in FUNCIONES_ESCALARES:
            self.error(SEMANTICO, f"La función '{nombre}' no existe o no está soportada"
                                  f"{sugerir(nombre, FUNCIONES_AGREGADAS | FUNCIONES_ESCALARES)}.")
        if ctx.ASTERISCO() is not None and nombre != "count":
            self.error(SINTACTICO, f"Solo COUNT admite '*' como argumento; "
                                   f"{nombre.upper()}(*) no es válido.")
        if agregada and not argumentos and ctx.ASTERISCO() is None:
            self.error(SINTACTICO, f"La función {nombre.upper()}() requiere un argumento.")
        if agregada and lugar in ("WHERE", "VALOR"):
            donde = "la cláusula WHERE" if lugar == "WHERE" else "un valor a guardar"
            self.error(SEMANTICO, f"Uso inválido de la función de agregación {nombre.upper()}() "
                                  f"en {donde} (MySQL error 1111); use HAVING.")
        libres = [] if agregada else [c for a in argumentos for c in a.columnas_libres]
        return Valor("funcion", ctx.getText(), agregada=agregada or any(a.agregada for a in argumentos),
                     columnas_libres=libres)

    def validar_valor(self, columna: Columna | None, valor: Valor):
        """Compatibilidad entre el valor y la definición de la columna."""
        if columna is None:
            return
        if valor.clase == "null" and not columna.admite_nulo:
            self.error(SEMANTICO, f"La columna '{columna.nombre}' es NOT NULL y no admite el valor "
                                  f"NULL (MySQL error 1048).")
        if columna.longitud and valor.cadenas == 1 and valor.clase in ("cadena", "numero", "booleano"):
            contenido = valor.dato if valor.clase == "cadena" else valor.texto
            if len(contenido) > columna.longitud:
                self.error(SEMANTICO, f"El valor '{contenido}' tiene {len(contenido)} caracteres y la "
                                      f"columna '{columna.nombre}' es {columna.describir()}: excede la "
                                      f"longitud máxima (MySQL error 1406, Data too long).")

    # ----------------------------------------------------------- condiciones
    def analizar_condicion(self, ctx, lugar: str):
        if isinstance(ctx, P.CondicionPredicadoContext):
            for op in operandos(ctx.predicado()):
                self.analizar_operando(op, lugar)
        else:
            for sub in ctx.getTypedRuleContexts(P.CondicionContext):
                self.analizar_condicion(sub, lugar)

    def analizar_where(self, ctx_where):
        """Valida la cláusula WHERE. Retorna la condición (o None)."""
        if ctx_where is None:
            return None
        cond = ctx_where.condicion()
        if cond is None:
            self.error(SINTACTICO, "La cláusula WHERE está vacía: falta la condición después de "
                                   "WHERE (p. ej. WHERE login = 'valor').")
            return None
        self.analizar_condicion(cond, "WHERE")
        return cond

    def revisar_orden_y_limite(self, ctx, num_columnas: int | None = None):
        orden = ctx.clausulaOrderBy()
        if orden is not None:
            for elemento in orden.elementoOrden():
                op = elemento.operando()
                es_const, valor = constante(op)
                if es_const and isinstance(valor, (int, float)):
                    if num_columnas is not None and not 1 <= valor <= num_columnas:
                        self.error(SEMANTICO, f"ORDER BY {op.getText()}: la posición está fuera del "
                                              f"rango de columnas del SELECT (1 a {num_columnas}).")
                else:
                    self.analizar_operando(op, "ORDER")
        limite = ctx.clausulaLimit()
        if limite is not None:
            for numero in limite.NUMERO():
                if not numero.getText().isdigit():
                    self.error(SINTACTICO, f"LIMIT solo admite números enteros "
                                           f"(se encontró {numero.getText()}).")

    def revisar_operacion_masiva(self, ctx_where, cond, instruccion: str):
        """Regla de seguridad para UPDATE / DELETE."""
        accion = "actualización" if instruccion == "UPDATE" else "eliminación"
        if ctx_where is None:
            self.error(PELIGROSA, f"{instruccion} sin cláusula WHERE: {accion} masiva que afectaría "
                                  f"TODOS los registros de la tabla.")
            return
        if cond is None or self.tabla is None:
            return  # WHERE vacío o tabla inválida: ya se reportó
        claves = self.tabla.claves
        if siempre_verdadera(cond, self.tabla):
            self.error(PELIGROSA, f"{instruccion} con una condición que siempre es verdadera "
                                  f"(WHERE {texto_original(cond)}): {accion} masiva de todos los "
                                  f"registros.")
        elif not es_selectiva(cond, claves):
            self.error(PELIGROSA, f"{accion.capitalize()} masiva: la condición WHERE "
                                  f"{texto_original(cond)} no filtra por la columna identificadora "
                                  f"({', '.join(claves)}) con '=' o IN, por lo que puede afectar "
                                  f"muchos registros a la vez.")

    # ---------------------------------------------------------- sentencias
    def visitScript(self, ctx: P.ScriptContext):
        sentencias = ctx.sentencia()
        if len(sentencias) > 1:
            self.error(PELIGROSA, f"La línea contiene {len(sentencias)} sentencias separadas por ';'. "
                                  f"Solo se permite una sentencia por línea (las sentencias apiladas "
                                  f"son una técnica de inyección SQL).")
        for sentencia in sentencias:
            self._reiniciar()
            self.visit(sentencia)
            self.tipos.append(self.tipo)

    # ---- SELECT
    def visitSentenciaSelect(self, ctx: P.SentenciaSelectContext):
        self.tipo = "SELECT"
        if ctx.tablaRef() is not None:
            self.fijar_tabla(ctx.tablaRef())
        else:
            self.sin_from = True

        lista = ctx.listaSeleccion()
        if lista is None:
            self.error(SINTACTICO, "Falta la lista de columnas entre SELECT y FROM: indique '*' o "
                                   "los nombres de las columnas (p. ej. SELECT login, estado FROM ...).")
            elementos = []
        else:
            elementos = lista.elementoSeleccion()

        valores: list[Valor] = []
        hay_asterisco = False
        for i, el in enumerate(elementos):
            if isinstance(el, P.SeleccionTodoContext):
                hay_asterisco = True
                if i > 0:
                    self.error(SINTACTICO, "El '*' debe ser el primer elemento de la lista del SELECT "
                                           "(o califíquelo: usuarios.*).")
                if self.sin_from:
                    self.error(SEMANTICO, "SELECT * requiere la cláusula FROM con la tabla a consultar.")
            elif isinstance(el, P.SeleccionTodoTablaContext):
                hay_asterisco = True
                calificador = nombre_identificador(el.tabla)
                if calificador.lower() not in self.calificadores:
                    self.error(SEMANTICO, f"'{calificador}.*': '{calificador}' no corresponde a la "
                                          f"tabla de la consulta.")
            else:
                expresion = el.operando()
                valores.append(self.analizar_operando(expresion, "SELECT"))
                if el.aliasImplicito is not None:
                    alias = nombre_identificador(el.aliasImplicito)
                    self.alias_select.add(alias.lower())
                    columnas_tabla = self.tabla.columnas if self.tabla else {}
                    if alias.lower() in columnas_tabla:
                        self.error(SINTACTICO, f"Falta una coma entre '{expresion.getText()}' y '{alias}'. "
                                               f"Sin la coma, MySQL toma '{alias}' como un alias de "
                                               f"'{expresion.getText()}' y la consulta no devolvería la "
                                               f"columna '{alias}'.")
                    elif self.estricto:
                        self.error(SINTACTICO, f"Alias '{alias}' sin la palabra AS (¿falta una coma "
                                               f"después de '{expresion.getText()}'?). Si es un alias, "
                                               f"escríbalo como '{expresion.getText()} AS {alias}'.")
                elif el.alias is not None:
                    texto_alias = el.alias.getText()
                    if texto_alias[:1] in "'\"":
                        texto_alias = decodificar_cadena(texto_alias)
                    self.alias_select.add(texto_alias.strip("`").lower())

        cond = self.analizar_where(ctx.clausulaWhere())
        if cond is not None and or_con_tautologia(cond, self.tabla):
            self.error(PELIGROSA, f"La condición WHERE {texto_original(cond)} contiene un OR con una "
                                  f"expresión siempre verdadera (p. ej. OR 1=1): patrón típico de "
                                  f"inyección SQL que expone todos los registros.")

        # GROUP BY / funciones de agregación (sql_mode ONLY_FULL_GROUP_BY de MySQL 8)
        agrupadas: set[str] = set()
        if ctx.clausulaGroupBy() is not None:
            for op in operandos(ctx.clausulaGroupBy()):
                valor = self.analizar_operando(op, "GROUP")
                agrupadas.update(valor.columnas_libres)
        usa_agregacion = any(v.agregada for v in valores)
        if usa_agregacion or ctx.clausulaGroupBy() is not None:
            if hay_asterisco and not (self.tabla and set(self.tabla.columnas) <= agrupadas):
                self.error(SEMANTICO, "No se puede combinar '*' con funciones de agregación o GROUP BY "
                                      "(MySQL ONLY_FULL_GROUP_BY).")
            for valor in valores:
                for columna in valor.columnas_libres:
                    if columna in agrupadas:
                        continue
                    if ctx.clausulaGroupBy() is not None:
                        self.error(SEMANTICO, f"La columna '{columna}' del SELECT no está en el GROUP BY "
                                              f"ni dentro de una función de agregación (MySQL error 1055).")
                    else:
                        self.error(SEMANTICO, f"La consulta mezcla funciones de agregación con la columna "
                                              f"'{columna}' sin GROUP BY (MySQL error 1140).")
        if ctx.clausulaHaving() is not None:
            self.analizar_condicion(ctx.clausulaHaving().condicion(), "HAVING")
        self.revisar_orden_y_limite(ctx, None if hay_asterisco else len(elementos) or None)

    # ---- INSERT
    def _inicio_insert(self, ctx) -> None:
        self.tipo = "INSERT"
        if ctx.INTO() is None and self.estricto:
            self.error(SINTACTICO, "Falta la palabra clave INTO después de INSERT: la forma correcta es "
                                   "INSERT INTO usuarios ... (MySQL la tolera como opcional, pero el "
                                   "analizador exige la sintaxis estándar de SQL).")
        if ctx.nombreTabla() is None:
            self.error(SINTACTICO, "Falta el nombre de la tabla en la sentencia INSERT.")
            self.tabla = None
        else:
            self.tabla = self.resolver_tabla(ctx.nombreTabla())
            self.calificadores = {nombre_identificador(ctx.nombreTabla().tabla).lower()}

    def _revisar_obligatorias(self, indicadas: list[str]):
        if self.tabla is None:
            return
        faltantes = [c.nombre for c in self.tabla.columnas.values()
                     if c.obligatoria and c.nombre.lower() not in indicadas]
        if faltantes:
            self.error(SEMANTICO, f"No se indicó valor para la(s) columna(s) obligatoria(s) "
                                  f"{', '.join(faltantes)} (NOT NULL y sin valor por defecto): MySQL "
                                  f"rechazaría la inserción (error 1364).")

    def visitInsertValues(self, ctx: P.InsertValuesContext):
        self._inicio_insert(ctx)
        explicitas = ctx.PAR_IZQ() is not None
        columnas: list[Columna | None] = []
        nombres: list[str] = []
        if explicitas:
            lista = ctx.listaColumnas()
            for ref in (lista.columnaRef() if lista is not None else []):
                nombre = nombre_identificador(ref.columna).lower()
                if nombre in nombres:
                    self.error(SEMANTICO, f"La columna '{nombre}' se indica más de una vez en el INSERT "
                                          f"(MySQL error 1110).")
                nombres.append(nombre)
                columnas.append(self.resolver_columna(ref))
        elif self.tabla is not None:
            columnas = list(self.tabla.columnas.values())
            nombres = [c.nombre.lower() for c in columnas]

        filas = ctx.filaValores()
        for i, fila in enumerate(filas, start=1):
            valores = [self.analizar_operando(op, "VALOR") for op in operandos(fila)]
            if self.tabla is None:
                continue
            if len(valores) != len(nombres):
                en_fila = f" en la fila {i}" if len(filas) > 1 else ""
                origen = "se indicaron" if explicitas else "la tabla tiene"
                self.error(SEMANTICO, f"La cantidad de valores no coincide con la de columnas{en_fila}: "
                                      f"{origen} {len(nombres)} columna(s) ({', '.join(nombres)}) pero "
                                      f"se dieron {len(valores)} valor(es) (MySQL error 1136).")
            else:
                for columna, valor in zip(columnas, valores):
                    self.validar_valor(columna, valor)
        if explicitas:
            self._revisar_obligatorias(nombres)

    def visitInsertSet(self, ctx: P.InsertSetContext):
        self._inicio_insert(ctx)
        nombres = self._revisar_asignaciones(ctx.asignacion(), "INSERT")
        self._revisar_obligatorias(nombres)

    def _revisar_asignaciones(self, asignaciones, instruccion: str) -> list[str]:
        nombres: list[str] = []
        for asignacion in asignaciones:
            ref = asignacion.columnaRef()
            nombre = nombre_identificador(ref.columna).lower()
            columna = self.resolver_columna(ref)
            if nombre in nombres:
                self.error(SEMANTICO, f"La columna '{nombre}' se asigna más de una vez en el "
                                      f"{instruccion} (la primera asignación se perdería).")
            nombres.append(nombre)
            valor = self.analizar_operando(asignacion.operando(), "VALOR", asignada_a=nombre)
            self.validar_valor(columna, valor)
        return nombres

    # ---- UPDATE
    def visitSentenciaUpdate(self, ctx: P.SentenciaUpdateContext):
        self.tipo = "UPDATE"
        if ctx.tablaRef() is None:
            self.error(SINTACTICO, "Falta el nombre de la tabla entre UPDATE y SET "
                                   "(forma correcta: UPDATE usuarios SET ...).")
        else:
            self.fijar_tabla(ctx.tablaRef())
        self._revisar_asignaciones(ctx.asignacion(), "UPDATE")
        cond = self.analizar_where(ctx.clausulaWhere())
        self.revisar_orden_y_limite(ctx)
        self.revisar_operacion_masiva(ctx.clausulaWhere(), cond, "UPDATE")

    # ---- DELETE
    def visitSentenciaDelete(self, ctx: P.SentenciaDeleteContext):
        self.tipo = "DELETE"
        if ctx.FROM() is None:
            self.error(SINTACTICO, "Falta la palabra clave FROM después de DELETE "
                                   "(forma correcta: DELETE FROM usuarios WHERE ...).")
        if ctx.tablaRef() is None:
            self.error(SINTACTICO, "Falta el nombre de la tabla en la sentencia DELETE "
                                   "(forma correcta: DELETE FROM usuarios WHERE ...).")
        else:
            self.fijar_tabla(ctx.tablaRef())
        cond = self.analizar_where(ctx.clausulaWhere())
        self.revisar_orden_y_limite(ctx)
        self.revisar_operacion_masiva(ctx.clausulaWhere(), cond, "DELETE")

    # ---- DROP / TRUNCATE / otras
    def visitDropTabla(self, ctx: P.DropTablaContext):
        self.tipo = "DROP TABLE"
        if ctx.TABLE() is None:
            self.error(SINTACTICO, "Falta la palabra clave TABLE después de DROP "
                                   "(forma correcta: DROP TABLE nombre_tabla).")
        tablas = ctx.nombreTabla()
        if not tablas:
            self.error(SINTACTICO, "Falta el nombre de la tabla a eliminar en la sentencia DROP.")
            return
        con_if_exists = ctx.EXISTS() is not None
        for nt in tablas:
            self.resolver_tabla(nt, exigir=not con_if_exists)
        nombres = ", ".join(texto_original(nt) for nt in tablas)
        self.error(PELIGROSA, f"DROP TABLE{' IF EXISTS' if con_if_exists else ''} {nombres}: aunque la "
                              f"sintaxis sea válida, eliminaría la tabla y TODOS sus registros. Una "
                              f"sentencia destructiva de estructura nunca se ejecuta desde este proceso.")

    def visitDropBaseDatos(self, ctx: P.DropBaseDatosContext):
        self.tipo = "DROP DATABASE"
        self.error(PELIGROSA, "DROP DATABASE eliminaría la base de datos completa. Nunca se ejecuta "
                              "desde este proceso.")

    def visitSentenciaTruncate(self, ctx: P.SentenciaTruncateContext):
        self.tipo = "TRUNCATE"
        if ctx.nombreTabla() is None:
            self.error(SINTACTICO, "Falta el nombre de la tabla en la sentencia TRUNCATE.")
            return
        self.resolver_tabla(ctx.nombreTabla())
        self.error(PELIGROSA, f"TRUNCATE {texto_original(ctx.nombreTabla())}: borraría TODOS los registros "
                              f"de la tabla sin posibilidad de deshacerlo.")

    def visitSentenciaNoPermitida(self, ctx: P.SentenciaNoPermitidaContext):
        instruccion = ctx.instruccion.text.upper()
        self.tipo = instruccion
        if instruccion in SOLO_METADATOS:
            self.error(NO_SOPORTADA, f"La instrucción {instruccion} no está soportada: el procesador "
                                     f"solo ejecuta SELECT, INSERT, UPDATE y DELETE.")
        else:
            self.error(PELIGROSA, f"La instrucción {instruccion} no está permitida: "
                                  f"{NO_PERMITIDAS[instruccion]}. El procesador solo ejecuta SELECT, "
                                  f"INSERT, UPDATE y DELETE.")


# ---------------------------------------------------------------------------
# Fachada: analiza una línea completa (fases 1, 2 y 3)
# ---------------------------------------------------------------------------
class AnalizadorSQL:

    def __init__(self, esquema: dict[str, Tabla] | None = None, base_datos: str = BASE_DATOS,
                 estricto: bool = True):
        self.esquema = esquema if esquema is not None else ESQUEMA
        self.base_datos = base_datos
        self.estricto = estricto

    @staticmethod
    def normalizar(linea: str) -> str:
        texto = linea.strip().lstrip("﻿").strip()
        # Si el CSV fue guardado con comillas (p. ej. desde Excel) se quitan
        if len(texto) >= 2 and texto[0] == '"' and texto.endswith('"'):
            campos = next(csv.reader([texto]), [])
            texto = campos[0].strip() if campos else ""
        return texto

    def analizar(self, linea: str, numero: int) -> Resultado:
        texto = self.normalizar(linea)
        resultado = Resultado(numero, texto, texto.rstrip("; \t").strip())
        if not texto:
            resultado.omitida = True
            return resultado

        # ---------------- Fase 1: análisis léxico
        lexer = MiniSQLLexer(InputStream(texto))
        lexer.removeErrorListeners()
        flujo = CommonTokenStream(lexer)
        flujo.fill()
        tokens = [t for t in flujo.tokens if t.type != Token.EOF]
        if not tokens:
            resultado.omitida = True  # la línea solo tenía comentarios
            return resultado
        primero = tokens[0]
        resultado.tipo = primero.text.upper()
        # En una instrucción que de todas formas se bloquea (GRANT, ALTER, ...)
        # no importan los caracteres extraños del resto: se clasifica por la instrucción.
        bloqueada_por_instruccion = primero.type in TOKENS_INICIO and resultado.tipo in (
            set(NO_PERMITIDAS) | SOLO_METADATOS)
        for t in ([] if bloqueada_por_instruccion else tokens):
            if t.type == MiniSQLLexer.CARACTER_INVALIDO:
                resultado.errores.append((LEXICO, f"Carácter no válido '{t.text}' en la posición "
                                                  f"{t.column + 1}."))
            elif t.type == MiniSQLLexer.CADENA_SIN_CERRAR:
                resultado.errores.append((LEXICO, f"Texto sin comilla de cierre a partir de la posición "
                                                  f"{t.column + 1}: {t.text[:25]}"))
            elif t.type == MiniSQLLexer.COMENTARIO_EJECUTABLE:
                resultado.errores.append((PELIGROSA, f"Comentario ejecutable de MySQL {t.text[:25]}: MySQL "
                                                     f"ejecuta su contenido (técnica de inyección SQL)."))
        if resultado.errores:
            return resultado

        if primero.type not in TOKENS_INICIO:
            cercana = difflib.get_close_matches(primero.text.upper(), INSTRUCCIONES_DML, n=1, cutoff=0.6)
            pista = f" (¿quiso decir {cercana[0]}?)" if cercana else ""
            resultado.errores.append((SINTACTICO, f"Instrucción no reconocida '{primero.text}'{pista}: "
                                                  f"una sentencia debe iniciar con SELECT, INSERT, "
                                                  f"UPDATE, DELETE o DROP."))
            return resultado

        # ---------------- Fase 2: análisis sintáctico
        parser = MiniSQLParser(flujo)
        parser.removeErrorListeners()
        escucha = EscuchaErroresSintacticos()
        parser.addErrorListener(escucha)
        arbol = parser.script()
        if escucha.errores:
            resultado.errores.append((SINTACTICO, escucha.errores[0]))
            return resultado

        # ---------------- Fase 3: análisis semántico + reglas de seguridad
        semantico = AnalizadorSemantico(self.esquema, self.base_datos, self.estricto)
        semantico.visit(arbol)
        resultado.tipo = "+".join(semantico.tipos)
        resultado.errores.extend(semantico.errores)
        return resultado
