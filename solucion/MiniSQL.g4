/*
 * ============================================================================
 *  MiniSQL.g4 - Gramática del Analizador Estático de sentencias SQL
 *  Compiladores - Lenguajes de Dominio Específico - Universidad El Bosque
 *  Laboratorio A7 - Análisis Semántico
 * ============================================================================
 *
 *  Reconoce el subconjunto de MySQL que llega en los archivos CSV:
 *      SELECT, INSERT, UPDATE, DELETE, DROP, TRUNCATE
 *  y además reconoce (para poder BLOQUEARLAS con un motivo claro) otras
 *  instrucciones DDL / DCL / administrativas: ALTER, CREATE, GRANT, ...
 *
 *  PRODUCCIONES DE ERROR  [PE]
 *  ---------------------------
 *  Algunas partes que en SQL son obligatorias (INTO, FROM, TABLE, el nombre
 *  de la tabla, la lista de columnas del SELECT, la condición del WHERE, la
 *  coma entre columnas o entre valores) se declaran aquí como OPCIONALES.
 *  Así el parser no se detiene con un error genérico de ANTLR, sino que
 *  construye el árbol y el analizador semántico (analizador.py) reporta un
 *  mensaje preciso, p. ej. "Falta la palabra clave FROM después de DELETE".
 *  Es la técnica de "producciones de error" (Aho, Lam, Sethi y Ullman,
 *  Compiladores, sección 4.1.4).
 *
 *  Generar el parser (Python):
 *      java -jar antlr-4.13.2-complete.jar -Dlanguage=Python3 -visitor -no-listener MiniSQL.g4
 * ============================================================================
 */
grammar MiniSQL;

// Las palabras clave de SQL no distinguen mayúsculas de minúsculas
options { caseInsensitive = true; }

// ============================================================================
//                                  PARSER
// ============================================================================

// Una línea del CSV. Puede traer varias sentencias separadas por ';'
// (se detecta y se rechaza en el análisis semántico: posible inyección).
script
    : sentencia (PUNTO_COMA+ sentencia)* PUNTO_COMA* EOF
    ;

sentencia
    : sentenciaSelect
    | sentenciaInsert
    | sentenciaUpdate
    | sentenciaDelete
    | sentenciaDrop
    | sentenciaTruncate
    | sentenciaNoPermitida
    ;

// ---------------------------------------------------------------- SELECT ---
sentenciaSelect
    : SELECT DISTINCT? listaSeleccion?            // [PE] lista de columnas
      (FROM tablaRef)?
      clausulaWhere?
      clausulaGroupBy?
      clausulaHaving?
      clausulaOrderBy?
      clausulaLimit?
    ;

listaSeleccion
    : elementoSeleccion (COMA elementoSeleccion)*
    ;

elementoSeleccion
    : ASTERISCO                                                     # seleccionTodo
    | tabla=identificador PUNTO ASTERISCO                           # seleccionTodoTabla
    | operando ( AS alias=nombreAlias
               | aliasImplicito=identificador )?                    # seleccionExpresion  // [PE] coma faltante
    ;

nombreAlias
    : identificador
    | CADENA
    ;

// ---------------------------------------------------------------- INSERT ---
sentenciaInsert
    : INSERT IGNORE? INTO? nombreTabla?                              // [PE] INTO / tabla
      (PAR_IZQ listaColumnas? PAR_DER)?
      (VALUES | VALUE) filaValores (COMA filaValores)*              # insertValues
    | INSERT IGNORE? INTO? nombreTabla?                              // [PE] INTO / tabla
      SET asignacion (COMA asignacion)*                             # insertSet
    ;

listaColumnas
    : columnaRef (COMA columnaRef)*
    ;

filaValores
    : PAR_IZQ (operando (COMA operando)*)? PAR_DER
    ;

// ---------------------------------------------------------------- UPDATE ---
sentenciaUpdate
    : UPDATE IGNORE? tablaRef?                                       // [PE] tabla
      SET asignacion (COMA asignacion)*
      clausulaWhere?
      clausulaOrderBy?
      clausulaLimit?
    ;

asignacion
    : columnaRef OP_IGUAL operando
    ;

// ---------------------------------------------------------------- DELETE ---
sentenciaDelete
    : DELETE IGNORE? FROM? tablaRef?                                 // [PE] FROM / tabla
      clausulaWhere?
      clausulaOrderBy?
      clausulaLimit?
    ;

