# Sistema de inferencia bayesiano para fallas de computadores

Proyecto académico de sistemas expertos. Implementa cinco hipótesis, diez síntomas, inferencia exacta mediante enumeración y selección adaptativa de preguntas por ganancia de información. El conocimiento está fuera del código y se consulta de forma granular en SQLite.

## Requisitos

- Python 3.10 o superior.
- No requiere paquetes externos.

## Ejecución y pruebas

Desde la raíz del proyecto:

```bash
# 1. Ejecutar el sistema experto
python main.py

# 2. Ejecutar las seis pruebas automatizadas
python -m unittest discover -s tests -v
```

La base `data/knowledge.db` se crea automáticamente en la primera ejecución. Para reconstruirla después de editar `data/knowledge_base.json`, elimine `data/knowledge.db` y vuelva a ejecutar el sistema.

## Uso

- `s`: sí.
- `n`: no.
- `ns`: no sé; la pregunta se descarta sin modificar la evidencia.
- `salir`: termina la sesión y muestra el resultado actual.

Después de cada respuesta se presentan las cinco probabilidades posteriores. Como las fallas pueden coexistir, los porcentajes no deben sumar 100 %.

## Estructura

- `src/presentation/`: interfaz de consola.
- `src/application/`: sesión, inferencia bayesiana y selección de preguntas.
- `src/domain/`: entidades y contrato del repositorio.
- `src/infrastructure/`: inicialización y consultas SQLite.
- `data/knowledge_base.json`: fuente editable del conocimiento.
- `docs/`: informe y diagramas en PNG, SVG y Mermaid.
- `tests/`: pruebas del motor y de la base de conocimiento.

## Alcance

Los valores de probabilidad son académicos e ilustrativos. El resultado orienta el diagnóstico, pero no reemplaza las pruebas técnicas del equipo.
