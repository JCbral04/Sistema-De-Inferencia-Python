"""Piezas compartidas por los generadores de los dos documentos: datos, referencias y paginación.

Los datos se leen de una base de datos temporal que se crea en el momento a partir del esquema y del
archivo JSON del conocimiento; así los documentos siempre reflejan lo que el sistema carga de verdad.
"""
from __future__ import annotations

import re
import sqlite3
import subprocess
import sys
import tempfile
import unicodedata
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from consultas_granulos import cargar_consultas  # noqa: E402
from src.dao.inicializador import crear_base_datos  # noqa: E402

DIAGRAMAS = RAIZ / "docs" / "diagramas"
CAPTURAS = RAIZ / "docs" / "capturas"
SALIDAS = RAIZ / "docs" / "salidas"
DESTINO = RAIZ / "docs" / "entregables"

TITULO_PROYECTO = "sistema experto para el diagnóstico de fallas de computadores"
AUTORES = "Juan Cabral y Laura Ruiz"
REPOSITORIO = "https://github.com/JCbral04/Sistema-De-Inferencia-Python"
FECHA_REVISION = "10 de noviembre de 2026"        # fecha de la portada y de consulta de las páginas web citadas


def lineas_de_portada() -> list[str]:
    """Líneas de la portada de estudiante; lo resaltado en amarillo lo completa la persona en Word."""
    return ["[[Programa académico]], [[Universidad]]", "[[Código del curso]]: Sistemas expertos",
            "[[Nombre del docente]]", FECHA_REVISION]


# ---------------------------------------------------------------------------- referencias (APA 7)
def _web(titulo: str, url: str) -> str:
    return f"*{titulo}*. Recuperado el {FECHA_REVISION}, de {url}"


REFERENCIAS = {
    "alur": {"cita": "Alur et al.", "anio": "2003",
             "texto": "Alur, D., Crupi, J., y Malks, D. (2003). *Core J2EE patterns: Best practices and design "
                      "strategies* (2.ª ed.). Prentice Hall."},
    "codd": {"cita": "Codd", "anio": "1970",
             "texto": "Codd, E. F. (1970). A relational model of data for large shared data banks. "
                      "*Communications of the ACM, 13*(6), 377–387. https://doi.org/10.1145/362384.362685"},
    "gane": {"cita": "Gane y Sarson", "anio": "1979",
             "texto": "Gane, C., y Sarson, T. (1979). *Structured systems analysis: Tools and techniques*. "
                      "Prentice-Hall."},
    "giarratano": {"cita": "Giarratano y Riley", "anio": "2005",
                   "texto": "Giarratano, J. C., y Riley, G. (2005). *Expert systems: Principles and programming* "
                            "(4.ª ed.). Thomson Course Technology."},
    "graphviz": {"cita": "Graphviz", "anio": "s. f.",
                 "texto": "Graphviz. (s. f.). " + _web("Graphviz documentation", "https://graphviz.org/documentation/")},
    "iso29148": {"cita": "ISO/IEC/IEEE", "anio": "2018",
                 "texto": "ISO/IEC/IEEE. (2018). *Systems and software engineering—Life cycle processes—"
                          "Requirements engineering* (ISO/IEC/IEEE 29148:2018). "
                          "https://doi.org/10.1109/IEEESTD.2018.8559686"},
    "omg": {"cita": "Object Management Group", "abrev": "OMG", "anio": "2017",
            "texto": "Object Management Group. (2017). *OMG Unified Modeling Language (OMG UML)* "
                     "(Versión 2.5.1; formal/17-12-05). https://www.omg.org/spec/UML/2.5.1"},
    "owasp": {"cita": "OWASP Cheat Sheet Series", "anio": "s. f.",
              "texto": "OWASP Cheat Sheet Series. (s. f.). " + _web(
                  "Cross-site request forgery prevention cheat sheet",
                  "https://cheatsheetseries.owasp.org/cheatsheets/"
                  "Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html")},
    "pallets": {"cita": "Pallets", "anio": "s. f.",
                "texto": "Pallets. (s. f.). " + _web("Flask documentation (3.1.x)", "https://flask.palletsprojects.com/")},
    "python": {"cita": "Python Software Foundation", "anio": "s. f.",
               "texto": "Python Software Foundation. (s. f.). " + _web("Python 3 documentation",
                                                                      "https://docs.python.org/3/")},
    "russell": {"cita": "Russell y Norvig", "anio": "2021",
                "texto": "Russell, S., y Norvig, P. (2021). *Artificial intelligence: A modern approach* "
                         "(4.ª ed.). Pearson."},
    "shortliffe": {"cita": "Shortliffe y Buchanan", "anio": "1975",
                   "texto": "Shortliffe, E. H., y Buchanan, B. G. (1975). A model of inexact reasoning in "
                            "medicine. *Mathematical Biosciences, 23*(3–4), 351–379. "
                            "https://doi.org/10.1016/0025-5564(75)90047-4"},
    "sommerville": {"cita": "Sommerville", "anio": "2016",
                    "texto": "Sommerville, I. (2016). *Software engineering* (10.ª ed.). Pearson."},
    "sqlite": {"cita": "SQLite", "anio": "s. f.",
               "texto": "SQLite. (s. f.). " + _web("SQLite foreign key support", "https://www.sqlite.org/foreignkeys.html")},
}


