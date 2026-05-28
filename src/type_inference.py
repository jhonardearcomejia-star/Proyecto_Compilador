"""
type_inference.py - Inferencia automática de tipos de dato

Este módulo proporciona la función reutilizable `infer_type(value)` que detecta
y convierte automáticamente el tipo de dato de cualquier valor string, sin necesidad
de especificarlo manualmente. Se integra con input(), asignaciones y expresiones.

Reglas de inferencia (en orden de prioridad):
  1. bool   → "true" / "false" (insensible a mayúsculas)
  2. int    → cadena que representa un entero (ej: "42", "-7", "0")
  3. float  → cadena que representa un decimal (ej: "3.14", "-2.5", "1e10")
  4. None   → "none" / "null" (insensible a mayúsculas)
  5. str    → cualquier otro valor queda como cadena de texto

Ejemplo de uso rápido:
    from src.type_inference import infer_type, smart_input

    x = infer_type("42")      # → int(42)
    y = infer_type("3.14")    # → float(3.14)
    z = infer_type("true")    # → bool(True)
    w = infer_type("hola")    # → str("hola")

    # Reemplaza input() con inferencia automática:
    edad = smart_input("¿Cuántos años tienes? ")  # el usuario escribe "25" → int(25)
"""

from typing import Any, Callable, Optional, Union


# ─── Función principal de inferencia ─────────────────────────────────────────

def infer_type(value: str) -> Any:
    """
    Detecta y convierte automáticamente el tipo de dato de una cadena de texto.

    Parámetros
    ----------
    value : str
        Cadena de texto a analizar (por ejemplo, la salida de input()).

    Retorna
    -------
    Any
        - bool   si el valor es "true" o "false" (sin importar mayúsculas)
        - int    si el valor representa un número entero (con signo opcional)
        - float  si el valor representa un número decimal o notación científica
        - None   si el valor es "none" o "null" (sin importar mayúsculas)
        - str    en cualquier otro caso (el valor original sin modificar)

    Lanza
    -----
    TypeError
        Si `value` no es una cadena de texto.

    Ejemplos
    --------
    >>> infer_type("42")
    42
    >>> infer_type("-3.14")
    -3.14
    >>> infer_type("True")
    True
    >>> infer_type("false")
    False
    >>> infer_type("None")
    # retorna None (el valor nulo de Python)
    >>> infer_type("hola mundo")
    'hola mundo'
    """
    # ── Validación de entrada ─────────────────────────────────────────────────
    if not isinstance(value, str):
        raise TypeError(
            f"infer_type() espera un str, pero recibió {type(value).__name__!r}. "
            f"Valor recibido: {value!r}"
        )

    # Normalizamos el valor para comparaciones (sin quitar espacios internos)
    stripped = value.strip()

    # ── Paso 1: Booleanos ─────────────────────────────────────────────────────
    # Se evalúa primero porque "True"/"False" también son palabras válidas
    # que int() / float() no pueden convertir, pero conviene detectarlos antes
    # de intentar otras conversiones.
    if stripped.lower() == "true":
        return True
    if stripped.lower() == "false":
        return False

    # ── Paso 2: None / null ───────────────────────────────────────────────────
    if stripped.lower() in ("none", "null"):
        return None

    # ── Paso 3: Entero (int) ──────────────────────────────────────────────────
    # Intenta convertir a int. Acepta enteros con signo: "42", "-7", "+3"
    # También acepta bases: "0x1F" (hex), "0o17" (octal), "0b1010" (binario)
    try:
        # int() con base 0 detecta automáticamente 0x, 0o, 0b
        return int(stripped, 0)
    except (ValueError, TypeError):
        pass

    # ── Paso 4: Decimal (float) ───────────────────────────────────────────────
    # Intenta convertir a float. Acepta: "3.14", "-2.5e3", ".5", "1."
    try:
        return float(stripped)
    except (ValueError, TypeError):
        pass

    # ── Paso 5: String ───────────────────────────────────────────────────────
    # Si ninguna conversión anterior tuvo éxito, se devuelve el string original
    return value


# ─── Función para asignaciones con inferencia ─────────────────────────────────

