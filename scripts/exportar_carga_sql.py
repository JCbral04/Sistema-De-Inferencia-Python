"""Exporta la carga del conocimiento como script SQL (database/carga_conocimiento.sql).

El script contiene solo sentencias INSERT de las siete tablas de la base de conocimiento, en
orden de dependencias, de modo que el conocimiento pueda cargarse sin Python:

    sqlite3 sistema.db < database/schema.sql
    sqlite3 sistema.db < database/carga_conocimiento.sql
"""
import sqlite3
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RUTA_BD = RAIZ / "data" / "sistema_experto.db"
SALIDA = RAIZ / "database" / "carga_conocimiento.sql"

# (tabla, columnas, orden); el orden respeta las claves foráneas.
TABLAS = [
    ("experto", "id, nombre, especialidad, anios_experiencia, fuente", "id"),
    ("categoria", "id, codigo, nombre, descripcion", "id"),
    ("sintoma", "id, codigo, pregunta", "id"),
    ("hipotesis", "id, codigo, nombre, descripcion, categoria_id, experto_id, severidad, "
                  "factor_certeza, solucion", "id"),
    ("nodo_arbol", "id, codigo, padre_id, rama, sintoma_id, hipotesis_id", "id"),
    ("regla", "id, codigo, hipotesis_id, nodo_hoja_id, factor_certeza", "id"),
    ("regla_condicion", "regla_id, orden, sintoma_id, valor", "regla_id, orden"),
]


def literal(valor) -> str:
    if valor is None:
        return "NULL"
    if isinstance(valor, (int, float)):
        return repr(valor)
    return "'" + str(valor).replace("'", "''") + "'"


def main() -> None:
    con = sqlite3.connect(RUTA_BD)
    lineas = [
        "-- Carga del conocimiento del experto humano en la base de conocimiento (SQLite 3).",
        "-- Generado por scripts/exportar_carga_sql.py a partir de data/sistema_experto.db.",
        "-- Uso: sqlite3 sistema.db < database/schema.sql",
        "--      sqlite3 sistema.db < database/carga_conocimiento.sql",
        "PRAGMA foreign_keys = ON;",
        "BEGIN TRANSACTION;",
    ]
    for tabla, columnas, orden in TABLAS:
        filas = con.execute(f"SELECT {columnas} FROM {tabla} ORDER BY {orden}").fetchall()
        lineas += ["", f"-- {tabla}: {len(filas)} registros",
                   f"INSERT INTO {tabla}({columnas}) VALUES"]
        valores = ["    (" + ", ".join(literal(v) for v in fila) + ")" for fila in filas]
        lineas.append(",\n".join(valores) + ";")
    lineas += ["", "COMMIT;", ""]
    SALIDA.write_text("\n".join(lineas), encoding="utf-8")
    con.close()
    print("ok", SALIDA.relative_to(RAIZ))


if __name__ == "__main__":
    main()
