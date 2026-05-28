# src/__init__.py
# Paquete del compilador/analizador de Python

# Exportaciones principales
from .type_inference import (
    infer_type,           # Inferencia de tipo a partir de un string
    infer_assignment,     # Inferencia en contexto de asignación (quita comillas)
    smart_input,          # Reemplazo de input() con inferencia automática
    infer_expression,     # Coerción automática en operaciones binarias
    describe_inferred_type,  # Nombre del tipo de un valor
)
