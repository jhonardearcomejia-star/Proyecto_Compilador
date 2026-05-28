"""
ast_generator.py - Generador y visualizador del Árbol Sintáctico Abstracto (AST)
Utiliza el módulo ast de Python para generar y visualizar el AST del código.
"""

import ast
import json
from typing import Any, Dict, List, Optional


class ASTGenerationError(Exception):
    def __init__(self, message, lineno=None, offset=None):
        super().__init__(message)
        self.lineno = lineno
        self.offset = offset


def parse_code(source_code: str) -> ast.AST:
    """
    Parsea el código fuente y retorna el AST.
    Lanza ASTGenerationError si hay errores de sintaxis.
    """
    try:
        tree = ast.parse(source_code, mode='exec')
        return tree
    except SyntaxError as e:
        raise ASTGenerationError(
            f"Error de sintaxis: {e.msg}",
            lineno=e.lineno,
            offset=e.offset
        )
    except ValueError as e:
        raise ASTGenerationError(f"Error de valor: {e}")


def ast_to_dict(node: Any, depth: int = 0, max_depth: int = 20) -> Dict:
    """
    Convierte un nodo AST a un diccionario serializable.
    """
    if depth > max_depth:
        return {"type": "...(profundidad máxima alcanzada)"}

    if isinstance(node, ast.AST):
        result = {"_type": type(node).__name__}

        # Agregar información de posición si está disponible
        if hasattr(node, 'lineno'):
            result["_line"] = node.lineno
        if hasattr(node, 'col_offset'):
            result["_col"] = node.col_offset

        for field_name, field_value in ast.iter_fields(node):
            result[field_name] = ast_to_dict(field_value, depth + 1, max_depth)

        return result

    elif isinstance(node, list):
        return [ast_to_dict(item, depth + 1, max_depth) for item in node]

    elif isinstance(node, (int, float, str, bool, type(None))):
        return node

    else:
        return str(node)


def ast_to_text_tree(node: Any, indent: str = "", is_last: bool = True, depth: int = 0, max_depth: int = 10) -> str:
    """
    Genera una representación de texto del AST con formato de árbol.
    """
    if depth > max_depth:
        return indent + ("└── " if is_last else "├── ") + "...\n"

    lines = []
    connector = "└── " if is_last else "├── "
    child_indent = indent + ("    " if is_last else "│   ")

    if isinstance(node, ast.AST):
        node_name = type(node).__name__

        # Agregar info extra útil según el tipo de nodo
        extra = _get_node_extra(node)
        label = f"{node_name}{extra}"

        lines.append(indent + connector + label + "\n")

        children = list(ast.iter_fields(node))
        for i, (field_name, field_value) in enumerate(children):
            is_last_child = (i == len(children) - 1)
            if isinstance(field_value, list) and field_value:
                lines.append(child_indent + ("└── " if is_last_child else "├── ") + f"[{field_name}]\n")
                list_indent = child_indent + ("    " if is_last_child else "│   ")
                for j, item in enumerate(field_value):
                    lines.append(ast_to_text_tree(item, list_indent, j == len(field_value) - 1, depth + 1, max_depth))
            elif isinstance(field_value, ast.AST):
                lines.append(child_indent + ("└── " if is_last_child else "├── ") + f"{field_name}:\n")
                sub_indent = child_indent + ("    " if is_last_child else "│   ")
                lines.append(ast_to_text_tree(field_value, sub_indent, True, depth + 1, max_depth))
            elif field_value is not None and field_value != [] and field_value != '':
                val_str = repr(field_value) if isinstance(field_value, str) else str(field_value)
                if len(val_str) > 40:
                    val_str = val_str[:37] + "..."
                lines.append(child_indent + ("└── " if is_last_child else "├── ") + f"{field_name}: {val_str}\n")

    elif isinstance(node, list):
        for i, item in enumerate(node):
            lines.append(ast_to_text_tree(item, indent, i == len(node) - 1, depth, max_depth))

    elif node is not None:
        val_str = repr(node) if isinstance(node, str) else str(node)
        lines.append(indent + connector + val_str + "\n")

    return "".join(lines)


