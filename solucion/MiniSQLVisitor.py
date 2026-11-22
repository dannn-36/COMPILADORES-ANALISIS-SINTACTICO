# Generated from MiniSQL.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .MiniSQLParser import MiniSQLParser
else:
    from MiniSQLParser import MiniSQLParser

# This class defines a complete generic visitor for a parse tree produced by MiniSQLParser.

class MiniSQLVisitor(ParseTreeVisitor):

    # Visit a parse tree produced by MiniSQLParser#script.
    def visitScript(self, ctx:MiniSQLParser.ScriptContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#sentencia.
    def visitSentencia(self, ctx:MiniSQLParser.SentenciaContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#sentenciaSelect.
    def visitSentenciaSelect(self, ctx:MiniSQLParser.SentenciaSelectContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#listaSeleccion.
    def visitListaSeleccion(self, ctx:MiniSQLParser.ListaSeleccionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#seleccionTodo.
    def visitSeleccionTodo(self, ctx:MiniSQLParser.SeleccionTodoContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#seleccionTodoTabla.
    def visitSeleccionTodoTabla(self, ctx:MiniSQLParser.SeleccionTodoTablaContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#seleccionExpresion.
    def visitSeleccionExpresion(self, ctx:MiniSQLParser.SeleccionExpresionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#nombreAlias.
    def visitNombreAlias(self, ctx:MiniSQLParser.NombreAliasContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#insertValues.
    def visitInsertValues(self, ctx:MiniSQLParser.InsertValuesContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#insertSet.
    def visitInsertSet(self, ctx:MiniSQLParser.InsertSetContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#listaColumnas.
    def visitListaColumnas(self, ctx:MiniSQLParser.ListaColumnasContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#filaValores.
    def visitFilaValores(self, ctx:MiniSQLParser.FilaValoresContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#sentenciaUpdate.
    def visitSentenciaUpdate(self, ctx:MiniSQLParser.SentenciaUpdateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#asignacion.
    def visitAsignacion(self, ctx:MiniSQLParser.AsignacionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#sentenciaDelete.
    def visitSentenciaDelete(self, ctx:MiniSQLParser.SentenciaDeleteContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#dropTabla.
    def visitDropTabla(self, ctx:MiniSQLParser.DropTablaContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#dropBaseDatos.
    def visitDropBaseDatos(self, ctx:MiniSQLParser.DropBaseDatosContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#sentenciaTruncate.
    def visitSentenciaTruncate(self, ctx:MiniSQLParser.SentenciaTruncateContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#sentenciaNoPermitida.
    def visitSentenciaNoPermitida(self, ctx:MiniSQLParser.SentenciaNoPermitidaContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#clausulaWhere.
    def visitClausulaWhere(self, ctx:MiniSQLParser.ClausulaWhereContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#clausulaGroupBy.
    def visitClausulaGroupBy(self, ctx:MiniSQLParser.ClausulaGroupByContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#clausulaHaving.
    def visitClausulaHaving(self, ctx:MiniSQLParser.ClausulaHavingContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#clausulaOrderBy.
    def visitClausulaOrderBy(self, ctx:MiniSQLParser.ClausulaOrderByContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#elementoOrden.
    def visitElementoOrden(self, ctx:MiniSQLParser.ElementoOrdenContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#clausulaLimit.
    def visitClausulaLimit(self, ctx:MiniSQLParser.ClausulaLimitContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#condicionPredicado.
    def visitCondicionPredicado(self, ctx:MiniSQLParser.CondicionPredicadoContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#condicionNot.
    def visitCondicionNot(self, ctx:MiniSQLParser.CondicionNotContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#condicionParentesis.
    def visitCondicionParentesis(self, ctx:MiniSQLParser.CondicionParentesisContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#condicionAnd.
    def visitCondicionAnd(self, ctx:MiniSQLParser.CondicionAndContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#condicionOr.
    def visitCondicionOr(self, ctx:MiniSQLParser.CondicionOrContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#predicadoComparacion.
    def visitPredicadoComparacion(self, ctx:MiniSQLParser.PredicadoComparacionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#predicadoIs.
    def visitPredicadoIs(self, ctx:MiniSQLParser.PredicadoIsContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#predicadoLike.
    def visitPredicadoLike(self, ctx:MiniSQLParser.PredicadoLikeContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#predicadoIn.
    def visitPredicadoIn(self, ctx:MiniSQLParser.PredicadoInContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#predicadoBetween.
    def visitPredicadoBetween(self, ctx:MiniSQLParser.PredicadoBetweenContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#predicadoSimple.
    def visitPredicadoSimple(self, ctx:MiniSQLParser.PredicadoSimpleContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#operadorComparacion.
    def visitOperadorComparacion(self, ctx:MiniSQLParser.OperadorComparacionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#operandoNegativo.
    def visitOperandoNegativo(self, ctx:MiniSQLParser.OperandoNegativoContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#operandoLiteral.
    def visitOperandoLiteral(self, ctx:MiniSQLParser.OperandoLiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#operandoFuncion.
    def visitOperandoFuncion(self, ctx:MiniSQLParser.OperandoFuncionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#operandoColumna.
    def visitOperandoColumna(self, ctx:MiniSQLParser.OperandoColumnaContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#literal.
    def visitLiteral(self, ctx:MiniSQLParser.LiteralContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#llamadaFuncion.
    def visitLlamadaFuncion(self, ctx:MiniSQLParser.LlamadaFuncionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#columnaRef.
    def visitColumnaRef(self, ctx:MiniSQLParser.ColumnaRefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#tablaRef.
    def visitTablaRef(self, ctx:MiniSQLParser.TablaRefContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#nombreTabla.
    def visitNombreTabla(self, ctx:MiniSQLParser.NombreTablaContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#identificador.
    def visitIdentificador(self, ctx:MiniSQLParser.IdentificadorContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by MiniSQLParser#palabraNoReservada.
    def visitPalabraNoReservada(self, ctx:MiniSQLParser.PalabraNoReservadaContext):
        return self.visitChildren(ctx)



del MiniSQLParser