# ---------------------------------------------------------------------------- utilidades de texto
def ajustar_codigo(texto: str, ancho: int = 76) -> str:
    """Parte las líneas largas en un espacio y sangra la continuación (Courier New de 10 pt: ~77 columnas)."""
    salida: list[str] = []
    for linea in texto.rstrip("\n").splitlines():
        while len(linea) > ancho:
            sangria = len(linea) - len(linea.lstrip())
            corte = linea.rfind(" ", sangria + 1, ancho)
            if corte <= sangria:
                corte = ancho
            salida.append(linea[:corte].rstrip())
            linea = " " * (sangria + 4) + linea[corte:].lstrip()
        salida.append(linea)
    return "\n".join(salida)


def decimal(valor: float) -> str:
    return f"{valor:.2f}"


# ---------------------------------------------------------------------------- datos desde la base
def _consultar(con: sqlite3.Connection, sql: str, parametros: tuple = ()) -> tuple[list[str], list[tuple]]:
    cursor = con.execute(sql, parametros)
    return [d[0] for d in cursor.description], [tuple(f) for f in cursor.fetchall()]


def cargar_datos() -> dict:
    """Crea una base temporal con el conocimiento y devuelve todo lo que los documentos necesitan."""
    with tempfile.TemporaryDirectory() as tmp:
        ruta = Path(tmp) / "documentos.db"
        crear_base_datos(ruta, con_usuarios_demo=False)
        con = sqlite3.connect(ruta)
        con.row_factory = sqlite3.Row
        hipotesis = [dict(f) for f in con.execute(
            """SELECT h.codigo, h.nombre, c.codigo AS cat_codigo, c.nombre AS categoria, h.severidad,
                      h.factor_certeza, h.solucion
               FROM hipotesis h JOIN categoria c ON c.id = h.categoria_id ORDER BY h.codigo""")]
        categorias = [dict(f) for f in con.execute("SELECT codigo, nombre, descripcion FROM categoria ORDER BY codigo")]
        sintomas = [dict(f) for f in con.execute("SELECT codigo, pregunta FROM sintoma ORDER BY codigo")]
        reglas = []
        for r in con.execute("""SELECT r.id, r.codigo, h.codigo AS hipotesis, r.factor_certeza FROM regla r
                                JOIN hipotesis h ON h.id = r.hipotesis_id ORDER BY r.codigo"""):
            condiciones = [(c["codigo"], c["valor"]) for c in con.execute(
                """SELECT s.codigo, rc.valor FROM regla_condicion rc JOIN sintoma s ON s.id = rc.sintoma_id
                   WHERE rc.regla_id = ? ORDER BY rc.orden""", (r["id"],))]
            reglas.append({"codigo": r["codigo"], "hipotesis": r["hipotesis"], "fc": r["factor_certeza"],
                           "condiciones": condiciones})
        tablas_bd = [f[0] for f in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid")]
        cuenta = {t: con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] for t in
                  ("experto", "categoria", "sintoma", "hipotesis", "nodo_arbol", "regla", "regla_condicion")}
        experto = dict(con.execute("SELECT nombre, especialidad, fuente FROM experto").fetchone())

        nodos = {f["id"]: dict(f) for f in con.execute(
            """SELECT n.id, n.codigo, n.padre_id, n.rama, s.codigo AS sintoma, h.codigo AS hipotesis
               FROM nodo_arbol n LEFT JOIN sintoma s ON s.id = n.sintoma_id
               LEFT JOIN hipotesis h ON h.id = n.hipotesis_id""")}
        hijos: dict[int, list[int]] = {}
        for nodo in nodos.values():
            if nodo["padre_id"] is not None:
                hijos.setdefault(nodo["padre_id"], []).append(nodo["id"])

        def hojas(i: int) -> list[str]:
            nodo = nodos[i]
            return [nodo["hipotesis"]] if nodo["hipotesis"] else [h for hijo in hijos[i] for h in hojas(hijo)]

        hojas_de = {n["codigo"]: sorted(hojas(i)) for i, n in nodos.items() if n["sintoma"]}
        # (nodo padre, rama) con que se llega a cada pregunta y a cada falla
        acceso = {(n["codigo"] if n["sintoma"] else n["hipotesis"]): (nodos[n["padre_id"]]["codigo"], n["rama"])
                  for n in nodos.values() if n["padre_id"] is not None}

        consultas = cargar_consultas()
        granulos: dict[str, dict] = {}
        for codigo in ("F17", "F05", "F21"):
            granulos[codigo] = {
                clave: _consultar(con, consultas[clave][1].replace("'F17'", "?"), (codigo,))
                for clave in ("G1", "G2", "G3", "G4", "G7")}
        general = {clave: _consultar(con, consultas[clave][1]) for clave in ("G5", "G6")}
        con.close()

    premisas = [len(r["condiciones"]) for r in reglas]
    return {
        "hipotesis": hipotesis, "categorias": categorias, "sintomas": sintomas, "reglas": reglas,
        "tablas_bd": tablas_bd, "cuenta": cuenta, "experto": experto, "granulos": granulos,
        "general": general, "consultas_sql": {k: v[1] for k, v in consultas.items()}, "hojas_de": hojas_de,
        "acceso": acceso,
        "n_preguntas": len(sintomas), "n_fallas": len(hipotesis), "n_reglas": len(reglas),
        "n_premisas": sum(premisas), "min_premisas": min(premisas), "max_premisas": max(premisas),
        "n_nodos": cuenta["nodo_arbol"],
    }