def infer_assignment(raw_value: str) -> Any:
    """
    Aplica inferencia de tipo a un valor de asignación.

    Además de las reglas de `infer_type`, elimina comillas externas si el
    valor está entre comillas simples o dobles (como en: x = "10" → se
    evalúa el contenido "10" → int(10)).

    Parámetros
    ----------
    raw_value : str
        Valor tal como aparece en el código fuente de una asignación.
        Por ejemplo: '"42"', "'hello'", "3.14", "True".

    Retorna
    -------
    Any
        Valor convertido al tipo inferido.

    Ejemplos
    --------
    >>> infer_assignment('"10"')   # x = "10"   → int(10)
    10
    >>> infer_assignment("'3.5'")  # x = '3.5'  → float(3.5)
    3.5
    >>> infer_assignment('"hola"') # x = "hola" → str('hola')
    'hola'
    >>> infer_assignment("42")     # x = 42     → int(42)
    42
    """
    if not isinstance(raw_value, str):
        raise TypeError(f"infer_assignment() espera un str, recibió {type(raw_value).__name__!r}")

    stripped = raw_value.strip()

    # Si el valor está entre comillas, extraemos el contenido y lo inferimos
    if (len(stripped) >= 2 and
            ((stripped[0] == '"' and stripped[-1] == '"') or
             (stripped[0] == "'" and stripped[-1] == "'"))):
        inner = stripped[1:-1]
        return infer_type(inner)

    # Sin comillas: aplicar inferencia directamente
    return infer_type(stripped)


# ─── Reemplazo inteligente de input() ────────────────────────────────────────

def smart_input(prompt: str = "", converter: Optional[Callable] = None) -> Any:
    """
    Versión mejorada de input() que infiere el tipo del valor ingresado.

    Muestra el prompt al usuario, lee su entrada y aplica `infer_type`
    automáticamente. Opcionalmente acepta un `converter` personalizado.

    Parámetros
    ----------
    prompt : str, opcional
        Texto que se muestra al usuario antes de leer la entrada.
    converter : callable, opcional
        Función de conversión personalizada. Si se proporciona, se usa en
        lugar de `infer_type`. Útil para validaciones específicas.

    Retorna
    -------
    Any
        Valor ingresado por el usuario, convertido al tipo inferido.

    Ejemplos
    --------
    # El usuario escribe "25" → retorna int(25)
    edad = smart_input("¿Cuántos años tienes? ")

    # El usuario escribe "3.14" → retorna float(3.14)
    radio = smart_input("Radio del círculo: ")

    # El usuario escribe "true" → retorna bool(True)
    activo = smart_input("¿Activo? (true/false): ")

    # El usuario escribe "Juan" → retorna str("Juan")
    nombre = smart_input("Tu nombre: ")
    """
    raw = input(prompt)
    if converter is not None:
        return converter(raw)
    return infer_type(raw)


# ─── Inferencia de expresiones ────────────────────────────────────────────────

def infer_expression(left: Any, op: str, right: Any) -> Any:
    """
    Aplica coerción automática de tipos en operaciones binarias.

    Permite operar entre int y float sin necesidad de conversión manual,
    siguiendo las mismas reglas de Python nativo pero de forma explícita.

    Parámetros
    ----------
    left : Any
        Operando izquierdo.
    op : str
        Operador como cadena: '+', '-', '*', '/', '//', '%', '**'
    right : Any
        Operando derecho.

    Retorna
    -------
    Any
        Resultado de la operación con coerción de tipos.

    Lanza
    -----
    TypeError
        Si los tipos no son compatibles con el operador.
    ValueError
        Si el operador no es reconocido.
    ZeroDivisionError
        Si se intenta dividir por cero.

    Ejemplos
    --------
    >>> infer_expression(10, '+', 3.5)   # int + float → float(13.5)
    13.5
    >>> infer_expression(7, '//', 2)      # int // int → int(3)
    3
    >>> infer_expression("Hola", '+', " Mundo")  # str + str → str
    'Hola Mundo'
    """
    # Coerción automática: si uno es float y el otro int, el resultado es float
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        # Aseguramos que bool no interfiera (bool es subclase de int en Python)
        if isinstance(left, bool) or isinstance(right, bool):
            left = int(left)
            right = int(right)

    ops = {
        '+':  lambda a, b: a + b,
        '-':  lambda a, b: a - b,
        '*':  lambda a, b: a * b,
        '/':  lambda a, b: a / b,
        '//': lambda a, b: a // b,
        '%':  lambda a, b: a % b,
        '**': lambda a, b: a ** b,
    }

    if op not in ops:
        raise ValueError(
            f"Operador no reconocido: {op!r}. "
            f"Operadores válidos: {', '.join(ops.keys())}"
        )

    try:
        return ops[op](left, right)
    except TypeError as e:
        raise TypeError(
            f"Operación '{op}' no válida entre {type(left).__name__!r} "
            f"y {type(right).__name__!r}: {e}"
        )
    except ZeroDivisionError:
        raise ZeroDivisionError(
            f"División por cero: {left!r} {op} {right!r}"
        )