def _get_node_extra(node: ast.AST) -> str:
    """Extrae información extra relevante de un nodo AST."""
    if isinstance(node, ast.Name):
        return f" → '{node.id}'"
    elif isinstance(node, ast.Constant):
        val = repr(node.value)
        if len(val) > 20:
            val = val[:17] + "..."
        return f" → {val}"
    elif isinstance(node, ast.FunctionDef):
        args = [a.arg for a in node.args.args]
        return f" → {node.name}({', '.join(args)})"
    elif isinstance(node, ast.AsyncFunctionDef):
        args = [a.arg for a in node.args.args]
        return f" → async {node.name}({', '.join(args)})"
    elif isinstance(node, ast.ClassDef):
        return f" → {node.name}"
    elif isinstance(node, ast.Import):
        names = [alias.name for alias in node.names]
        return f" → {', '.join(names)}"
    elif isinstance(node, ast.ImportFrom):
        return f" → from {node.module}"
    elif isinstance(node, ast.Assign):
        targets = []
        for t in node.targets:
            if isinstance(t, ast.Name):
                targets.append(t.id)
        if targets:
            return f" → {', '.join(targets)}"
    elif isinstance(node, ast.AugAssign):
        if isinstance(node.target, ast.Name):
            return f" → {node.target.id}"
    elif isinstance(node, ast.For):
        if isinstance(node.target, ast.Name):
            return f" → {node.target.id}"
    elif isinstance(node, ast.Attribute):
        return f" → .{node.attr}"
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            return f" → {node.func.id}()"
        elif isinstance(node.func, ast.Attribute):
            return f" → .{node.func.attr}()"
    return ""


def get_ast_summary(tree: ast.AST) -> Dict:
    """
    Genera un resumen estadístico del AST.
    """
    summary = {
        "funciones": [],
        "clases": [],
        "variables": [],
        "importaciones": [],
        "total_nodos": 0,
        "tipos_nodos": {}
    }

    for node in ast.walk(tree):
        summary["total_nodos"] += 1
        node_type = type(node).__name__
        summary["tipos_nodos"][node_type] = summary["tipos_nodos"].get(node_type, 0) + 1

        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = [a.arg for a in node.args.args]
            summary["funciones"].append({
                "nombre": node.name,
                "args": args,
                "linea": node.lineno,
                "es_async": isinstance(node, ast.AsyncFunctionDef)
            })
        elif isinstance(node, ast.ClassDef):
            bases = []
            for b in node.bases:
                if isinstance(b, ast.Name):
                    bases.append(b.id)
            summary["clases"].append({
                "nombre": node.name,
                "bases": bases,
                "linea": node.lineno
            })
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    val_type = _infer_type(node.value)
                    summary["variables"].append({
                        "nombre": target.id,
                        "tipo_inferido": val_type,
                        "linea": node.lineno
                    })
        elif isinstance(node, ast.Import):
            for alias in node.names:
                summary["importaciones"].append({
                    "modulo": alias.name,
                    "alias": alias.asname,
                    "linea": node.lineno
                })
        elif isinstance(node, ast.ImportFrom):
            for alias in node.names:
                summary["importaciones"].append({
                    "modulo": f"{node.module}.{alias.name}",
                    "alias": alias.asname,
                    "linea": node.lineno
                })

    return summary


def _infer_type(node: ast.AST) -> str:
    """Infiere el tipo de un nodo de valor AST."""
    if isinstance(node, ast.Constant):
        return type(node.value).__name__
    elif isinstance(node, ast.List):
        return 'list'
    elif isinstance(node, ast.Dict):
        return 'dict'
    elif isinstance(node, ast.Set):
        return 'set'
    elif isinstance(node, ast.Tuple):
        return 'tuple'
    elif isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name):
            return f'{node.func.id}()'
    elif isinstance(node, (ast.BinOp, ast.UnaryOp)):
        return 'expr'
    elif isinstance(node, ast.ListComp):
        return 'list'
    elif isinstance(node, ast.DictComp):
        return 'dict'
    return 'unknown'


# ─── Árbol estructural simplificado ──────────────────────────────────────────
# Nodos estructurales que se muestran en el grafo (excluye nodos internos/expr)
_STRUCTURAL = (
    ast.Module,
    ast.FunctionDef, ast.AsyncFunctionDef,
    ast.ClassDef,
    ast.Import, ast.ImportFrom,
    ast.Assign, ast.AugAssign, ast.AnnAssign,
    ast.If, ast.For, ast.While,
    ast.Try, ast.With,
    ast.Return, ast.Yield, ast.YieldFrom, ast.Raise,
    ast.Delete, ast.Global, ast.Nonlocal,
    ast.Assert, ast.Pass, ast.Break, ast.Continue,
    ast.ExceptHandler,
)

