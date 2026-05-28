"""
lexer.py - Analizador léxico para código Python
Tokeniza el código fuente identificando todos los elementos del lenguaje.

Integra inferencia de tipos para tokens STRING que contienen valores numéricos
o booleanos (ej: "42", "true"), añadiendo un campo `inferred_content_type`
al token para uso en el analizador semántico y la UI.
"""

import re
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Optional

# Importación diferida del módulo de inferencia para evitar dependencias circulares
def _infer(value: str):
    try:
        from type_inference import infer_type
        return infer_type(value)
    except Exception:
        return value


class TokenType(Enum):
    # Palabras clave
    KEYWORD = auto()
    # Identificadores
    IDENTIFIER = auto()
    # Literales
    INTEGER = auto()
    FLOAT = auto()
    STRING = auto()
    BOOL = auto()
    NONE = auto()
    # Operadores
    OPERATOR = auto()
    COMPARISON = auto()
    LOGICAL = auto()
    ASSIGNMENT = auto()
    AUGMENTED_ASSIGN = auto()
    # Delimitadores
    LPAREN = auto()
    RPAREN = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    LBRACE = auto()
    RBRACE = auto()
    COMMA = auto()
    COLON = auto()
    SEMICOLON = auto()
    DOT = auto()
    ARROW = auto()
    # Estructura
    NEWLINE = auto()
    INDENT = auto()
    DEDENT = auto()
    # Especiales
    COMMENT = auto()
    EOF = auto()
    ERROR = auto()


KEYWORDS = {
    'False', 'None', 'True', 'and', 'as', 'assert', 'async', 'await',
    'break', 'class', 'continue', 'def', 'del', 'elif', 'else', 'except',
    'finally', 'for', 'from', 'global', 'if', 'import', 'in', 'is',
    'lambda', 'nonlocal', 'not', 'or', 'pass', 'raise', 'return',
    'try', 'while', 'with', 'yield'
}

BOOL_LITERALS = {'True', 'False'}
NONE_LITERAL = {'None'}


@dataclass
class Token:
    type: TokenType
    value: str
    line: int
    column: int
    data_type: Optional[str] = None

    def __repr__(self):
        dt = f", dtype={self.data_type}" if self.data_type else ""
        return f"Token({self.type.name}, {self.value!r}, L{self.line}:C{self.column}{dt})"

    def to_dict(self):
        return {
            "type": self.type.name,
            "value": self.value,
            "line": self.line,
            "column": self.column,
            "data_type": self.data_type
        }


class LexerError(Exception):
    def __init__(self, message, line, column):
        super().__init__(message)
        self.line = line
        self.column = column


