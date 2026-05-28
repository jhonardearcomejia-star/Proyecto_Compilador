# 🐍 Python Compiler & Analyzer

Un analizador y compilador de código Python con interfaz gráfica que incluye análisis léxico, sintáctico, semántico y generación de Árbol Sintáctico Abstracto (AST).

---

## 📋 Características

| Módulo | Descripción |
|--------|-------------|
| **Lexer** | Tokeniza código Python e identifica todos los tipos de tokens |
| **Parser** | Valida la sintaxis y extrae información estructural |
| **AST Generator** | Construye y visualiza el Árbol Sintáctico Abstracto |
| **Semantic Analyzer** | Detecta errores semánticos, variables no definidas, tipos inconsistentes y más |
| **UI** | Interfaz gráfica con tablas de celdas, resaltado de sintaxis, análisis en tiempo real y consola de ejecución |

### 🔤 Análisis Léxico
- Identifica **palabras clave**, identificadores, números (int/float), cadenas, operadores, signos de puntuación
- Detecta **tipos de datos** literales: `int`, `float`, `str`, `bool`, `NoneType`
- Reporte de errores léxicos con línea y columna
- Resumen estadístico de tokens

### ✅ Análisis Sintáctico
- Valida la sintaxis del código Python
- Extrae funciones, clases, importaciones y variables globales
- Calcula complejidad ciclomática
- Detecta advertencias de estilo (PEP 8)

### 🌳 AST (Árbol Sintáctico Abstracto)
- Generación del AST usando el módulo `ast` nativo de Python
- Visualización en árbol interactivo con zoom y arrastre
- Resumen: total de nodos, funciones, clases, importaciones

### 🔍 Análisis Semántico
- Tabla de símbolos con scope global y local
- Detección de variables no declaradas o usadas antes de asignación
- Verificación de número de argumentos en llamadas a funciones
- Detección de variables e importaciones no utilizadas
- Identificación de código inalcanzable (`unreachable`)
- Verificación de retornos inconsistentes en funciones
- División por cero detectada estáticamente

### ⚡ Ejecución
- Ejecuta código Python de forma segura con captura de salida
- Muestra errores de ejecución claramente
- Consola integrada con soporte de entrada (`input()`) sin ventanas emergentes

---

## 🖥️ Interfaz Visual — Tablas con Celdas

Todas las pestañas de resultados usan **tablas de celdas** (`ttk.Treeview`) con:

- **Filas alternas de color** para facilitar la lectura (fila par / fila impar)
- **Anchos de columna optimizados** por tipo de dato
- **Alineación por columna** (texto a la izquierda, números al centro)
- **Scrollbars horizontal y vertical** en cada tabla
- **Coloreado por tipo de token** en la tabla de tokens

### Pestaña 🔤 Tokens

Tabla de celdas con las columnas:

| Columna | Descripción |
|---------|-------------|
| **Tipo** | Categoría del token (KEYWORD, IDENTIFIER, INTEGER, etc.) — coloreado por tipo |
| **Valor** | Texto literal del token |
| **Línea** | Número de línea en el código fuente |
| **Col** | Columna de inicio |
| **Tipo Dato** | Tipo de dato inferido (int, float, str, bool, NoneType) |

### Pestaña 📊 Tipos de Datos

Dos tablas de celdas independientes:

**Tabla 1 — Resumen por Tipo:**

| Columna | Descripción |
|---------|-------------|
| **Icono** | Símbolo visual del tipo |
| **Tipo de Dato** | Nombre del tipo (int, float, str, etc.) |
| **Cantidad** | Total de literales encontrados |
| **Distribución (%)** | Porcentaje y barra visual de distribución |

**Tabla 2 — Valores Encontrados:**

| Columna | Descripción |
|---------|-------------|
| **Icono** | Símbolo visual del tipo |
| **Tipo de Dato** | Nombre del tipo |
| **Valores (hasta 10)** | Lista de los primeros 10 valores únicos encontrados |

### Pestaña 🌳 AST

