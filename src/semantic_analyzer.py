"""
semantic_analyzer.py - Analizador Semántico para código Python
Realiza verificaciones de tipo, tabla de símbolos, variables no declaradas,
uso antes de asignación, funciones no definidas, retornos inconsistentes y más.
"""

import ast
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum, auto


# ─── Tipos de errores y advertencias ─────────────────────────────────────────

class SemanticErrorKind(Enum):
    UNDEFINED_VAR        = auto()
    UNDEFINED_FUNC       = auto()
    TYPE_MISMATCH        = auto()
    REDECLARED_VAR       = auto()
    UNUSED_VAR           = auto()
    UNUSED_IMPORT        = auto()
    MISSING_RETURN       = auto()
    UNREACHABLE_CODE     = auto()
    WRONG_ARG_COUNT      = auto()
    DIVISION_BY_ZERO     = auto()
    INVALID_OPERATION    = auto()
    SCOPE_ERROR          = auto()


@dataclass
class SemanticError:
    kind: SemanticErrorKind
    message: str
    line: int
    column: int = 0
    is_warning: bool = False

    def __str__(self):
        level = "⚠ Advertencia" if self.is_warning else "✗ Error"
        return f"[{level}] Línea {self.line}: {self.message}"

    def to_dict(self):
        return {
            "kind": self.kind.name,
            "message": self.message,
            "line": self.line,
            "column": self.column,
            "is_warning": self.is_warning,
        }


# ─── Símbolo y tabla de símbolos ─────────────────────────────────────────────

@dataclass
class Symbol:
    name: str
    symbol_type: str          # 'variable', 'function', 'class', 'import', 'parameter'
    inferred_type: str        # 'int', 'float', 'str', 'bool', 'None', 'list', 'dict', 'unknown'
    line: int
    scope: str
    used: bool = False
    assigned: bool = True

    def to_dict(self):
        return {
            "name": self.name,
            "symbol_type": self.symbol_type,
            "inferred_type": self.inferred_type,
            "line": self.line,
            "scope": self.scope,
            "used": self.used,
        }


class SymbolTable:
    """Tabla de símbolos con soporte de scopes anidados."""

    def __init__(self, name: str = "global", parent: Optional["SymbolTable"] = None):
        self.name = name
        self.parent = parent
        self.symbols: Dict[str, Symbol] = {}
        self.children: List["SymbolTable"] = []

    def define(self, symbol: Symbol):
        self.symbols[symbol.name] = symbol

    def lookup(self, name: str) -> Optional[Symbol]:
        if name in self.symbols:
            return self.symbols[name]
        if self.parent:
            return self.parent.lookup(name)
        return None

    def lookup_local(self, name: str) -> Optional[Symbol]:
        return self.symbols.get(name)

    def mark_used(self, name: str) -> bool:
        sym = self.lookup(name)
        if sym:
            sym.used = True
            return True
        return False

    def child_scope(self, name: str) -> "SymbolTable":
        child = SymbolTable(name=name, parent=self)
        self.children.append(child)
        return child

    def all_symbols_flat(self) -> List[Symbol]:
        result = list(self.symbols.values())
        for child in self.children:
            result.extend(child.all_symbols_flat())
        return result


# ─── Inferencia de tipo desde nodos AST ──────────────────────────────────────