// ------------------------------------------------------------ DROP / DDL ---
sentenciaDrop
    : DROP TEMPORARY? TABLE? (IF EXISTS)?                            // [PE] TABLE
      nombreTabla? (COMA nombreTabla)*                              // [PE] tabla
      (RESTRICT | CASCADE)?                                         # dropTabla
    | DROP (DATABASE | SCHEMA) (IF EXISTS)? identificador?          # dropBaseDatos
    ;

sentenciaTruncate
    : TRUNCATE TABLE? nombreTabla?                                   // [PE] tabla
    ;

// Instrucciones que el procesador NO debe ejecutar nunca. Solo se reconoce la
// palabra inicial y se consume el resto de la sentencia.
sentenciaNoPermitida
    : instruccion=( ALTER | CREATE | RENAME | GRANT | REVOKE | REPLACE | LOAD
                  | CALL | LOCK | UNLOCK | SHUTDOWN | KILL | USE | SET
                  | SHOW | DESCRIBE | DESC | EXPLAIN | BEGIN | START
                  | COMMIT | ROLLBACK | HANDLER | DO )
      (~PUNTO_COMA)*
    ;

// --------------------------------------------------------------- CLÁUSULAS ---
clausulaWhere
    : WHERE condicion?                                               // [PE] WHERE vacío
    ;

clausulaGroupBy
    : GROUP BY operando (COMA operando)*
    ;

clausulaHaving
    : HAVING condicion
    ;

clausulaOrderBy
    : ORDER BY elementoOrden (COMA elementoOrden)*
    ;

elementoOrden
    : operando (ASC | DESC)?
    ;

clausulaLimit
    : LIMIT NUMERO ((COMA | OFFSET) NUMERO)?
    ;

// ------------------------------------------------- CONDICIONES (WHERE/HAVING) ---
// El orden de las alternativas define la precedencia: NOT > AND > OR
condicion
    : NOT condicion                                                  # condicionNot
    | condicion (AND | AND_SIMBOLO) condicion                        # condicionAnd
    | condicion (OR | OR_SIMBOLO) condicion                          # condicionOr
    | PAR_IZQ condicion PAR_DER                                      # condicionParentesis
    | predicado                                                      # condicionPredicado
    ;

predicado
    : izquierdo=operando operadorComparacion derecho=operando        # predicadoComparacion
    | operando IS NOT? (NULL | TRUE | FALSE)                         # predicadoIs
    | operando NOT? LIKE operando                                    # predicadoLike
    | operando NOT? IN PAR_IZQ operando (COMA operando)* PAR_DER     # predicadoIn
    | operando NOT? BETWEEN operando AND operando                    # predicadoBetween
    | operando                                                       # predicadoSimple
    ;

operadorComparacion
    : OP_IGUAL | OP_DISTINTO | OP_DISTINTO_SQL | OP_MENOR | OP_MAYOR
    | OP_MENOR_IGUAL | OP_MAYOR_IGUAL | OP_IGUAL_NULL
    ;

// --------------------------------------------------------------- OPERANDOS ---
operando
    : MENOS operando                                                 # operandoNegativo
    | literal                                                        # operandoLiteral
    | llamadaFuncion                                                 # operandoFuncion
    | columnaRef                                                     # operandoColumna
    ;

literal
    : CADENA+          // [PE] varias cadenas seguidas: MySQL las concatena (coma faltante)
    | NUMERO
    | NULL
    | TRUE
    | FALSE
    ;

llamadaFuncion
    : nombre=identificador PAR_IZQ
      ( ASTERISCO | DISTINCT? operando (COMA operando)* )?
      PAR_DER
    ;

columnaRef
    : (calificador=identificador PUNTO)? columna=identificador
    ;

tablaRef
    : nombreTabla (AS? aliasTabla=identificador)?
    ;

nombreTabla
    : (baseDatos=identificador PUNTO)? tabla=identificador
    ;

identificador
    : ID
    | ID_COMILLAS
    | palabraNoReservada
    ;

// Palabras clave que MySQL permite usar también como nombres
palabraNoReservada
    : VALUE | OFFSET | TEMPORARY | BEGIN | START | COMMIT | ROLLBACK
    | HANDLER | DO | SHUTDOWN
    ;

// ============================================================================
//                                  LEXER
// ============================================================================