# ---------------------------------------------------------------------------- paginación con LibreOffice
def convertir_a_pdf(docx: Path, carpeta: Path) -> Path:
    carpeta.mkdir(parents=True, exist_ok=True)
    subprocess.run(["soffice", "--headless", "--convert-to", "pdf", "--outdir", str(carpeta), str(docx)],
                   check=True, capture_output=True, timeout=600)
    return carpeta / f"{docx.stem}.pdf"


def paginas_del_pdf(pdf: Path) -> list[str]:
    texto = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], check=True, capture_output=True,
                           text=True).stdout
    paginas = texto.split("\f")
    if paginas and not paginas[-1].strip():
        paginas.pop()
    return [unicodedata.normalize("NFC", p) for p in paginas]


def _patron(texto: str) -> re.Pattern:
    palabras = unicodedata.normalize("NFC", texto).split()
    return re.compile(r"(?m)^\s*" + r"\s+".join(re.escape(p) for p in palabras) + r"\s*$")


def localizar_paginas(registro: dict, paginas: list[str]) -> dict[str, int]:
    """Página de cada encabezado y de cada rótulo de tabla o figura (búsqueda en orden de aparición)."""
    resultado: dict[str, int] = {}
    for clave, texto_de in (("encabezados", lambda e: e.get("busqueda") or e["texto"]),
                            ("rotulos", lambda r: r["etiqueta"])):
        cursor = 0
        for elemento in registro[clave]:
            patron = _patron(texto_de(elemento))
            for n in range(cursor, len(paginas)):
                if patron.search(paginas[n]):
                    resultado[elemento["marcador"]] = n + 1
                    cursor = n
                    break
            else:
                print(f"  aviso: no se encontró «{texto_de(elemento)}» en el PDF")
    return resultado


def construir_estable(constructor, ruta: Path, carpeta_pdf: Path, maximo: int = 6):
    """Construye el documento hasta que la numeración y las páginas de los índices dejen de cambiar.

    Devuelve (documento, registro, pdf, páginas), donde páginas es el texto de cada página del PDF."""
    previo: dict = {}
    for pasada in range(1, maximo + 1):
        documento = constructor(previo)
        registro = documento.guardar(ruta)
        pdf = convertir_a_pdf(ruta, carpeta_pdf)
        paginas = paginas_del_pdf(pdf)
        nuevo = {"etiquetas": registro["etiquetas"], "encabezados": registro["encabezados"],
                 "rotulos": registro["rotulos"], "paginas": localizar_paginas(registro, paginas),
                 "total": len(paginas)}
        print(f"  pasada {pasada}: {len(paginas)} páginas")
        if nuevo == previo:
            return documento, registro, pdf, paginas
        previo = nuevo
    raise RuntimeError("La paginación no se estabilizó; revise el contenido.")
