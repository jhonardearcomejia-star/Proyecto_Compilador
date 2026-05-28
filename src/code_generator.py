"""
code_generator.py - Generador de Código Objeto (pseudo-ensamblador)
Traduce instrucciones TAC optimizadas a código ensamblador de bajo nivel
estilo x86 (con registros, MOV, ADD, CMP, JMP, CALL, PUSH/POP, etc.)
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple

from src.intermediate_code_generator import TACInstruction
from src.optimizer import OptimizationResult


# ─── Registro de resultado ────────────────────────────────────────────────────

@dataclass
class ObjLine:
    """Una línea de código objeto."""
    kind: str           # "instr" | "label" | "comment" | "blank" | "directive"
    text: str           # texto completo a mostrar
    tac_ref: str = ""   # instrucción TAC de origen (para anotación)


@dataclass
class CodeGenResult:
    success: bool
    lines: List[ObjLine] = field(default_factory=list)
    error: str = ""
    register_map: Dict[str, str] = field(default_factory=dict)
    stats: Dict[str, int] = field(default_factory=dict)


# ─── Registros disponibles ────────────────────────────────────────────────────

_REGS = ["eax", "ebx", "ecx", "edx", "esi", "edi", "r8d", "r9d", "r10d", "r11d"]
_FLOAT_REGS = ["xmm0", "xmm1", "xmm2", "xmm3", "xmm4", "xmm5"]

_OP_MAP = {
    "+": "ADD",  "-": "SUB",  "*": "IMUL",  "/": "IDIV",
    "%": "IDIV", "**": "CALL __pow__",
    "==": "CMP", "!=": "CMP", "<": "CMP",  "<=": "CMP",
    ">": "CMP",  ">=": "CMP",
    "&": "AND",  "|": "OR",   "^": "XOR",  "<<": "SHL", ">>": "SHR",
    "and": "AND", "or": "OR",  "not": "NOT",
}

_CMP_JUMP = {
    "==": "JE",  "!=": "JNE", "<": "JL",  "<=": "JLE",
    ">": "JG",  ">=": "JGE",
}


# ─── Generador principal ──────────────────────────────────────────────────────

class CodeGenerator:
    def __init__(self):
        self._reg_counter = 0
        self._var_map: Dict[str, str] = {}   # variable → registro o [rbp-offset]
        self._stack_offset = 0
        self._lines: List[ObjLine] = []
        self._current_func: Optional[str] = None
        self._param_queue: List[str] = []
        self._stats = {
            "instrucciones_objeto": 0,
            "registros_usados": 0,
            "labels_emitidos": 0,
            "llamadas": 0,
        }

    # ── helpers ───────────────────────────────────────────────────────────────

    def _emit(self, text: str, kind: str = "instr", tac_ref: str = "") -> None:
        self._lines.append(ObjLine(kind=kind, text=text, tac_ref=tac_ref))
        if kind == "instr":
            self._stats["instrucciones_objeto"] += 1

    def _blank(self) -> None:
        self._lines.append(ObjLine(kind="blank", text=""))

    def _comment(self, text: str) -> None:
        self._lines.append(ObjLine(kind="comment", text=f"    ; {text}"))

    def _directive(self, text: str) -> None:
        self._lines.append(ObjLine(kind="directive", text=text))

    def _alloc_reg(self) -> str:
        reg = _REGS[self._reg_counter % len(_REGS)]
        self._reg_counter += 1
        self._stats["registros_usados"] = max(
            self._stats["registros_usados"], self._reg_counter)
        return reg

    def _loc(self, var: str) -> str:
        """Devuelve la ubicación (registro o memoria) de una variable."""
        if var is None:
            return "0"
        # Constante numérica
        try:
            float(var)
            return var
        except (ValueError, TypeError):
            pass
        # Constante string / bool
        if var in ("True", "False"):
            return "1" if var == "True" else "0"
        if var.startswith('"') or var.startswith("'"):
            return var

        if var not in self._var_map:
            reg = self._alloc_reg()
            self._var_map[var] = reg
        return self._var_map[var]

    def _loc_result(self, var: str) -> str:
        """Crea o devuelve ubicación de resultado."""
        if var is None:
            return self._alloc_reg()
        if var not in self._var_map:
            reg = self._alloc_reg()
            self._var_map[var] = reg
        return self._var_map[var]

    # ── traducción por opcode ─────────────────────────────────────────────────

    def _gen_assign(self, instr: TACInstruction) -> None:
        dst = self._loc_result(instr.result)
        src = self._loc(instr.arg1)
        tac = str(instr).strip()
        if src == dst:
            self._comment(f"MOV {dst}, {src}  (eliminado, mismo registro)")
            return
        self._emit(f"    MOV  {dst}, {src}", tac_ref=tac)

    def _gen_binary(self, instr: TACInstruction) -> None:
        op  = instr.label or "+"
        a   = self._loc(instr.arg1)
        b   = self._loc(instr.arg2)
        dst = self._loc_result(instr.result)
        tac = str(instr).strip()

        if op in ("==", "!=", "<", "<=", ">", ">="):
            self._emit(f"    MOV  {dst}, {a}", tac_ref=tac)
            self._emit(f"    CMP  {dst}, {b}")
            jmp = _CMP_JUMP[op]
            self._emit(f"    {jmp}  .set_true_{instr.result}")
            self._emit(f"    MOV  {dst}, 0")
            self._emit(f"    JMP  .end_cmp_{instr.result}")
            self._emit(f".set_true_{instr.result}:", "label")
            self._stats["labels_emitidos"] += 1
            self._emit(f"    MOV  {dst}, 1")
            self._emit(f".end_cmp_{instr.result}:", "label")
            self._stats["labels_emitidos"] += 1
        elif op == "*":
            self._emit(f"    MOV  eax, {a}", tac_ref=tac)
            self._emit(f"    IMUL eax, {b}")
            self._emit(f"    MOV  {dst}, eax")
        elif op == "/":
            self._emit(f"    MOV  eax, {a}", tac_ref=tac)
            self._emit(f"    CDQ")
            self._emit(f"    MOV  ecx, {b}")
            self._emit(f"    IDIV ecx")
            self._emit(f"    MOV  {dst}, eax")
        elif op == "%":
            self._emit(f"    MOV  eax, {a}", tac_ref=tac)
            self._emit(f"    CDQ")
            self._emit(f"    MOV  ecx, {b}")
            self._emit(f"    IDIV ecx")
            self._emit(f"    MOV  {dst}, edx")
        elif op in _OP_MAP:
            mnemonic = _OP_MAP[op]
            self._emit(f"    MOV  {dst}, {a}", tac_ref=tac)
            self._emit(f"    {mnemonic:<4} {dst}, {b}")
        else:
            self._emit(f"    MOV  {dst}, {a}", tac_ref=tac)
            self._emit(f"    ; operador desconocido: {op}")

    def _gen_unary(self, instr: TACInstruction) -> None:
        tac = str(instr).strip()
        src = self._loc(instr.arg1)
        dst = self._loc_result(instr.result)
        op  = instr.arg2 or "-"
        if op == "-":
            self._emit(f"    MOV  {dst}, {src}", tac_ref=tac)
            self._emit(f"    NEG  {dst}")
        elif op == "not":
            self._emit(f"    MOV  {dst}, {src}", tac_ref=tac)
            self._emit(f"    XOR  {dst}, 1")
        else:
            self._emit(f"    MOV  {dst}, {src}", tac_ref=tac)

    def _gen_label(self, instr: TACInstruction) -> None:
        lbl = instr.label or ""
        self._emit(f"{lbl}:", kind="label")
        self._stats["labels_emitidos"] += 1

    def _gen_goto(self, instr: TACInstruction) -> None:
        self._emit(f"    JMP  {instr.label}", tac_ref=str(instr).strip())

    def _gen_if_true(self, instr: TACInstruction) -> None:
        cond = self._loc(instr.arg1)
        tac  = str(instr).strip()
        self._emit(f"    CMP  {cond}, 1", tac_ref=tac)
        self._emit(f"    JE   {instr.label}")

    def _gen_if_false(self, instr: TACInstruction) -> None:
        cond = self._loc(instr.arg1)
        tac  = str(instr).strip()
        self._emit(f"    CMP  {cond}, 0", tac_ref=tac)
        self._emit(f"    JE   {instr.label}")

    def _gen_param(self, instr: TACInstruction) -> None:
        arg = self._loc(instr.arg1)
        self._param_queue.append(arg)
        self._emit(f"    PUSH {arg}", tac_ref=str(instr).strip())

    def _gen_call(self, instr: TACInstruction) -> None:
        tac  = str(instr).strip()
        name = instr.arg1 or "func"
        self._emit(f"    CALL {name}", tac_ref=tac)
        self._stats["llamadas"] += 1
        argc = int(instr.arg2 or 0)
        if argc > 0:
            self._emit(f"    ADD  esp, {argc * 4}   ; limpiar {argc} arg(s)")
        if instr.result:
            dst = self._loc_result(instr.result)
            self._emit(f"    MOV  {dst}, eax")
        self._param_queue.clear()

    def _gen_return(self, instr: TACInstruction) -> None:
        tac = str(instr).strip()
        if instr.arg1:
            val = self._loc(instr.arg1)
            self._emit(f"    MOV  eax, {val}", tac_ref=tac)
        self._emit(f"    POP  ebp")
        self._emit(f"    RET")

    def _gen_begin_func(self, instr: TACInstruction) -> None:
        name = instr.arg1 or "func"
        self._current_func = name
        self._var_map = {}
        self._reg_counter = 0
        self._blank()
        self._directive(f"section .text")
        self._emit(f"global {name}", kind="directive")
        self._emit(f"{name}:", kind="label")
        self._stats["labels_emitidos"] += 1
        self._emit(f"    PUSH ebp")
        self._emit(f"    MOV  ebp, esp")
        self._emit(f"    SUB  esp, 64   ; reservar espacio local")

    def _gen_end_func(self, instr: TACInstruction) -> None:
        name = instr.arg1 or "func"
        self._emit(f"    MOV  esp, ebp")
        self._emit(f"    POP  ebp")
        self._emit(f"    RET")
        self._blank()

    def _gen_index_load(self, instr: TACInstruction) -> None:
        dst = self._loc_result(instr.result)
        arr = self._loc(instr.arg1)
        idx = self._loc(instr.arg2)
        tac = str(instr).strip()
        self._emit(f"    MOV  ecx, {idx}", tac_ref=tac)
        self._emit(f"    MOV  {dst}, [{arr} + ecx*4]")

    def _gen_index_store(self, instr: TACInstruction) -> None:
        arr = self._loc(instr.arg1)
        idx = self._loc(instr.arg2)
        src = self._loc(instr.result)
        tac = str(instr).strip()
        self._emit(f"    MOV  ecx, {idx}", tac_ref=tac)
        self._emit(f"    MOV  [{arr} + ecx*4], {src}")

    # ── dispatch ──────────────────────────────────────────────────────────────

    def _translate(self, instr: TACInstruction) -> None:
        op = instr.op
        if op == "assign":
            self._gen_assign(instr)
        elif op == "binary":
            self._gen_binary(instr)
        elif op == "unary":
            self._gen_unary(instr)
        elif op == "label":
            self._gen_label(instr)
        elif op == "goto":
            self._gen_goto(instr)
        elif op == "if_true":
            self._gen_if_true(instr)
        elif op == "if_false":
            self._gen_if_false(instr)
        elif op == "param":
            self._gen_param(instr)
        elif op == "call":
            self._gen_call(instr)
        elif op == "return":
            self._gen_return(instr)
        elif op == "begin_func":
            self._gen_begin_func(instr)
        elif op == "end_func":
            self._gen_end_func(instr)
        elif op == "index_load":
            self._gen_index_load(instr)
        elif op == "index_store":
            self._gen_index_store(instr)
        elif op == "comment":
            self._comment(instr.comment or "")
        elif op == "nop":
            self._emit("    NOP")
        else:
            self._comment(f"? {str(instr).strip()}")

    def generate(self, instructions: list) -> CodeGenResult:
        try:
            self._directive("; ─── Código Objeto (pseudo-ensamblador x86) ───────────────────────────────")
            self._directive("; Generado automáticamente por el compilador Python → TAC → Objeto")
            self._blank()

            # Prologo: si el código principal no está envuelto en funciones
            has_funcs = any(i.op == "begin_func" for i in instructions)
            if not has_funcs:
                self._directive("section .text")
                self._directive("global _main")
                self._emit("_main:", kind="label")
                self._emit("    PUSH ebp")
                self._emit("    MOV  ebp, esp")
                self._blank()

            for instr in instructions:
                self._translate(instr)

            if not has_funcs:
                self._blank()
                self._emit("    XOR  eax, eax   ; return 0")
                self._emit("    POP  ebp")
                self._emit("    RET")

            self._blank()
            self._directive("; ─── Fin de código objeto ─────────────────────────────────────────────────")

            return CodeGenResult(
                success=True,
                lines=self._lines,
                register_map=dict(self._var_map),
                stats=self._stats,
            )
        except Exception as exc:
            return CodeGenResult(success=False, error=str(exc))


# ─── Función pública ──────────────────────────────────────────────────────────

def generate_object_code(opt_result: OptimizationResult) -> CodeGenResult:
    """Genera código objeto a partir del resultado de la optimización."""
    gen = CodeGenerator()
    instructions = (
        opt_result.optimized_instructions
        if opt_result.success and opt_result.optimized_instructions
        else opt_result.original_instructions
    )
    return gen.generate(instructions)
