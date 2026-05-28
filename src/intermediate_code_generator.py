"""
intermediate_code_generator.py - Generador de Código Intermedio (TAC)
Genera instrucciones de Código de Tres Direcciones (Three-Address Code)
a partir del AST de Python.

Formato TAC:
  - Asignación simple:    x = y
  - Op. binaria:          t0 = a + b
  - Op. unaria:           t0 = -a
  - Salto incondicional:  goto L0
  - Salto condicional:    if t0 goto L1  /  ifFalse t0 goto L1
  - Etiqueta:             L0:
  - Parámetro:            param x
  - Llamada:              t0 = call func, n
  - Retorno:              return x
  - Inicio/fin función:   begin_func func / end_func func
  - Índice (subscript):   t0 = a[i]  /  a[i] = t0
"""

import ast
from dataclasses import dataclass, field
from typing import List, Optional


# ─── Instrucción TAC ─────────────────────────────────────────────────────────

@dataclass
class TACInstruction:
    op: str
    result: Optional[str] = None
    arg1: Optional[str] = None
    arg2: Optional[str] = None
    label: Optional[str] = None
    comment: Optional[str] = None

    def __str__(self) -> str:
        if self.op == "label":
            return f"{self.label}:"
        if self.op == "goto":
            return f"    goto {self.label}"
        if self.op == "if_true":
            return f"    if {self.arg1} goto {self.label}"
        if self.op == "if_false":
            return f"    ifFalse {self.arg1} goto {self.label}"
        if self.op == "param":
            return f"    param {self.arg1}"
        if self.op == "call":
            if self.result:
                return f"    {self.result} = call {self.arg1}, {self.arg2}"
            return f"    call {self.arg1}, {self.arg2}"
        if self.op == "return":
            return f"    return {self.arg1}" if self.arg1 else "    return"
        if self.op == "begin_func":
            return f"\nbegin_func {self.arg1}"
        if self.op == "end_func":
            return f"end_func {self.arg1}\n"
        if self.op == "assign":
            return f"    {self.result} = {self.arg1}"
        if self.op == "binary":
            return f"    {self.result} = {self.arg1} {self.label} {self.arg2}"
        if self.op == "unary":
            return f"    {self.result} = {self.arg1}{self.arg2}"
        if self.op == "index_load":
            return f"    {self.result} = {self.arg1}[{self.arg2}]"
        if self.op == "index_store":
            return f"    {self.arg1}[{self.arg2}] = {self.result}"
        if self.op == "comment":
            return f"    # {self.comment}"
        if self.op == "nop":
            return "    nop"
        parts = ["    "]
        if self.result:
            parts.append(f"{self.result} = ")
        parts.append(self.op)
        if self.arg1:
            parts.append(f" {self.arg1}")
        if self.arg2:
            parts.append(f", {self.arg2}")
        return "".join(parts)

    def to_dict(self) -> dict:
        return {
            "op": self.op,
            "result": self.result,
            "arg1": self.arg1,
            "arg2": self.arg2,
            "label": self.label,
            "comment": self.comment,
        }


# ─── Resultado de la generación ───────────────────────────────────────────────

@dataclass
class ICGResult:
    success: bool
    instructions: List[TACInstruction] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)
    temp_count: int = 0
    label_count: int = 0

    def to_text(self) -> str:
        lines = []
        for instr in self.instructions:
            s = str(instr)
            if s is not None:
                lines.append(s)
        return "\n".join(lines)

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "instructions": [i.to_dict() for i in self.instructions],
            "errors": self.errors,
            "temp_count": self.temp_count,
            "label_count": self.label_count,
        }


# ─── Generador de Código Intermedio ──────────────────────────────────────────