# ─── Descripción del tipo inferido (para reportes y UI) ──────────────────────

def describe_inferred_type(value: Any) -> str:
    """
    Retorna el nombre del tipo de Python de un valor como cadena legible.

    Parámetros
    ----------
    value : Any
        Valor del que se quiere conocer el tipo.

    Retorna
    -------
    str
        Nombre del tipo: 'int', 'float', 'bool', 'str', 'NoneType', etc.

    Ejemplos
    --------
    >>> describe_inferred_type(42)
    'int'
    >>> describe_inferred_type(3.14)
    'float'
    >>> describe_inferred_type(True)
    'bool'
    >>> describe_inferred_type("hola")
    'str'
    >>> describe_inferred_type(None)
    'NoneType'
    """
    return type(value).__name__


# ─── Punto de entrada para pruebas rápidas ───────────────────────────────────

if __name__ == "__main__":
    test_cases = [
        # (entrada,        tipo_esperado, valor_esperado)
        ("42",             "int",         42),
        ("-7",             "int",         -7),
        ("+3",             "int",         3),
        ("0",              "int",         0),
        ("0xFF",           "int",         255),
        ("0b1010",         "int",         10),
        ("3.14",           "float",       3.14),
        ("-2.5",           "float",       -2.5),
        ("1e10",           "float",       1e10),
        (".5",             "float",       0.5),
        ("true",           "bool",        True),
        ("True",           "bool",        True),
        ("TRUE",           "bool",        True),
        ("false",          "bool",        False),
        ("False",          "bool",        False),
        ("none",           "NoneType",    None),
        ("None",           "NoneType",    None),
        ("null",           "NoneType",    None),
        ("hola",           "str",         "hola"),
        ("hola mundo",     "str",         "hola mundo"),
        ("  42  ",         "int",         42),   # espacios ignorados
        ("",               "str",         ""),   # cadena vacía → str
    ]

    print("=" * 60)
    print(" PRUEBAS DE infer_type()")
    print("=" * 60)

    passed = 0
    failed = 0

    for entrada, tipo_esp, valor_esp in test_cases:
        resultado = infer_type(entrada)
        tipo_real = describe_inferred_type(resultado)
        ok = resultado == valor_esp and tipo_real == tipo_esp
        estado = "✅ OK" if ok else "❌ FALLO"
        if ok:
            passed += 1
        else:
            failed += 1
        print(f"  {estado}  infer_type({entrada!r:12}) → {resultado!r:10} ({tipo_real})")

    print("-" * 60)
    print(f"  Resultado: {passed} pasaron, {failed} fallaron")
    print("=" * 60)

    # Prueba de infer_assignment
    print("\n" + "=" * 60)
    print(" PRUEBAS DE infer_assignment()")
    print("=" * 60)
    assign_cases = [
        ('"10"',   int,   10),
        ("'3.5'",  float, 3.5),
        ('"true"', bool,  True),
        ('"hola"', str,   "hola"),
        ("42",     int,   42),
    ]
    for raw, tipo_esp, valor_esp in assign_cases:
        resultado = infer_assignment(raw)
        ok = isinstance(resultado, tipo_esp) and resultado == valor_esp
        print(f"  {'✅' if ok else '❌'}  infer_assignment({raw!r:10}) → {resultado!r} ({type(resultado).__name__})")

    # Prueba de infer_expression
    print("\n" + "=" * 60)
    print(" PRUEBAS DE infer_expression()")
    print("=" * 60)
    expr_cases = [
        (10,    '+',  3.5,  13.5),
        (7,     '//', 2,    3),
        (2,     '**', 10,   1024),
        ("Hi",  '+',  "!",  "Hi!"),
    ]
    for left, op, right, esperado in expr_cases:
        resultado = infer_expression(left, op, right)
        ok = resultado == esperado
        print(f"  {'✅' if ok else '❌'}  infer_expression({left!r}, {op!r}, {right!r}) → {resultado!r}")
