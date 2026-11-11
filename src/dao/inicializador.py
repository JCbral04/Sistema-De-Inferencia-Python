"""Crea la base de datos y carga el conocimiento del experto humano.

Las reglas SI-ENTONCES no se escriben a mano: se derivan de cada camino raíz-hoja del
árbol de decisión, de modo que árbol y reglas siempre son consistentes.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from werkzeug.security import generate_password_hash

RAIZ = Path(__file__).resolve().parents[2]
RUTA_ESQUEMA = RAIZ / "database" / "schema.sql"
RUTA_CONOCIMIENTO = RAIZ / "data" / "conocimiento_experto.json"
RUTA_BD = RAIZ / "data" / "sistema_experto.db"

ROLES = [
    ("Administrador", "Gestiona usuarios, supervisa todos los casos y consulta reportes."),
    ("Experto", "Ingeniero de conocimiento: mantiene hipótesis, soluciones, árbol y reglas."),
    ("Técnico", "Toma casos diagnosticados, registra seguimiento y confirma el diagnóstico."),
    ("Cliente", "Registra sus equipos, abre casos y ejecuta la consulta de diagnóstico."),
]

USUARIOS_DEMO = [
    ("Administrador del sistema", "admin@sistemaexperto.local", "Admin123*", "Administrador"),
    ("Experto del dominio", "experto@sistemaexperto.local", "Experto123*", "Experto"),
    ("Técnico de soporte", "tecnico@sistemaexperto.local", "Tecnico123*", "Técnico"),
    ("Cliente de prueba", "cliente@sistemaexperto.local", "Cliente123*", "Cliente"),
]


def validar_arbol(conocimiento: dict) -> None:
    """Comprueba que el árbol sea un árbol binario completo que cubre cada falla una vez."""
    nodos = {n["nodo"]: n for n in conocimiento["arbol"]["nodos"]}
    fallas = {h["codigo"] for h in conocimiento["hipotesis"]}
    sintomas = {s["codigo"] for s in conocimiento["sintomas"]}
    raiz = conocimiento["arbol"]["raiz"]
    hojas: list[str] = []
    visitados: set[str] = set()

    def recorrer(codigo: str) -> None:
        if codigo in fallas:
            hojas.append(codigo)
            return
        if codigo not in nodos:
            raise ValueError(f"Nodo desconocido en el árbol: {codigo}")
        if codigo in visitados:
            raise ValueError(f"El nodo {codigo} tiene más de un padre o hay un ciclo.")
        visitados.add(codigo)
        nodo = nodos[codigo]
        if nodo["sintoma"] not in sintomas:
            raise ValueError(f"Síntoma desconocido en {codigo}: {nodo['sintoma']}")
        recorrer(nodo["si"])
        recorrer(nodo["no"])

    recorrer(raiz)
    if set(nodos) != visitados:
        raise ValueError(f"Nodos inalcanzables: {sorted(set(nodos) - visitados)}")
    if len(hojas) != len(set(hojas)) or set(hojas) != fallas:
        raise ValueError("Cada falla debe aparecer exactamente una vez como hoja del árbol.")


def crear_base_datos(ruta_bd: Path | str = RUTA_BD, ruta_json: Path | str = RUTA_CONOCIMIENTO,
                     con_usuarios_demo: bool = True) -> None:
    ruta_bd = Path(ruta_bd)
    conocimiento = json.loads(Path(ruta_json).read_text(encoding="utf-8"))
    validar_arbol(conocimiento)

    ruta_bd.parent.mkdir(parents=True, exist_ok=True)
    if ruta_bd.exists():
        ruta_bd.unlink()

    conexion = sqlite3.connect(ruta_bd)
    try:
        conexion.executescript(RUTA_ESQUEMA.read_text(encoding="utf-8"))
        conexion.execute("PRAGMA foreign_keys = ON")
        _cargar_conocimiento(conexion, conocimiento)
        conexion.executemany("INSERT INTO rol(nombre, descripcion) VALUES(?, ?)", ROLES)
        if con_usuarios_demo:
            for nombre, correo, clave, rol in USUARIOS_DEMO:
                conexion.execute(
                    """INSERT INTO usuario(nombre, correo, clave_hash, rol_id)
                       VALUES(?, ?, ?, (SELECT id FROM rol WHERE nombre = ?))""",
                    (nombre, correo, generate_password_hash(clave), rol))
        conexion.commit()
    finally:
        conexion.close()


def _cargar_conocimiento(conexion: sqlite3.Connection, k: dict) -> None:
    e = k["experto"]
    experto_id = conexion.execute(
        "INSERT INTO experto(nombre, especialidad, anios_experiencia, fuente) VALUES(?, ?, ?, ?)",
        (e["nombre"], e["especialidad"], e["anios_experiencia"], e["fuente"])).lastrowid

    categorias = {}
    for c in k["categorias"]:
        categorias[c["codigo"]] = conexion.execute(
            "INSERT INTO categoria(codigo, nombre, descripcion) VALUES(?, ?, ?)",
            (c["codigo"], c["nombre"], c["descripcion"])).lastrowid

    sintomas = {}
    for s in k["sintomas"]:
        sintomas[s["codigo"]] = conexion.execute(
            "INSERT INTO sintoma(codigo, pregunta) VALUES(?, ?)",
            (s["codigo"], s["pregunta"])).lastrowid

    hipotesis, certeza = {}, {}
    for h in k["hipotesis"]:
        hipotesis[h["codigo"]] = conexion.execute(
            """INSERT INTO hipotesis(codigo, nombre, descripcion, categoria_id, experto_id,
                                     severidad, factor_certeza, solucion)
               VALUES(?, ?, ?, ?, ?, ?, ?, ?)""",
            (h["codigo"], h["nombre"], h["descripcion"], categorias[h["categoria"]], experto_id,
             h["severidad"], h["factor_certeza"], h["solucion"])).lastrowid
        certeza[h["codigo"]] = h["factor_certeza"]

    nodos = {n["nodo"]: n for n in k["arbol"]["nodos"]}
    reglas_creadas = 0

    def insertar(codigo: str, padre_id, rama, condiciones: list[tuple[str, str]]) -> None:
        nonlocal reglas_creadas
        if codigo in hipotesis:  # hoja: se crea el nodo y la regla del camino recorrido
            nodo_id = conexion.execute(
                "INSERT INTO nodo_arbol(codigo, padre_id, rama, hipotesis_id) VALUES(?, ?, ?, ?)",
                (f"L-{codigo}", padre_id, rama, hipotesis[codigo])).lastrowid
            reglas_creadas += 1
            # El código de la regla replica el de su falla (F05 -> R05) para facilitar la lectura.
            regla_id = conexion.execute(
                "INSERT INTO regla(codigo, hipotesis_id, nodo_hoja_id, factor_certeza) VALUES(?, ?, ?, ?)",
                (f"R{codigo[1:]}", hipotesis[codigo], nodo_id, certeza[codigo])).lastrowid
            conexion.executemany(
                "INSERT INTO regla_condicion(regla_id, orden, sintoma_id, valor) VALUES(?, ?, ?, ?)",
                [(regla_id, orden, sintomas[s], v) for orden, (s, v) in enumerate(condiciones, 1)])
            return
        nodo = nodos[codigo]
        nodo_id = conexion.execute(
            "INSERT INTO nodo_arbol(codigo, padre_id, rama, sintoma_id) VALUES(?, ?, ?, ?)",
            (codigo, padre_id, rama, sintomas[nodo["sintoma"]])).lastrowid
        insertar(nodo["si"], nodo_id, "si", condiciones + [(nodo["sintoma"], "si")])
        insertar(nodo["no"], nodo_id, "no", condiciones + [(nodo["sintoma"], "no")])

    insertar(k["arbol"]["raiz"], None, None, [])
