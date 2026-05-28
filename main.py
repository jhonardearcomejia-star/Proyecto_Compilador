"""
main.py - Punto de entrada del Compilador/Analizador de Python
Puede usarse como módulo o ejecutarse directamente en la terminal.
"""

import sys
import os
import json
import argparse

# Agregar src al path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from src.lexer import Lexer, TokenType
from src.parser import Parser
from src.ast_generator import generate_ast_report


BANNER = """
╔═══════════════════════════════════════════════════════════╗
║        🐍  Compilador / Analizador de Python  🐍          ║
║              Análisis Léxico · Sintáctico · AST            ║
╚═══════════════════════════════════════════════════════════╝
"""


def analyze_code(source_code: str, verbose: bool = True) -> dict:
    """
    Función principal que ejecuta todo el pipeline de análisis.
    """
    results = {}

    # ─── 1. ANÁLISIS LÉXICO ───────────────────────────────────────────────────
    lexer = Lexer(source_code)
    tokens = lexer.tokenize()
    data_types = lexer.get_data_types()
    token_summary = lexer.get_summary()

    results["lexer"] = {
        "tokens": [t.to_dict() for t in tokens],
        "data_types": data_types,
        "summary": token_summary,
        "errors": [{"message": str(e), "line": e.line, "col": e.column} for e in lexer.errors]
    }

    # ─── 2. ANÁLISIS SINTÁCTICO ───────────────────────────────────────────────
    parser = Parser()
    parse_result = parser.parse(source_code)

    results["parser"] = {
        "success": parse_result.success,
        "errors": [{"message": e.message, "line": e.line, "col": e.column} for e in parse_result.errors],
        "warnings": parse_result.warnings,
        "stats": parse_result.stats
    }

    # ─── 3. ANÁLISIS AST ─────────────────────────────────────────────────────
    ast_report = generate_ast_report(source_code)
    results["ast"] = ast_report

    # ─── 4. EJECUCIÓN OPCIONAL ───────────────────────────────────────────────
    results["execution"] = None

    if verbose:
        _print_results(results, source_code)

    return results


