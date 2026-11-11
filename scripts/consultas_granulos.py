"""Ejecuta las consultas de gránulos (sql/consultas_granulos.sql) para una o varias hipótesis.

Uso:  python scripts/consultas_granulos.py F05 F17 F21
Sin argumentos muestra el resumen G5 de las 31 hipótesis.

Las consultas se leen del archivo .sql (única fuente); el código de ejemplo 'F17' se
reemplaza por el de cada hipótesis solicitada.
"""
import re
import sqlite3
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RUTA_BD = RAIZ / "data" / "sistema_experto.db"
RUTA_SQL = RAIZ / "sql" / "consultas_granulos.sql"
POR_HIPOTESIS = ("G1", "G2", "G3", "G4", "G7")


def cargar_consultas() -> dict[str, tuple[str, str]]:
    """Devuelve {'G1': (descripción, sql), ...} a partir del archivo .sql."""
    partes = re.split(r"(?m)^-- (G\d+)\. ", RUTA_SQL.read_text(encoding="utf-8"))[1:]
    consultas = {}
    for codigo, cuerpo in zip(partes[::2], partes[1::2]):
        descripcion, _, sql = cuerpo.partition("\n")
        consultas[codigo] = (descripcion.strip(), sql.strip())
    return consultas


def imprimir(titulo: str, cursor: sqlite3.Cursor) -> None:
    print(f"\n== {titulo}")
    columnas = [d[0] for d in cursor.description]
    filas = cursor.fetchall()
    if len(filas) == 1 and len(columnas) > 4:  # una sola fila ancha: se muestra en vertical
        ancho = max(len(c) for c in columnas)
        for columna, valor in zip(columnas, filas[0]):
            print(f"{columna.ljust(ancho)} : {valor}")
        return
    ancho = [min(70, max(len(str(x)) for x in [c] + [f[i] for f in filas])) for i, c in enumerate(columnas)]
    print(" | ".join(c.ljust(a) for c, a in zip(columnas, ancho)))
    print("-+-".join("-" * a for a in ancho))
    for fila in filas:
        print(" | ".join(str(v)[:70].ljust(a) for v, a in zip(fila, ancho)))


def main(codigos: list[str]) -> None:
    consultas = cargar_consultas()
    con = sqlite3.connect(RUTA_BD)
    if not codigos:
        descripcion, sql = consultas["G5"]
        imprimir(f"G5. {descripcion}", con.execute(sql))
    for codigo in codigos:
        for clave in POR_HIPOTESIS:
            descripcion, sql = consultas[clave]
            imprimir(f"{clave}. {descripcion} [{codigo}]", con.execute(sql.replace("'F17'", "?"), (codigo,)))
    con.close()


if __name__ == "__main__":
    main(sys.argv[1:])
