"""
optimizer.py - Optimizador de Código Intermedio TAC
Aplica optimizaciones clásicas de compiladores sobre instrucciones TAC:
  1. Plegado de constantes   (Constant Folding)
  2. Propagación de copias   (Copy Propagation)
  3. Eliminación de código muerto (Dead Code Elimination)
  4. Simplificación algebraica   (Algebraic Simplification)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import operator as _op

from src.intermediate_code_generator import TACInstruction, ICGResult


# ─── Resultado de la optimización ────────────────────────────────────────────

@dataclass
class OptimizationResult:
    success: bool
    original_instructions: List[TACInstruction] = field(default_factory=list)
    optimized_instructions: List[TACInstruction] = field(default_factory=list)
    log: List[Tuple[str, str, str]] = field(default_factory=list)  # (tipo, original, resultado)
    stats: Dict[str, int] = field(default_factory=dict)

    @property
    def original_count(self) -> int:
        return len(self.original_instructions)

    @property
    def optimized_count(self) -> int:
        return len(self.optimized_instructions)

    @property
    def reduction(self) -> int:
        return self.original_count - self.optimized_count

    @property
    def reduction_pct(self) -> float:
        if self.original_count == 0:
            return 0.0
        return self.reduction / self.original_count * 100


# ─── Evaluador de constantes ─────────────────────────────────────────────────

_BIN_OPS = {
    "+":  lambda a, b: a + b,
    "-":  lambda a, b: a - b,
    "*":  lambda a, b: a * b,
    "/":  lambda a, b: a / b  if b != 0 else None,
    "//": lambda a, b: a // b if b != 0 else None,
    "%":  lambda a, b: a % b  if b != 0 else None,
    "**": lambda a, b: a ** b if (isinstance(b, int) and b >= 0 and b <= 64) else None,
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    "<":  lambda a, b: a < b,
    "<=": lambda a, b: a <= b,
    ">":  lambda a, b: a > b,
    ">=": lambda a, b: a >= b,
    "and": lambda a, b: a and b,
    "or":  lambda a, b: a or b,
}


def _parse_literal(s: str):
    """Intenta convertir una cadena a un valor Python literal. None si no es literal."""
    if s is None:
        return None, False
    s = s.strip()
    # Booleans first (before int)
    if s == "True":
        return True, True
    if s == "False":
        return False, True
    if s == "None":
        return None, True
    try:
        return int(s), True
    except ValueError:
        pass
    try:
        return float(s), True
    except ValueError:
        pass
    # Quoted string literal
    if (s.startswith("'") and s.endswith("'")) or (s.startswith('"') and s.endswith('"')):
        try:
            return s[1:-1], True
        except Exception:
            pass
    return None, False


def _literal_repr(val) -> str:
    """Representa un valor literal como cadena TAC."""
    if isinstance(val, bool):
        return "True" if val else "False"
    if val is None:
        return "None"
    if isinstance(val, str):
        return repr(val)
    return str(val)


# ─── Optimizador principal ────────────────────────────────────────────────────

class TACOptimizer:
    """Aplica múltiples pasadas de optimización sobre una lista de instrucciones TAC."""

    def __init__(self):
        self._log: List[Tuple[str, str, str]] = []
        self._stats: Dict[str, int] = {
            "constant_folding": 0,
            "copy_propagation": 0,
            "algebraic_simplification": 0,
            "dead_code_elimination": 0,
        }

    # ── Pasada 1: Plegado de constantes ──────────────────────────────────────

    def _constant_folding(self, instructions: List[TACInstruction]) -> List[TACInstruction]:
        """
        Si ambos operandos de una operación binaria son literales,
        evalúa la expresión en tiempo de compilación.
        Ejemplo:  t0 = 2 + 3  →  t0 = 5
        """
        result = []
        for instr in instructions:
            if instr.op == "binary" and instr.arg1 and instr.arg2 and instr.label:
                v1, ok1 = _parse_literal(instr.arg1)
                v2, ok2 = _parse_literal(instr.arg2)
                fn = _BIN_OPS.get(instr.label)
                if ok1 and ok2 and fn is not None:
                    try:
                        folded = fn(v1, v2)
                        if folded is not None:
                            original = str(instr)
                            new_instr = TACInstruction(
                                op="assign",
                                result=instr.result,
                                arg1=_literal_repr(folded),
                            )
                            self._log.append(("Plegado de constantes", original.strip(), str(new_instr).strip()))
                            self._stats["constant_folding"] += 1
                            result.append(new_instr)
                            continue
                    except Exception:
                        pass
            result.append(instr)
        return result

    # ── Pasada 2: Simplificación algebraica ──────────────────────────────────

    def _algebraic_simplification(self, instructions: List[TACInstruction]) -> List[TACInstruction]:
        """
        Simplifica expresiones como:
          x + 0 → x,  x * 1 → x,  x * 0 → 0,  x - 0 → x,  x / 1 → x
          x ** 1 → x, x ** 0 → 1
        """
        result = []
        for instr in instructions:
            if instr.op == "binary" and instr.label and instr.arg1 and instr.arg2 and instr.result:
                op = instr.label
                a, a_ok = _parse_literal(instr.arg1)
                b, b_ok = _parse_literal(instr.arg2)
                simplified = None

                if op == "+" :
                    if b_ok and b == 0:   simplified = instr.arg1
                    elif a_ok and a == 0: simplified = instr.arg2
                elif op == "-":
                    if b_ok and b == 0:   simplified = instr.arg1
                elif op == "*":
                    if b_ok and b == 1:   simplified = instr.arg1
                    elif a_ok and a == 1: simplified = instr.arg2
                    elif b_ok and b == 0: simplified = "0"
                    elif a_ok and a == 0: simplified = "0"
                elif op == "/":
                    if b_ok and b == 1:   simplified = instr.arg1
                elif op == "**":
                    if b_ok and b == 1:   simplified = instr.arg1
                    elif b_ok and b == 0: simplified = "1"
                    elif a_ok and a == 1: simplified = "1"

                if simplified is not None:
                    original = str(instr)
                    new_instr = TACInstruction(op="assign", result=instr.result, arg1=simplified)
                    self._log.append(("Simplificación algebraica", original.strip(), str(new_instr).strip()))
                    self._stats["algebraic_simplification"] += 1
                    result.append(new_instr)
                    continue

            result.append(instr)
        return result

    # ── Pasada 3: Propagación de copias ──────────────────────────────────────

    def _copy_propagation(self, instructions: List[TACInstruction]) -> List[TACInstruction]:
        """
        Si x = y (copia simple), reemplaza usos posteriores de x por y.
        Solo propaga dentro del mismo bloque básico (antes de labels/jumps).
        """
        copies: Dict[str, str] = {}
        result = []

        for instr in instructions:
            # Cualquier salto, etiqueta o llamada de función invalida el entorno de copias
            if instr.op in ("label", "goto", "if_true", "if_false", "begin_func", "end_func"):
                copies.clear()
                result.append(instr)
                continue

            # Sustituir usos de variables que son copias conocidas
            changed = False
            new_arg1 = instr.arg1
            new_arg2 = instr.arg2

            if instr.arg1 and instr.arg1 in copies:
                new_arg1 = copies[instr.arg1]
                changed = True
            if instr.arg2 and instr.arg2 in copies:
                new_arg2 = copies[instr.arg2]
                changed = True

            if changed:
                original = str(instr)
                instr = TACInstruction(
                    op=instr.op,
                    result=instr.result,
                    arg1=new_arg1,
                    arg2=new_arg2,
                    label=instr.label,
                    comment=instr.comment,
                )
                self._log.append(("Propagación de copias", original.strip(), str(instr).strip()))
                self._stats["copy_propagation"] += 1

            # Si es una asignación simple (t = x), registrar como copia propagable
            if instr.op == "assign" and instr.result and instr.arg1:
                _, is_lit = _parse_literal(instr.arg1)
                if not is_lit and not instr.arg1.startswith("<"):
                    copies[instr.result] = instr.arg1
                else:
                    copies.pop(instr.result, None)
            elif instr.result:
                # El resultado es redefinido; invalidar copia anterior
                copies.pop(instr.result, None)

            result.append(instr)
        return result

    # ── Pasada 4: Eliminación de código muerto ────────────────────────────────

    def _dead_code_elimination(self, instructions: List[TACInstruction]) -> List[TACInstruction]:
        """
        Elimina instrucciones cuyo resultado (temporal) nunca se usa.
        Solo se aplica a temporales (t0, t1, …) que no son variables de usuario.
        No elimina llamadas a funciones (pueden tener efectos secundarios).
        """
        # Recopilar todos los usos de variables
        used: set = set()
        for instr in instructions:
            if instr.arg1 and not instr.arg1.startswith("<"):
                used.add(instr.arg1)
            if instr.arg2 and not instr.arg2.startswith("<"):
                used.add(instr.arg2)
            if instr.label and instr.op in ("if_true", "if_false"):
                used.add(instr.arg1 or "")
            if instr.op in ("param", "return"):
                used.add(instr.arg1 or "")

        result = []
        for instr in instructions:
            # Solo eliminar asignaciones a temporales no usados
            is_temp_assign = (
                instr.op in ("assign", "binary", "unary", "index_load")
                and instr.result
                and instr.result.startswith("t")
                and instr.result[1:].isdigit()
                and instr.result not in used
            )
            if is_temp_assign:
                self._log.append((
                    "Eliminación de código muerto",
                    str(instr).strip(),
                    "(eliminada — resultado nunca usado)"
                ))
                self._stats["dead_code_elimination"] += 1
                continue
            result.append(instr)
        return result

    # ── Punto de entrada ──────────────────────────────────────────────────────

    def optimize(self, ic_result: ICGResult) -> OptimizationResult:
        """Ejecuta todas las pasadas de optimización y devuelve el resultado."""
        if not ic_result.success or not ic_result.instructions:
            return OptimizationResult(
                success=False,
                original_instructions=list(ic_result.instructions),
                optimized_instructions=list(ic_result.instructions),
                log=[],
                stats=self._stats,
            )

        original = list(ic_result.instructions)
        instrs = list(original)

        # Aplicar pasadas en orden
        instrs = self._constant_folding(instrs)
        instrs = self._algebraic_simplification(instrs)
        instrs = self._copy_propagation(instrs)
        instrs = self._dead_code_elimination(instrs)

        return OptimizationResult(
            success=True,
            original_instructions=original,
            optimized_instructions=instrs,
            log=self._log,
            stats=dict(self._stats),
        )


# ─── Función de conveniencia ──────────────────────────────────────────────────

def optimize_intermediate_code(ic_result: ICGResult) -> OptimizationResult:
    """
    Aplica optimizaciones TAC al resultado del generador de código intermedio.

    Parámetros
    ----------
    ic_result : ICGResult
        Resultado de generate_intermediate_code().

    Retorna
    -------
    OptimizationResult con las instrucciones optimizadas y el log de cambios.
    """
    optimizer = TACOptimizer()
    return optimizer.optimize(ic_result)
