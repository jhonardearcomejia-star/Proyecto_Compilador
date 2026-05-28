"""
parser.py - Analizador sintáctico para código Python
Valida la sintaxis y extrae información estructural del código.
"""

import ast
import sys
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class ParseError:
    message: str
    line: int
    column: int
    text: Optional[str] = None

    def __str__(self):
        loc = f"Línea {self.line}, Columna {self.column}"
        txt = f"\n  → {self.text}" if self.text else ""
        return f"[Error de sintaxis] {loc}: {self.message}{txt}"


@dataclass
class ParseResult:
    success: bool
    errors: List[ParseError] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    tree: Optional[ast.AST] = None
    stats: Dict = field(default_factory=dict)

    def to_dict(self):
        return {
            "success": self.success,
            "errors": [{"message": e.message, "line": e.line, "column": e.column, "text": e.text} for e in self.errors],
            "warnings": self.warnings,
            "stats": self.stats
        }


class Parser:
    """
    Analizador sintáctico que valida código Python y extrae su estructura.
    """

    def __init__(self):
        self.errors: List[ParseError] = []
        self.warnings: List[str] = []

    def parse(self, source_code: str) -> ParseResult:
        """
        Parsea el código fuente y retorna un ParseResult con toda la información.
        """
        self.errors = []
        self.warnings = []

        if not source_code.strip():
            return ParseResult(
                success=True,
                warnings=["El código está vacío."],
                stats={}
            )

        try:
            tree = ast.parse(source_code, mode='exec')
            stats = self._analyze_tree(tree, source_code)
            self._check_style_warnings(source_code, tree)

            return ParseResult(
                success=True,
                errors=[],
                warnings=self.warnings,
                tree=tree,
                stats=stats
            )

        except SyntaxError as e:
            error = ParseError(
                message=e.msg,
                line=e.lineno or 0,
                column=e.offset or 0,
                text=e.text.strip() if e.text else None
            )
            self.errors.append(error)
            return ParseResult(
                success=False,
                errors=self.errors,
                warnings=self.warnings,
                tree=None,
                stats={}
            )

        except Exception as e:
            error = ParseError(
                message=str(e),
                line=0,
                column=0
            )
            self.errors.append(error)
            return ParseResult(
                success=False,
                errors=self.errors,
                warnings=self.warnings,
                tree=None,
                stats={}
            )

    def _analyze_tree(self, tree: ast.AST, source: str) -> Dict:
        """Analiza el árbol AST y extrae estadísticas."""
        stats = {
            "lineas_totales": len(source.splitlines()),
            "lineas_codigo": sum(1 for l in source.splitlines() if l.strip() and not l.strip().startswith('#')),
            "lineas_comentarios": sum(1 for l in source.splitlines() if l.strip().startswith('#')),
            "funciones": [],
            "clases": [],
            "variables_globales": [],
            "importaciones": [],
            "complejidad_ciclomatica": 1,  # base
            "bucles": 0,
            "condicionales": 0,
            "excepciones": 0,
        }

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                func_info = self._analyze_function(node)
                stats["funciones"].append(func_info)

            elif isinstance(node, ast.ClassDef):
                class_info = self._analyze_class(node)
                stats["clases"].append(class_info)

            elif isinstance(node, ast.Assign) and self._is_global_assignment(node, tree):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        stats["variables_globales"].append({
                            "nombre": target.id,
                            "linea": node.lineno
                        })

            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                imp = self._analyze_import(node)
                stats["importaciones"].append(imp)

            # Complejidad ciclomática
            elif isinstance(node, (ast.If, ast.While, ast.For, ast.ExceptHandler)):
                stats["complejidad_ciclomatica"] += 1

            if isinstance(node, (ast.For, ast.While, ast.AsyncFor)):
                stats["bucles"] += 1

            if isinstance(node, ast.If):
                stats["condicionales"] += 1

            if isinstance(node, (ast.Try, ast.ExceptHandler)):
                stats["excepciones"] += 1

        return stats

    def _analyze_function(self, node: ast.FunctionDef) -> Dict:
        """Analiza una función y extrae su información."""
        args = []
        for arg in node.args.args:
            arg_info = {"nombre": arg.arg, "anotacion": None}
            if arg.annotation:
                if isinstance(arg.annotation, ast.Name):
                    arg_info["anotacion"] = arg.annotation.id
                elif isinstance(arg.annotation, ast.Constant):
                    arg_info["anotacion"] = str(arg.annotation.value)
            args.append(arg_info)

        # Valor de retorno
        returns = None
        if node.returns:
            if isinstance(node.returns, ast.Name):
                returns = node.returns.id
            elif isinstance(node.returns, ast.Constant):
                returns = str(node.returns.value)

        # Docstring
        docstring = ast.get_docstring(node)

        # Decoradores
        decorators = []
        for dec in node.decorator_list:
            if isinstance(dec, ast.Name):
                decorators.append(dec.id)
            elif isinstance(dec, ast.Attribute):
                decorators.append(f"{dec.value.id if isinstance(dec.value, ast.Name) else '?'}.{dec.attr}")

        return {
            "nombre": node.name,
            "args": args,
            "retorno": returns,
            "linea": node.lineno,
            "es_async": isinstance(node, ast.AsyncFunctionDef),
            "docstring": docstring,
            "decoradores": decorators,
            "longitud": node.end_lineno - node.lineno + 1 if hasattr(node, 'end_lineno') else None
        }

    def _analyze_class(self, node: ast.ClassDef) -> Dict:
        """Analiza una clase y extrae su información."""
        bases = []
        for base in node.bases:
            if isinstance(base, ast.Name):
                bases.append(base.id)

        methods = []
        for item in node.body:
            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                methods.append(item.name)

        docstring = ast.get_docstring(node)

        return {
            "nombre": node.name,
            "bases": bases,
            "metodos": methods,
            "linea": node.lineno,
            "docstring": docstring
        }

    def _analyze_import(self, node) -> Dict:
        """Analiza una importación."""
        if isinstance(node, ast.Import):
            return {
                "tipo": "import",
                "modulos": [{"nombre": a.name, "alias": a.asname} for a in node.names],
                "linea": node.lineno
            }
        else:  # ImportFrom
            return {
                "tipo": "from_import",
                "modulo": node.module or "",
                "nombres": [{"nombre": a.name, "alias": a.asname} for a in node.names],
                "linea": node.lineno
            }

    def _is_global_assignment(self, node: ast.Assign, tree: ast.AST) -> bool:
        """Verifica si una asignación es en el scope global."""
        for top_node in ast.walk(tree):
            if isinstance(top_node, ast.Module):
                for child in top_node.body:
                    if child is node:
                        return True
        return False

    def _check_style_warnings(self, source: str, tree: ast.AST):
        """Verifica posibles advertencias de estilo."""
        lines = source.splitlines()

        # Líneas muy largas
        for i, line in enumerate(lines, 1):
            if len(line) > 79:
                self.warnings.append(f"Línea {i}: excede 79 caracteres (PEP 8) — tiene {len(line)}")

        # Funciones sin docstring
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                if not ast.get_docstring(node) and node.name != '__init__':
                    self.warnings.append(f"Función '{node.name}' (línea {node.lineno}) no tiene docstring")

        # Variables con nombres de una sola letra (excepto i, j, k, x, y, z)
        allowed_singles = {'i', 'j', 'k', 'x', 'y', 'z', 'n', 'm', '_'}
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                if len(node.id) == 1 and node.id not in allowed_singles:
                    self.warnings.append(f"Variable '{node.id}' tiene nombre muy corto (línea {node.lineno})")


def validate_syntax(source_code: str) -> Tuple[bool, Optional[str], Optional[int]]:
    """
    Función rápida para validar sintaxis.
    Retorna (es_valido, mensaje_error, numero_linea)
    """
    parser = Parser()
    result = parser.parse(source_code)

    if result.success:
        return True, None, None
    else:
        if result.errors:
            err = result.errors[0]
            return False, str(err.message), err.line
        return False, "Error desconocido", None