class IntermediateCodeGenerator(ast.NodeVisitor):
    """
    Recorre el AST de Python y genera instrucciones TAC.
    """

    def __init__(self):
        self._temp_counter = 0
        self._label_counter = 0
        self._instructions: List[TACInstruction] = []
        self._errors: List[str] = []
        self._current_func: Optional[str] = None

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _new_temp(self) -> str:
        t = f"t{self._temp_counter}"
        self._temp_counter += 1
        return t

    def _new_label(self) -> str:
        L = f"L{self._label_counter}"
        self._label_counter += 1
        return L

    def _emit(self, instr: TACInstruction):
        self._instructions.append(instr)

    def _emit_label(self, label: str):
        self._emit(TACInstruction(op="label", label=label))

    # ── Tablas de operadores ─────────────────────────────────────────────────

    def _binop_sym(self, op: ast.operator) -> str:
        return {
            ast.Add: "+",     ast.Sub: "-",    ast.Mult: "*",
            ast.Div: "/",     ast.FloorDiv: "//", ast.Mod: "%",
            ast.Pow: "**",    ast.BitAnd: "&", ast.BitOr: "|",
            ast.BitXor: "^",  ast.LShift: "<<", ast.RShift: ">>",
            ast.MatMult: "@",
        }.get(type(op), "?")

    def _cmpop_sym(self, op: ast.cmpop) -> str:
        return {
            ast.Eq: "==",    ast.NotEq: "!=",
            ast.Lt: "<",     ast.LtE: "<=",
            ast.Gt: ">",     ast.GtE: ">=",
            ast.In: "in",    ast.NotIn: "not in",
            ast.Is: "is",    ast.IsNot: "is not",
        }.get(type(op), "?")

    def _unaryop_sym(self, op: ast.unaryop) -> str:
        return {
            ast.USub: "-",   ast.UAdd: "+",
            ast.Not: "not ", ast.Invert: "~",
        }.get(type(op), "?")

    def _boolop_sym(self, op: ast.boolop) -> str:
        return "and" if isinstance(op, ast.And) else "or"

    # ── Generación de expresiones ─────────────────────────────────────────────

    def _gen_expr(self, node: ast.expr) -> str:
        """
        Genera instrucciones para una expresión y retorna el nombre
        del temporal (o literal) donde queda el resultado.
        """
        if isinstance(node, ast.Constant):
            return repr(node.value)

        if isinstance(node, ast.Name):
            return node.id

        if isinstance(node, ast.BinOp):
            left = self._gen_expr(node.left)
            right = self._gen_expr(node.right)
            sym = self._binop_sym(node.op)
            t = self._new_temp()
            self._emit(TACInstruction(op="binary", result=t, arg1=left, arg2=right, label=sym))
            return t

        if isinstance(node, ast.UnaryOp):
            operand = self._gen_expr(node.operand)
            sym = self._unaryop_sym(node.op)
            t = self._new_temp()
            self._emit(TACInstruction(op="unary", result=t, arg1=sym, arg2=operand))
            return t

        if isinstance(node, ast.BoolOp):
            sym = self._boolop_sym(node.op)
            left = self._gen_expr(node.values[0])
            for value in node.values[1:]:
                right = self._gen_expr(value)
                t = self._new_temp()
                self._emit(TACInstruction(op="binary", result=t, arg1=left, arg2=right, label=sym))
                left = t
            return left

        if isinstance(node, ast.Compare):
            left = self._gen_expr(node.left)
            t = left
            for op, comparator in zip(node.ops, node.comparators):
                right = self._gen_expr(comparator)
                sym = self._cmpop_sym(op)
                t = self._new_temp()
                self._emit(TACInstruction(op="binary", result=t, arg1=left, arg2=right, label=sym))
                left = t
            return t

        if isinstance(node, ast.Call):
            args_temps = [self._gen_expr(arg) for arg in node.args]
            for kw in node.keywords:
                if kw.value:
                    args_temps.append(self._gen_expr(kw.value))
            for arg_t in args_temps:
                self._emit(TACInstruction(op="param", arg1=arg_t))
            if isinstance(node.func, ast.Name):
                func_name = node.func.id
            elif isinstance(node.func, ast.Attribute):
                obj = self._gen_expr(node.func.value)
                func_name = f"{obj}.{node.func.attr}"
            else:
                func_name = "?"
            t = self._new_temp()
            self._emit(TACInstruction(
                op="call", result=t,
                arg1=func_name, arg2=str(len(args_temps))
            ))
            return t

        if isinstance(node, ast.Subscript):
            obj = self._gen_expr(node.value)
            if isinstance(node.slice, ast.Constant):
                idx = repr(node.slice.value)
            elif isinstance(node.slice, ast.Name):
                idx = node.slice.id
            else:
                idx = self._gen_expr(node.slice)
            t = self._new_temp()
            self._emit(TACInstruction(op="index_load", result=t, arg1=obj, arg2=idx))
            return t

        if isinstance(node, ast.Attribute):
            obj = self._gen_expr(node.value)
            t = self._new_temp()
            self._emit(TACInstruction(op="assign", result=t, arg1=f"{obj}.{node.attr}"))
            return t

        if isinstance(node, ast.IfExp):
            cond = self._gen_expr(node.test)
            t = self._new_temp()
            true_lbl = self._new_label()
            end_lbl = self._new_label()
            self._emit(TACInstruction(op="if_true", arg1=cond, label=true_lbl))
            false_val = self._gen_expr(node.orelse)
            self._emit(TACInstruction(op="assign", result=t, arg1=false_val))
            self._emit(TACInstruction(op="goto", label=end_lbl))
            self._emit_label(true_lbl)
            true_val = self._gen_expr(node.body)
            self._emit(TACInstruction(op="assign", result=t, arg1=true_val))
            self._emit_label(end_lbl)
            return t

        if isinstance(node, ast.List):
            elems = [self._gen_expr(e) for e in node.elts]
            t = self._new_temp()
            self._emit(TACInstruction(op="assign", result=t, arg1=f"[{', '.join(elems)}]"))
            return t

        if isinstance(node, ast.Tuple):
            elems = [self._gen_expr(e) for e in node.elts]
            t = self._new_temp()
            self._emit(TACInstruction(op="assign", result=t, arg1=f"({', '.join(elems)})"))
            return t

        if isinstance(node, ast.Dict):
            t = self._new_temp()
            self._emit(TACInstruction(op="assign", result=t, arg1="{}"))
            return t

        if isinstance(node, ast.Set):
            elems = [self._gen_expr(e) for e in node.elts]
            t = self._new_temp()
            self._emit(TACInstruction(op="assign", result=t, arg1=f"{{{', '.join(elems)}}}"))
            return t

        if isinstance(node, (ast.ListComp, ast.SetComp, ast.GeneratorExp)):
            t = self._new_temp()
            self._emit(TACInstruction(op="assign", result=t, arg1="<comprehension>"))
            return t

        if isinstance(node, ast.DictComp):
            t = self._new_temp()
            self._emit(TACInstruction(op="assign", result=t, arg1="<dict_comprehension>"))
            return t

        if isinstance(node, ast.Lambda):
            t = self._new_temp()
            self._emit(TACInstruction(op="assign", result=t, arg1="<lambda>"))
            return t

        if isinstance(node, ast.JoinedStr):
            t = self._new_temp()
            self._emit(TACInstruction(op="assign", result=t, arg1="<f-string>"))
            return t

        if isinstance(node, ast.Starred):
            val = self._gen_expr(node.value)
            t = self._new_temp()
            self._emit(TACInstruction(op="assign", result=t, arg1=f"*{val}"))
            return t

        t = self._new_temp()
        self._emit(TACInstruction(op="assign", result=t, arg1=f"<{type(node).__name__}>"))
        return t

    # ── Generación de instrucciones (statements) ──────────────────────────────

    def visit_Module(self, node: ast.Module):
        self._emit(TACInstruction(op="comment", comment="── Inicio del módulo ──────────────────"))
        for stmt in node.body:
            self.visit(stmt)
        self._emit(TACInstruction(op="comment", comment="── Fin del módulo ─────────────────────"))

    def visit_Expr(self, node: ast.Expr):
        self._gen_expr(node.value)

    def visit_Assign(self, node: ast.Assign):
        val = self._gen_expr(node.value)
        for target in node.targets:
            self._assign_target(target, val)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        if node.value is not None:
            val = self._gen_expr(node.value)
            self._assign_target(node.target, val)

    def visit_AugAssign(self, node: ast.AugAssign):
        target_name = self._lvalue_str(node.target)
        rhs = self._gen_expr(node.value)
        sym = self._binop_sym(node.op)
        t = self._new_temp()
        self._emit(TACInstruction(op="binary", result=t, arg1=target_name, arg2=rhs, label=sym))
        self._assign_target(node.target, t)

    def _lvalue_str(self, target: ast.expr) -> str:
        if isinstance(target, ast.Name):
            return target.id
        if isinstance(target, ast.Attribute):
            obj = self._gen_expr(target.value)
            return f"{obj}.{target.attr}"
        if isinstance(target, ast.Subscript):
            return self._gen_expr(target)
        return "?"

    def _assign_target(self, target: ast.expr, val: str):
        if isinstance(target, ast.Name):
            self._emit(TACInstruction(op="assign", result=target.id, arg1=val))
        elif isinstance(target, ast.Subscript):
            obj = self._gen_expr(target.value)
            if isinstance(target.slice, ast.Constant):
                idx = repr(target.slice.value)
            elif isinstance(target.slice, ast.Name):
                idx = target.slice.id
            else:
                idx = self._gen_expr(target.slice)
            self._emit(TACInstruction(op="index_store", result=val, arg1=obj, arg2=idx))
        elif isinstance(target, ast.Attribute):
            obj = self._gen_expr(target.value)
            self._emit(TACInstruction(op="assign", result=f"{obj}.{target.attr}", arg1=val))
        elif isinstance(target, (ast.Tuple, ast.List)):
            t_seq = self._new_temp()
            self._emit(TACInstruction(op="assign", result=t_seq, arg1=val))
            for i, elt in enumerate(target.elts):
                t_elem = self._new_temp()
                self._emit(TACInstruction(op="index_load", result=t_elem, arg1=t_seq, arg2=str(i)))
                self._assign_target(elt, t_elem)

    def visit_If(self, node: ast.If):
        cond = self._gen_expr(node.test)
        else_lbl = self._new_label()
        end_lbl = self._new_label()

        if node.orelse:
            self._emit(TACInstruction(op="if_false", arg1=cond, label=else_lbl))
        else:
            self._emit(TACInstruction(op="if_false", arg1=cond, label=end_lbl))

        for stmt in node.body:
            self.visit(stmt)

        if node.orelse:
            self._emit(TACInstruction(op="goto", label=end_lbl))
            self._emit_label(else_lbl)
            for stmt in node.orelse:
                self.visit(stmt)

        self._emit_label(end_lbl)

    def visit_While(self, node: ast.While):
        start_lbl = self._new_label()
        end_lbl = self._new_label()

        self._emit_label(start_lbl)
        cond = self._gen_expr(node.test)
        self._emit(TACInstruction(op="if_false", arg1=cond, label=end_lbl))

        for stmt in node.body:
            self.visit(stmt)

        self._emit(TACInstruction(op="goto", label=start_lbl))
        self._emit_label(end_lbl)

    def visit_For(self, node: ast.For):
        iter_t = self._gen_expr(node.iter)
        idx_t = self._new_temp()
        len_t = self._new_temp()
        start_lbl = self._new_label()
        end_lbl = self._new_label()

        self._emit(TACInstruction(op="assign", result=idx_t, arg1="0"))
        self._emit(TACInstruction(op="param", arg1=iter_t))
        self._emit(TACInstruction(op="call", result=len_t, arg1="len", arg2="1"))

        self._emit_label(start_lbl)
        cond_t = self._new_temp()
        self._emit(TACInstruction(op="binary", result=cond_t, arg1=idx_t, arg2=len_t, label="<"))
        self._emit(TACInstruction(op="if_false", arg1=cond_t, label=end_lbl))

        elem_t = self._new_temp()
        self._emit(TACInstruction(op="index_load", result=elem_t, arg1=iter_t, arg2=idx_t))
        self._assign_target(node.target, elem_t)

        for stmt in node.body:
            self.visit(stmt)

        next_idx = self._new_temp()
        self._emit(TACInstruction(op="binary", result=next_idx, arg1=idx_t, arg2="1", label="+"))
        self._emit(TACInstruction(op="assign", result=idx_t, arg1=next_idx))
        self._emit(TACInstruction(op="goto", label=start_lbl))
        self._emit_label(end_lbl)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        prev_func = self._current_func
        self._current_func = node.name

        self._emit(TACInstruction(op="begin_func", arg1=node.name))

        all_args = (node.args.args + node.args.posonlyargs + node.args.kwonlyargs)
        for arg in all_args:
            self._emit(TACInstruction(op="assign", result=arg.arg, arg1=f"param_{arg.arg}"))

        for stmt in node.body:
            self.visit(stmt)

        self._emit(TACInstruction(op="end_func", arg1=node.name))
        self._current_func = prev_func

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Return(self, node: ast.Return):
        if node.value is not None:
            val = self._gen_expr(node.value)
            self._emit(TACInstruction(op="return", arg1=val))
        else:
            self._emit(TACInstruction(op="return"))

    def visit_ClassDef(self, node: ast.ClassDef):
        self._emit(TACInstruction(op="comment", comment=f"── Clase: {node.name} ──"))
        for stmt in node.body:
            self.visit(stmt)
        self._emit(TACInstruction(op="comment", comment=f"── Fin clase: {node.name} ──"))

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[0]
            self._emit(TACInstruction(op="assign", result=name, arg1=f"import({alias.name})"))

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for alias in node.names:
            if alias.name == "*":
                continue
            name = alias.asname or alias.name
            self._emit(TACInstruction(
                op="assign", result=name, arg1=f"import({node.module}.{alias.name})"))

    def visit_Delete(self, node: ast.Delete):
        for target in node.targets:
            name = self._lvalue_str(target)
            self._emit(TACInstruction(op="assign", result=name, arg1="<deleted>"))

    def visit_Global(self, node: ast.Global):
        for name in node.names:
            self._emit(TACInstruction(op="comment", comment=f"global {name}"))

    def visit_Nonlocal(self, node: ast.Nonlocal):
        for name in node.names:
            self._emit(TACInstruction(op="comment", comment=f"nonlocal {name}"))

    def visit_Pass(self, node: ast.Pass):
        self._emit(TACInstruction(op="nop"))

    def visit_Break(self, node: ast.Break):
        self._emit(TACInstruction(op="comment", comment="break"))

    def visit_Continue(self, node: ast.Continue):
        self._emit(TACInstruction(op="comment", comment="continue"))

    def visit_Assert(self, node: ast.Assert):
        cond = self._gen_expr(node.test)
        ok_lbl = self._new_label()
        self._emit(TACInstruction(op="if_true", arg1=cond, label=ok_lbl))
        if node.msg and hasattr(ast, "unparse"):
            msg = repr(ast.unparse(node.msg))
        else:
            msg = '"AssertionError"'
        self._emit(TACInstruction(op="comment", comment=f"assert fail → raise AssertionError({msg})"))
        self._emit_label(ok_lbl)

    def visit_Raise(self, node: ast.Raise):
        if node.exc:
            exc = self._gen_expr(node.exc)
            self._emit(TACInstruction(op="comment", comment=f"raise {exc}"))
        else:
            self._emit(TACInstruction(op="comment", comment="raise"))

    def visit_Try(self, node: ast.Try):
        end_lbl = self._new_label()
        self._emit(TACInstruction(op="comment", comment="── try ──────────────────────────────"))
        for stmt in node.body:
            self.visit(stmt)
        self._emit(TACInstruction(op="goto", label=end_lbl))
        for handler in node.handlers:
            exc_name = (handler.type.id
                        if handler.type and isinstance(handler.type, ast.Name)
                        else "Exception")
            self._emit(TACInstruction(op="comment", comment=f"── except {exc_name} ──"))
            if handler.name:
                self._emit(TACInstruction(op="assign", result=handler.name, arg1="<exception>"))
            for stmt in handler.body:
                self.visit(stmt)
        if node.orelse:
            self._emit(TACInstruction(op="comment", comment="── else (sin excepción) ──"))
            for stmt in node.orelse:
                self.visit(stmt)
        if node.finalbody:
            self._emit(TACInstruction(op="comment", comment="── finally ──────────────────────────"))
            for stmt in node.finalbody:
                self.visit(stmt)
        self._emit_label(end_lbl)

    def visit_With(self, node: ast.With):
        for item in node.items:
            ctx = self._gen_expr(item.context_expr)
            if item.optional_vars:
                self._assign_target(item.optional_vars, ctx)
        for stmt in node.body:
            self.visit(stmt)

    # ── Punto de entrada ──────────────────────────────────────────────────────

    def generate(self, source_code: str) -> ICGResult:
        """
        Genera el código intermedio TAC para el código fuente dado.
        Retorna un ICGResult con todas las instrucciones generadas.
        """
        self._temp_counter = 0
        self._label_counter = 0
        self._instructions = []
        self._errors = []
        self._current_func = None

        try:
            tree = ast.parse(source_code, mode="exec")
        except SyntaxError as e:
            return ICGResult(
                success=False,
                errors=[f"Error de sintaxis: {e.msg} (línea {e.lineno})"]
            )

        try:
            self.visit(tree)
        except Exception as e:
            self._errors.append(f"Error en la generación: {e}")

        return ICGResult(
            success=True,
            instructions=self._instructions,
            errors=self._errors,
            temp_count=self._temp_counter,
            label_count=self._label_counter,
        )


# ─── Función de conveniencia ──────────────────────────────────────────────────

def generate_intermediate_code(source_code: str) -> ICGResult:
    """
    Función principal para generar código intermedio TAC
    a partir de código fuente Python.

    Parámetros
    ----------
    source_code : str
        Código fuente Python a procesar.

    Retorna
    -------
    ICGResult
        Objeto con las instrucciones TAC generadas, errores y estadísticas.

    Ejemplo
    -------
    >>> result = generate_intermediate_code("x = 1 + 2\\nprint(x)")
    >>> print(result.to_text())
        # ── Inicio del módulo ──────────────────────
        t0 = 1 + 2
        x = t0
        param x
        t1 = call print, 1
        # ── Fin del módulo ─────────────────────────
    """
    gen = IntermediateCodeGenerator()
    return gen.generate(source_code)