# Etiquetas legibles y categorías de color para cada tipo de nodo
_NODE_META = {
    ast.Module:             ("Módulo",         "module"),
    ast.FunctionDef:        ("Función",         "function"),
    ast.AsyncFunctionDef:   ("Func. async",     "function"),
    ast.ClassDef:           ("Clase",           "class"),
    ast.Import:             ("import",          "import"),
    ast.ImportFrom:         ("from … import",   "import"),
    ast.Assign:             ("Asignación",      "assign"),
    ast.AugAssign:          ("Asig. compuesta", "assign"),
    ast.AnnAssign:          ("Var. tipada",     "assign"),
    ast.If:                 ("if",              "control"),
    ast.For:                ("for",             "control"),
    ast.While:              ("while",           "control"),
    ast.Try:                ("try / except",    "control"),
    ast.With:               ("with",            "control"),
    ast.ExceptHandler:      ("except",          "control"),
    ast.Return:             ("return",          "return"),
    ast.Yield:              ("yield",           "return"),
    ast.YieldFrom:          ("yield from",      "return"),
    ast.Raise:              ("raise",           "return"),
    ast.Delete:             ("del",             "default"),
    ast.Global:             ("global",          "default"),
    ast.Nonlocal:           ("nonlocal",        "default"),
    ast.Assert:             ("assert",          "default"),
    ast.Pass:               ("pass",            "value"),
    ast.Break:              ("break",           "control"),
    ast.Continue:           ("continue",        "control"),
}


def _node_label_extra(node: ast.AST):
    """Etiqueta legible y detalle extra para cada nodo estructural."""
    label, category = _NODE_META.get(type(node), (type(node).__name__, "default"))

    # Detalle adicional (nombre, condición, variable, etc.)
    extra = ""
    if isinstance(node, ast.Module):
        n = len(node.body)
        extra = f"{n} instrucción{'es' if n != 1 else ''}"
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        args = [a.arg for a in node.args.args]
        args_str = ", ".join(args[:4]) + ("…" if len(args) > 4 else "")
        extra = f"{node.name}({args_str})"
    elif isinstance(node, ast.ClassDef):
        bases = [b.id for b in node.bases if isinstance(b, ast.Name)]
        extra = node.name + (f"({', '.join(bases)})" if bases else "")
    elif isinstance(node, ast.Import):
        names = [a.name for a in node.names[:2]]
        extra = ", ".join(names) + ("…" if len(node.names) > 2 else "")
    elif isinstance(node, ast.ImportFrom):
        extra = f"{node.module or '?'}"
    elif isinstance(node, ast.Assign):
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        extra = ", ".join(targets[:3]) if targets else ""
    elif isinstance(node, ast.AugAssign):
        if isinstance(node.target, ast.Name):
            op = type(node.op).__name__.replace("Add", "+=").replace("Sub", "-=") \
                    .replace("Mult", "*=").replace("Div", "/=")
            extra = f"{node.target.id} {op}"
    elif isinstance(node, ast.AnnAssign):
        if isinstance(node.target, ast.Name):
            ann = node.annotation.id if isinstance(node.annotation, ast.Name) else "?"
            extra = f"{node.target.id}: {ann}"
    elif isinstance(node, ast.If):
        extra = _expr_summary(node.test)
    elif isinstance(node, ast.For):
        var = node.target.id if isinstance(node.target, ast.Name) else "?"
        extra = f"{var} in …"
    elif isinstance(node, ast.While):
        extra = _expr_summary(node.test)
    elif isinstance(node, ast.With):
        if node.items:
            ctx = node.items[0].context_expr
            extra = _expr_summary(ctx)
    elif isinstance(node, ast.ExceptHandler):
        if node.type:
            extra = node.type.id if isinstance(node.type, ast.Name) else "?"
        if node.name:
            extra += f" as {node.name}"
    elif isinstance(node, ast.Return):
        if node.value:
            extra = _expr_summary(node.value)
    elif isinstance(node, ast.Raise):
        if node.exc:
            extra = _expr_summary(node.exc)
    elif isinstance(node, ast.Assert):
        extra = _expr_summary(node.test)
    elif isinstance(node, ast.Global):
        extra = ", ".join(node.names[:3])
    elif isinstance(node, ast.Nonlocal):
        extra = ", ".join(node.names[:3])
    elif isinstance(node, ast.Delete):
        targets = [_expr_summary(t) for t in node.targets[:2]]
        extra = ", ".join(targets)

    return label, extra, category


def _expr_summary(node: ast.AST) -> str:
    """Representación compacta de una expresión (para mostrar en el nodo)."""
    if isinstance(node, ast.Name):
        return node.id
    elif isinstance(node, ast.Constant):
        v = repr(node.value)
        return v[:16] + "…" if len(v) > 16 else v
    elif isinstance(node, ast.Call):
        fn = _expr_summary(node.func)
        return f"{fn}()"
    elif isinstance(node, ast.Attribute):
        return f"{_expr_summary(node.value)}.{node.attr}"
    elif isinstance(node, ast.Compare):
        left = _expr_summary(node.left)
        op = type(node.ops[0]).__name__ if node.ops else "?"
        right = _expr_summary(node.comparators[0]) if node.comparators else "?"
        op_sym = {"Eq": "==", "NotEq": "!=", "Lt": "<", "LtE": "<=",
                  "Gt": ">", "GtE": ">=", "In": "in", "NotIn": "not in",
                  "Is": "is", "IsNot": "is not"}.get(op, op)
        return f"{left} {op_sym} {right}"
    elif isinstance(node, ast.BoolOp):
        op = "and" if isinstance(node.op, ast.And) else "or"
        return f"… {op} …"
    elif isinstance(node, ast.BinOp):
        return f"{_expr_summary(node.left)} ○ {_expr_summary(node.right)}"
    elif isinstance(node, ast.UnaryOp):
        op = "not " if isinstance(node.op, ast.Not) else "-"
        return f"{op}{_expr_summary(node.operand)}"
    elif isinstance(node, ast.Subscript):
        return f"{_expr_summary(node.value)}[…]"
    return type(node).__name__