// ---- Palabras reservadas ----------------------------------------------------
SELECT      : 'SELECT';
DISTINCT    : 'DISTINCT';
FROM        : 'FROM';
WHERE       : 'WHERE';
AND         : 'AND';
OR          : 'OR';
NOT         : 'NOT';
IS          : 'IS';
NULL        : 'NULL';
LIKE        : 'LIKE';
IN          : 'IN';
BETWEEN     : 'BETWEEN';
TRUE        : 'TRUE';
FALSE       : 'FALSE';
AS          : 'AS';
GROUP       : 'GROUP';
BY          : 'BY';
HAVING      : 'HAVING';
ORDER       : 'ORDER';
ASC         : 'ASC';
DESC        : 'DESC';
LIMIT       : 'LIMIT';
OFFSET      : 'OFFSET';
INSERT      : 'INSERT';
IGNORE      : 'IGNORE';
INTO        : 'INTO';
VALUES      : 'VALUES';
VALUE       : 'VALUE';
UPDATE      : 'UPDATE';
SET         : 'SET';
DELETE      : 'DELETE';
DROP        : 'DROP';
TABLE       : 'TABLE';
TEMPORARY   : 'TEMPORARY';
IF          : 'IF';
EXISTS      : 'EXISTS';
DATABASE    : 'DATABASE';
SCHEMA      : 'SCHEMA';
RESTRICT    : 'RESTRICT';
CASCADE     : 'CASCADE';
TRUNCATE    : 'TRUNCATE';
ALTER       : 'ALTER';
CREATE      : 'CREATE';
RENAME      : 'RENAME';
GRANT       : 'GRANT';
REVOKE      : 'REVOKE';
REPLACE     : 'REPLACE';
LOAD        : 'LOAD';
CALL        : 'CALL';
LOCK        : 'LOCK';
UNLOCK      : 'UNLOCK';
SHUTDOWN    : 'SHUTDOWN';
KILL        : 'KILL';
USE         : 'USE';
SHOW        : 'SHOW';
DESCRIBE    : 'DESCRIBE';
EXPLAIN     : 'EXPLAIN';
BEGIN       : 'BEGIN';
START       : 'START';
COMMIT      : 'COMMIT';
ROLLBACK    : 'ROLLBACK';
HANDLER     : 'HANDLER';
DO          : 'DO';

// ---- Operadores y signos de puntuación --------------------------------------
OP_IGUAL_NULL   : '<=>';
OP_MENOR_IGUAL  : '<=';
OP_MAYOR_IGUAL  : '>=';
OP_DISTINTO     : '!=';
OP_DISTINTO_SQL : '<>';
OP_IGUAL        : '=';
OP_MENOR        : '<';
OP_MAYOR        : '>';
AND_SIMBOLO     : '&&';
OR_SIMBOLO      : '||';
PUNTO_COMA      : ';';
COMA            : ',';
PUNTO           : '.';
PAR_IZQ         : '(';
PAR_DER         : ')';
ASTERISCO       : '*';
MENOS           : '-';

// ---- Literales e identificadores --------------------------------------------
NUMERO
    : [0-9]+ ('.' [0-9]*)? ([e] [+-]? [0-9]+)?
    | '.' [0-9]+ ([e] [+-]? [0-9]+)?
    ;

// Cadenas con comilla simple o doble; admite '' y \' como escape
CADENA
    : '\'' ( '\\' . | '\'\'' | ~['\\] )* '\''
    | '"'  ( '\\' . | '""'   | ~["\\] )* '"'
    ;

// Cadena que se abre y nunca se cierra (error léxico)
CADENA_SIN_CERRAR
    : '\'' ( '\\' . | '\'\'' | ~['\\] )*
    | '"'  ( '\\' . | '""'   | ~["\\] )*
    ;

ID          : [\p{L}_] [\p{L}\p{N}_$]* ;
ID_COMILLAS : '`' ( ~'`' | '``' )+ '`' ;

// ---- Comentarios y espacios -------------------------------------------------
// Comentario ejecutable de MySQL /*! ... */ : MySQL SÍ ejecuta su contenido,
// por eso no se ignora (el analizador lo rechaza).
COMENTARIO_EJECUTABLE : '/*!' .*? '*/' ;
COMENTARIO_BLOQUE     : '/*' .*? '*/'         -> skip ;
COMENTARIO_LINEA      : ('--' | '#') ~[\r\n]* -> skip ;
ESPACIOS              : [ \t\r\n\u000B\u000C ﻿]+ -> skip ;

// Cualquier otro carácter: error léxico (se reporta con su posición)
CARACTER_INVALIDO     : . ;
