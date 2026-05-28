"""
ui.py - Interfaz gráfica con Tkinter para el Compilador/Analizador de Python
Interfaz dividida en paneles: editor, tokens, tipos de datos, AST y consola.
Tablas reestructuradas con celdas (ttk.Treeview) en todas las pestañas de resultados.
"""

import tkinter as tk
from tkinter import ttk, scrolledtext, filedialog, messagebox, font
import threading
import sys
import os
import json
import io
import contextlib

# Agregar src al path
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..'))

from src.lexer import Lexer, TokenType
from src.parser import Parser
from src.ast_generator import generate_ast_report
from src.semantic_analyzer import run_semantic_analysis
from src.intermediate_code_generator import generate_intermediate_code
from src.optimizer import optimize_intermediate_code
from src.code_generator import generate_object_code


# ─── DETECCIÓN DE FUENTES DISPONIBLES ────────────────────────────────────────

def _resolve_font(candidates, fallback="TkDefaultFont"):
    """Devuelve la primera familia de fuente disponible en el sistema."""
    import tkinter as _tk
    from tkinter import font as _font
    try:
        root_test = _tk.Tk()
        root_test.withdraw()
        available = set(_font.families(root_test))
        root_test.destroy()
    except Exception:
        return fallback
    for c in candidates:
        if c in available:
            return c
    return fallback


_UI_FONT_FAMILY = _resolve_font([
    "Inter", "Noto Sans", "Liberation Sans", "DejaVu Sans",
    "Ubuntu", "Cantarell", "Segoe UI", "Helvetica Neue", "Arial"
])

_MONO_FONT_FAMILY = _resolve_font([
    "JetBrains Mono", "Cascadia Code", "Fira Code", "Hack",
    "DejaVu Sans Mono", "Liberation Mono", "Consolas", "Courier New"
])


# ─── PALETA DE COLORES — Tema GitHub Dark Refinado ───────────────────────────
COLORS = {
    "bg_dark":       "#0d1117",
    "bg_medium":     "#161b22",
    "bg_light":      "#1c2128",
    "bg_input":      "#0d1117",
    "border":        "#21262d",
    "border_outer":  "#30363d",
    "text":          "#e6edf3",
    "text_dim":      "#8b949e",
    "text_faint":    "#484f58",

    # Acentos
    "accent":        "#58a6ff",
    "accent2":       "#3fb950",
    "accent3":       "#ff7b72",
    "accent4":       "#d2a8ff",
    "accent5":       "#ffa657",
    "yellow":        "#e3b341",
    "success":       "#3fb950",
    "error":         "#f85149",
    "warning":       "#e3b341",

    # Botones
    "btn_green":     "#238636",
    "btn_green_fg":  "#ffffff",
    "btn_green_hov": "#2ea043",
    "btn_blue":      "#1f6feb",
    "btn_blue_fg":   "#ffffff",
    "btn_blue_hov":  "#388bfd",
    "btn_ghost":     "#21262d",
    "btn_ghost_fg":  "#c9d1d9",
    "btn_ghost_hov": "#30363d",

    # Sintaxis
    "kw":            "#ff7b72",
    "str_color":     "#a5d6ff",
    "num":           "#79c0ff",
    "identifier":    "#c9d1d9",
    "comment":       "#8b949e",
    "operator":      "#ff7b72",
    "bool_color":    "#79c0ff",
    "type_hint":     "#ffa657",

    # Filas alternas
    "row_even":      "#161b22",
    "row_odd":       "#1c2128",
    "row_sel":       "#1f4a8a",

    # Scrollbars
    "scroll_thumb":  "#388bfd",
    "scroll_trough": "#0d1117",
}

KEYWORDS_SET = {
    'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
    'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
    'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
    'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return',
    'try', 'while', 'with', 'yield'
}


# ─── UTILIDADES DE ESTILO ────────────────────────────────────────────────────

def _configure_table_style(style: ttk.Style, name: str = "Treeview"):
    """Configura el estilo común de todas las tablas.

    IMPORTANTE: el padding de las celdas (8px izq.) debe coincidir con
    el padding del heading para que datos y títulos queden alineados.
    """
    CELL_PAD = 8   # px de sangría izquierda — igual en celdas y en heading

    style.configure(name,
                    background=COLORS["bg_medium"],
                    foreground=COLORS["text"],
                    rowheight=30,
                    fieldbackground=COLORS["bg_medium"],
                    borderwidth=0,
                    relief="flat",
                    padding=(CELL_PAD, 0, CELL_PAD, 0),
                    font=(_MONO_FONT_FAMILY, 10))
    style.configure(f"{name}.Heading",
                    background="#0d1117",
                    foreground=COLORS["accent"],
                    font=(_UI_FONT_FAMILY, 9, "bold"),
                    borderwidth=0,
                    relief="flat",
                    padding=(CELL_PAD, 6, CELL_PAD, 6))
    style.map(name,
              background=[("selected", COLORS["row_sel"])],
              foreground=[("selected", "#ffffff")])
    style.map(f"{name}.Heading",
              relief=[("active", "flat")])