def _print_results(results: dict, source_code: str):
    """Imprime los resultados del análisis en la terminal."""

    print(BANNER)

    # Código fuente
    print("=" * 60)
    print("📄 CÓDIGO FUENTE:")
    print("=" * 60)
    for i, line in enumerate(source_code.splitlines(), 1):
        print(f"  {i:3d} │ {line}")
    print()

    # Tokens
    print("=" * 60)
    print("🔤 TOKENS IDENTIFICADOS:")
    print("=" * 60)
    tokens = results["lexer"]["tokens"]
    printable_types = {
        TokenType.KEYWORD.name, TokenType.IDENTIFIER.name,
        TokenType.INTEGER.name, TokenType.FLOAT.name,
        TokenType.STRING.name, TokenType.BOOL.name,
        TokenType.NONE.name, TokenType.OPERATOR.name,
        TokenType.COMPARISON.name, TokenType.ASSIGNMENT.name,
        TokenType.AUGMENTED_ASSIGN.name
    }
    for tok in tokens:
        if tok["type"] in printable_types and tok["type"] != "EOF":
            dt_str = f" [{tok['data_type']}]" if tok.get("data_type") else ""
            color = _token_color(tok["type"])
            print(f"  {color}{tok['type']:<20}{RESET}  {tok['value']!r:<20} L{tok['line']}:C{tok['column']}{dt_str}")

    print()

    # Tipos de datos
    print("=" * 60)
    print("📊 TIPOS DE DATOS DETECTADOS:")
    print("=" * 60)
    data_types = results["lexer"]["data_types"]
    if data_types:
        for dtype, count in sorted(data_types.items()):
            bar = "█" * min(count * 3, 30)
            print(f"  {dtype:<12} {bar} ({count})")
    else:
        print("  (No se detectaron literales de tipos de datos)")
    print()

    # Resumen del parser
    print("=" * 60)
    print("✅ ANÁLISIS SINTÁCTICO:")
    print("=" * 60)
    parser_result = results["parser"]
    if parser_result["success"]:
        print(f"  ✅ Sintaxis VÁLIDA")
        stats = parser_result["stats"]
        if stats:
            print(f"  📋 Líneas totales:    {stats.get('lineas_totales', 0)}")
            print(f"  📝 Líneas de código:  {stats.get('lineas_codigo', 0)}")
            print(f"  💬 Comentarios:       {stats.get('lineas_comentarios', 0)}")
            print(f"  🔀 Complejidad:       {stats.get('complejidad_ciclomatica', 1)}")
            print(f"  🔁 Bucles:            {stats.get('bucles', 0)}")
            print(f"  ❓ Condicionales:     {stats.get('condicionales', 0)}")

            if stats.get("funciones"):
                print(f"\n  🔧 FUNCIONES ({len(stats['funciones'])}):")
                for f in stats["funciones"]:
                    args = ", ".join(a["nombre"] for a in f["args"])
                    async_str = "async " if f["es_async"] else ""
                    ret = f" → {f['retorno']}" if f.get("retorno") else ""
                    print(f"     • {async_str}{f['nombre']}({args}){ret}  [L{f['linea']}]")

            if stats.get("clases"):
                print(f"\n  🏛️  CLASES ({len(stats['clases'])}):")
                for c in stats["clases"]:
                    bases = f"({', '.join(c['bases'])})" if c["bases"] else ""
                    print(f"     • {c['nombre']}{bases}  [L{c['linea']}]")
                    if c["metodos"]:
                        print(f"       métodos: {', '.join(c['metodos'])}")

            if stats.get("importaciones"):
                print(f"\n  📦 IMPORTACIONES ({len(stats['importaciones'])}):")
                for imp in stats["importaciones"]:
                    if imp["tipo"] == "import":
                        for mod in imp["modulos"]:
                            print(f"     • import {mod['nombre']}")
                    else:
                        nombres = [n["nombre"] for n in imp["nombres"]]
                        print(f"     • from {imp['modulo']} import {', '.join(nombres)}")

        if parser_result["warnings"]:
            print(f"\n  ⚠️  ADVERTENCIAS ({len(parser_result['warnings'])}):")
            for w in parser_result["warnings"][:5]:  # Máximo 5
                print(f"     • {w}")
    else:
        print(f"  ❌ Sintaxis INVÁLIDA")
        for err in parser_result["errors"]:
            print(f"     ✗ L{err['line']}, C{err['col']}: {err['message']}")
    print()

    # AST
    print("=" * 60)
    print("🌳 ÁRBOL SINTÁCTICO ABSTRACTO (AST):")
    print("=" * 60)
    ast_data = results["ast"]
    if ast_data["success"] and ast_data["tree_text"]:
        for line in ast_data["tree_text"].splitlines():
            print("  " + line)
    elif not ast_data["success"] and ast_data["error"]:
        print(f"  ❌ No se pudo generar el AST: {ast_data['error']['message']}")
    print()

    # Errores léxicos
    if results["lexer"]["errors"]:
        print("=" * 60)
        print("⚠️  ERRORES LÉXICOS:")
        print("=" * 60)
        for err in results["lexer"]["errors"]:
            print(f"  ✗ L{err['line']}, C{err['col']}: {err['message']}")
        print()

    print("=" * 60)
    print("✨ Análisis completado.")
    print("=" * 60)


# Colores ANSI para la terminal
RESET = "\033[0m"
def _token_color(token_type: str) -> str:
    colors = {
        "KEYWORD":          "\033[1;35m",  # Magenta bold
        "IDENTIFIER":       "\033[0;36m",  # Cyan
        "INTEGER":          "\033[0;33m",  # Yellow
        "FLOAT":            "\033[0;33m",  # Yellow
        "STRING":           "\033[0;32m",  # Green
        "BOOL":             "\033[1;33m",  # Yellow bold
        "NONE":             "\033[0;37m",  # White
        "OPERATOR":         "\033[0;31m",  # Red
        "COMPARISON":       "\033[0;31m",  # Red
        "ASSIGNMENT":       "\033[1;31m",  # Red bold
        "AUGMENTED_ASSIGN": "\033[1;31m",  # Red bold
    }
    return colors.get(token_type, "\033[0m")