Canvas interactivo para el árbol sintáctico:
- Zoom con rueda del ratón o botones `🔍+` / `🔍−`
- Arrastre para mover el árbol
- Ajuste automático con `📐 Ajustar`
- Información detallada al pasar el cursor sobre cada nodo
- Leyenda de colores por categoría de nodo

### Pestaña ✅ Parser

Cuatro tablas de celdas más un área de texto:

**Tabla 1 — Estadísticas del Código:**

| Columna | Descripción |
|---------|-------------|
| **Métrica** | Nombre del indicador (líneas, complejidad, bucles, etc.) |
| **Valor** | Valor numérico de la métrica |

**Tabla 2 — Funciones:**

| Columna | Descripción |
|---------|-------------|
| **Nombre** | Nombre de la función |
| **Argumentos** | Lista de parámetros con anotaciones de tipo |
| **Retorno** | Tipo de retorno declarado |
| **Async** | Si es función asíncrona (sí / no) |
| **Línea** | Línea de definición |
| **Decoradores** | Decoradores aplicados |

**Tabla 3 — Clases:**

| Columna | Descripción |
|---------|-------------|
| **Nombre** | Nombre de la clase |
| **Bases** | Clases base (herencia) |
| **Métodos** | Lista de métodos definidos |
| **Línea** | Línea de definición |

**Tabla 4 — Importaciones:**

| Columna | Descripción |
|---------|-------------|
| **Tipo** | `import` o `from … import` |
| **Módulo** | Nombre del módulo importado |
| **Nombres / Alias** | Nombres específicos importados y sus alias |
| **Línea** | Línea de la instrucción |

**Área de texto — Errores y Advertencias PEP 8:**
- Errores de sintaxis con número de línea y columna
- Advertencias de estilo PEP 8

### Pestaña 🔍 Semántico

**Tabla de Símbolos** con celdas y filas alternas:

| Columna | Descripción |
|---------|-------------|
| **Nombre** | Identificador del símbolo |
| **Tipo Símbolo** | Categoría (variable, función, clase, parámetro, etc.) |
| **Tipo Inferido** | Tipo de dato inferido por el analizador |
| **Scope** | Ámbito donde está definido (global / nombre de función) |
| **Línea** | Línea de definición |
| **Usado** | ✔ si fue usado, ✖ si no fue utilizado (aparece en gris) |

**Área de texto — Errores y Advertencias Semánticas:**
- Errores con número de línea y descripción
- Advertencias (variables no usadas, importaciones innecesarias, etc.)

### Pestaña ⚡ Consola
- Área de salida de solo lectura con coloreado de texto
- Barra de entrada inline para `input()` (sin ventanas emergentes)

### Atajos
- El análisis se ejecuta automáticamente mientras escribes (con un pequeño delay de 800 ms)
- Los botones **▶ Analizar** y **⚡ Ejecutar** están siempre disponibles en la barra de herramientas

---

## 📦 Librerías Utilizadas

El proyecto usa **únicamente la biblioteca estándar de Python 3.8+**. No se requieren dependencias externas.

### Módulos de la Biblioteca Estándar