def _make_scrolled_tree(parent, columns, col_widths, col_anchors=None,
                        height=None, stretch_last=True):
    """Crea un ttk.Treeview con scrollbars y filas alternas.

    El último (o único) argumento de columna con el mayor ancho tiene
    stretch=True para rellenar el espacio disponible.
    """
    outer = tk.Frame(parent, bg=COLORS["border_outer"], padx=1, pady=1)

    inner = tk.Frame(outer, bg=COLORS["bg_dark"])
    inner.pack(fill="both", expand=True)

    tree_kw = dict(columns=columns, show="headings", selectmode="browse")
    if height:
        tree_kw["height"] = height
    tree = ttk.Treeview(inner, **tree_kw)

    if col_anchors is None:
        col_anchors = {}

    # Determinar qué columna estirará
    if stretch_last:
        # buscar la columna con mayor ancho asignado para que crezca
        max_w = max(col_widths)
        stretch_col = columns[col_widths.index(max_w)]
    else:
        stretch_col = None

    for col, w in zip(columns, col_widths):
        label      = col.replace("_", " ")
        do_stretch = (col == stretch_col)
        col_anchor = col_anchors.get(col, "w")
        # El anchor del heading DEBE coincidir con el anchor de los datos
        tree.heading(col, text=label.upper(), anchor=col_anchor)
        tree.column(col,
                    width=w,
                    minwidth=max(40, w // 3),
                    anchor=col_anchor,
                    stretch=do_stretch)

    vsb = ttk.Scrollbar(inner, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(inner, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    inner.rowconfigure(0, weight=1)
    inner.columnconfigure(0, weight=1)

    tree.tag_configure("even", background=COLORS["row_even"])
    tree.tag_configure("odd",  background=COLORS["row_odd"])

    return outer, tree


def _section_label(parent, text, color=None):
    """Label de sección con barra de acento lateral."""
    color = color or COLORS["accent"]
    wrapper = tk.Frame(parent, bg=COLORS["bg_dark"])
    wrapper.pack(fill="x", padx=8, pady=(12, 3))

    bar = tk.Frame(wrapper, bg=color, width=3)
    bar.pack(side="left", fill="y")

    header = tk.Frame(wrapper, bg=COLORS["bg_light"])
    header.pack(side="left", fill="x", expand=True)

    tk.Label(header, text=f"  {text.upper()}",
             bg=COLORS["bg_light"], fg=color,
             font=(_UI_FONT_FAMILY, 8, "bold"),
             pady=5, anchor="w", padx=6).pack(fill="x")

    tk.Frame(parent, bg=COLORS["border"], height=1).pack(fill="x", padx=8, pady=(0, 4))


def _parser_section(parent, text, accent_color=None):
    """Encabezado de sección moderno para la pestaña Parser."""
    accent_color = accent_color or COLORS["accent"]
    wrapper = tk.Frame(parent, bg=COLORS["bg_dark"])
    wrapper.pack(fill="x", padx=0, pady=(16, 0))

    bar = tk.Frame(wrapper, bg=accent_color, width=4)
    bar.pack(side="left", fill="y")

    header = tk.Frame(wrapper, bg="#13181f")
    header.pack(side="left", fill="x", expand=True)

    tk.Label(header, text="●", fg=accent_color, bg="#13181f",
             font=(_UI_FONT_FAMILY, 9), padx=10).pack(side="left")
    tk.Label(header, text=text.upper(),
             bg="#13181f", fg=COLORS["text"],
             font=(_UI_FONT_FAMILY, 9, "bold"),
             pady=7, anchor="w").pack(side="left")

    tk.Frame(parent, bg=accent_color, height=1).pack(fill="x", pady=(0, 3))
    return wrapper


def _make_metric_card(parent, label, icon, accent):
    """Tarjeta de métrica estilo dashboard."""
    CARD_BG = "#0d1117"
    outer = tk.Frame(parent, bg=COLORS["border"], padx=1, pady=1)

    card = tk.Frame(outer, bg=CARD_BG, padx=10, pady=10)
    card.pack(fill="both", expand=True)

    tk.Frame(card, bg=accent, height=3).pack(fill="x", pady=(0, 7))

    tk.Label(card, text=icon, bg=CARD_BG, fg=accent,
             font=(_UI_FONT_FAMILY, 11)).pack(anchor="w")

    val_var = tk.StringVar(value="—")
    tk.Label(card, textvariable=val_var, bg=CARD_BG, fg="#e6edf3",
             font=(_UI_FONT_FAMILY, 20, "bold"), anchor="w").pack(fill="x", pady=(3, 0))

    tk.Label(card, text=label, bg=CARD_BG, fg=COLORS["text_dim"],
             font=(_UI_FONT_FAMILY, 7), anchor="w",
             wraplength=96, justify="left").pack(fill="x")

    return outer, val_var


def _make_btn(parent, text, command, style="ghost", pady_inner=6, padx_inner=14):
    """Crea un botón estilizado con efecto hover."""
    if style == "green":
        bg, fg, hbg = COLORS["btn_green"],  COLORS["btn_green_fg"], COLORS["btn_green_hov"]
    elif style == "blue":
        bg, fg, hbg = COLORS["btn_blue"],   COLORS["btn_blue_fg"],  COLORS["btn_blue_hov"]
    else:
        bg, fg, hbg = COLORS["btn_ghost"],  COLORS["btn_ghost_fg"], COLORS["btn_ghost_hov"]

    btn = tk.Button(
        parent, text=text, command=command,
        bg=bg, fg=fg,
        activebackground=hbg, activeforeground=fg,
        font=(_UI_FONT_FAMILY, 10, "bold"),
        relief="flat",
        padx=padx_inner, pady=pady_inner,
        cursor="hand2", bd=0
    )

    def _on_enter(e):
        btn.config(bg=hbg)

    def _on_leave(e):
        btn.config(bg=bg)

    btn.bind("<Enter>", _on_enter)
    btn.bind("<Leave>", _on_leave)
    return btn


# ─── CLASE PRINCIPAL ──────────────────────────────────────────────────────────

class AnalyzerApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("JAS Compiler — Python Compiler & Analyzer")
        self.root.configure(bg=COLORS["bg_dark"])
        self.root.geometry("1440x900")
        self.root.minsize(1000, 680)

        self._setup_fonts()
        self._setup_global_style()
        self._build_ui()
        self._load_example()
        self._bind_events()

    # ─────────────────────────────────────────────────────────────────────────
    # Configuración de fuentes
    # ─────────────────────────────────────────────────────────────────────────
    def _setup_fonts(self):
        self.font_code       = font.Font(family=_MONO_FONT_FAMILY, size=12)
        self.font_ui         = font.Font(family=_UI_FONT_FAMILY, size=10)
        self.font_title      = font.Font(family=_UI_FONT_FAMILY, size=11, weight="bold")
        self.font_small      = font.Font(family=_UI_FONT_FAMILY, size=9)
        self.font_mono_small = font.Font(family=_MONO_FONT_FAMILY, size=10)

    # ─────────────────────────────────────────────────────────────────────────
    # Estilos globales ttk
    # ─────────────────────────────────────────────────────────────────────────
    def _setup_global_style(self):
        style = ttk.Style()
        style.theme_use("default")

        # ── Notebook (pestañas) ───────────────────────────────────────────────
        style.configure("Custom.TNotebook",
                        background=COLORS["bg_dark"],
                        borderwidth=0,
                        tabmargins=[0, 0, 0, 0])
        style.configure("Custom.TNotebook.Tab",
                        background=COLORS["bg_medium"],
                        foreground=COLORS["text_dim"],
                        padding=[7, 5],
                        font=(_UI_FONT_FAMILY, 8),
                        borderwidth=0)
        style.map("Custom.TNotebook.Tab",
                  background=[("selected", COLORS["bg_dark"])],
                  foreground=[("selected", COLORS["accent"])],
                  font=[("selected", (_UI_FONT_FAMILY, 8, "bold"))])

        _configure_table_style(style, "Treeview")

        # ── Scrollbars ────────────────────────────────────────────────────────
        for sb in ("Vertical.TScrollbar", "Horizontal.TScrollbar", "TScrollbar"):
            style.configure(sb,
                            background=COLORS["scroll_thumb"],
                            troughcolor=COLORS["scroll_trough"],
                            borderwidth=0,
                            arrowsize=12,
                            relief="flat")
            style.map(sb,
                      background=[("active",  "#1f6feb"),
                                  ("pressed", "#0d4fa0"),
                                  ("!active", COLORS["scroll_thumb"])])

    # ─────────────────────────────────────────────────────────────────────────
    # Construcción de la interfaz principal
    # ─────────────────────────────────────────────────────────────────────────
    def _build_ui(self):
        # ── TOOLBAR ──────────────────────────────────────────────────────────
        toolbar = tk.Frame(self.root, bg=COLORS["bg_medium"], height=56)
        toolbar.pack(fill="x")
        toolbar.pack_propagate(False)
        tk.Frame(self.root, bg=COLORS["border"], height=1).pack(fill="x")

        # Logo
        logo_frame = tk.Frame(toolbar, bg=COLORS["bg_medium"])
        logo_frame.pack(side="left", padx=(16, 0), pady=10)

        logo_icon = tk.Label(logo_frame, text="⚙",
                             bg="#101828", fg=COLORS["accent"],
                             font=(_UI_FONT_FAMILY, 16),
                             padx=10, pady=3, relief="flat")
        logo_icon.pack(side="left")

        logo_text_frame = tk.Frame(logo_frame, bg=COLORS["bg_medium"])
        logo_text_frame.pack(side="left", padx=(8, 0))

        tk.Label(logo_text_frame, text="JAS Compiler",
                 bg=COLORS["bg_medium"], fg=COLORS["text"],
                 font=(_UI_FONT_FAMILY, 13, "bold")).pack(anchor="w")
        tk.Label(logo_text_frame, text="Python Compiler & Analyzer",
                 bg=COLORS["bg_medium"], fg=COLORS["text_faint"],
                 font=(_UI_FONT_FAMILY, 8)).pack(anchor="w")

        # Separador vertical
        tk.Frame(toolbar, bg=COLORS["border"], width=1).pack(
            side="left", fill="y", padx=14, pady=12)

        # Botones de acción
        _make_btn(toolbar, "⚙  Analizar", self.run_analysis,
                  style="green").pack(side="left", padx=3, pady=10)
        _make_btn(toolbar, "▶  Ejecutar", self.run_code,
                  style="blue").pack(side="left", padx=3, pady=10)
        _make_btn(toolbar, "✕  Limpiar", self.clear_all,
                  style="ghost").pack(side="left", padx=3, pady=10)
        _make_btn(toolbar, "📂  Abrir", self.open_file,
                  style="ghost").pack(side="left", padx=3, pady=10)
        _make_btn(toolbar, "💾  Guardar", self.save_file,
                  style="ghost").pack(side="left", padx=3, pady=10)

        tk.Frame(toolbar, bg=COLORS["border"], width=1).pack(
            side="left", fill="y", padx=12, pady=12)

        # LIVE toggle
        self._live_mode = tk.BooleanVar(value=True)
        self._live_btn = tk.Button(
            toolbar, text="● LIVE",
            command=self._toggle_live_mode,
            bg="#0f2010", fg="#3fb950",
            activebackground="#0f2010", activeforeground="#56d364",
            font=(_UI_FONT_FAMILY, 9, "bold"), relief="flat",
            padx=10, pady=6, cursor="hand2", bd=0,
            highlightthickness=1,
            highlightbackground="#238636",
            highlightcolor="#3fb950"
        )
        self._live_btn.pack(side="left", padx=4, pady=10)

        # Indicador de actividad (spinner)
        self._activity_var = tk.StringVar(value="")
        tk.Label(toolbar, textvariable=self._activity_var,
                 bg=COLORS["bg_medium"], fg=COLORS["text_dim"],
                 font=(_UI_FONT_FAMILY, 9)).pack(side="left", padx=6)

        # Status (derecha)
        self.status_var = tk.StringVar(value="Listo")
        self.status_label = tk.Label(
            toolbar, textvariable=self.status_var,
            bg=COLORS["bg_medium"], fg=COLORS["text_dim"],
            font=self.font_small)
        self.status_label.pack(side="right", padx=18)

        # ── TAB BAR — botones de función ─────────────────────────────────────
        tab_bar = tk.Frame(self.root, bg=COLORS["bg_medium"], height=38)
        tab_bar.pack(fill="x")
        tab_bar.pack_propagate(False)
        tk.Frame(self.root, bg="#1f6feb", height=2).pack(fill="x")

        self._panel_frames = {}
        self._tab_buttons  = {}
        self._active_panel = "editor"

        _PANEL_DEFS = [
            ("editor",   "  Editor  "),
            ("tokens",   "  Tokens  "),
            ("types",    "  Tipos  "),
            ("ast",      "  AST  "),
            ("parser",   "  Parser  "),
            ("semantic", "  Semántico  "),
            ("ic",       "  Intermedio  "),
            ("opt",      "  Optimación  "),
            ("objcode",  "  Cód. Objeto  "),
        ]

        for key, label in _PANEL_DEFS:
            is_active = (key == "editor")
            btn = tk.Button(
                tab_bar, text=label,
                command=lambda k=key: self._show_panel(k),
                bg="#1f6feb" if is_active else COLORS["bg_medium"],
                fg="#ffffff"  if is_active else COLORS["text_dim"],
                activebackground="#1f6feb",
                activeforeground="#ffffff",
                font=(_UI_FONT_FAMILY, 9, "bold") if is_active else (_UI_FONT_FAMILY, 9),
                relief="flat", padx=12, pady=0,
                cursor="hand2", bd=0, highlightthickness=0,
            )
            btn.pack(side="left", fill="y", padx=1, pady=4)
            def _enter(e, b=btn, k=key):
                if self._active_panel != k:
                    b.config(bg=COLORS["border_outer"], fg=COLORS["text"])
            def _leave(e, b=btn, k=key):
                if self._active_panel != k:
                    b.config(bg=COLORS["bg_medium"], fg=COLORS["text_dim"],
                             font=(_UI_FONT_FAMILY, 9))
            btn.bind("<Enter>", _enter)
            btn.bind("<Leave>", _leave)
            self._tab_buttons[key] = btn

        # ── VERTICAL PANED WINDOW — contenido + consola ───────────────────────
        v_pane = tk.PanedWindow(
            self.root, orient="vertical",
            bg=COLORS["border"], sashwidth=6,
            sashrelief="flat", sashpad=0)
        v_pane.pack(fill="both", expand=True)

        # ── ÁREA DE CONTENIDO (panel superior) ──────────────────────────────
        self._content_area = tk.Frame(v_pane, bg=COLORS["bg_dark"])
        v_pane.add(self._content_area, minsize=250, stretch="always")

        # ── EDITOR ──────────────────────────────────────────────────────────
        editor_frame = tk.Frame(self._content_area, bg=COLORS["bg_dark"])
        self._panel_frames["editor"] = editor_frame

        editor_header = tk.Frame(editor_frame, bg=COLORS["bg_medium"])
        editor_header.pack(fill="x")
        tk.Label(editor_header, text="  📄",
                 bg=COLORS["bg_medium"], fg=COLORS["text_dim"],
                 font=(_UI_FONT_FAMILY, 10)).pack(side="left", pady=6)
        tk.Label(editor_header, text="script.py",
                 bg=COLORS["bg_medium"], fg=COLORS["text"],
                 font=(_UI_FONT_FAMILY, 10, "bold")).pack(side="left", pady=6)
        tk.Label(editor_header, text=" Python 3 ",
                 bg="#0d2040", fg=COLORS["accent"],
                 font=(_UI_FONT_FAMILY, 8), relief="flat",
                 padx=5, pady=1).pack(side="left", padx=8, pady=7)
        tk.Frame(editor_frame, bg=COLORS["border"], height=1).pack(fill="x")

        editor_container = tk.Frame(editor_frame, bg=COLORS["bg_dark"])
        editor_container.pack(fill="both", expand=True)

        self.line_numbers = tk.Text(
            editor_container, width=4,
            bg=COLORS["bg_medium"], fg=COLORS["text_faint"],
            font=self.font_code, state="disabled",
            relief="flat", padx=8,
            selectbackground=COLORS["bg_medium"])
        self.line_numbers.pack(side="left", fill="y")
        tk.Frame(editor_container, bg=COLORS["border"], width=1).pack(side="left", fill="y")

        self.code_editor = scrolledtext.ScrolledText(
            editor_container,
            bg=COLORS["bg_input"], fg=COLORS["text"],
            font=self.font_code, insertbackground=COLORS["accent"],
            relief="flat", padx=14, pady=10, tabs=("1c",),
            selectbackground="#264f78", undo=True, wrap="none"
        )
        self.code_editor.pack(fill="both", expand=True)

        tk.Frame(editor_frame, bg=COLORS["border"], height=1).pack(fill="x")
        status_bar = tk.Frame(editor_frame, bg=COLORS["bg_medium"])
        status_bar.pack(fill="x")
        self._editor_status_var = tk.StringVar(value="UTF-8  ·  Python 3")
        tk.Label(status_bar, textvariable=self._editor_status_var,
                 bg=COLORS["bg_medium"], fg=COLORS["text_faint"],
                 font=(_UI_FONT_FAMILY, 8), pady=4, padx=10).pack(side="right")

        # ── CONSTRUIR PANELES DE FUNCIÓN ─────────────────────────────────────
        self._build_tokens_tab()
        self._build_types_tab()
        self._build_ast_tab()
        self._build_parser_tab()
        self._build_semantic_tab()
        self._build_intermediate_tab()
        self._build_optimization_tab()
        self._build_object_code_tab()

        # ── ÁREA DE CONSOLA (panel inferior, siempre visible) ─────────────────
        console_outer = tk.Frame(v_pane, bg=COLORS["bg_dark"])
        v_pane.add(console_outer, minsize=130, stretch="never")
        self._build_console_tab(console_outer)

        # Posición inicial del sash
        self.root.after(80, lambda: v_pane.sash_place(0, 0, 640))

        # Mostrar el editor al inicio
        self._show_panel("editor")
    # ─────────────────────────────────────────────────────────────────────────
    # Cambio de panel activo
    # ─────────────────────────────────────────────────────────────────────────
    def _show_panel(self, name: str):
        if self._active_panel in self._panel_frames:
            self._panel_frames[self._active_panel].pack_forget()
        for key, btn in self._tab_buttons.items():
            if key == name:
                btn.config(bg="#1f6feb", fg="#ffffff",
                           font=(_UI_FONT_FAMILY, 9, "bold"))
            else:
                btn.config(bg=COLORS["bg_medium"], fg=COLORS["text_dim"],
                           font=(_UI_FONT_FAMILY, 9))
        self._active_panel = name
        if name in self._panel_frames:
            self._panel_frames[name].pack(fill="both", expand=True)

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 1: Tokens
    # ─────────────────────────────────────────────────────────────────────────
    def _build_tokens_tab(self):
        frame = tk.Frame(self._content_area, bg=COLORS["bg_dark"])
        self._panel_frames["tokens"] = frame

        stats_bar = tk.Frame(frame, bg=COLORS["bg_medium"])
        stats_bar.pack(fill="x")
        tk.Frame(frame, bg=COLORS["border"], height=1).pack(fill="x")

        self.token_stats_var = tk.StringVar(value="")
        tk.Label(stats_bar, textvariable=self.token_stats_var,
                 bg=COLORS["bg_medium"], fg=COLORS["text_dim"],
                 font=(_UI_FONT_FAMILY, 9), pady=6, padx=12).pack(side="left")

        cols    = ("Tipo", "Valor", "Línea", "Col", "Tipo Dato")
        widths  = [170, 220, 70, 70, 120]
        anchors = {"Línea": "center", "Col": "center", "Tipo Dato": "center"}

        tree_frame, self.token_tree = _make_scrolled_tree(
            frame, cols, widths, col_anchors=anchors)
        tree_frame.pack(fill="both", expand=True, padx=8, pady=8)

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 2: Tipos de Datos
    # ─────────────────────────────────────────────────────────────────────────
    def _build_types_tab(self):
        frame = tk.Frame(self._content_area, bg=COLORS["bg_dark"])
        self._panel_frames["types"] = frame

        _section_label(frame, "Resumen por Tipo", COLORS["accent"])

        count_cols    = ("Icono", "Tipo de Dato", "Cantidad", "Distribución (%)")
        count_widths  = [52, 150, 90, 280]
        count_anchors = {"Icono": "center", "Cantidad": "center"}

        count_frame, self.types_count_tree = _make_scrolled_tree(
            frame, count_cols, count_widths,
            col_anchors=count_anchors, height=7)
        count_frame.pack(fill="x", padx=8, pady=(0, 4))

        _section_label(frame, "Valores Encontrados por Tipo", COLORS["text_dim"])

        vals_cols    = ("Icono", "Tipo de Dato", "Valores (hasta 10)")
        vals_widths  = [52, 150, 600]
        vals_anchors = {"Icono": "center"}

        vals_frame, self.types_vals_tree = _make_scrolled_tree(
            frame, vals_cols, vals_widths, col_anchors=vals_anchors)
        vals_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 3: AST
    # ─────────────────────────────────────────────────────────────────────────
    NODE_COLORS = {
        "module":   {"fill": "#0e1f0e", "outline": "#3fb950", "text": "#56d364", "glow": "#3fb950"},
        "function": {"fill": "#0b1428", "outline": "#58a6ff", "text": "#79c0ff", "glow": "#58a6ff"},
        "class":    {"fill": "#170d2e", "outline": "#d2a8ff", "text": "#d2a8ff", "glow": "#d2a8ff"},
        "import":   {"fill": "#1a1508", "outline": "#ffa657", "text": "#ffa657", "glow": "#ffa657"},
        "control":  {"fill": "#200d0d", "outline": "#ff7b72", "text": "#ff7b72", "glow": "#ff7b72"},
        "assign":   {"fill": "#1c1508", "outline": "#e3b341", "text": "#e3b341", "glow": "#e3b341"},
        "return":   {"fill": "#220808", "outline": "#f85149", "text": "#f85149", "glow": "#f85149"},
        "call":     {"fill": "#081a0c", "outline": "#56d364", "text": "#56d364", "glow": "#56d364"},
        "value":    {"fill": "#141920", "outline": "#384048", "text": "#8b949e", "glow": "#30363d"},
        "operator": {"fill": "#0d1117", "outline": "#6e7681", "text": "#c9d1d9", "glow": "#484f58"},
        "default":  {"fill": "#161b22", "outline": "#30363d", "text": "#8b949e", "glow": "#21262d"},
    }

    CAT_ICONS = {
        "module": "◈", "function": "ƒ", "class": "⊕", "import": "⬇",
        "control": "⋮", "assign": "←", "return": "↩", "call": "▷",
        "value": "◇", "operator": "±", "default": "·",
    }

    def _build_ast_tab(self):
        frame = tk.Frame(self._content_area, bg=COLORS["bg_dark"])
        self._panel_frames["ast"] = frame

        # Toolbar del AST
        ast_toolbar = tk.Frame(frame, bg=COLORS["bg_medium"], height=40)
        ast_toolbar.pack(fill="x")
        ast_toolbar.pack_propagate(False)
        tk.Frame(frame, bg=COLORS["border"], height=1).pack(fill="x")

        btn_s = {
            "bg": COLORS["bg_light"], "fg": COLORS["text"],
            "font": (_UI_FONT_FAMILY, 9), "relief": "flat",
            "padx": 10, "pady": 4, "cursor": "hand2",
            "activebackground": COLORS["border_outer"],
            "activeforeground": COLORS["text"], "bd": 0
        }

        tk.Button(ast_toolbar, text="🔍+", command=self._ast_zoom_in,
                  **btn_s).pack(side="left", padx=(8, 2), pady=6)
        tk.Button(ast_toolbar, text="🔍−", command=self._ast_zoom_out,
                  **btn_s).pack(side="left", padx=2, pady=6)
        tk.Button(ast_toolbar, text="⟲  Reset", command=self._ast_reset_view,
                  **btn_s).pack(side="left", padx=2, pady=6)
        tk.Button(ast_toolbar, text="📐  Ajustar", command=self._ast_fit_view,
                  **btn_s).pack(side="left", padx=2, pady=6)

        # Leyenda de categorías
        legend_frame = tk.Frame(ast_toolbar, bg=COLORS["bg_medium"])
        legend_frame.pack(side="right", padx=12)
        legend_items = [
            ("Módulo",    "#3fb950"), ("Función",  "#58a6ff"), ("Clase",    "#d2a8ff"),
            ("Import",    "#ffa657"), ("Control",  "#ff7b72"), ("Asign.",   "#e3b341"),
            ("return",    "#f85149"), ("Llamada",  "#56d364"),
        ]
        for lbl, color in legend_items:
            tk.Label(legend_frame, text="●", fg=color, bg=COLORS["bg_medium"],
                     font=(_UI_FONT_FAMILY, 10)).pack(side="left", padx=1)
            tk.Label(legend_frame, text=lbl, fg=COLORS["text_dim"], bg=COLORS["bg_medium"],
                     font=(_UI_FONT_FAMILY, 8)).pack(side="left", padx=(0, 6))

        # Barra de información hover
        self.ast_info_var = tk.StringVar(
            value="  ← Pasa el cursor sobre un nodo | Arrastra para mover | Rueda para zoom")
        ast_info_bar = tk.Frame(frame, bg=COLORS["bg_medium"])
        ast_info_bar.pack(fill="x")
        tk.Label(ast_info_bar, textvariable=self.ast_info_var,
                 bg=COLORS["bg_medium"], fg=COLORS["text_dim"],
                 font=(_UI_FONT_FAMILY, 9), pady=5, anchor="w", padx=12).pack(fill="x")
        tk.Frame(frame, bg=COLORS["border"], height=1).pack(fill="x")

        # Canvas
        canvas_frame = tk.Frame(frame, bg=COLORS["bg_dark"])
        canvas_frame.pack(fill="both", expand=True)

        self.ast_canvas = tk.Canvas(canvas_frame, bg=COLORS["bg_dark"], highlightthickness=0)
        vsb = ttk.Scrollbar(canvas_frame, orient="vertical", command=self.ast_canvas.yview)
        hsb = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.ast_canvas.xview)
        self.ast_canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        vsb.pack(side="right", fill="y")
        hsb.pack(side="bottom", fill="x")
        self.ast_canvas.pack(fill="both", expand=True)

        self._ast_zoom       = 1.0
        self._ast_pan_start  = None
        self._ast_graph_data = None
        self._ast_positions  = {}
        self._ast_canvas_nodes = {}
        self._ast_node_info    = {}

        self.ast_canvas.bind("<ButtonPress-1>", self._ast_pan_start_cb)
        self.ast_canvas.bind("<B1-Motion>",     self._ast_pan_move_cb)
        self.ast_canvas.bind("<MouseWheel>",    self._ast_mouse_wheel)
        self.ast_canvas.bind("<Button-4>", lambda e: self._ast_scroll_zoom(e, 1.1))
        self.ast_canvas.bind("<Button-5>", lambda e: self._ast_scroll_zoom(e, 0.9))
        self.ast_canvas.bind("<Motion>",   self._ast_on_hover)

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 4: Parser
    # ─────────────────────────────────────────────────────────────────────────
    def _build_parser_tab(self):
        outer = tk.Frame(self._content_area, bg=COLORS["bg_dark"])
        self._panel_frames["parser"] = outer

        # Banner de estado
        self.parser_status_var   = tk.StringVar(value="")
        self.parser_status_label = tk.Label(
            outer, textvariable=self.parser_status_var,
            bg="#0a1a0a", fg=COLORS["success"],
            font=(_UI_FONT_FAMILY, 12, "bold"),
            pady=11, anchor="w", padx=18)
        self.parser_status_label.pack(fill="x")
        self._parser_banner_line = tk.Frame(outer, bg=COLORS["success"], height=3)
        self._parser_banner_line.pack(fill="x")

        # Canvas scrollable para el contenido
        scroll_canvas = tk.Canvas(outer, bg=COLORS["bg_dark"],
                                  highlightthickness=0, bd=0)
        vsb = ttk.Scrollbar(outer, orient="vertical", command=scroll_canvas.yview)
        scroll_canvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        scroll_canvas.pack(side="left", fill="both", expand=True)

        inner = tk.Frame(scroll_canvas, bg=COLORS["bg_dark"])
        inner_id = scroll_canvas.create_window((0, 0), window=inner, anchor="nw")

        inner.bind("<Configure>",
                   lambda e: scroll_canvas.configure(
                       scrollregion=scroll_canvas.bbox("all")))
        scroll_canvas.bind("<Configure>",
                           lambda e: scroll_canvas.itemconfig(
                               inner_id, width=e.width))

        def _mw(e):
            scroll_canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")

        scroll_canvas.bind("<MouseWheel>", _mw)
        inner.bind("<MouseWheel>", _mw)

        # Contenido con padding horizontal
        c = tk.Frame(inner, bg=COLORS["bg_dark"])
        c.pack(fill="x", padx=28, pady=(6, 24))

        # ── Tarjetas de métricas ──────────────────────────────────────────────
        _parser_section(c, "Estadísticas del Código", COLORS["accent"])

        self._parser_card_specs = [
            ("Total líneas",  "📄", "#58a6ff", "lineas_totales"),
            ("Cód. líneas",   "💻", "#3fb950", "lineas_codigo"),
            ("Comentarios",   "💬", "#8b949e", "lineas_comentarios"),
            ("Complejidad",   "🌀", "#d2a8ff", "complejidad_ciclomatica"),
            ("Bucles",        "🔁", "#ffa657", "bucles"),
            ("Condicionales", "❓", "#f78166", "condicionales"),
            ("Try / Except",  "🛡",  "#e3b341", "excepciones"),
        ]
        self._parser_card_vars = {}

        cards_outer = tk.Frame(c, bg=COLORS["bg_dark"])
        cards_outer.pack(fill="x", pady=(6, 8))

        num_cards = len(self._parser_card_specs)
        cols_per_row = 4
        for idx, (label, icon, accent, key) in enumerate(self._parser_card_specs):
            row_n = idx // cols_per_row
            col_n = idx % cols_per_row
            card, var = _make_metric_card(cards_outer, label, icon, accent)
            card.grid(row=row_n, column=col_n, padx=4, pady=4, sticky="nsew")
            cards_outer.columnconfigure(col_n, weight=1)
            self._parser_card_vars[key] = var

        tk.Frame(c, bg=COLORS["border"], height=1).pack(fill="x", pady=(6, 0))

        # ── Tabla: Funciones ──────────────────────────────────────────────────
        _parser_section(c, "Funciones", COLORS["accent2"])
        func_cols   = ("Nombre", "Argumentos", "Retorno", "Async", "Línea", "Decoradores")
        func_widths = [160, 220, 120, 65, 60, 140]
        func_frame, self.parser_func_tree = _make_scrolled_tree(
            c, func_cols, func_widths,
            col_anchors={"Async": "center", "Línea": "center"},
            height=5)
        func_frame.pack(fill="x", pady=(3, 6))
        self.parser_func_tree.tag_configure("async_row", foreground=COLORS["accent5"])
        self.parser_func_tree.tag_configure("decorated",  foreground=COLORS["accent4"])

        # ── Tabla: Clases ─────────────────────────────────────────────────────
        _parser_section(c, "Clases", COLORS["accent4"])
        cls_cols   = ("Nombre", "Bases", "Métodos", "Línea")
        cls_widths = [180, 180, 380, 65]
        cls_frame, self.parser_cls_tree = _make_scrolled_tree(
            c, cls_cols, cls_widths,
            col_anchors={"Línea": "center"},
            height=4)
        cls_frame.pack(fill="x", pady=(3, 6))

        # ── Tabla: Importaciones ──────────────────────────────────────────────
        _parser_section(c, "Importaciones", COLORS["accent5"])
        imp_cols   = ("Tipo", "Módulo", "Nombres / Alias", "Línea")
        imp_widths = [130, 220, 380, 65]
        imp_frame, self.parser_imp_tree = _make_scrolled_tree(
            c, imp_cols, imp_widths,
            col_anchors={"Tipo": "center", "Línea": "center"},
            height=4)
        imp_frame.pack(fill="x", pady=(3, 6))
        self.parser_imp_tree.tag_configure("from_import",  foreground=COLORS["accent4"])
        self.parser_imp_tree.tag_configure("plain_import", foreground=COLORS["accent"])

        # ── Errores y advertencias PEP 8 ─────────────────────────────────────
        _parser_section(c, "Errores y Advertencias", COLORS["warning"])
        err_outer = tk.Frame(c, bg=COLORS["bg_dark"],
                             highlightthickness=1,
                             highlightbackground=COLORS["border"])
        err_outer.pack(fill="x", pady=(3, 6))

        self.parser_text = scrolledtext.ScrolledText(
            err_outer, bg=COLORS["bg_dark"], fg=COLORS["text"],
            font=(_MONO_FONT_FAMILY, 10), state="disabled",
            relief="flat", padx=14, pady=10, height=7,
            selectbackground="#264f78"
        )
        self.parser_text.pack(fill="both", expand=True)
        self.parser_text.tag_configure("ok",      foreground=COLORS["success"])
        self.parser_text.tag_configure("error",   foreground=COLORS["error"])
        self.parser_text.tag_configure("warning", foreground=COLORS["warning"])
        self.parser_text.tag_configure("header",  foreground=COLORS["accent"],
                                       font=(_UI_FONT_FAMILY, 10, "bold"))
        self.parser_text.tag_configure("info",    foreground=COLORS["accent4"])
        self.parser_stats_tree = None

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 5: Semántico
    # ─────────────────────────────────────────────────────────────────────────
    def _build_semantic_tab(self):
        frame = tk.Frame(self._content_area, bg=COLORS["bg_dark"])
        self._panel_frames["semantic"] = frame

        _section_label(frame, "Tabla de Símbolos", COLORS["accent"])

        sym_cols    = ("Nombre", "Tipo Símbolo", "Tipo Inferido", "Scope", "Línea", "Usado")
        sym_widths  = [150, 130, 130, 160, 70, 70]
        sym_anchors = {"Línea": "center", "Usado": "center"}

        sym_frame, self.sym_tree = _make_scrolled_tree(
            frame, sym_cols, sym_widths,
            col_anchors=sym_anchors, height=9)
        sym_frame.pack(fill="both", expand=True, padx=8, pady=(4, 0))

        self.sym_tree.tag_configure("even_unused",
                                    background=COLORS["row_even"],
                                    foreground=COLORS["text_faint"])
        self.sym_tree.tag_configure("odd_unused",
                                    background=COLORS["row_odd"],
                                    foreground=COLORS["text_faint"])

        _section_label(frame, "Errores y Advertencias Semánticas", COLORS["error"])

        self.semantic_text = scrolledtext.ScrolledText(
            frame, bg=COLORS["bg_dark"], fg=COLORS["text"],
            font=(_MONO_FONT_FAMILY, 10), state="disabled",
            relief="flat", padx=14, pady=10, height=10
        )
        self.semantic_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.semantic_text.tag_configure("error",   foreground=COLORS["error"])
        self.semantic_text.tag_configure("warning", foreground=COLORS["warning"])
        self.semantic_text.tag_configure("ok",      foreground=COLORS["success"])
        self.semantic_text.tag_configure("header",  foreground=COLORS["accent"],
                                         font=(_UI_FONT_FAMILY, 11, "bold"))
        self.semantic_text.tag_configure("dim",     foreground=COLORS["text_dim"])

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 6: Código Intermedio (TAC)
    # ─────────────────────────────────────────────────────────────────────────
    def _build_intermediate_tab(self):
        frame = tk.Frame(self._content_area, bg=COLORS["bg_dark"])
        self._panel_frames["ic"] = frame

        # Barra de estadísticas
        stats_bar = tk.Frame(frame, bg=COLORS["bg_medium"])
        stats_bar.pack(fill="x")
        tk.Frame(frame, bg=COLORS["border"], height=1).pack(fill="x")

        self.ic_stats_var = tk.StringVar(value="")
        tk.Label(stats_bar, textvariable=self.ic_stats_var,
                 bg=COLORS["bg_medium"], fg=COLORS["text_dim"],
                 font=(_UI_FONT_FAMILY, 9), pady=6, padx=12).pack(side="left")

        # Vista de texto TAC (arriba)
        _section_label(frame, "Vista de Texto TAC", COLORS["text_dim"])

        self.ic_text = scrolledtext.ScrolledText(
            frame, bg=COLORS["bg_dark"], fg=COLORS["accent2"],
            font=(_MONO_FONT_FAMILY, 10), state="disabled",
            relief="flat", padx=14, pady=10, height=9,
            selectbackground="#264f78"
        )
        self.ic_text.pack(fill="both", expand=True, padx=8, pady=(0, 4))
        self.ic_text.tag_configure("label",   foreground=COLORS["accent5"],
                                   font=(_MONO_FONT_FAMILY, 10, "bold"))
        self.ic_text.tag_configure("func",    foreground=COLORS["accent2"],
                                   font=(_MONO_FONT_FAMILY, 10, "bold"))
        self.ic_text.tag_configure("jump",    foreground=COLORS["warning"])
        self.ic_text.tag_configure("comment", foreground=COLORS["comment"])
        self.ic_text.tag_configure("error",   foreground=COLORS["error"])

        # Tabla TAC (abajo)
        _section_label(frame, "Instrucciones TAC (Código de Tres Direcciones)", COLORS["accent4"])

        tac_cols    = ("#", "Instrucción", "Operando 1", "Op.", "Operando 2", "Resultado")
        tac_widths  = [42, 120, 160, 52, 160, 160]
        tac_anchors = {"#": "center", "Op.": "center"}

        tac_frame, self.ic_tree = _make_scrolled_tree(
            frame, tac_cols, tac_widths,
            col_anchors=tac_anchors, height=10)
        tac_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self.ic_tree.tag_configure("label_row",
                                   foreground=COLORS["accent5"],
                                   font=(_MONO_FONT_FAMILY, 10, "bold"))
        self.ic_tree.tag_configure("func_row",
                                   foreground=COLORS["accent2"],
                                   font=(_MONO_FONT_FAMILY, 10, "bold"))
        self.ic_tree.tag_configure("jump_row",  foreground=COLORS["warning"])
        self.ic_tree.tag_configure("comment_row", foreground=COLORS["comment"])

    # ─────────────────────────────────────────────────────────────────────────
    # Actualización: Código Intermedio
    # ─────────────────────────────────────────────────────────────────────────
    def _update_intermediate_tab(self, ic_result):
        for item in self.ic_tree.get_children():
            self.ic_tree.delete(item)

        t = self.ic_text
        t.config(state="normal")
        t.delete("1.0", "end")

        if not ic_result.success:
            for err in ic_result.errors:
                t.insert("end", f"  ❌ {err}\n", "error")
            t.config(state="disabled")
            self.ic_stats_var.set("  ❌ Error en la generación de código intermedio")
            return

        _OP_LABELS = {
            "assign":      ("←", ""),
            "binary":      ("op", ""),
            "unary":       ("unario", ""),
            "index_load":  ("[]", "carga"),
            "index_store": ("[]", "guarda"),
            "call":        ("call", ""),
            "param":       ("param", ""),
            "return":      ("return", ""),
            "goto":        ("goto", ""),
            "if_true":     ("if", "goto"),
            "if_false":    ("ifFalse", "goto"),
            "label":       ("label", ""),
            "begin_func":  ("begin_func", ""),
            "end_func":    ("end_func", ""),
            "comment":     ("//", ""),
            "nop":         ("nop", ""),
        }

        row_count = 0
        for i, instr in enumerate(ic_result.instructions):
            op = instr.op
            stripe = "even" if row_count % 2 == 0 else "odd"

            if op == "label":
                row_tag = ("label_row", stripe)
                vals = (f"{i+1}", f"{instr.label}:", "", "", "", "")
            elif op in ("begin_func", "end_func"):
                row_tag = ("func_row", stripe)
                vals = (f"{i+1}", op, instr.arg1 or "", "", "", "")
            elif op == "comment":
                row_tag = ("comment_row", stripe)
                vals = (f"{i+1}", f"# {instr.comment}", "", "", "", "")
            elif op in ("goto", "if_true", "if_false"):
                row_tag = ("jump_row", stripe)
                op_sym = "goto" if op == "goto" else ("if" if op == "if_true" else "ifFalse")
                vals = (f"{i+1}", op_sym, instr.arg1 or "", "→", instr.label or "", "")
            elif op == "binary":
                row_tag = (stripe,)
                vals = (f"{i+1}", "binary", instr.arg1 or "", instr.label or "", instr.arg2 or "", instr.result or "")
            elif op == "unary":
                row_tag = (stripe,)
                vals = (f"{i+1}", "unary", f"{instr.arg1}{instr.arg2}", "", "", instr.result or "")
            elif op == "assign":
                row_tag = (stripe,)
                vals = (f"{i+1}", "asignar", instr.arg1 or "", "→", "", instr.result or "")
            elif op == "call":
                row_tag = (stripe,)
                vals = (f"{i+1}", "call", instr.arg1 or "", f"n={instr.arg2}", "", instr.result or "")
            elif op == "param":
                row_tag = (stripe,)
                vals = (f"{i+1}", "param", instr.arg1 or "", "", "", "")
            elif op == "return":
                row_tag = (stripe,)
                vals = (f"{i+1}", "return", instr.arg1 or "", "", "", "")
            elif op in ("index_load", "index_store"):
                row_tag = (stripe,)
                lbl = "a[i]→" if op == "index_load" else "→a[i]"
                vals = (f"{i+1}", lbl, instr.arg1 or "", f"[{instr.arg2}]", "", instr.result or "")
            elif op == "nop":
                row_tag = (stripe,)
                vals = (f"{i+1}", "nop", "", "", "", "")
            else:
                row_tag = (stripe,)
                vals = (f"{i+1}", op,
                        instr.arg1 or "", instr.label or "",
                        instr.arg2 or "", instr.result or "")

            self.ic_tree.insert("", "end", values=vals, tags=row_tag)
            row_count += 1

        # Vista de texto con coloreado
        for line in ic_result.to_text().splitlines():
            stripped = line.strip()
            if not stripped:
                t.insert("end", "\n")
            elif stripped.startswith("#"):
                t.insert("end", line + "\n", "comment")
            elif stripped.endswith(":") and not stripped.startswith("ifFalse") and not stripped.startswith("if "):
                t.insert("end", line + "\n", "label")
            elif stripped.startswith("begin_func") or stripped.startswith("end_func"):
                t.insert("end", line + "\n", "func")
            elif stripped.startswith("goto") or stripped.startswith("if") or stripped.startswith("ifFalse"):
                t.insert("end", line + "\n", "jump")
            else:
                t.insert("end", line + "\n")

        t.config(state="disabled")

        n_instr = len(ic_result.instructions)
        n_temps  = ic_result.temp_count
        n_labels = ic_result.label_count
        err_str  = f"  |  ⚠ {len(ic_result.errors)} advertencia(s)" if ic_result.errors else ""
        self.ic_stats_var.set(
            f"  Instrucciones: {n_instr}  |  Temporales: t0…t{max(n_temps-1,0)}"
            f"  |  Etiquetas: {n_labels}{err_str}"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 7: Optimación de Código Intermedio
    # ─────────────────────────────────────────────────────────────────────────
    def _build_optimization_tab(self):
        frame = tk.Frame(self._content_area, bg=COLORS["bg_dark"])
        self._panel_frames["opt"] = frame

        # ── stats bar (siempre visible en la parte superior) ─────────────────
        stats_bar = tk.Frame(frame, bg=COLORS["bg_medium"])
        stats_bar.pack(fill="x", side="top")
        tk.Frame(frame, bg=COLORS["border"], height=1).pack(fill="x", side="top")

        self.opt_stats_var = tk.StringVar(value="")
        tk.Label(stats_bar, textvariable=self.opt_stats_var,
                 bg=COLORS["bg_medium"], fg=COLORS["text_dim"],
                 font=(_UI_FONT_FAMILY, 9), pady=6, padx=12).pack(side="left")

        # ── contenedor scrollable para cards + texto + tabla ──────────────────
        scroll_host = tk.Frame(frame, bg=COLORS["bg_dark"])
        scroll_host.pack(fill="both", expand=True, side="top")

        opt_vsb = ttk.Scrollbar(scroll_host, orient="vertical")
        opt_vsb.pack(side="right", fill="y")

        opt_canvas = tk.Canvas(
            scroll_host, bg=COLORS["bg_dark"],
            highlightthickness=0,
            yscrollcommand=opt_vsb.set)
        opt_canvas.pack(side="left", fill="both", expand=True)
        opt_vsb.config(command=opt_canvas.yview)

        inner = tk.Frame(opt_canvas, bg=COLORS["bg_dark"])
        _cw = opt_canvas.create_window((0, 0), window=inner, anchor="nw")

        def _on_inner_cfg(e):
            opt_canvas.config(scrollregion=opt_canvas.bbox("all"))
        def _on_canvas_cfg(e):
            opt_canvas.itemconfig(_cw, width=e.width)
        inner.bind("<Configure>", _on_inner_cfg)
        opt_canvas.bind("<Configure>", _on_canvas_cfg)

        # Scroll con rueda del ratón
        def _on_wheel(e):
            opt_canvas.yview_scroll(int(-1*(e.delta/120)), "units")
        opt_canvas.bind_all("<MouseWheel>", _on_wheel)

        # ── tarjetas métricas ─────────────────────────────────────────────────
        cards_row = tk.Frame(inner, bg=COLORS["bg_dark"])
        cards_row.pack(fill="x", padx=8, pady=(10, 4))

        self._opt_card_vars = {}
        card_specs = [
            ("Instrucciones\nOriginales",  "📄", COLORS["text_dim"],  "orig"),
            ("Instrucciones\nOptimadas",   "⚡", COLORS["accent"],    "opt"),
            ("Reducción\n(instrucciones)", "📉", COLORS["success"],   "red"),
            ("Plegado de\nConstantes",     "🔢", COLORS["accent5"],   "cf"),
            ("Simplif.\nAlgebraica",       "➕", COLORS["yellow"],   "alg"),
            ("Propagación\nde Copias",     "📋", COLORS["accent4"],   "cp"),
            ("Cód. Muerto\nEliminado",     "🗑", COLORS["accent3"],   "dce"),
        ]
        for i, (label, icon, accent, key) in enumerate(card_specs):
            card_outer, val_var = _make_metric_card(cards_row, label, icon, accent)
            card_outer.grid(row=0, column=i, padx=4, pady=2, sticky="nsew")
            cards_row.columnconfigure(i, weight=1)
            self._opt_card_vars[key] = val_var

        _section_label(inner, "Vista de Texto TAC Optimado", COLORS["accent"])

        self.opt_text = scrolledtext.ScrolledText(
            inner, bg=COLORS["bg_dark"], fg=COLORS["success"],
            font=(_MONO_FONT_FAMILY, 10), state="disabled",
            relief="flat", padx=14, pady=10, height=14,
            selectbackground="#264f78"
        )
        self.opt_text.pack(fill="x", padx=8, pady=(0, 4))
        self.opt_text.tag_configure("label",   foreground=COLORS["accent5"],
                                    font=(_MONO_FONT_FAMILY, 10, "bold"))
        self.opt_text.tag_configure("func",    foreground=COLORS["accent2"],
                                    font=(_MONO_FONT_FAMILY, 10, "bold"))
        self.opt_text.tag_configure("jump",    foreground=COLORS["warning"])
        self.opt_text.tag_configure("comment", foreground=COLORS["comment"])
        self.opt_text.tag_configure("changed", foreground=COLORS["success"],
                                    font=(_MONO_FONT_FAMILY, 10, "bold"))
        self.opt_text.tag_configure("error",   foreground=COLORS["error"])
        _section_label(inner, "Registro de Transformaciones Aplicadas", COLORS["accent4"])

        log_cols   = ("#", "Tipo de Optimación", "Instrucción Original", "Resultado")
        log_widths = [38, 200, 300, 300]

        log_frame, self.opt_log_tree = _make_scrolled_tree(
            inner, log_cols, log_widths, height=8)
        log_frame.pack(fill="x", padx=8, pady=(0, 8))

        self.opt_log_tree.tag_configure("cf",  foreground=COLORS["accent5"])
        self.opt_log_tree.tag_configure("alg", foreground=COLORS["yellow"])
        self.opt_log_tree.tag_configure("cp",  foreground=COLORS["accent4"])
        self.opt_log_tree.tag_configure("dce", foreground=COLORS["accent3"])

    # ─────────────────────────────────────────────────────────────────────────
    # Actualización: Optimación
    # ─────────────────────────────────────────────────────────────────────────
    def _update_optimization_tab(self, opt_result):
        t = self.opt_text
        t.config(state="normal")
        t.delete("1.0", "end")
        for item in self.opt_log_tree.get_children():
            self.opt_log_tree.delete(item)

        stats = opt_result.stats
        red   = opt_result.reduction
        pct   = opt_result.reduction_pct

        self.opt_stats_var.set(
            f"  Original: {opt_result.original_count}  |  "
            f"Optimado: {opt_result.optimized_count}  |  "
            f"Reduccion: {red} instrucciones ({pct:.1f}%)"
        )

        self._opt_card_vars["orig"].set(str(opt_result.original_count))
        self._opt_card_vars["opt"].set(str(opt_result.optimized_count))
        self._opt_card_vars["red"].set(f"-{red}")
        self._opt_card_vars["cf"].set(str(stats.get("constant_folding", 0)))
        self._opt_card_vars["alg"].set(str(stats.get("algebraic_simplification", 0)))
        self._opt_card_vars["cp"].set(str(stats.get("copy_propagation", 0)))
        self._opt_card_vars["dce"].set(str(stats.get("dead_code_elimination", 0)))

        orig_strs = set(str(i).strip() for i in opt_result.original_instructions)

        for instr in opt_result.optimized_instructions:
            line     = str(instr)
            stripped = line.strip()
            is_new   = stripped not in orig_strs and stripped != ""

            if not stripped:
                t.insert("end", "\n")
            elif stripped.startswith("#"):
                t.insert("end", line + "\n", "comment")
            elif stripped.endswith(":") and not stripped.startswith("ifFalse") and not stripped.startswith("if "):
                t.insert("end", line + "\n", "label")
            elif stripped.startswith("begin_func") or stripped.startswith("end_func"):
                t.insert("end", line + "\n", "func")
            elif stripped.startswith("goto") or stripped.startswith("if") or stripped.startswith("ifFalse"):
                t.insert("end", line + "\n", "jump")
            elif is_new:
                t.insert("end", line + "\n", "changed")
            else:
                t.insert("end", line + "\n")

        t.config(state="disabled")

        type_tags = {
            "Plegado de constantes":        "cf",
            "Simplificación algebraica":    "alg",
            "Propagación de copias":        "cp",
            "Eliminación de código muerto": "dce",
        }
        for j, (opt_type, original, resultado) in enumerate(opt_result.log):
            tag    = type_tags.get(opt_type, "even")
            stripe = "even" if j % 2 == 0 else "odd"
            self.opt_log_tree.insert("", "end",
                values=(f"{j+1}", opt_type, original, resultado),
                tags=(tag, stripe))

        if not opt_result.log:
            self.opt_log_tree.insert("", "end",
                values=("—", "Sin transformaciones", "El código ya es óptimo", ""),
                tags=("even",))

    # ─────────────────────────────────────────────────────────────────────────
    # Tab 8: Código Objeto
    # ─────────────────────────────────────────────────────────────────────────
    def _build_object_code_tab(self):
        frame = tk.Frame(self._content_area, bg=COLORS["bg_dark"])
        self._panel_frames["objcode"] = frame

        stats_bar = tk.Frame(frame, bg=COLORS["bg_medium"])
        stats_bar.pack(fill="x")
        tk.Frame(frame, bg=COLORS["border"], height=1).pack(fill="x")
        self.obj_stats_var = tk.StringVar(value="")
        tk.Label(stats_bar, textvariable=self.obj_stats_var,
                 bg=COLORS["bg_medium"], fg=COLORS["text_dim"],
                 font=(_UI_FONT_FAMILY, 9), pady=6, padx=12).pack(side="left")

        _section_label(frame, "Vista de Código Objeto (pseudo-ensamblador x86)", COLORS["accent"])

        self.obj_text = scrolledtext.ScrolledText(
            frame, bg=COLORS["bg_dark"], fg=COLORS["text"],
            font=(_MONO_FONT_FAMILY, 10), state="disabled",
            relief="flat", padx=14, pady=10,
            selectbackground="#264f78"
        )
        self.obj_text.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        self.obj_text.tag_configure("directive", foreground=COLORS["text_dim"],
                                    font=(_MONO_FONT_FAMILY, 9))
        self.obj_text.tag_configure("label",     foreground=COLORS["accent5"],
                                    font=(_MONO_FONT_FAMILY, 10, "bold"))
        self.obj_text.tag_configure("instr",     foreground=COLORS["text"])
        self.obj_text.tag_configure("mov",       foreground=COLORS["accent2"])
        self.obj_text.tag_configure("jump",      foreground=COLORS["warning"])
        self.obj_text.tag_configure("call",      foreground=COLORS["accent"])
        self.obj_text.tag_configure("comment",   foreground=COLORS["comment"])
        self.obj_text.tag_configure("error",     foreground=COLORS["error"])

    # ─────────────────────────────────────────────────────────────────────────
    # Actualización: Código Objeto
    # ─────────────────────────────────────────────────────────────────────────
    def _update_object_code_tab(self, cg_result):
        t = self.obj_text
        t.config(state="normal")
        t.delete("1.0", "end")

        if not cg_result.success:
            t.insert("end", f"; ERROR: {cg_result.error}\n", "error")
            t.config(state="disabled")
            return

        _MOV_OPS = ("MOV", "PUSH", "POP", "LEA", "XCHG")
        _JMP_OPS = ("JMP", "JE", "JNE", "JG", "JGE", "JL", "JLE")

        for ol in cg_result.lines:
            text = ol.text
            if ol.kind == "blank":
                t.insert("end", "\n")
            elif ol.kind == "directive":
                t.insert("end", text + "\n", "directive")
            elif ol.kind == "label":
                t.insert("end", "\n" + text + "\n", "label")
            elif ol.kind == "comment":
                t.insert("end", text + "\n", "comment")
            elif ol.kind == "instr":
                stripped = text.lstrip()
                mnemonic = stripped.split()[0].upper() if stripped else ""
                if mnemonic in ("CALL", "RET"):
                    tag = "call"
                elif mnemonic.startswith("J"):
                    tag = "jump"
                elif mnemonic in _MOV_OPS:
                    tag = "mov"
                else:
                    tag = "instr"
                t.insert("end", text + "\n", tag)
            else:
                t.insert("end", text + "\n")

        t.config(state="disabled")

        s = cg_result.stats
        self.obj_stats_var.set(
            f"  Instrucciones: {s.get('instrucciones_objeto', 0)}  |  "
            f"Registros: {s.get('registros_usados', 0)}  |  "
            f"Labels: {s.get('labels_emitidos', 0)}  |  "
            f"Llamadas: {s.get('llamadas', 0)}"
        )

    # Tab 9: Consola
    # ─────────────────────────────────────────────────────────────────────────
    def _build_console_tab(self, parent):
        frame = tk.Frame(parent, bg=COLORS["bg_dark"])
        frame.pack(fill="both", expand=True)

        header_bar = tk.Frame(frame, bg=COLORS["bg_medium"])
        header_bar.pack(fill="x")
        tk.Label(header_bar, text="  ▶  CONSOLA DE SALIDA",
                 bg=COLORS["bg_medium"], fg=COLORS["text_dim"],
                 font=(_UI_FONT_FAMILY, 8, "bold"), pady=6, padx=8).pack(side="left")
        tk.Frame(frame, bg=COLORS["border"], height=1).pack(fill="x")

        self.console_text = scrolledtext.ScrolledText(
            frame, bg="#080c10", fg=COLORS["accent2"],
            font=self.font_mono_small, state="disabled",
            relief="flat", padx=14, pady=10
        )
        self.console_text.pack(fill="both", expand=True)
        self.console_text.tag_configure("error",        foreground=COLORS["error"])
        self.console_text.tag_configure("info",         foreground=COLORS["text_dim"])
        self.console_text.tag_configure("input_prompt", foreground=COLORS["yellow"])
        self.console_text.tag_configure("input_value",  foreground=COLORS["accent"])

        # Barra de entrada de consola
        tk.Frame(frame, bg=COLORS["border"], height=1).pack(fill="x", side="bottom")
        input_bar = tk.Frame(frame, bg=COLORS["bg_medium"])
        input_bar.pack(fill="x", side="bottom")

        self._console_prompt_label = tk.Label(
            input_bar, text="›", bg=COLORS["bg_medium"],
            fg=COLORS["yellow"], font=(_MONO_FONT_FAMILY, 14, "bold"), padx=10)
        self._console_prompt_label.pack(side="left")

        self._console_input_var = tk.StringVar()
        self._console_input_entry = tk.Entry(
            input_bar, textvariable=self._console_input_var,
            bg=COLORS["bg_input"], fg=COLORS["text"],
            insertbackground=COLORS["accent"],
            font=(_MONO_FONT_FAMILY, 11), relief="flat",
            highlightthickness=1,
            highlightcolor=COLORS["accent"],
            highlightbackground=COLORS["border"],
            state="disabled"
        )
        self._console_input_entry.pack(
            fill="x", side="left", expand=True,
            ipady=5, padx=(0, 8), pady=6)
        self._console_input_entry.bind("<Return>", self._on_console_input_submit)
        self._console_input_queue = None

    # ─────────────────────────────────────────────────────────────────────────
    # Canvas AST — dibujo y controles
    # ─────────────────────────────────────────────────────────────────────────
    def _round_rect(self, x1, y1, x2, y2, r, **kw):
        """Dibuja un rectángulo con esquinas redondeadas en el canvas AST."""
        r = max(2, min(r, (x2 - x1) // 2, (y2 - y1) // 2))
        pts = [
            x1 + r, y1,   x2 - r, y1,
            x2,     y1,   x2,     y1 + r,
            x2,     y2 - r, x2,   y2,
            x2 - r, y2,   x1 + r, y2,
            x1,     y2,   x1,     y2 - r,
            x1,     y1 + r, x1,   y1,
        ]
        return self.ast_canvas.create_polygon(pts, smooth=True, **kw)

    def _ast_layout_tree(self, nodes, edges):
        if not nodes:
            return {}
        children = {n["id"]: [] for n in nodes}
        parents  = {}
        for e in edges:
            children[e["from"]].append(e["to"])
            parents[e["to"]] = e["from"]
        all_children = set(parents.keys())
        roots   = [n["id"] for n in nodes if n["id"] not in all_children]
        root_id = roots[0] if roots else nodes[0]["id"]

        from collections import deque
        level_nodes = {}
        q       = deque([(root_id, 0)])
        visited = set()
        while q:
            nid, lvl = q.popleft()
            if nid in visited:
                continue
            visited.add(nid)
            level_nodes.setdefault(lvl, []).append(nid)
            for child in children.get(nid, []):
                if child not in visited:
                    q.append((child, lvl + 1))

        NODE_W = 155
        NODE_H = 54
        H_GAP  = 28
        V_GAP  = 82
        positions = {}
        for lvl, nids in sorted(level_nodes.items()):
            total_w = len(nids) * NODE_W + (len(nids) - 1) * H_GAP
            start_x = -total_w / 2
            for i, nid in enumerate(nids):
                x = start_x + i * (NODE_W + H_GAP) + NODE_W / 2
                y = lvl * (NODE_H + V_GAP) + NODE_H / 2
                positions[nid] = (x, y)
        return positions

    def _ast_draw_graph(self):
        if not self._ast_graph_data:
            return
        self.ast_canvas.delete("all")
        nodes = self._ast_graph_data["nodes"]
        edges = self._ast_graph_data["edges"]
        if not nodes:
            self.ast_canvas.create_text(
                400, 300, text="No hay nodos para mostrar",
                fill=COLORS["text_dim"], font=(_UI_FONT_FAMILY, 14))
            return

        positions = self._ast_layout_tree(nodes, edges)
        self._ast_positions = positions
        cw   = self.ast_canvas.winfo_width() or 800
        ch   = self.ast_canvas.winfo_height() or 600
        cx, cy = cw / 2, 70
        zoom   = self._ast_zoom
        NODE_W = int(155 * zoom)
        NODE_H = int(48  * zoom)
        RAD    = int(10  * zoom)
        font_size       = max(7,  int(9  * zoom))
        small_font_size = max(6,  int(7  * zoom))
        icon_font_size  = max(8,  int(11 * zoom))

        self._ast_canvas_nodes = {}
        self._ast_node_info    = {n["id"]: n for n in nodes}

        # Fondo: rejilla punteada sutil
        grid_step = int(36 * zoom)
        if grid_step > 5:
            bx0 = int(cx - 1200);  by0 = int(cy - 200)
            bx1 = int(cx + 1200);  by1 = int(cy + 2000)
            for gx in range(bx0, bx1, grid_step):
                for gy in range(by0, by1, grid_step):
                    self.ast_canvas.create_oval(
                        gx - 1, gy - 1, gx + 1, gy + 1,
                        fill="#1a1f28", outline="", tags="bg")

        # Aristas
        for e in edges:
            if e["from"] not in positions or e["to"] not in positions:
                continue
            x1, y1 = positions[e["from"]]
            x2, y2 = positions[e["to"]]
            sx  = cx + x1 * zoom
            sy  = cy + y1 * zoom + NODE_H // 2
            ex  = cx + x2 * zoom
            ey  = cy + y2 * zoom - NODE_H // 2
            my  = (sy + ey) / 2
            self.ast_canvas.create_line(
                sx, sy, sx, my, ex, my, ex, ey,
                smooth=True, fill="#1e2840",
                width=max(3, int(4 * zoom)), tags="edge")
            self.ast_canvas.create_line(
                sx, sy, sx, my, ex, my, ex, ey,
                smooth=True, fill="#2d4060",
                width=max(1, int(2 * zoom)), tags="edge")
            aw = max(4, int(6 * zoom))
            ah = max(6, int(9 * zoom))
            self.ast_canvas.create_polygon(
                ex, ey,
                ex - aw, ey - ah,
                ex + aw, ey - ah,
                fill="#4080c0", outline="", tags="edge")

        # Nodos
        for n in nodes:
            nid = n["id"]
            if nid not in positions:
                continue
            lx, ly = positions[nid]
            sx = cx + lx * zoom - NODE_W // 2
            sy = cy + ly * zoom - NODE_H // 2
            ex = sx + NODE_W
            ey = sy + NODE_H
            cat    = n.get("category", "default")
            colors = self.NODE_COLORS.get(cat, self.NODE_COLORS["default"])

            # Sombra
            for soff, salpha in [(5, "#050a10"), (3, "#080e18"), (1, "#0d1520")]:
                self._round_rect(sx + soff, sy + soff, ex + soff, ey + soff,
                                 RAD, fill=salpha, outline="", tags="shadow")

            # Borde glow
            self._round_rect(sx - 1, sy - 1, ex + 1, ey + 1, RAD + 1,
                             fill="", outline=colors["glow"],
                             width=1, tags=("node", nid))

            # Cuerpo
            self._round_rect(sx, sy, ex, ey, RAD,
                             fill=colors["fill"], outline=colors["outline"],
                             width=max(1, int(2 * zoom)), tags=("node", nid))

            # Franja superior de color
            bar_h = max(3, int(4 * zoom))
            self._round_rect(sx, sy, ex, sy + bar_h + RAD, RAD,
                             fill=colors["outline"], outline="", tags=("node", nid))
            self.ast_canvas.create_rectangle(
                sx, sy + bar_h, ex, sy + bar_h + RAD,
                fill=colors["outline"], outline="", tags=("node", nid))

            # Icono de categoría
            icon = self.CAT_ICONS.get(cat, "·")
            if zoom >= 0.5:
                self.ast_canvas.create_text(
                    sx + int(10 * zoom), sy + bar_h + int(4 * zoom),
                    text=icon, fill=colors["outline"],
                    font=(_UI_FONT_FAMILY, icon_font_size, "bold"),
                    anchor="nw", tags=("node_text", nid))

            # Etiqueta principal
            label = n["label"]
            if len(label) > 15:
                label = label[:13] + "…"
            label_y = sy + NODE_H // 2 + (bar_h // 2)
            if n.get("extra"):
                label_y -= int(6 * zoom)
            self.ast_canvas.create_text(
                sx + NODE_W // 2, label_y,
                text=label, fill=colors["text"],
                font=(_MONO_FONT_FAMILY, font_size, "bold"),
                tags=("node_text", nid))

            # Valor extra (línea secundaria)
            extra = n.get("extra", "")
            if extra and zoom >= 0.55:
                extra_disp = extra[:18] + "…" if len(extra) > 18 else extra
                self.ast_canvas.create_text(
                    sx + NODE_W // 2, label_y + int(13 * zoom),
                    text=extra_disp, fill=COLORS["text_dim"],
                    font=(_UI_FONT_FAMILY, small_font_size),
                    tags=("node_extra", nid))

            # Número de línea (esquina superior derecha)
            if n.get("line") and zoom >= 0.75:
                self.ast_canvas.create_text(
                    ex - int(5 * zoom), sy + bar_h + int(3 * zoom),
                    text=f":{n['line']}", fill=colors["outline"],
                    font=(_UI_FONT_FAMILY, max(6, int(7 * zoom))),
                    anchor="ne", tags=("line_num", nid))

            # Registrar items para hover
            for item in self.ast_canvas.find_withtag(nid):
                self._ast_canvas_nodes[item] = nid

        bbox = self.ast_canvas.bbox("all")
        if bbox:
            pad = 60
            self.ast_canvas.configure(
                scrollregion=(bbox[0] - pad, bbox[1] - pad,
                              bbox[2] + pad, bbox[3] + pad))

    def _ast_zoom_in(self):
        self._ast_zoom = min(3.0, self._ast_zoom * 1.2)
        self._ast_draw_graph()

    def _ast_zoom_out(self):
        self._ast_zoom = max(0.2, self._ast_zoom / 1.2)
        self._ast_draw_graph()

    def _ast_reset_view(self):
        self._ast_zoom = 1.0
        self.ast_canvas.xview_moveto(0)
        self.ast_canvas.yview_moveto(0)
        self._ast_draw_graph()

    def _ast_fit_view(self):
        if not self._ast_positions:
            return
        self.ast_canvas.update_idletasks()
        cw = self.ast_canvas.winfo_width() or 800
        ch = self.ast_canvas.winfo_height() or 600
        xs = [p[0] for p in self._ast_positions.values()]
        ys = [p[1] for p in self._ast_positions.values()]
        if not xs:
            return
        tree_w = (max(xs) - min(xs)) + 200
        tree_h = (max(ys) - min(ys)) + 100
        if tree_w == 0 or tree_h == 0:
            return
        zoom_x = cw / tree_w
        zoom_y = ch / tree_h
        self._ast_zoom = min(zoom_x, zoom_y, 2.0)
        self._ast_draw_graph()

    def _ast_pan_start_cb(self, event):
        self._ast_pan_start  = (event.x, event.y)
        self._ast_pan_scroll = (self.ast_canvas.xview()[0], self.ast_canvas.yview()[0])

    def _ast_pan_move_cb(self, event):
        if self._ast_pan_start is None:
            return
        dx = event.x - self._ast_pan_start[0]
        dy = event.y - self._ast_pan_start[1]
        bbox = self.ast_canvas.bbox("all")
        if not bbox:
            return
        total_w = bbox[2] - bbox[0] or 1
        total_h = bbox[3] - bbox[1] or 1
        self.ast_canvas.xview_moveto(self._ast_pan_scroll[0] - dx / total_w)
        self.ast_canvas.yview_moveto(self._ast_pan_scroll[1] - dy / total_h)

    def _ast_mouse_wheel(self, event):
        if event.delta > 0:
            self._ast_scroll_zoom(event, 1.1)
        else:
            self._ast_scroll_zoom(event, 0.9)

    def _ast_scroll_zoom(self, event, factor):
        self._ast_zoom = max(0.2, min(3.0, self._ast_zoom * factor))
        self._ast_draw_graph()

    def _ast_on_hover(self, event):
        items = self.ast_canvas.find_overlapping(
            event.x - 1, event.y - 1, event.x + 1, event.y + 1)
        for item in items:
            nid = self._ast_canvas_nodes.get(item)
            if nid and nid in self._ast_node_info:
                n = self._ast_node_info[nid]
                line_str  = f"  |  Línea {n['line']}" if n.get("line") else ""
                extra_str = f"  |  {n['extra']}"       if n.get("extra") else ""
                self.ast_info_var.set(
                    f"  🔹 {n['label']}{extra_str}  |  Categoría: {n['category']}{line_str}")
                return
        self.ast_info_var.set(
            "  ← Pasa el cursor sobre un nodo para ver detalles"
            " | Arrastra para mover | Rueda para zoom")

    # ─────────────────────────────────────────────────────────────────────────
    # Actualización de tablas: Tokens
    # ─────────────────────────────────────────────────────────────────────────
    def _update_tokens_tab(self, tokens, lexer):
        for item in self.token_tree.get_children():
            self.token_tree.delete(item)

        tag_colors = {
            "KEYWORD":          COLORS["kw"],
            "IDENTIFIER":       COLORS["identifier"],
            "INTEGER":          COLORS["num"],
            "FLOAT":            COLORS["num"],
            "STRING":           COLORS["str_color"],
            "BOOL":             COLORS["bool_color"],
            "NONE":             COLORS["text_dim"],
            "OPERATOR":         COLORS["accent3"],
            "COMPARISON":       COLORS["accent3"],
            "ASSIGNMENT":       COLORS["accent5"],
            "AUGMENTED_ASSIGN": COLORS["accent5"],
            "COMMENT":          COLORS["comment"],
            "ERROR":            COLORS["error"],
        }

        for ttype, color in tag_colors.items():
            self.token_tree.tag_configure(f"type_{ttype}", foreground=color)

        skip_types = {"NEWLINE", "EOF", "INDENT", "DEDENT"}
        count = 0
        for tok in tokens:
            if tok.type.name in skip_types:
                continue
            val = tok.value if len(tok.value) <= 30 else tok.value[:27] + "..."
            dt  = tok.data_type or ""
            stripe    = "even" if count % 2 == 0 else "odd"
            color_tag = f"type_{tok.type.name}"
            self.token_tree.insert("", "end",
                                   values=(tok.type.name, val, tok.line, tok.column, dt),
                                   tags=(stripe, color_tag))
            count += 1

        summary  = lexer.get_summary()
        kw_count = summary.get("KEYWORD", 0)
        id_count = summary.get("IDENTIFIER", 0)
        self.token_stats_var.set(
            f"  Total tokens: {count}  |  Keywords: {kw_count}  |  "
            f"Identificadores: {id_count}  |  Errores léxicos: {len(lexer.errors)}"
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Actualización de tablas: Tipos de Datos
    # ─────────────────────────────────────────────────────────────────────────
    def _update_types_tab(self, data_types, tokens):
        for item in self.types_count_tree.get_children():
            self.types_count_tree.delete(item)
        for item in self.types_vals_tree.get_children():
            self.types_vals_tree.delete(item)

        type_icons = {
            "int": "🔢", "float": "🔣", "str": "📝",
            "bool": "✅", "NoneType": "∅"
        }

        if not data_types:
            self.types_count_tree.insert("", "end",
                values=("—", "Sin literales detectados", "0", ""), tags=("even",))
            return

        total     = sum(data_types.values()) or 1
        max_count = max(data_types.values()) or 1

        for i, (dtype, count) in enumerate(sorted(data_types.items())):
            icon      = type_icons.get(dtype, "◆")
            bar_n     = int((count / max_count) * 20)
            bar       = "█" * bar_n + "░" * (20 - bar_n)
            pct       = f"{count / total * 100:.1f}%  {bar}"
            stripe    = "even" if i % 2 == 0 else "odd"
            self.types_count_tree.insert("", "end",
                values=(icon, dtype, count, pct), tags=(stripe,))

        by_type = {}
        for tok in tokens:
            if tok.data_type:
                by_type.setdefault(tok.data_type, []).append(tok.value)

        for i, (dtype, values) in enumerate(sorted(by_type.items())):
            icon        = type_icons.get(dtype, "◆")
            unique_vals = list(dict.fromkeys(values))[:10]
            vals_str    = ",  ".join(str(v) for v in unique_vals)
            if len(values) > 10:
                vals_str += f"  … (+{len(values) - 10} más)"
            stripe = "even" if i % 2 == 0 else "odd"
            self.types_vals_tree.insert("", "end",
                values=(icon, dtype, vals_str), tags=(stripe,))

    # ─────────────────────────────────────────────────────────────────────────
    # Actualización de tablas: AST
    # ─────────────────────────────────────────────────────────────────────────
    def _update_ast_tab(self, ast_report):
        self.ast_canvas.delete("all")
        self._ast_canvas_nodes = {}
        self._ast_node_info    = {}
        self._ast_positions    = {}

        if not ast_report["success"]:
            err      = ast_report.get("error", {})
            msg      = err.get("message", "Error desconocido")
            line_info = (f"\nLinea {err['lineno']}, Col {err.get('offset', '?')}"
                         if err.get("lineno") else "")
            self.ast_canvas.create_text(400, 180,
                text=f"Error al generar el AST\n\n{msg}{line_info}",
                fill=COLORS["error"],
                font=(_UI_FONT_FAMILY, 12), justify="center", width=600)
            self.ast_info_var.set("  Error al analizar el codigo")
            return

        graph = ast_report.get("graph", {})
        if not graph or not graph.get("nodes"):
            self.ast_canvas.create_text(400, 200, text="Sin nodos para mostrar",
                fill=COLORS["text_dim"], font=(_UI_FONT_FAMILY, 13))
            return

        self._ast_graph_data = graph
        self._ast_zoom       = 1.0
        summary = ast_report.get("summary", {})
        total   = (summary.get("total_nodos", len(graph["nodes"]))
                   if summary else len(graph["nodes"]))
        funcs   = len(summary.get("funciones", [])) if summary else 0
        classes = len(summary.get("clases",    [])) if summary else 0
        self.ast_info_var.set(
            f"  Nodos: {total}  |  Funciones: {funcs}  |  Clases: {classes}"
            f"  ·  Arrastra para mover · Rueda para zoom")
        self.ast_canvas.update_idletasks()
        self._ast_draw_graph()

    # ─────────────────────────────────────────────────────────────────────────
    # Actualización: Parser
    # ─────────────────────────────────────────────────────────────────────────
    def _update_parser_tab(self, parse_result, code):
        stats = parse_result.stats or {}

        # Banner de estado
        if parse_result.success:
            n_funcs = len(stats.get("funciones",     []))
            n_cls   = len(stats.get("clases",        []))
            n_imp   = len(stats.get("importaciones", []))
            details = f"  ·  {n_funcs} func.  {n_cls} clases  {n_imp} imports"
            self.parser_status_var.set(f"  ✅  SINTAXIS VÁLIDA{details}")
            self.parser_status_label.config(bg="#0f1f0f", fg=COLORS["success"])
            self._parser_banner_line.config(bg=COLORS["success"])
        else:
            errs = len(parse_result.errors)
            self.parser_status_var.set(
                f"  ❌  {errs} ERROR(ES) DE SINTAXIS  —  revisa el área de advertencias")
            self.parser_status_label.config(bg="#1f0f0f", fg=COLORS["error"])
            self._parser_banner_line.config(bg=COLORS["error"])

        # Tarjetas
        for _, _, _, key in self._parser_card_specs:
            if key in self._parser_card_vars:
                self._parser_card_vars[key].set(str(stats.get(key, 0)))

        # Tabla: Funciones
        for item in self.parser_func_tree.get_children():
            self.parser_func_tree.delete(item)

        for i, f in enumerate(stats.get("funciones", [])):
            args_str  = ", ".join(
                a["nombre"] + (f":{a['anotacion']}" if a.get("anotacion") else "")
                for a in f["args"])
            ret_str   = f["retorno"] if f.get("retorno") else "—"
            async_str = "⚡ sí" if f["es_async"] else "no"
            decs_str  = "@" + ", @".join(f["decoradores"]) if f.get("decoradores") else "—"
            stripe    = "even" if i % 2 == 0 else "odd"
            extra_tag = "async_row" if f["es_async"] else ("decorated" if f.get("decoradores") else "")
            tags      = (stripe, extra_tag) if extra_tag else (stripe,)
            self.parser_func_tree.insert("", "end",
                values=(f["nombre"], args_str or "—", ret_str, async_str,
                        f["linea"], decs_str),
                tags=tags)

        if not stats.get("funciones"):
            self.parser_func_tree.insert("", "end",
                values=("—", "Sin funciones detectadas", "", "", "", ""),
                tags=("even",))

        # Tabla: Clases
        for item in self.parser_cls_tree.get_children():
            self.parser_cls_tree.delete(item)

        for i, c in enumerate(stats.get("clases", [])):
            bases_str   = ", ".join(c["bases"])   if c["bases"]   else "—"
            methods_str = ", ".join(c["metodos"]) if c["metodos"] else "—"
            stripe = "even" if i % 2 == 0 else "odd"
            self.parser_cls_tree.insert("", "end",
                values=(c["nombre"], bases_str, methods_str, c["linea"]),
                tags=(stripe,))

        if not stats.get("clases"):
            self.parser_cls_tree.insert("", "end",
                values=("—", "Sin clases detectadas", "", ""), tags=("even",))

        # Tabla: Importaciones
        for item in self.parser_imp_tree.get_children():
            self.parser_imp_tree.delete(item)

        idx = 0
        for imp in stats.get("importaciones", []):
            if imp["tipo"] == "import":
                for mod in imp["modulos"]:
                    al     = f" as {mod['alias']}" if mod.get("alias") else ""
                    stripe = "even" if idx % 2 == 0 else "odd"
                    self.parser_imp_tree.insert("", "end",
                        values=("import", mod["nombre"] + al, "—", imp.get("linea", "?")),
                        tags=(stripe, "plain_import"))
                    idx += 1
            else:
                nombres = [
                    n["nombre"] + (f" as {n['alias']}" if n.get("alias") else "")
                    for n in imp["nombres"]
                ]
                stripe = "even" if idx % 2 == 0 else "odd"
                self.parser_imp_tree.insert("", "end",
                    values=("from … import", imp["modulo"],
                            ", ".join(nombres), imp.get("linea", "?")),
                    tags=(stripe, "from_import"))
                idx += 1

        if not stats.get("importaciones"):
            self.parser_imp_tree.insert("", "end",
                values=("—", "Sin importaciones", "", ""), tags=("even",))

        # Errores y advertencias PEP 8
        t = self.parser_text
        t.config(state="normal")
        t.delete("1.0", "end")

        if not parse_result.success:
            t.insert("end", "── ERRORES DE SINTAXIS ──────────────────────\n", "header")
            for err in parse_result.errors:
                t.insert("end", f"  ✗  Línea {err.line}, Col {err.column}:  ", "error")
                t.insert("end", f"{err.message}\n")
                if err.text:
                    t.insert("end", f"      ▸ {err.text}\n", "info")
            t.insert("end", "\n")
        else:
            t.insert("end", "  ✅  Sin errores de sintaxis.\n", "ok")

        if parse_result.warnings:
            t.insert("end",
                     f"\n── ADVERTENCIAS PEP 8  ({len(parse_result.warnings)}) ───────────\n",
                     "header")
            for w in parse_result.warnings:
                t.insert("end", f"  ⚠  {w}\n", "warning")
        elif parse_result.success:
            t.insert("end", "  ✅  Sin advertencias de estilo.\n", "ok")

        t.config(state="disabled")

    # ─────────────────────────────────────────────────────────────────────────
    # Actualización de tablas: Semántico
    # ─────────────────────────────────────────────────────────────────────────
    def _update_semantic_tab(self, sem_result):
        for item in self.sym_tree.get_children():
            self.sym_tree.delete(item)

        all_syms = sem_result.symbol_table.all_symbols_flat()
        for i, sym in enumerate(sorted(all_syms, key=lambda s: s.line)):
            used_str = "✔" if sym.used else "✖"
            stripe   = "even" if i % 2 == 0 else "odd"
            if sym.used:
                tags = (stripe,)
            else:
                tags = (f"{stripe}_unused",)
            self.sym_tree.insert("", "end", values=(
                sym.name, sym.symbol_type, sym.inferred_type,
                sym.scope, sym.line, used_str
            ), tags=tags)

        t = self.semantic_text
        t.config(state="normal")
        t.delete("1.0", "end")

        errors   = sem_result.errors
        warnings = sem_result.warnings

        if not errors and not warnings:
            t.insert("end", "✅  Sin errores ni advertencias semánticas.\n", "ok")
        else:
            if errors:
                t.insert("end", f"─── Errores ({len(errors)}) ───────────────\n", "header")
                for e in errors:
                    t.insert("end", f"  ✗ Línea {e.line}: ", "error")
                    t.insert("end", f"{e.message}\n")
            if warnings:
                t.insert("end", f"\n─── Advertencias ({len(warnings)}) ────────\n", "header")
                for w in warnings:
                    t.insert("end", f"  ⚠ Línea {w.line}: ", "warning")
                    t.insert("end", f"{w.message}\n")

        t.config(state="disabled")

    # ─────────────────────────────────────────────────────────────────────────
    # Análisis, ejecución y eventos
    # ─────────────────────────────────────────────────────────────────────────
    def _bind_events(self):
        self.code_editor.bind("<KeyRelease>", self._on_key_release)
        self.code_editor.bind("<ButtonRelease-1>", self._update_line_numbers)
        self._after_id = None
        self._pulse_id = None
        self._update_line_numbers()

    def _toggle_live_mode(self):
        self._live_mode.set(not self._live_mode.get())
        if self._live_mode.get():
            self._live_btn.config(
                text="● LIVE", bg="#1a3a1a", fg="#3fb950",
                activebackground="#1a3a1a", activeforeground="#56d364")
            self._activity_var.set("")
        else:
            self._live_btn.config(
                text="○ LIVE", bg=COLORS["bg_light"], fg=COLORS["text_dim"],
                activebackground=COLORS["bg_light"], activeforeground=COLORS["text_dim"])
            self._activity_var.set("")
            if self._after_id:
                self.root.after_cancel(self._after_id)
                self._after_id = None

    def _pulse_activity(self,
                        frames=("⠋","⠙","⠹","⠸","⠼","⠴","⠦","⠧","⠇","⠏"),
                        idx=0):
        if not self._live_mode.get():
            self._activity_var.set("")
            return
        self._activity_var.set(f"{frames[idx % len(frames)]} analizando…")
        self._pulse_id = self.root.after(
            80, lambda: self._pulse_activity(frames, idx + 1))

    def _stop_pulse(self):
        if self._pulse_id:
            self.root.after_cancel(self._pulse_id)
            self._pulse_id = None
        self._activity_var.set("")

    def _on_key_release(self, event=None):
        self._update_line_numbers()
        self._highlight_syntax()

        if not self._live_mode.get():
            return

        if self._after_id:
            self.root.after_cancel(self._after_id)
        if self._pulse_id:
            self.root.after_cancel(self._pulse_id)

        self._pulse_activity()
        self._after_id = self.root.after(600, self._run_live_analysis)

    def _run_live_analysis(self):
        self._stop_pulse()
        self.run_analysis()

    def _update_line_numbers(self, event=None):
        code  = self.code_editor.get("1.0", "end-1c")
        lines = code.count('\n') + 1
        self.line_numbers.config(state="normal")
        self.line_numbers.delete("1.0", "end")
        for i in range(1, lines + 1):
            self.line_numbers.insert("end", f"{i}\n")
        self.line_numbers.config(state="disabled")

    def _highlight_syntax(self):
        import re
        editor = self.code_editor
        for tag in ["kw", "str_tag", "num_tag", "comment_tag", "bool_tag"]:
            editor.tag_remove(tag, "1.0", "end")
        editor.tag_configure("kw",          foreground=COLORS["kw"])
        editor.tag_configure("str_tag",     foreground=COLORS["str_color"])
        editor.tag_configure("num_tag",     foreground=COLORS["num"])
        editor.tag_configure("comment_tag", foreground=COLORS["comment"])
        editor.tag_configure("bool_tag",    foreground=COLORS["bool_color"])

        editor.tag_configure("err_syntax",
                             background="#3d1515", underline=True,
                             foreground="#f85149")
        editor.tag_configure("err_semantic",
                             background="#2d1f00", underline=True,
                             foreground="#ffa657")
        editor.tag_configure("err_warning",
                             background="#252010", underline=True,
                             foreground="#e3b341")
        for etag in ("err_syntax", "err_semantic", "err_warning"):
            editor.tag_raise(etag)

        code  = editor.get("1.0", "end-1c")
        lines = code.split('\n')
        for line_idx, line in enumerate(lines, 1):
            m = re.search(r'#.*$', line)
            if m:
                editor.tag_add("comment_tag",
                               f"{line_idx}.{m.start()}", f"{line_idx}.{m.end()}")
            for m in re.finditer(
                    r'(""".*?"""|\'\'\'.*?\'\'\'|"[^"\\]*"|\'[^\'\\]*\')', line):
                editor.tag_add("str_tag",
                               f"{line_idx}.{m.start()}", f"{line_idx}.{m.end()}")
            for m in re.finditer(r'\b\d+\.?\d*\b', line):
                editor.tag_add("num_tag",
                               f"{line_idx}.{m.start()}", f"{line_idx}.{m.end()}")
            for m in re.finditer(r'\b([a-zA-Z_]\w*)\b', line):
                word  = m.group(1)
                start = f"{line_idx}.{m.start()}"
                end   = f"{line_idx}.{m.end()}"
                if word in ("True", "False", "None"):
                    editor.tag_add("bool_tag", start, end)
                elif word in KEYWORDS_SET:
                    editor.tag_add("kw", start, end)

    # ─────────────────────────────────────────────────────────────────────────
    # Marcas de error/warning estilo VS Code en el editor
    # ─────────────────────────────────────────────────────────────────────────
    def _clear_error_marks(self):
        for tag in ("err_syntax", "err_semantic", "err_warning"):
            self.code_editor.tag_remove(tag, "1.0", "end")
        self._error_map = {}

    def _mark_range(self, tag, line, col, code_lines):
        import re as _re
        if line < 1 or line > len(code_lines):
            return
        line_text = code_lines[line - 1]
        col = max(0, col)

        if col >= len(line_text):
            stripped = len(line_text) - len(line_text.lstrip())
            end_pos  = len(line_text.rstrip())
            start_c  = stripped
            end_c    = max(end_pos, stripped + 1)
        else:
            rest  = line_text[col:]
            m     = _re.match(r'\w+', rest)
            span  = len(m.group(0)) if m else 1
            start_c = col
            end_c   = col + span

        self.code_editor.tag_add(tag, f"{line}.{start_c}", f"{line}.{end_c}")

    def _apply_error_marks(self, parse_result, sem_result):
        self._clear_error_marks()
        editor     = self.code_editor
        code_lines = editor.get("1.0", "end-1c").split('\n')

        for err in parse_result.errors:
            line = err.line or 1
            col  = max(0, (err.column or 1) - 1)
            self._mark_range("err_syntax", line, col, code_lines)
            self._error_map[(line, col)] = f"❌ Sintaxis: {err.message}"

        if sem_result:
            for err in sem_result.errors:
                line = err.line or 1
                col  = err.column or 0
                tag  = "err_warning" if err.is_warning else "err_semantic"
                self._mark_range(tag, line, col, code_lines)
                prefix = "⚠" if err.is_warning else "⚠ Semántico"
                self._error_map[(line, col)] = f"{prefix}: {err.message}"

        for etag in ("err_syntax", "err_semantic", "err_warning"):
            editor.tag_raise(etag)

        if not getattr(self, '_tooltip_bound', False):
            editor.bind("<Motion>", self._on_editor_motion)
            self._tooltip_bound = True

    # ── Tooltip de error ──────────────────────────────────────────────────────
    def _on_editor_motion(self, event):
        editor = self.code_editor
        try:
            idx = editor.index(f"@{event.x},{event.y}")
        except Exception:
            return

        active_tags = editor.tag_names(idx)
        msg = None
        for tag in ("err_syntax", "err_semantic", "err_warning"):
            if tag in active_tags:
                line = int(idx.split('.')[0])
                col  = int(idx.split('.')[1])
                msg  = self._error_map.get((line, col))
                if msg is None:
                    for (l, c), m in self._error_map.items():
                        if l == line:
                            msg = m
                            break
                break

        if msg:
            self._show_tooltip(event.x_root, event.y_root, msg)
        else:
            self._hide_tooltip()

    def _show_tooltip(self, x, y, text):
        if not hasattr(self, '_tooltip_win'):
            self._tooltip_win = None

        if self._tooltip_win:
            try:
                lbl = self._tooltip_win.winfo_children()[0]
                if lbl.cget("text") == text:
                    return
                lbl.config(text=text)
                self._tooltip_win.geometry(f"+{x + 14}+{y + 10}")
                return
            except Exception:
                pass

        tw = tk.Toplevel(self.root)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x + 14}+{y + 10}")
        tw.attributes("-topmost", True)

        lbl = tk.Label(
            tw, text=text,
            bg="#1e1e1e", fg="#f85149",
            font=(_UI_FONT_FAMILY, 9),
            relief="flat", bd=0,
            padx=10, pady=5,
            wraplength=400, justify="left"
        )
        lbl.pack()
        tw.configure(bg="#333")
        tw.attributes("-alpha", 0.97)
        self._tooltip_win = tw

    def _hide_tooltip(self):
        if hasattr(self, '_tooltip_win') and self._tooltip_win:
            try:
                self._tooltip_win.destroy()
            except Exception:
                pass
            self._tooltip_win = None

    # ─────────────────────────────────────────────────────────────────────────
    # Análisis principal
    # ─────────────────────────────────────────────────────────────────────────
    def run_analysis(self, event=None):
        code = self.code_editor.get("1.0", "end-1c").strip()
        if not code:
            self.status_var.set("⚠ No hay código para analizar")
            self._clear_error_marks()
            return

        self.status_var.set("⏳ Analizando...")
        self.root.update_idletasks()

        try:
            lexer      = Lexer(code)
            tokens     = lexer.tokenize()
            data_types = lexer.get_data_types()

            parser       = Parser()
            parse_result = parser.parse(code)

            ast_report = generate_ast_report(code)
            sem_result = run_semantic_analysis(code) if parse_result.success else None

            self._apply_error_marks(parse_result, sem_result)
            self._update_tokens_tab(tokens, lexer)
            self._update_types_tab(data_types, tokens)
            self._update_ast_tab(ast_report)
            self._update_parser_tab(parse_result, code)
            if sem_result is not None:
                self._update_semantic_tab(sem_result)

            ic_result = generate_intermediate_code(code) if parse_result.success else None
            if ic_result is not None:
                self._update_intermediate_tab(ic_result)
                opt_result = optimize_intermediate_code(ic_result)
                self._update_optimization_tab(opt_result)
                cg_result = generate_object_code(opt_result)
                self._update_object_code_tab(cg_result)

            if parse_result.success:
                sem_errors = len([e for e in sem_result.errors
                                  if not e.is_warning]) if sem_result else 0
                sem_warns  = len([e for e in sem_result.errors
                                  if e.is_warning])     if sem_result else 0
                if sem_errors:
                    self.status_var.set(
                        f"⚠ Sintaxis OK · {sem_errors} error(es) semántico(s)")
                    self.status_label.config(fg=COLORS["warning"])
                elif sem_warns:
                    self.status_var.set(
                        f"✅ Análisis OK · {sem_warns} advertencia(s)")
                    self.status_label.config(fg=COLORS["success"])
                else:
                    self.status_var.set("✅ Análisis completado — Sin errores")
                    self.status_label.config(fg=COLORS["success"])
            else:
                errs = len(parse_result.errors)
                self.status_var.set(f"❌ {errs} error(es) de sintaxis encontrado(s)")
                self.status_label.config(fg=COLORS["error"])

        except Exception as e:
            self.status_var.set(f"❌ Error interno: {e}")
            self.status_label.config(fg=COLORS["error"])

    # ─────────────────────────────────────────────────────────────────────────
    # Consola: escritura y entrada
    # ─────────────────────────────────────────────────────────────────────────
    def _console_write(self, text, tag=None):
        def _write():
            self.console_text.config(state="normal")
            if tag:
                self.console_text.insert("end", text, tag)
            else:
                self.console_text.insert("end", text)
            self.console_text.see("end")
            self.console_text.config(state="disabled")
        self.root.after(0, _write)

    def _ask_input(self, prompt=""):
        import queue as queue_mod
        self._console_input_queue = queue_mod.Queue()

        def _enable_input():
            self.console_text.config(state="normal")
            if prompt:
                self.console_text.insert("end", str(prompt), "input_prompt")
            self.console_text.see("end")
            self.console_text.config(state="disabled")
            self._console_prompt_label.config(text="›")
            self._console_input_var.set("")
            self._console_input_entry.config(state="normal")
            self._console_input_entry.focus_set()

        self.root.after(0, _enable_input)
        value = self._console_input_queue.get()

        def _disable_input():
            self._console_input_entry.config(state="disabled")
            self._console_input_var.set("")

        self.root.after(0, _disable_input)
        if value is None:
            raise KeyboardInterrupt("Ejecución cancelada por el usuario.")
        return value

    def _on_console_input_submit(self, event=None):
        if self._console_input_queue is None:
            return
        value = self._console_input_var.get()
        self.console_text.config(state="normal")
        self.console_text.insert("end", value + "\n", "input_value")
        self.console_text.see("end")
        self.console_text.config(state="disabled")
        self._console_input_entry.config(state="disabled")
        self._console_input_var.set("")
        self._console_input_queue.put(value)
        self._console_input_queue = None

    # ─────────────────────────────────────────────────────────────────────────
    # Ejecución de código
    # ─────────────────────────────────────────────────────────────────────────
    def run_code(self):
        code = self.code_editor.get("1.0", "end-1c").strip()
        if not code:
            return

        self.console_text.config(state="normal")
        self.console_text.delete("1.0", "end")
        self.console_text.insert("end", "─" * 42 + "\n", "info")
        self.console_text.config(state="disabled")
        self._console_input_entry.config(state="disabled")
        self._console_input_queue = None
        self.root.update_idletasks()

        def _execute():
            error_msg = None
            success   = False

            try:
                import sys as _sys, os as _os
                _sys.path.insert(0, _os.path.dirname(_os.path.abspath(__file__)))
                from type_inference import (
                    infer_type, smart_input,
                    infer_assignment, infer_expression,
                    describe_inferred_type,
                )
                _type_inference_ok = True
            except Exception:
                _type_inference_ok = False
                def infer_type(v):               return v
                def infer_assignment(v):          return v
                def infer_expression(a, op, b):   return None
                def describe_inferred_type(v):    return type(v).__name__

            def custom_input(prompt=""):
                raw = self._ask_input(prompt)
                return infer_type(raw)

            builtins_dict = (__builtins__ if isinstance(__builtins__, dict)
                             else vars(__builtins__))
            exec_globals = {
                "__builtins__":          {**builtins_dict, "input": custom_input},
                "infer_type":             infer_type,
                "smart_input":            smart_input if _type_inference_ok else custom_input,
                "infer_assignment":       infer_assignment,
                "infer_expression":       infer_expression,
                "describe_inferred_type": describe_inferred_type,
            }

            class ConsolePrinter(io.TextIOBase):
                def write(self_inner, text):
                    if text:
                        self._console_write(text)
                    return len(text)
                def flush(self_inner):
                    pass

            try:
                printer = ConsolePrinter()
                with contextlib.redirect_stdout(printer):
                    with contextlib.redirect_stderr(printer):
                        exec(compile(code, '<pyanalyzer>', 'exec'), exec_globals)
                success = True
            except KeyboardInterrupt as e:
                error_msg = f"⚠ {e}"
            except SyntaxError as e:
                error_msg = f"SyntaxError: {e.msg} (línea {e.lineno})"
            except Exception as e:
                error_msg = f"{type(e).__name__}: {e}"

            def finish_console():
                self._console_input_entry.config(state="disabled")
                self._console_input_var.set("")
                if self._console_input_queue is not None:
                    self._console_input_queue.put(None)
                    self._console_input_queue = None
                self.console_text.config(state="normal")
                if error_msg:
                    self.console_text.insert("end", f"\n❌ {error_msg}\n", "error")
                elif success:
                    self.console_text.insert("end", "\n✅ Ejecución completada.\n", "info")
                self.console_text.see("end")
                self.console_text.config(state="disabled")

            self.root.after(0, finish_console)

        threading.Thread(target=_execute, daemon=True).start()

    # ─────────────────────────────────────────────────────────────────────────
    # Acciones: limpiar, abrir, guardar
    # ─────────────────────────────────────────────────────────────────────────
    def clear_all(self):
        self.code_editor.delete("1.0", "end")

        for tree in (self.token_tree, self.types_count_tree, self.types_vals_tree,
                     self.parser_func_tree, self.parser_cls_tree,
                     self.parser_imp_tree, self.sym_tree):
            for item in tree.get_children():
                tree.delete(item)

        for key, var in self._parser_card_vars.items():
            var.set("—")

        for item in self.ic_tree.get_children():
            self.ic_tree.delete(item)

        self.opt_text.config(state="normal")
        self.opt_text.delete("1.0", "end")
        self.opt_text.config(state="disabled")
        self.opt_stats_var.set('')
        self.obj_stats_var.set('')

        for widget in [self.parser_text, self.console_text, self.semantic_text, self.ic_text, self.opt_text, self.obj_text]:
            widget.config(state="normal")
            widget.delete("1.0", "end")
            widget.config(state="disabled")

        self.ast_canvas.delete("all")
        self._ast_graph_data   = None
        self._ast_positions    = {}
        self._ast_canvas_nodes = {}
        self._ast_node_info    = {}
        self.ast_info_var.set(
            "  ← Pasa el cursor sobre un nodo para ver detalles"
            " | Arrastra para mover | Rueda para zoom")
        self.parser_status_var.set("")
        self.status_var.set("Limpiado")
        self.status_label.config(fg=COLORS["text_dim"])
        self._update_line_numbers()

    def open_file(self):
        path = filedialog.askopenfilename(
            title="Abrir archivo Python",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        if path:
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                self.code_editor.delete("1.0", "end")
                self.code_editor.insert("1.0", content)
                self._update_line_numbers()
                self._highlight_syntax()
                self.run_analysis()
                self.status_var.set(f"📂 Abierto: {os.path.basename(path)}")
                self.status_label.config(fg=COLORS["accent"])
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo abrir el archivo:\n{e}")

    def save_file(self):
        path = filedialog.asksaveasfilename(
            title="Guardar archivo Python",
            defaultextension=".py",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        if path:
            try:
                code = self.code_editor.get("1.0", "end-1c")
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(code)
                self.status_var.set(f"💾 Guardado: {os.path.basename(path)}")
                self.status_label.config(fg=COLORS["success"])
            except Exception as e:
                messagebox.showerror("Error", f"No se pudo guardar:\n{e}")

    def _load_example(self):
        example = '''# Ejemplo de código Python para analizar
def calcular_factorial(n: int) -> int:
    """Calcula el factorial de un número entero."""
    if n < 0:
        raise ValueError("No existe factorial de negativos")
    if n == 0 or n == 1:
        return 1
    return n * calcular_factorial(n - 1)


class Calculadora:
    """Calculadora básica con historial."""

    def __init__(self):
        self.historial = []
        self.precision = 2

    def sumar(self, a: float, b: float) -> float:
        resultado = a + b
        self.historial.append(f"{a} + {b} = {resultado}")
        return round(resultado, self.precision)

    def mostrar_historial(self):
        for op in self.historial:
            print(f"  → {op}")


# Uso del código
calc = Calculadora()
resultado = calc.sumar(3.14, 2.86)
print(f"Resultado: {resultado}")

numeros = [1, 2, 3, 4, 5]
factoriales = [calcular_factorial(n) for n in numeros]
print(f"Factoriales: {factoriales}")

datos = {"nombre": "Python", "version": 3.12, "activo": True}
'''
        self.code_editor.insert("1.0", example)
        self._update_line_numbers()
        self._highlight_syntax()
        self.root.after(300, self.run_analysis)


# ─── PUNTO DE ENTRADA ─────────────────────────────────────────────────────────

def launch_ui():
    root = tk.Tk()
    app = AnalyzerApp(root)
    try:
        root.iconbitmap("assets/icon.ico")
    except Exception:
        pass
    root.mainloop()


if __name__ == "__main__":
    launch_ui()