def _structural_children(node: ast.AST) -> List:
    """Devuelve solo los hijos estructurales (statements relevantes) de un nodo."""
    result = []

    def _scan_body(stmts):
        for stmt in (stmts or []):
            if isinstance(stmt, _STRUCTURAL):
                result.append(stmt)
            elif isinstance(stmt, ast.Expr):
                # Exponer llamadas a funciones en nivel de expresión
                if isinstance(stmt.value, ast.Call):
                    result.append(("call_expr", stmt.value, getattr(stmt, 'lineno', None)))

    if isinstance(node, ast.Module):
        _scan_body(node.body)
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        _scan_body(node.body)
    elif isinstance(node, ast.ClassDef):
        _scan_body(node.body)
    elif isinstance(node, ast.If):
        _scan_body(node.body)
        _scan_body(node.orelse)
    elif isinstance(node, ast.For):
        _scan_body(node.body)
        _scan_body(node.orelse)
    elif isinstance(node, ast.While):
        _scan_body(node.body)
        _scan_body(node.orelse)
    elif isinstance(node, ast.Try):
        _scan_body(node.body)
        _scan_body(node.handlers)   # ExceptHandler items
        _scan_body(node.orelse)
        _scan_body(node.finalbody)
    elif isinstance(node, ast.With):
        _scan_body(node.body)
    elif isinstance(node, ast.ExceptHandler):
        _scan_body(node.body)

    return result


def ast_to_graph(source_node: Any) -> Dict:
    """
    Convierte el AST en un grafo simplificado que muestra solo
    la estructura del código (módulo, funciones, clases, imports,
    asignaciones, control de flujo, etc.).
    Retorna: {"nodes": [...], "edges": [...]}
    """
    nodes: List = []
    edges: List = []
    counter = [0]

    def _visit(node, parent_id, depth, max_depth=30):
        if depth > max_depth:
            return

        # Nodo de llamada a función desempaquetado de ast.Expr
        if isinstance(node, tuple) and node[0] == "call_expr":
            _, call_node, lineno = node
            nid = f"n{counter[0]}"
            counter[0] += 1
            fn_name = _expr_summary(call_node.func)
            nodes.append({
                "id": nid,
                "label": "Llamada",
                "extra": f"{fn_name}()",
                "category": "call",
                "line": lineno,
                "depth": depth,
            })
            if parent_id:
                edges.append({"from": parent_id, "to": nid})
            return

        if not isinstance(node, ast.AST):
            return

        nid = f"n{counter[0]}"
        counter[0] += 1

        label, extra, category = _node_label_extra(node)
        line_info = getattr(node, 'lineno', None)

        nodes.append({
            "id": nid,
            "label": label,
            "extra": extra,
            "category": category,
            "line": line_info,
            "depth": depth,
        })

        if parent_id is not None:
            edges.append({"from": parent_id, "to": nid})

        for child in _structural_children(node):
            _visit(child, nid, depth + 1, max_depth)

    _visit(source_node, None, 0)
    return {"nodes": nodes, "edges": edges}


def _get_node_category(node: ast.AST) -> str:
    """Clasifica un nodo AST para asignarle un color en la visualización."""
    _, _, cat = _node_label_extra(node)
    return cat


def generate_ast_report(source_code: str) -> Dict:
    """
    Genera un reporte completo del AST para un código fuente dado.
    """
    try:
        tree = parse_code(source_code)
        tree_dict = ast_to_dict(tree)
        tree_text = "Módulo\n" + ast_to_text_tree(tree, "", True, 0)
        summary = get_ast_summary(tree)

        graph_data = ast_to_graph(tree)

        return {
            "success": True,
            "tree_dict": tree_dict,
            "tree_text": tree_text,
            "summary": summary,
            "graph": graph_data,
            "error": None
        }
    except ASTGenerationError as e:
        return {
            "success": False,
            "tree_dict": None,
            "tree_text": None,
            "summary": None,
            "error": {
                "message": str(e),
                "lineno": e.lineno,
                "offset": e.offset
            }
        }