| Módulo | Usado en | ¿Qué hace en este proyecto? |
|--------|----------|-----------------------------|
| `ast` | `ast_generator.py`, `parser.py`, `semantic_analyzer.py` | Parsea código Python y genera el Árbol Sintáctico Abstracto nativo. Permite recorrer el árbol con `NodeVisitor` para extraer funciones, clases, importaciones y realizar análisis semántico. |
| `re` | `lexer.py` | Expresiones regulares para tokenizar el código fuente: identifica patrones de palabras clave, identificadores, números, cadenas y operadores. |
| `tkinter` | `ui.py` | Framework de interfaz gráfica incluido en Python. Construye toda la UI: ventana principal, editor de código, paneles de resultados, pestañas y botones. |
| `tkinter.ttk` | `ui.py` | Extensión de Tkinter con widgets con estilos mejorados: `Notebook` (pestañas), `Treeview` (tablas de celdas), `Scrollbar`, etc. Las tablas de celdas con filas alternas se implementan íntegramente con `ttk.Treeview`. |
| `tkinter.scrolledtext` | `ui.py` | Widget de texto con barra de desplazamiento integrada, usado para el editor de código, la consola y las áreas de errores/advertencias. |
| `tkinter.filedialog` | `ui.py` | Diálogos nativos del SO para abrir y guardar archivos `.py`. |
| `tkinter.messagebox` | `ui.py` | Cuadros de diálogo para mostrar alertas, confirmaciones y errores al usuario. |
| `tkinter.font` | `ui.py` | Gestión de fuentes tipográficas para personalizar el editor (familia, tamaño, estilo). |
| `threading` | `ui.py` | Ejecución en hilos secundarios para correr el análisis sin bloquear la interfaz gráfica. |
| `sys` | `main.py`, `ui.py`, `parser.py` | Acceso al intérprete Python, gestión del `sys.path` para importar módulos locales y captura del contexto de errores. |
| `os` | `main.py`, `ui.py` | Operaciones del sistema de archivos: construcción de rutas (`os.path.join`), obtención del directorio del script. |
| `json` | `main.py`, `ast_generator.py`, `ui.py` | Serialización de resultados de análisis. Permite exportar la salida del compilador en formato JSON desde la línea de comandos. |
| `io` | `ui.py` | Flujos de entrada/salida en memoria. Se usa para capturar el `stdout` durante la ejecución del código del usuario. |
| `contextlib` | `ui.py` | `contextlib.redirect_stdout` redirige la salida estándar para capturarla en la consola integrada de la UI. |
| `argparse` | `main.py` | Procesamiento de argumentos de línea de comandos: flags `--file`, `--code`, `--run`, `--json`. |
| `dataclasses` | `lexer.py`, `parser.py`, `semantic_analyzer.py` | Decorador `@dataclass` para definir estructuras de datos (Token, ParseResult, ParseError, etc.) sin escribir `__init__` manualmente. |
| `enum` | `lexer.py`, `semantic_analyzer.py` | Enumeraciones tipadas (`TokenType`, `SemanticErrorKind`) para clasificar tokens y tipos de errores de forma segura. |
| `typing` | `lexer.py`, `parser.py`, `ast_generator.py`, `semantic_analyzer.py` | Anotaciones de tipo (`List`, `Dict`, `Optional`, `Set`, `Tuple`) para mejorar legibilidad y soporte de IDEs. |
| `collections` | `ui.py` | `collections.deque` para el recorrido BFS en el layout jerárquico del árbol AST. |
| `queue` | `ui.py` | `queue.Queue` para la sincronización entre el hilo de ejecución y la consola de entrada (`input()`). |

### Dependencias Opcionales

Estas librerías no son requeridas, pero pueden instalarse para funcionalidades adicionales:

```bash
pip install autopep8   # Formateo automático de código (estilo PEP 8)
pip install pygments   # Resaltado de sintaxis más avanzado
```

---

## 🚀 Instalación y Uso

### Requisitos
- Python **3.8** o superior
- Tkinter (incluido en Python estándar — en Linux puede requerir: `sudo apt install python3-tk`)

### Instalación

```bash
# 1. Descomprimir el proyecto
unzip python_compiler.zip
cd python_compiler

# 2. (Opcional) Crear entorno virtual
python -m venv venv
source venv/bin/activate      # Linux/Mac
venv\Scripts\activate.bat     # Windows

# 3. No se necesitan dependencias externas
```

### Ejecutar la Interfaz Gráfica

```bash
python main.py
```

### Analizar un archivo Python

```bash
python main.py --file mi_script.py
```

### Analizar código inline

```bash
python main.py --code "x = 42; print(x)"
```

### Analizar y ejecutar un archivo

```bash
python main.py --file mi_script.py --run
```

### Obtener resultados en JSON

```bash
python main.py --file mi_script.py --json
```

---

## 📁 Estructura del Proyecto