def infer_type(node: ast.expr, scope: SymbolTable) -> str:
    """Infiere el tipo de una expresión AST de forma básica."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool):
            return "bool"
        if isinstance(node.value, int):
            return "int"
        if isinstance(node.value, float):
            return "float"
        if isinstance(node.value, str):
            return "str"
        if node.value is None:
            return "None"
        return "unknown"

    if isinstance(node, ast.List):
        return "list"
    if isinstance(node, ast.Dict):
        return "dict"
    if isinstance(node, ast.Set):
        return "set"
    if isinstance(node, ast.Tuple):
        return "tuple"

    if isinstance(node, ast.Name):
        sym = scope.lookup(node.id)
        if sym:
            return sym.inferred_type
        return "unknown"

    if isinstance(node, ast.BinOp):
        left = infer_type(node.left, scope)
        right = infer_type(node.right, scope)
        # Reglas básicas de promoción
        if left == right:
            return left
        if {left, right} == {"int", "float"}:
            return "float"
        if isinstance(node.op, ast.Add) and "str" in (left, right):
            return "str"
        return "unknown"

    if isinstance(node, ast.BoolOp):
        return "bool"
    if isinstance(node, ast.Compare):
        return "bool"
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return "bool"
        return infer_type(node.operand, scope)

    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            built = {
                "int": "int", "float": "float", "str": "str",
                "bool": "bool", "list": "list", "dict": "dict",
                "set": "set", "tuple": "tuple", "len": "int",
                "range": "range", "print": "None",
                # input() ahora devuelve tipo inferido automáticamente (no siempre str)
                "input": "inferred",
                # Funciones del módulo type_inference disponibles en ejecución
                "infer_type": "inferred", "smart_input": "inferred",
                "abs": "int", "round": "float", "type": "type",
            }
            if node.func.id in built:
                return built[node.func.id]
            sym = scope.lookup(node.func.id)
            if sym and sym.symbol_type == "function":
                return sym.inferred_type  # tipo de retorno guardado
        return "unknown"

    if isinstance(node, ast.Subscript):
        base = infer_type(node.value, scope)
        if base in ("list", "tuple", "str"):
            return "unknown"  # no inferimos el tipo del elemento
        return "unknown"

    if isinstance(node, ast.IfExp):
        return infer_type(node.body, scope)

    return "unknown"


def type_annotation_to_str(annotation) -> str:
    """Convierte una anotación de tipo AST a string."""
    if annotation is None:
        return "unknown"
    if isinstance(annotation, ast.Name):
        return annotation.id
    if isinstance(annotation, ast.Constant):
        return str(annotation.value)
    if isinstance(annotation, ast.Subscript):
        return ast.unparse(annotation) if hasattr(ast, "unparse") else "unknown"
    return "unknown"


# ─── Analizador Semántico principal ──────────────────────────────────────────

class SemanticAnalyzer(ast.NodeVisitor):
    """
    Recorre el AST y realiza análisis semántico:
    - Tabla de símbolos por scope
    - Inferencia de tipos
    - Variables no declaradas / no usadas
    - Funciones no definidas / argumentos incorrectos
    - División por cero
    - Retorno faltante o inconsistente
    - Código inalcanzable
    - Importaciones no usadas
    """

    def __init__(self):
        self.global_scope = SymbolTable("global")
        self.current_scope = self.global_scope
        self.errors: List[SemanticError] = []
        self.warnings: List[SemanticError] = []
        self._function_stack: List[Dict] = []  # info sobre la función actual
        self._loop_depth = 0

        # Builtins conocidos (no se reportan como no definidos)
        self._builtins: Set[str] = {
            "print", "input", "len", "range", "int", "float", "str", "bool",
            "list", "dict", "set", "tuple", "type", "isinstance", "issubclass",
            "hasattr", "getattr", "setattr", "delattr", "abs", "round", "min",
            "max", "sum", "sorted", "reversed", "enumerate", "zip", "map",
            "filter", "any", "all", "open", "repr", "id", "hash", "chr", "ord",
            "hex", "oct", "bin", "format", "vars", "dir", "help", "callable",
            "iter", "next", "super", "object", "classmethod", "staticmethod",
            "property", "NotImplemented", "Ellipsis", "__name__", "__file__",
            "__doc__", "Exception", "ValueError", "TypeError", "KeyError",
            "IndexError", "AttributeError", "RuntimeError", "StopIteration",
            "OverflowError", "ZeroDivisionError", "FileNotFoundError",
            "OSError", "IOError", "ImportError", "NameError", "AssertionError",
            "NotImplementedError", "RecursionError", "MemoryError",
            "ArithmeticError", "LookupError", "SyntaxError", "IndentationError",
            "GeneratorExit", "SystemExit", "KeyboardInterrupt", "BaseException",
            "print", "True", "False", "None",
        }

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _add_error(self, kind: SemanticErrorKind, msg: str,
                   line: int, col: int = 0, warning: bool = False):
        e = SemanticError(kind, msg, line, col, is_warning=warning)
        if warning:
            self.warnings.append(e)
        else:
            self.errors.append(e)

    def _enter_scope(self, name: str) -> SymbolTable:
        child = self.current_scope.child_scope(name)
        self.current_scope = child
        return child

    def _leave_scope(self):
        self.current_scope = self.current_scope.parent

    def _define(self, name: str, sym_type: str, inferred: str, line: int):
        sym = Symbol(
            name=name,
            symbol_type=sym_type,
            inferred_type=inferred,
            line=line,
            scope=self.current_scope.name,
        )
        self.current_scope.define(sym)

    # ── Visits ────────────────────────────────────────────────────────────────

    def visit_Import(self, node: ast.Import):
        for alias in node.names:
            local_name = alias.asname if alias.asname else alias.name.split(".")[0]
            self._define(local_name, "import", "module", node.lineno)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom):
        for alias in node.names:
            local_name = alias.asname if alias.asname else alias.name
            if local_name == "*":
                continue  # wildcard import — no podemos rastrear
            self._define(local_name, "import", "unknown", node.lineno)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        # Inferir tipo de retorno desde anotación si existe
        return_type = type_annotation_to_str(node.returns)

        self._define(node.name, "function", return_type, node.lineno)

        self._enter_scope(f"function:{node.name}")
        self._function_stack.append({
            "name": node.name,
            "line": node.lineno,
            "has_return": False,
            "all_paths_return": False,
            "annotated_return": node.returns is not None and return_type != "None",
        })

        # Definir parámetros en el scope de la función
        all_args = (
            node.args.args +
            node.args.posonlyargs +
            node.args.kwonlyargs +
            ([node.args.vararg] if node.args.vararg else []) +
            ([node.args.kwarg] if node.args.kwarg else [])
        )
        for arg in all_args:
            ann = type_annotation_to_str(arg.annotation) if arg.annotation else "unknown"
            self._define(arg.arg, "parameter", ann, node.lineno)

        self.generic_visit(node)

        # Verificar retorno faltante
        func_info = self._function_stack[-1]
        if (func_info["annotated_return"] and
                not func_info["has_return"] and
                node.name != "__init__"):
            self._add_error(
                SemanticErrorKind.MISSING_RETURN,
                f"La función '{node.name}' tiene anotación de retorno pero no contiene 'return'",
                node.lineno, warning=True
            )

        # Advertir sobre variables no usadas en este scope
        for sym in self.current_scope.symbols.values():
            if (sym.symbol_type == "variable" and
                    not sym.used and
                    not sym.name.startswith("_")):
                self._add_error(
                    SemanticErrorKind.UNUSED_VAR,
                    f"Variable '{sym.name}' declarada en '{node.name}' pero nunca usada",
                    sym.line, warning=True
                )

        self._function_stack.pop()
        self._leave_scope()

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef):
        self._define(node.name, "class", "class", node.lineno)
        self._enter_scope(f"class:{node.name}")
        self.generic_visit(node)
        self._leave_scope()

    def visit_Assign(self, node: ast.Assign):
        # Primero visitar el valor para registrar usos
        self.visit(node.value)

        inferred = infer_type(node.value, self.current_scope)

        for target in node.targets:
            if isinstance(target, ast.Name):
                existing = self.current_scope.lookup_local(target.id)
                if existing and existing.inferred_type != inferred and inferred != "unknown":
                    # Reasignación con tipo diferente → advertencia
                    if existing.inferred_type != "unknown":
                        self._add_error(
                            SemanticErrorKind.TYPE_MISMATCH,
                            f"Variable '{target.id}' fue '{existing.inferred_type}', "
                            f"ahora se reasigna como '{inferred}'",
                            node.lineno, warning=True
                        )
                self._define(target.id, "variable", inferred, node.lineno)
            elif isinstance(target, (ast.Tuple, ast.List)):
                for elt in target.elts:
                    if isinstance(elt, ast.Name):
                        self._define(elt.id, "variable", "unknown", node.lineno)
            else:
                self._visit_target(target)

    def _visit_target(self, target):
        """Visita sub-targets (atributos, subscripts) para marcar usos."""
        if isinstance(target, ast.Attribute):
            self.visit(target.value)
        elif isinstance(target, ast.Subscript):
            self.visit(target.value)
            self.visit(target.slice)

    def visit_AnnAssign(self, node: ast.AnnAssign):
        ann = type_annotation_to_str(node.annotation)
        if node.value:
            self.visit(node.value)
            inferred = infer_type(node.value, self.current_scope)
            # Verificar consistencia anotación vs inferido
            if ann != "unknown" and inferred != "unknown" and ann != inferred:
                self._add_error(
                    SemanticErrorKind.TYPE_MISMATCH,
                    f"Variable '{ast.unparse(node.target) if hasattr(ast,'unparse') else '?'}' "
                    f"anotada como '{ann}' pero se asigna valor de tipo '{inferred}'",
                    node.lineno, warning=True
                )
        if isinstance(node.target, ast.Name):
            self._define(node.target.id, "variable", ann, node.lineno)

    def visit_AugAssign(self, node: ast.AugAssign):
        if isinstance(node.target, ast.Name):
            sym = self.current_scope.lookup(node.target.id)
            if sym is None and node.target.id not in self._builtins:
                self._add_error(
                    SemanticErrorKind.UNDEFINED_VAR,
                    f"Variable '{node.target.id}' usada antes de ser definida",
                    node.lineno
                )
            elif sym:
                sym.used = True
        self.visit(node.value)

    def visit_Name(self, node: ast.Name):
        if isinstance(node.ctx, ast.Load):
            name = node.id
            if name in ("True", "False", "None"):
                return
            if name in self._builtins:
                return
            sym = self.current_scope.lookup(name)
            if sym is None:
                self._add_error(
                    SemanticErrorKind.UNDEFINED_VAR,
                    f"Nombre '{name}' no está definido en este scope",
                    node.lineno
                )
            else:
                sym.used = True

    def visit_Return(self, node: ast.Return):
        if self._function_stack:
            self._function_stack[-1]["has_return"] = True
        self.generic_visit(node)

    def visit_For(self, node: ast.For):
        self._loop_depth += 1
        # Definir variable(s) del loop
        if isinstance(node.target, ast.Name):
            self._define(node.target.id, "variable", "unknown", node.lineno)
        elif isinstance(node.target, (ast.Tuple, ast.List)):
            for elt in node.target.elts:
                if isinstance(elt, ast.Name):
                    self._define(elt.id, "variable", "unknown", node.lineno)
        self.visit(node.iter)
        for stmt in node.body:
            self.visit(stmt)
        for stmt in node.orelse:
            self.visit(stmt)
        self._loop_depth -= 1

    def visit_While(self, node: ast.While):
        self._loop_depth += 1
        self.generic_visit(node)
        self._loop_depth -= 1

    def visit_Call(self, node: ast.Call):
        # Verificar llamadas a funciones definidas por el usuario
        if isinstance(node.func, ast.Name):
            name = node.func.id
            if name not in self._builtins:
                sym = self.current_scope.lookup(name)
                if sym is None:
                    self._add_error(
                        SemanticErrorKind.UNDEFINED_FUNC,
                        f"Función o nombre '{name}' no está definido",
                        node.lineno
                    )
                elif sym.symbol_type == "function":
                    sym.used = True
        self.generic_visit(node)

    def visit_BinOp(self, node: ast.BinOp):
        self.generic_visit(node)

        # División por cero estática
        if isinstance(node.op, (ast.Div, ast.FloorDiv, ast.Mod)):
            if isinstance(node.right, ast.Constant) and node.right.value == 0:
                self._add_error(
                    SemanticErrorKind.DIVISION_BY_ZERO,
                    "División por cero detectada estáticamente",
                    node.lineno
                )

        # Operación inválida entre tipos incompatibles
        left_t = infer_type(node.left, self.current_scope)
        right_t = infer_type(node.right, self.current_scope)
        if left_t != "unknown" and right_t != "unknown":
            if isinstance(node.op, ast.Sub) and "str" in (left_t, right_t):
                self._add_error(
                    SemanticErrorKind.INVALID_OPERATION,
                    f"Operación '-' inválida entre tipos '{left_t}' y '{right_t}'",
                    node.lineno, warning=True
                )
            if isinstance(node.op, ast.Mult) and left_t == "str" and right_t == "str":
                self._add_error(
                    SemanticErrorKind.INVALID_OPERATION,
                    "Operación '*' entre dos strings no está permitida",
                    node.lineno, warning=True
                )

    def visit_If(self, node: ast.If):
        self.visit(node.test)
        for stmt in node.body:
            self.visit(stmt)
        # Detectar código inalcanzable: if True: ... else: <unreachable>
        if isinstance(node.test, ast.Constant):
            if node.test.value is True and node.orelse:
                self._add_error(
                    SemanticErrorKind.UNREACHABLE_CODE,
                    "El bloque 'else' es inalcanzable (condición siempre verdadera)",
                    node.lineno, warning=True
                )
            elif node.test.value is False and node.body:
                self._add_error(
                    SemanticErrorKind.UNREACHABLE_CODE,
                    "El bloque 'if' es inalcanzable (condición siempre falsa)",
                    node.lineno, warning=True
                )
        for stmt in node.orelse:
            self.visit(stmt)

    def visit_Global(self, node: ast.Global):
        for name in node.names:
            sym = self.global_scope.lookup(name)
            if sym is None:
                self._add_error(
                    SemanticErrorKind.SCOPE_ERROR,
                    f"'global {name}': '{name}' no está definido en el scope global",
                    node.lineno, warning=True
                )

    def _check_unused_imports(self):
        for sym in self.global_scope.symbols.values():
            if sym.symbol_type == "import" and not sym.used:
                self._add_error(
                    SemanticErrorKind.UNUSED_IMPORT,
                    f"Importación '{sym.name}' nunca se usa",
                    sym.line, warning=True
                )

    def _check_unused_globals(self):
        for sym in self.global_scope.symbols.values():
            if (sym.symbol_type == "variable" and
                    not sym.used and
                    not sym.name.startswith("_")):
                self._add_error(
                    SemanticErrorKind.UNUSED_VAR,
                    f"Variable global '{sym.name}' declarada pero nunca usada",
                    sym.line, warning=True
                )

    # ── Punto de entrada ──────────────────────────────────────────────────────

    def analyze(self, source_code: str) -> "SemanticResult":
        import ast as _ast
        self.errors = []
        self.warnings = []
        self.global_scope = SymbolTable("global")
        self.current_scope = self.global_scope
        self._function_stack = []

        try:
            tree = _ast.parse(source_code, mode="exec")
        except SyntaxError as e:
            return SemanticResult(
                success=False,
                errors=[SemanticError(
                    SemanticErrorKind.INVALID_OPERATION,
                    f"No se puede analizar: error de sintaxis — {e.msg}",
                    e.lineno or 0, is_warning=False
                )],
                warnings=[],
                symbol_table=self.global_scope,
            )

        self.visit(tree)
        self._check_unused_imports()
        self._check_unused_globals()

        return SemanticResult(
            success=len(self.errors) == 0,
            errors=self.errors,
            warnings=self.warnings,
            symbol_table=self.global_scope,
        )


# ─── Resultado ────────────────────────────────────────────────────────────────

@dataclass
class SemanticResult:
    success: bool
    errors: List[SemanticError]
    warnings: List[SemanticError]
    symbol_table: SymbolTable

    def to_dict(self):
        return {
            "success": self.success,
            "errors": [e.to_dict() for e in self.errors],
            "warnings": [w.to_dict() for w in self.warnings],
            "symbols": [s.to_dict() for s in self.symbol_table.all_symbols_flat()],
        }


# ─── Helper de conveniencia ───────────────────────────────────────────────────

def run_semantic_analysis(source_code: str) -> SemanticResult:
    analyzer = SemanticAnalyzer()
    return analyzer.analyze(source_code)