def execute_code(source_code: str) -> dict:
    """
    Ejecuta el código Python de forma controlada.
    """
    import io
    import contextlib
    from io import StringIO

    output_buffer = StringIO()
    error_message = None
    success = False

    try:
        with contextlib.redirect_stdout(output_buffer):
            with contextlib.redirect_stderr(output_buffer):
                exec(compile(source_code, '<pyanalyzer>', 'exec'), {})
        success = True
    except SyntaxError as e:
        error_message = f"Error de sintaxis: {e.msg} (línea {e.lineno})"
    except Exception as e:
        error_message = f"{type(e).__name__}: {e}"

    return {
        "success": success,
        "output": output_buffer.getvalue(),
        "error": error_message
    }


def main():
    """Punto de entrada principal con argumentos de línea de comandos."""
    parser = argparse.ArgumentParser(
        description="🐍 Compilador/Analizador de Python - Análisis Léxico, Sintáctico y AST",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos de uso:
  python main.py                          # Inicia la interfaz gráfica
  python main.py --file script.py         # Analiza un archivo
  python main.py --code "x = 1 + 2"      # Analiza código inline
  python main.py --file mi.py --run       # Analiza y ejecuta
  python main.py --file mi.py --json      # Salida en formato JSON
        """
    )
    parser.add_argument('--file', '-f', help='Archivo Python a analizar')
    parser.add_argument('--code', '-c', help='Código Python inline a analizar')
    parser.add_argument('--run', '-r', action='store_true', help='Ejecutar el código después de analizar')
    parser.add_argument('--json', '-j', action='store_true', help='Mostrar resultados en formato JSON')
    parser.add_argument('--gui', '-g', action='store_true', default=True, help='Iniciar interfaz gráfica (por defecto)')

    args = parser.parse_args()

    source_code = None

    if args.file:
        try:
            with open(args.file, 'r', encoding='utf-8') as f:
                source_code = f.read()
            print(f"📂 Analizando: {args.file}")
        except FileNotFoundError:
            print(f"❌ Archivo no encontrado: {args.file}")
            sys.exit(1)
        except Exception as e:
            print(f"❌ Error leyendo archivo: {e}")
            sys.exit(1)

    elif args.code:
        source_code = args.code

    if source_code is not None:
        # Modo terminal
        results = analyze_code(source_code, verbose=not args.json)

        if args.json:
            # Remover el AST tree (no es serializable directamente)
            output = {k: v for k, v in results.items() if k != 'ast'}
            if results.get('ast'):
                output['ast'] = {k: v for k, v in results['ast'].items() if k != 'tree_dict'}
            print(json.dumps(output, indent=2, ensure_ascii=False))

        if args.run and source_code:
            print("\n" + "=" * 60)
            print("▶️  EJECUTANDO CÓDIGO:")
            print("=" * 60)
            exec_result = execute_code(source_code)
            if exec_result["output"]:
                print(exec_result["output"])
            if exec_result["error"]:
                print(f"❌ {exec_result['error']}")
            elif exec_result["success"] and not exec_result["output"]:
                print("(El código se ejecutó sin producir salida)")

    else:
        # Iniciar GUI
        try:
            from src.ui import launch_ui
            launch_ui()
        except ImportError as e:
            print(f"❌ No se pudo iniciar la interfaz: {e}")
            print("💡 Usa --file o --code para analizar código en la terminal")
            print("   Ejemplo: python main.py --code \"print('Hola mundo')\"")


if __name__ == '__main__':
    main()