class Lexer:
    def __init__(self, source_code: str):
        self.source = source_code
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []
        self.errors: List[LexerError] = []

    def current_char(self) -> Optional[str]:
        if self.pos < len(self.source):
            return self.source[self.pos]
        return None

    def peek(self, offset=1) -> Optional[str]:
        idx = self.pos + offset
        if idx < len(self.source):
            return self.source[idx]
        return None

    def advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def skip_whitespace(self):
        while self.current_char() in (' ', '\t', '\r'):
            self.advance()

    def read_string(self, quote_char: str) -> Token:
        start_col = self.column
        start_line = self.line
        value = quote_char
        self.advance()  # skip opening quote

        # Triple quote?
        triple = False
        if self.current_char() == quote_char and self.peek() == quote_char:
            triple = True
            value += quote_char + quote_char
            self.advance()
            self.advance()

        while self.current_char() is not None:
            ch = self.current_char()
            if ch == '\\':
                value += ch
                self.advance()
                if self.current_char():
                    value += self.advance()
            elif triple:
                if ch == quote_char and self.peek() == quote_char and self.peek(2) == quote_char:
                    value += ch + quote_char + quote_char
                    self.advance(); self.advance(); self.advance()
                    break
                else:
                    value += self.advance()
            else:
                if ch == quote_char:
                    value += self.advance()
                    break
                elif ch == '\n':
                    self.errors.append(LexerError("Cadena de texto no cerrada", start_line, start_col))
                    break
                else:
                    value += self.advance()

        return Token(TokenType.STRING, value, start_line, start_col, data_type='str')

    def read_number(self) -> Token:
        start_col = self.column
        start_line = self.line
        value = ''
        is_float = False

        while self.current_char() and (self.current_char().isdigit() or self.current_char() == '_'):
            value += self.advance()

        if self.current_char() == '.' and self.peek() and self.peek().isdigit():
            is_float = True
            value += self.advance()
            while self.current_char() and (self.current_char().isdigit() or self.current_char() == '_'):
                value += self.advance()

        if self.current_char() in ('e', 'E'):
            is_float = True
            value += self.advance()
            if self.current_char() in ('+', '-'):
                value += self.advance()
            while self.current_char() and self.current_char().isdigit():
                value += self.advance()

        token_type = TokenType.FLOAT if is_float else TokenType.INTEGER
        data_type = 'float' if is_float else 'int'
        return Token(token_type, value, start_line, start_col, data_type=data_type)

    def read_identifier(self) -> Token:
        start_col = self.column
        start_line = self.line
        value = ''

        while self.current_char() and (self.current_char().isalnum() or self.current_char() == '_'):
            value += self.advance()

        if value in BOOL_LITERALS:
            return Token(TokenType.BOOL, value, start_line, start_col, data_type='bool')
        elif value in NONE_LITERAL:
            return Token(TokenType.NONE, value, start_line, start_col, data_type='NoneType')
        elif value in KEYWORDS:
            return Token(TokenType.KEYWORD, value, start_line, start_col)
        else:
            return Token(TokenType.IDENTIFIER, value, start_line, start_col)

    def read_comment(self) -> Token:
        start_col = self.column
        start_line = self.line
        value = ''
        while self.current_char() and self.current_char() != '\n':
            value += self.advance()
        return Token(TokenType.COMMENT, value, start_line, start_col)

    def tokenize(self) -> List[Token]:
        self.tokens = []
        self.errors = []

        while self.current_char() is not None:
            ch = self.current_char()

            # Saltos de línea
            if ch == '\n':
                self.tokens.append(Token(TokenType.NEWLINE, '\\n', self.line, self.column))
                self.advance()
                continue

            # Espacios en blanco
            if ch in (' ', '\t', '\r'):
                self.skip_whitespace()
                continue

            # Comentarios
            if ch == '#':
                tok = self.read_comment()
                self.tokens.append(tok)
                continue

            # Cadenas
            if ch in ('"', "'"):
                tok = self.read_string(ch)
                self.tokens.append(tok)
                continue

            # Números
            if ch.isdigit():
                tok = self.read_number()
                self.tokens.append(tok)
                continue

            # Identificadores / palabras clave
            if ch.isalpha() or ch == '_':
                tok = self.read_identifier()
                self.tokens.append(tok)
                continue

            # Operadores y delimitadores
            start_col = self.column
            start_line = self.line

            # Operadores de dos caracteres
            two_char = (self.current_char() or '') + (self.peek() or '')
            aug_assigns = {'+=', '-=', '*=', '/=', '//=', '%=', '**=', '&=', '|=', '^=', '>>=', '<<='}
            comparisons = {'==', '!=', '<=', '>=', '**', '//', '->', '<<', '>>'}

            if two_char in aug_assigns:
                self.advance(); self.advance()
                self.tokens.append(Token(TokenType.AUGMENTED_ASSIGN, two_char, start_line, start_col))
                continue

            if two_char in comparisons:
                self.advance(); self.advance()
                ttype = TokenType.COMPARISON if two_char in {'==','!=','<=','>='} else TokenType.OPERATOR
                if two_char == '->':
                    ttype = TokenType.ARROW
                self.tokens.append(Token(ttype, two_char, start_line, start_col))
                continue

            # Un carácter
            single_map = {
                '=': TokenType.ASSIGNMENT,
                '+': TokenType.OPERATOR, '-': TokenType.OPERATOR,
                '*': TokenType.OPERATOR, '/': TokenType.OPERATOR,
                '%': TokenType.OPERATOR, '^': TokenType.OPERATOR,
                '&': TokenType.OPERATOR, '|': TokenType.OPERATOR,
                '~': TokenType.OPERATOR, '@': TokenType.OPERATOR,
                '<': TokenType.COMPARISON, '>': TokenType.COMPARISON,
                '(': TokenType.LPAREN, ')': TokenType.RPAREN,
                '[': TokenType.LBRACKET, ']': TokenType.RBRACKET,
                '{': TokenType.LBRACE, '}': TokenType.RBRACE,
                ',': TokenType.COMMA, ':': TokenType.COLON,
                ';': TokenType.SEMICOLON, '.': TokenType.DOT,
            }

            if ch in single_map:
                self.advance()
                self.tokens.append(Token(single_map[ch], ch, start_line, start_col))
                continue

            # Carácter desconocido
            self.errors.append(LexerError(f"Carácter inesperado: {ch!r}", self.line, self.column))
            self.tokens.append(Token(TokenType.ERROR, ch, self.line, self.column))
            self.advance()

        self.tokens.append(Token(TokenType.EOF, '', self.line, self.column))
        return self.tokens

    def get_data_types(self) -> dict:
        """Analiza y cuenta los tipos de datos encontrados en los tokens."""
        type_counts = {}
        for tok in self.tokens:
            if tok.data_type:
                type_counts[tok.data_type] = type_counts.get(tok.data_type, 0) + 1
        return type_counts

    def get_inferred_string_types(self) -> List[dict]:
        """
        Analiza tokens STRING para detectar si su contenido tiene un tipo
        inferido diferente a str (ej: la cadena "42" contiene un int).

        Retorna una lista de dicts con:
          - token    : el Token original
          - raw      : valor original del token (con comillas)
          - content  : contenido sin comillas
          - inferred : tipo Python inferido del contenido ('int', 'float', 'bool', 'NoneType', 'str')

        Ejemplo:
          # Código: x = "42"
          # Token STRING '"42"' → inferred = 'int'
        """
        results = []
        for tok in self.tokens:
            if tok.type != TokenType.STRING:
                continue
            raw = tok.value
            # Quitar las comillas externas (simples, dobles o triples)
            content = raw
            for q in ('"""', "'''", '"', "'"):
                if content.startswith(q) and content.endswith(q) and len(content) >= len(q) * 2:
                    content = content[len(q):-len(q)]
                    break
            inferred_val = _infer(content)
            inferred_type = type(inferred_val).__name__
            if inferred_type != "str":  # Solo reportar cuando difiere del str literal
                results.append({
                    "token":    tok,
                    "raw":      raw,
                    "content":  content,
                    "inferred": inferred_type,
                    "line":     tok.line,
                    "column":   tok.column,
                })
        return results

    def get_summary(self) -> dict:
        """Retorna un resumen del análisis léxico."""
        summary = {}
        for tok in self.tokens:
            key = tok.type.name
            summary[key] = summary.get(key, 0) + 1
        return summary