```
python_compiler/
├── main.py                  # Punto de entrada principal (CLI básico)
├── requirements.txt         # Dependencias (solo stdlib)
├── README.md                # Este archivo
└── src/
    ├── __init__.py
    ├── main.py              # Pipeline completo (léxico + sintáctico + semántico)
    ├── lexer.py             # Analizador léxico — tokenización con re + dataclasses
    ├── parser.py            # Analizador sintáctico — valida sintaxis con ast
    ├── ast_generator.py     # Generador y visualizador de AST
    ├── semantic_analyzer.py # Analizador semántico — tabla de símbolos y tipos
    └── ui.py                # Interfaz gráfica completa (Tkinter + tablas de celdas)
```

---

## 🧪 Ejemplo de Uso Programático

```python
from src.lexer import Lexer
from src.parser import Parser
from src.ast_generator import generate_ast_report
from src.semantic_analyzer import run_semantic_analysis

codigo = """
def suma(a, b):
    return a + b

resultado = suma(3, 4)
print(resultado)
"""

# Análisis léxico
lexer = Lexer(codigo)
tokens = lexer.tokenize()
print(f"Tokens: {len(tokens)}")
print(f"Tipos de datos: {lexer.get_data_types()}")

# Análisis sintáctico
parser = Parser()
resultado = parser.parse(codigo)
print(f"Sintaxis válida: {resultado.success}")
print(f"Funciones encontradas: {resultado.stats.get('funciones', [])}")

# AST
reporte = generate_ast_report(codigo)
if reporte["success"]:
    print(reporte["tree_text"])

# Análisis semántico
semantico = run_semantic_analysis(codigo)
print(f"Errores semánticos: {len(semantico['errors'])}")
print(f"Advertencias: {len(semantico['warnings'])}")
```

---

## 📝 Tipos de Tokens Identificados

| Tipo | Ejemplos |
|------|---------|
| `KEYWORD` | `if`, `def`, `class`, `return`, `import` |
| `IDENTIFIER` | `variable`, `función`, `mi_clase` |
| `INTEGER` | `42`, `0`, `1000` |
| `FLOAT` | `3.14`, `2.5e-3` |
| `STRING` | `"hola"`, `'mundo'`, `"""docstring"""` |
| `BOOL` | `True`, `False` |
| `NONE` | `None` |
| `OPERATOR` | `+`, `-`, `*`, `/`, `**`, `//` |
| `COMPARISON` | `==`, `!=`, `<`, `>`, `<=`, `>=` |
| `ASSIGNMENT` | `=` |
| `AUGMENTED_ASSIGN` | `+=`, `-=`, `*=` |
| `COMMENT` | `# comentario` |

---

## 🎨 Diseño de las Tablas de Celdas

Las tablas usan la función interna `_make_scrolled_tree()` que construye un `ttk.Treeview` estándar con:

```
┌──────────────────┬─────────────────────┬────────┬────────┬────────────┐
│ Tipo             │ Valor               │ Línea  │  Col   │ Tipo Dato  │
├──────────────────┼─────────────────────┼────────┼────────┼────────────┤
│ KEYWORD          │ def                 │  1     │  0     │            │  ← fila par
├──────────────────┼─────────────────────┼────────┼────────┼────────────┤
│ IDENTIFIER       │ calcular_factorial  │  1     │  4     │            │  ← fila impar
├──────────────────┼─────────────────────┼────────┼────────┼────────────┤
│ INTEGER          │ 42                  │  5     │  8     │ int        │  ← fila par
└──────────────────┴─────────────────────┴────────┴────────┴────────────┘
```

Las filas alternas usan los colores `#161b22` (par) y `#1c2128` (impar) sobre el tema oscuro del proyecto.

---

## 🤝 Contribuir

Siéntete libre de extender este proyecto con:
- Soporte para más lenguajes
- Visualización gráfica del AST (con `networkx` + `matplotlib`)
- Análisis de tipos más avanzado
- Exportar resultados a HTML/PDF
- Filtrado y búsqueda en las tablas de celdas

---

## 📄 Licencia

MIT License — libre para uso educativo y comercial.
