"""Genera los diagramas del manual técnico y el modelo relacional exportado del SGBD.

Requiere el ejecutable `dot` de Graphviz, matplotlib y Pillow. Salida:
  docs/diagramas/*.png y *.svg, docs/salidas/modelo_relacional.txt y
  database/modelo_relacional.sql (volcado del esquema real de SQLite).

Los diagramas están dimensionados para la hoja carta del manual (APA 7): los verticales caben
en 6,5 pulgadas de ancho y los horizontales en 9; así el texto se imprime a su tamaño real
(8 a 11 puntos, fuente sans serif) sin reducir la imagen.
"""
from __future__ import annotations

import functools
import html
import json
import sqlite3
import subprocess
import textwrap
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402
from PIL import Image  # noqa: E402

plt.rcParams["font.family"] = ["Liberation Sans", "DejaVu Sans"]
plt.rcParams["svg.fonttype"] = "none"

RAIZ = Path(__file__).resolve().parents[1]
SALIDA = RAIZ / "docs" / "diagramas"
BD = RAIZ / "data" / "sistema_experto.db"
CONOCIMIENTO = RAIZ / "data" / "conocimiento_experto.json"
FUENTE = "Arial"          # fontconfig la resuelve a Liberation Sans (misma métrica)
DPI = 200
VERTICAL = (6.5, 7.8)     # pulgadas útiles de una página vertical (sin contar el título de la figura)
HORIZONTAL = (9.0, 5.4)   # ídem, página horizontal

TABLAS_CONOCIMIENTO = ["experto", "categoria", "hipotesis", "sintoma", "nodo_arbol", "regla",
                       "regla_condicion"]
RAMA = {"si": "Sí", "no": "No"}      # rótulo de cada rama del árbol
MEDIDAS: dict[str, tuple[float, float]] = {}


def esc(texto: str) -> str:
    return html.escape(texto, quote=True)


def envolver(texto: str, ancho: int) -> list[str]:
    return textwrap.wrap(texto, ancho) or [""]


def html_lineas(lineas: list[str]) -> str:
    return "<BR/>".join(esc(x) for x in lineas)


# Todos los diagramas son en blanco y negro: fondo blanco, líneas y texto negros, sin rellenos de color.
CABECERA = f"""graph [fontname="{FUENTE}", fontsize=10, bgcolor="white", pad=0.08];
node  [fontname="{FUENTE}", fontsize=9.5, color="black", fontcolor="black"];
edge  [fontname="{FUENTE}", fontsize=9, color="black", fontcolor="black"];"""


def registrar_medida(nombre: str, limite: tuple[float, float]) -> None:
    ruta = SALIDA / f"{nombre}.png"
    imagen = Image.open(ruta)
    ancho, alto = imagen.size[0] / DPI, imagen.size[1] / DPI
    imagen.save(ruta, dpi=(DPI, DPI))
    MEDIDAS[nombre] = (round(ancho, 2), round(alto, 2))
    aviso = "" if ancho <= limite[0] + 0.01 and alto <= limite[1] + 0.01 else "   <-- EXCEDE EL ESPACIO"
    print(f"ok {nombre:34s} {ancho:5.2f} x {alto:5.2f} pulg{aviso}")


def render(nombre: str, dot: str, limite: tuple[float, float]) -> None:
    SALIDA.mkdir(parents=True, exist_ok=True)
    for formato in ("png", "svg"):
        subprocess.run(["dot", f"-T{formato}", f"-Gdpi={DPI if formato == 'png' else 72}",
                        "-o", str(SALIDA / f"{nombre}.{formato}")],
                       input=dot.encode("utf-8"), check=True)
    registrar_medida(nombre, limite)


# ====================================================================== árbol de decisión
class Arbol:
    """Datos del conocimiento organizados para dibujar el árbol."""

    def __init__(self, k: dict):
        self.nodos = {n["nodo"]: n for n in k["arbol"]["nodos"]}
        self.hip = {h["codigo"]: h for h in k["hipotesis"]}
        self.sint = {s["codigo"]: s for s in k["sintomas"]}
        self.raiz = k["arbol"]["raiz"]

    def es_hoja(self, codigo: str) -> bool:
        return codigo in self.hip

    @functools.cache
    def hojas(self, codigo: str) -> tuple[str, ...]:
        if self.es_hoja(codigo):
            return (codigo,)
        n = self.nodos[codigo]
        return self.hojas(n["si"]) + self.hojas(n["no"])

    def etiqueta(self, codigo: str) -> str:
        s = self.sint[self.nodos[codigo]["sintoma"]]
        return s.get("etiqueta") or s["pregunta"]

    def rango(self, codigo: str) -> str:
        hojas = sorted(self.hojas(codigo))
        return hojas[0] if len(hojas) == 1 else f"{hojas[0]}–{hojas[-1]}"

    def tronco(self) -> list[str]:
        """Camino principal: en cada nodo se sigue el hijo con más fallas mientras tenga 3 o más."""
        camino, actual = [], self.raiz
        while True:
            camino.append(actual)
            n = self.nodos[actual]
            hijos = [h for h in (n["si"], n["no"]) if not self.es_hoja(h) and len(self.hojas(h)) >= 3]
            if not hijos:
                return camino
            actual = max(hijos, key=lambda h: len(self.hojas(h)))


TITULOS_SUBARBOL = {
    "N02": "Equipo sin encendido", "N06": "Pitidos largos o continuos", "N08": "Sin imagen en pantalla",
    "N11": "El sistema operativo no carga", "N16": "Apagados y reinicios repentinos",
    "N20": "Lentitud del equipo", "N25": "Problemas de conexión a internet",
    "N28": "Fallas de imagen", "N30": "Periférico no reconocido",
}



def dibujar_completo(a: Arbol) -> None:
    """Árbol entero en una sola página; cada nodo lleva solo su código (el texto está en las figuras de detalle).

    Las hojas se ordenan de izquierda a derecha con la rama Sí siempre a la izquierda de la rama No; cada
    pregunta se centra sobre sus dos ramas y cada nivel del árbol ocupa una fila."""
    columna: dict[str, float] = {}
    nivel: dict[str, int] = {}
    hojas_colocadas = [0]

    def colocar(codigo: str, n: int) -> None:
        nivel[codigo] = n
        if a.es_hoja(codigo):
            columna[codigo] = hojas_colocadas[0]
            hojas_colocadas[0] += 1
            return
        nodo = a.nodos[codigo]
        colocar(nodo["si"], n + 1)
        colocar(nodo["no"], n + 1)
        columna[codigo] = (columna[nodo["si"]] + columna[nodo["no"]]) / 2

    colocar(a.raiz, 0)
    ancho, alto, margen = 9.0, 4.95, 0.2
    w, h = 0.235, 0.17                     # caja de un nodo: tres caracteres a 8 pt
    barra = 0.065                          # distancia entre la caja del padre y la barra que une a sus hijos
    paso_x = (ancho - 2 * margen) / (hojas_colocadas[0] - 1)
    y_raiz, y_ultima = alto - 0.1 - h / 2, 0.55 + h / 2
    paso_y = (y_raiz - y_ultima) / max(nivel.values())

    def px(c: str) -> float:
        return margen + columna[c] * paso_x

    def py(c: str) -> float:
        return y_raiz - nivel[c] * paso_y

    fig = plt.figure(figsize=(ancho, alto))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, ancho)
    ax.set_ylim(0, alto)
    ax.axis("off")

    def linea(x0, y0, x1, y1):
        ax.plot([x0, x1], [y0, y1], color="black", lw=0.9, solid_capstyle="butt", zorder=1)

    for codigo, nodo in a.nodos.items():
        x, y_barra = px(codigo), py(codigo) - h / 2 - barra
        hijos = [(nodo["si"], "si"), (nodo["no"], "no")]
        linea(x, py(codigo) - h / 2, x, y_barra)
        linea(px(hijos[0][0]), y_barra, px(hijos[1][0]), y_barra)
        for hijo, rama in hijos:
            y_tope = py(hijo) + h / 2
            linea(px(hijo), y_barra, px(hijo), y_tope)
            ax.text(px(hijo), (y_barra + y_tope) / 2, RAMA[rama], ha="center", va="center_baseline",
                    fontsize=8, color="black", zorder=3,
                    bbox=dict(boxstyle="square,pad=0.05", fc="white", ec="none"))

    def caja(x, y, forma, texto=""):
        if forma == "falla":
            ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.06",
                                        fc="white", ec="black", lw=0.9, zorder=2))
        else:
            ax.add_patch(Rectangle((x - w / 2, y - h / 2), w, h, fc="white", ec="black", lw=0.9, zorder=2))
        if texto:
            ax.text(x, y, texto, ha="center", va="center_baseline", fontsize=8, color="black", zorder=4)

    for codigo in columna:
        caja(px(codigo), py(codigo), "falla" if a.es_hoja(codigo) else "pregunta", codigo)

    # leyenda
    yl = 0.2
    caja(0.35, yl, "pregunta")
    ax.text(0.55, yl, f"Pregunta ({a.raiz} a N{len(a.nodos):02d})", va="center_baseline", fontsize=8, color="black")
    caja(2.55, yl, "falla")
    ax.text(2.75, yl, f"Falla (F01 a F{len(a.hip):02d})", va="center_baseline", fontsize=8, color="black")
    SALIDA.mkdir(parents=True, exist_ok=True)
    for formato in ("png", "svg"):
        fig.savefig(SALIDA / f"arbol_completo.{formato}", dpi=DPI)
    plt.close(fig)
    registrar_medida("arbol_completo", HORIZONTAL)


def dibujar_tronco(a: Arbol) -> None:
    """Vista general: el camino principal del árbol (peldaños) y los subárboles que cuelgan de él."""
    tronco = a.tronco()
    ancho, alto = 9.0, 4.95
    fig = plt.figure(figsize=(ancho, alto))
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, ancho)
    ax.set_ylim(0, alto)
    ax.axis("off")
    x_t, w_t = 0.08, 3.9          # columna del tronco
    x_s, w_s = 5.05, 3.87         # columna de subárboles y fallas
    h_caja, paso, y_inicial = 0.27, 0.445, alto - 0.22

    def caja(x, y, w, h, texto, forma="pregunta"):
        """pregunta: rectángulo; subárbol: rectángulo de doble borde; falla: rectángulo de esquinas redondeadas."""
        if forma == "falla":
            ax.add_patch(FancyBboxPatch((x, y - h / 2), w, h, boxstyle="round,pad=0,rounding_size=0.1",
                                        fc="white", ec="black", lw=1.0))
        else:
            ax.add_patch(Rectangle((x, y - h / 2), w, h, fc="white", ec="black", lw=1.0))
            if forma == "subarbol":
                ax.add_patch(Rectangle((x + 0.04, y - h / 2 + 0.04), w - 0.08, h - 0.08, fc="none", ec="black",
                                       lw=0.8))
        if texto:
            ax.text(x + 0.1, y, texto, va="center", ha="left", fontsize=8.8, color="black")

    def flecha(x0, y0, x1, y1):
        ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                    arrowprops=dict(arrowstyle="-|>", color="black", lw=1.0, shrinkA=0, shrinkB=0,
                                    mutation_scale=9))

    def rotulo(x, y, rama):
        ax.text(x, y, RAMA[rama], ha="center", va="center", fontsize=8.8, color="black",
                bbox=dict(boxstyle="square,pad=0.12", fc="white", ec="none"))

    y_de = {codigo: y_inicial - paso * i for i, codigo in enumerate(tronco)}
    for codigo in tronco:
        n = a.nodos[codigo]
        caja(x_t, y_de[codigo], w_t, h_caja, f"{codigo} · {n['sintoma']}   {a.etiqueta(codigo)}")

    for i, codigo in enumerate(tronco):
        n, y = a.nodos[codigo], y_de[codigo]
        siguiente = tronco[i + 1] if i + 1 < len(tronco) else None
        laterales = []
        for rama in ("si", "no"):
            destino = n[rama]
            if destino == siguiente:
                y2 = y_de[destino]
                flecha(x_t + 0.3, y - h_caja / 2, x_t + 0.3, y2 + h_caja / 2)
                rotulo(x_t + 0.58, (y + y2) / 2, rama)
            else:
                laterales.append((rama, destino))
        for j, (rama, destino) in enumerate(laterales):
            ys = y if len(laterales) == 1 else y + (0.11 if j == 0 else -0.19)
            h = h_caja if len(laterales) == 1 else 0.25
            if a.es_hoja(destino):
                caja(x_s, ys, w_s, h, f"{destino}  {a.hip[destino]['nombre'][:46]}", "falla")
            else:
                titulo = TITULOS_SUBARBOL.get(destino, a.etiqueta(destino))
                caja(x_s, ys, w_s, h, f"{destino} · {titulo}  ({a.rango(destino)})", "subarbol")
            flecha(x_t + w_t, y, x_s, ys)
            rotulo((x_t + w_t + x_s) / 2, (y + ys) / 2, rama)

    # leyenda
    yl = 0.17
    caja(0.1, yl, 0.28, 0.18, "")
    ax.text(0.45, yl, "Pregunta del tronco", va="center", fontsize=8.5, color="black")
    caja(2.3, yl, 0.28, 0.18, "", "subarbol")
    ax.text(2.65, yl, "Subárbol (ver figuras siguientes)", va="center", fontsize=8.5, color="black")
    caja(5.05, yl, 0.28, 0.18, "", "falla")
    ax.text(5.4, yl, "Falla", va="center", fontsize=8.5, color="black")
    SALIDA.mkdir(parents=True, exist_ok=True)
    for formato in ("png", "svg"):
        fig.savefig(SALIDA / f"arbol_tronco.{formato}", dpi=DPI)
    plt.close(fig)
    registrar_medida("arbol_tronco", HORIZONTAL)



def dot_subarbol(a: Arbol, raices: list[str]) -> str:
    """Subárbol(es) en horizontal: cada pregunta bifurca a la derecha en Sí (arriba) y No (abajo)."""
    lineas = ["digraph sub {", CABECERA, "rankdir=LR; nodesep=0.14; ranksep=0.3; newrank=true;",
              'node [shape=box, margin="0.09,0.05"];']

    def agregar(codigo: str) -> None:
        if a.es_hoja(codigo):
            h = a.hip[codigo]
            nombre = html_lineas(envolver(h["nombre"], 24))
            lineas.append(
                f'{codigo} [style=rounded, label=<<B>{codigo}</B>  {nombre}<BR/>'
                f'<FONT POINT-SIZE="8">{h["severidad"]} · FC {h["factor_certeza"]:.2f}</FONT>>];')
            return
        n = a.nodos[codigo]
        texto = html_lineas(envolver(a.etiqueta(codigo), 22))
        lineas.append(f'{codigo} [label=<<B>{codigo}</B> · {n["sintoma"]}<BR/>{texto}>];')
        for rama in ("si", "no"):
            destino = n[rama]
            lineas.append(f'{codigo} -> {destino} [label=" {RAMA[rama]} "];')
            agregar(destino)

    for r in raices:
        agregar(r)
    lineas.append("}")
    return "\n".join(lineas)


# ====================================================================== modelo relacional
def introspeccion(con: sqlite3.Connection) -> dict:
    tablas = [r[0] for r in con.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY rowid")]
    info = {}
    for t in tablas:
        columnas = con.execute(f"PRAGMA table_info({t})").fetchall()
        fks = {f[3]: (f[2], f[4]) for f in con.execute(f"PRAGMA foreign_key_list({t})")}
        unicos = set()
        for idx in con.execute(f"PRAGMA index_list({t})"):
            if idx[2] and idx[3] == "u":
                cols = [c[2] for c in con.execute(f"PRAGMA index_info({idx[1]})")]
                if len(cols) == 1:
                    unicos.add(cols[0])
        info[t] = {"columnas": columnas, "fks": fks, "unicos": unicos}
    return info


def exportar_modelo_texto(con: sqlite3.Connection, info: dict) -> None:
    lineas = ["MODELO RELACIONAL (SGBD: SQLite 3)",
              "Notación: PK = clave primaria · FK = clave foránea · UK = valor único · NN = obligatorio", ""]
    for tabla, d in info.items():
        lineas.append(f"{tabla}(")
        for c in d["columnas"]:
            etiquetas = []
            if c[5]:
                etiquetas.append("PK")
            if c[1] in d["fks"]:
                etiquetas.append(f"FK→{d['fks'][c[1]][0]}.{d['fks'][c[1]][1]}")
            if c[1] in d["unicos"]:
                etiquetas.append("UK")
            if c[3] and not c[5]:
                etiquetas.append("NN")
            lineas.append(f"    {c[1]}" + (" [" + ", ".join(etiquetas) + "]" if etiquetas else "") + ",")
        lineas += [")", ""]
    (RAIZ / "docs" / "salidas" / "modelo_relacional.txt").write_text("\n".join(lineas), encoding="utf-8")
    ddl = [f"{r[0]};" for r in con.execute(
        "SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'sqlite_%' ORDER BY rowid")]
    (RAIZ / "database" / "modelo_relacional.sql").write_text(
        "-- Volcado del esquema exportado desde el SGBD (SQLite 3)\nPRAGMA foreign_keys = ON;\n\n"
        + "\n\n".join(ddl) + "\n", encoding="utf-8")



TIPOS = {"integer": "int", "text": "text", "real": "real"}


def tabla_html(tabla: str, d: dict, completa: bool = True, externa: bool = False) -> str:
    """Tabla del modelo: nombre arriba, una fila por columna (nombre, tipo y clave); borde punteado si es externa."""
    estilo = ' STYLE="dashed"' if externa else ""
    filas = []
    columnas = d["columnas"] if completa else [c for c in d["columnas"] if c[5]]
    for c in columnas:
        clave = "PK" if c[5] else ("FK" if c[1] in d["fks"] else ("UK" if c[1] in d["unicos"] else ""))
        nombre = f"<B>{esc(c[1])}</B>" if c[5] else esc(c[1])
        filas.append(
            f'<TR><TD ALIGN="LEFT" PORT="{esc(c[1])}">{nombre}</TD>'
            f'<TD ALIGN="LEFT">{TIPOS.get(c[2].lower(), c[2].lower())}</TD>'
            f'<TD PORT="{esc(c[1])}_k"><B>{clave or "&nbsp;"}</B></TD></TR>')
    return (f'<TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="2"{estilo}>'
            f'<TR><TD COLSPAN="3" ALIGN="CENTER"><B>{esc(tabla)}</B></TD></TR><HR/>{"".join(filas)}</TABLE>')


def dot_modelo(info: dict, tablas: list[str], externas: list[str], razon: str) -> str:
    lineas = ["digraph mr {", CABECERA, f"rankdir=LR; nodesep=0.28; ranksep={razon}; splines=true;",
              'node [shape=none, margin=0, fontsize=8.5];',
              'edge [arrowtail=crow, arrowhead=tee, dir=both, arrowsize=0.7];']
    for t in tablas:
        lineas.append(f'{t} [label=<{tabla_html(t, info[t])}>];')
    for t in externas:
        lineas.append(f'{t} [label=<{tabla_html(t, info[t], completa=False, externa=True)}>];')
    visibles = set(tablas) | set(externas)
    for t in tablas:
        for columna, (destino, destino_col) in info[t]["fks"].items():
            if destino in visibles:
                lineas.append(f'{t}:{columna}_k:e -> {destino}:{destino_col}:w;')
    lineas.append("}")
    return "\n".join(lineas)


def modelo_relacional(con: sqlite3.Connection) -> None:
    info = introspeccion(con)
    exportar_modelo_texto(con, info)
    render("modelo_relacional_conocimiento", dot_modelo(info, TABLAS_CONOCIMIENTO, [], "0.5"), HORIZONTAL)
    render("modelo_relacional_transaccional_1",
           dot_modelo(info, ["rol", "usuario", "equipo", "caso", "seguimiento"], [], "0.5"), HORIZONTAL)
    render("modelo_relacional_transaccional_2",
           dot_modelo(info, ["consulta", "respuesta", "diagnostico"],
                      ["caso", "nodo_arbol", "sintoma", "hipotesis", "regla"], "0.55"), HORIZONTAL)


# ====================================================================== arquitectura

def arquitectura() -> None:
    capas = [
        ("Presentación", "Flask: rutas por rol (src/web/rutas.py) · plantillas Jinja2 · sesión, CSRF y control de roles"),
        ("Servicios", "AutenticacionService · EquipoService · DiagnosticoService · MotorInferencia"),
        ("Acceso a datos (DAO)", "BaseDAO y un DAO por tabla o grupo de tablas · entidades inmutables (src/domain)"),
        ("Base de datos", "SQLite 3: base de conocimiento (7 tablas) y sistema transaccional (8 tablas)"),
    ]
    lineas = ["digraph arq {", CABECERA, "rankdir=TB; nodesep=0.3; ranksep=0.38;",
              'node [shape=box, margin="0.16,0.09", width=6.0];',
              'usuarios [label="Navegador web\\nCliente · Técnico · Experto · Administrador"];']
    for i, (nombre, detalle) in enumerate(capas):
        partes = envolver(detalle, 70)
        lineas.append(f'c{i} [label=<<B>{esc(nombre)}</B><BR/><FONT POINT-SIZE="8.5">{html_lineas(partes)}</FONT>>];')
    lineas.append('usuarios -> c0 [label=" HTTP", dir=both];')
    for i in range(3):
        lineas.append(f'c{i} -> c{i + 1} [dir=both];')
    lineas.append("}")
    render("arquitectura", "\n".join(lineas), VERTICAL)


# ====================================================================== casos de uso
def etiqueta_dot(texto: str, ancho: int) -> str:
    """Texto en varias líneas con el salto \\n propio de Graphviz."""
    partes = [p for bloque in texto.split("\n") for p in envolver(bloque, ancho)]
    return "\\n".join(partes)



def casos_de_uso(nombre: str, izquierda: dict[str, list[str]], derecha: dict[str, list[str]],
                 incluidos: list[tuple[str, str]], limite: tuple[float, float]) -> None:
    """Los actores de `izquierda` se dibujan a la izquierda del sistema y los de `derecha` a la derecha."""
    lineas = ["digraph cu {", CABECERA, "rankdir=LR; nodesep=0.14; ranksep=0.55; compound=true;",
              "node [fontsize=9.5];"]
    for a in list(izquierda) + list(derecha):
        lineas.append(f'"{a}" [shape=box, label=<«actor»<BR/><B>{esc(a)}</B>>, width=1.1];')
    lineas.append('subgraph cluster_sistema { label="Sistema experto de diagnóstico de fallas de computadores"; '
                  'labeljust=l; style=solid; color="black"; fontsize=10; margin=12;')
    ids: dict[str, str] = {}
    for grupo in (izquierda, derecha):
        for casos in grupo.values():
            for c in casos:
                ids[c] = f"cu{len(ids) + 1}"
                lineas.append(f'{ids[c]} [shape=ellipse, label="{etiqueta_dot(c, 22)}"];')
    for _, incluido in incluidos:
        ids[incluido] = f"cu{len(ids) + 1}"
        lineas.append(f'{ids[incluido]} [shape=ellipse, label="{etiqueta_dot(incluido, 22)}"];')
    lineas.append("}")
    for a, casos in izquierda.items():
        lineas += [f'"{a}" -> {ids[c]} [dir=none];' for c in casos]
    for a, casos in derecha.items():
        lineas += [f'{ids[c]} -> "{a}" [dir=none];' for c in casos]
    for origen, incluido in incluidos:
        lineas.append(f'{ids[origen]} -> {ids[incluido]} [style=dashed, label="«include»", fontsize=8.5];')
    # los casos de la derecha quedan en la columna siguiente a los de la izquierda
    primeros = [ids[c] for casos in izquierda.values() for c in casos][:1]
    for casos in derecha.values():
        lineas += [f'{primeros[0]} -> {ids[c]} [style=invis];' for c in casos if primeros]
    lineas.append("}")
    render(nombre, "\n".join(lineas), limite)


def diagramas_casos_de_uso() -> None:
    casos_de_uso(
        "casos_de_uso_cliente_tecnico",
        {"Cliente": ["Registrarse e iniciar sesión", "Gestionar equipos", "Abrir caso",
                     "Ejecutar consulta de diagnóstico", "Consultar historial de casos"]},
        {"Técnico": ["Consultar cola de casos", "Tomar caso", "Registrar seguimiento",
                     "Resolver caso y validar diagnóstico"]},
        [("Ejecutar consulta de diagnóstico", "Inferir diagnóstico (árbol y reglas)")], HORIZONTAL)
    casos_de_uso(
        "casos_de_uso_experto_admin",
        {"Experto": ["Gestionar hipótesis y soluciones", "Consultar árbol y reglas",
                     "Gestionar preguntas (síntomas)", "Consultar gránulos por hipótesis"]},
        {"Administrador": ["Gestionar usuarios y roles", "Supervisar todos los casos", "Consultar reportes"]},
        [], HORIZONTAL)


# ====================================================================== flujo de datos

class LienzoDFD:
    """Diagrama de flujo de datos con la notación de Gane y Sarson y coordenadas explícitas (pulgadas)."""

    COLOR = "black"

    def __init__(self, ancho: float, alto: float):
        self.fig = plt.figure(figsize=(ancho, alto))
        self.ax = self.fig.add_axes([0, 0, 1, 1])
        self.ax.set_xlim(0, ancho)
        self.ax.set_ylim(0, alto)
        self.ax.axis("off")
        self.formas: dict[str, tuple[float, float, float, float]] = {}

    def borde(self, clave: str, lado: str, d: float = 0.0) -> tuple[float, float]:
        """Punto del borde (n, s, e, w) de una forma, desplazado d a lo largo de ese lado."""
        cx, cy, w, h = self.formas[clave]
        return {"n": (cx + d, cy + h / 2), "s": (cx + d, cy - h / 2),
                "e": (cx + w / 2, cy + d), "w": (cx - w / 2, cy + d)}[lado]

    def entidad(self, clave: str, cx: float, cy: float, texto: str, w: float = 0.95, h: float = 0.46,
                repetida: bool = False, dibujar_texto: bool = True) -> None:
        self.formas[clave] = (cx, cy, w, h)
        self.ax.add_patch(Rectangle((cx - w / 2, cy - h / 2), w, h, fc="white", ec="black", lw=1.2))
        if dibujar_texto:
            self.ax.text(cx, cy, texto, ha="center", va="center", fontsize=9, color="black", linespacing=1.1)
        if repetida:   # marca de entidad repetida: diagonal en la esquina inferior derecha
            s = 0.15
            x1, y0 = cx + w / 2, cy - h / 2
            self.ax.plot([x1 - s, x1], [y0, y0 + s], color="black", lw=1.2, solid_capstyle="butt")

    def proceso(self, clave: str, cx: float, cy: float, numero: str, texto: str, w: float = 1.15,
                h: float = 0.84, dibujar_texto: bool = True) -> None:
        self.formas[clave] = (cx, cy, w, h)
        x0, y0 = cx - w / 2, cy - h / 2
        self.ax.add_patch(FancyBboxPatch((x0, y0), w, h, boxstyle="round,pad=0,rounding_size=0.09",
                                         fc="white", ec="black", lw=1.2))
        self.ax.plot([x0, x0 + w], [y0 + h - 0.22, y0 + h - 0.22], color="black", lw=1.0)
        if dibujar_texto:
            self.ax.text(cx, y0 + h - 0.11, numero, ha="center", va="center", fontsize=8.5,
                         fontweight="bold", color="black")
            self.ax.text(cx, y0 + (h - 0.22) / 2, texto, ha="center", va="center", fontsize=8.5,
                         color="black", linespacing=1.1)

    def almacen(self, clave: str, cx: float, cy: float, codigo: str, texto: str, w: float,
                h: float = 0.46, dibujar_texto: bool = True) -> None:
        """Almacén de datos: rectángulo abierto por la derecha, con su código en una celda a la izquierda."""
        self.formas[clave] = (cx, cy, w, h)
        x0, y0, ancho_id = cx - w / 2, cy - h / 2, 0.38
        self.ax.add_patch(Rectangle((x0, y0), ancho_id, h, fc="white", ec="black", lw=1.2))
        for y in (y0, y0 + h):
            self.ax.plot([x0 + ancho_id, x0 + w], [y, y], color="black", lw=1.2, solid_capstyle="butt")
        if dibujar_texto:
            self.ax.text(x0 + ancho_id / 2, cy, codigo, ha="center", va="center", fontsize=8.5,
                         fontweight="bold", color="black")
            self.ax.text(x0 + ancho_id + (w - ancho_id) / 2, cy, texto, ha="center", va="center",
                         fontsize=8.5, color="black", linespacing=1.1)

    def flujo(self, puntos: list[tuple[float, float]], etiqueta: str = "",
              pos: tuple[float, float] | None = None, ha: str = "center", va: str = "center") -> None:
        """Flecha poligonal (la punta va en el último tramo) con su etiqueta."""
        for a, b in zip(puntos[:-2], puntos[1:-1]):
            self.ax.plot([a[0], b[0]], [a[1], b[1]], color=self.COLOR, lw=1.0, solid_capstyle="butt")
        a, b = puntos[-2], puntos[-1]
        self.ax.annotate("", xy=b, xytext=a, arrowprops=dict(
            arrowstyle="-|>", color=self.COLOR, lw=1.0, shrinkA=0, shrinkB=0, mutation_scale=9))
        if etiqueta:
            x, y = pos if pos else ((a[0] + b[0]) / 2, (a[1] + b[1]) / 2)
            self.ax.text(x, y, etiqueta, ha=ha, va=va, fontsize=7.8, color="black", linespacing=1.05,
                         bbox=dict(boxstyle="square,pad=0.05", fc="white", ec="none"))

    def leyenda(self, x: float, y: float) -> None:
        """Notación usada, en la esquina inferior izquierda."""
        f, paso = 7.8, 0.2
        self.ax.text(x, y + 4 * paso, "Notación", fontsize=f, fontweight="bold", va="center", color="black")
        self.ax.add_patch(Rectangle((x, y + 3 * paso - 0.06), 0.3, 0.13, fc="white", ec="black", lw=1.0))
        self.ax.text(x + 0.4, y + 3 * paso, "Entidad externa", fontsize=f, va="center", color="black")
        self.ax.add_patch(FancyBboxPatch((x, y + 2 * paso - 0.06), 0.3, 0.13,
                                         boxstyle="round,pad=0,rounding_size=0.04", fc="white", ec="black", lw=1.0))
        self.ax.text(x + 0.4, y + 2 * paso, "Proceso", fontsize=f, va="center", color="black")
        for yy in (y + paso - 0.06, y + paso + 0.07):
            self.ax.plot([x, x + 0.3], [yy, yy], color="black", lw=1.0)
        self.ax.plot([x, x], [y + paso - 0.06, y + paso + 0.07], color="black", lw=1.0)
        self.ax.text(x + 0.4, y + paso, "Almacén de datos", fontsize=f, va="center", color="black")
        self.ax.annotate("", xy=(x + 0.3, y), xytext=(x, y), arrowprops=dict(
            arrowstyle="-|>", color=self.COLOR, lw=1.0, shrinkA=0, shrinkB=0, mutation_scale=7))
        self.ax.text(x + 0.4, y, "Flujo de datos", fontsize=f, va="center", color="black")
        self.ax.add_patch(Rectangle((x + 1.45, y - 0.065), 0.3, 0.13, fc="white", ec="black", lw=1.0))
        self.ax.plot([x + 1.67, x + 1.75], [y - 0.065, y + 0.015], color="black", lw=1.0, solid_capstyle="butt")
        self.ax.text(x + 1.85, y, "Entidad repetida", fontsize=f, va="center", color="black")

    def guardar(self, nombre: str, limite: tuple[float, float]) -> None:
        SALIDA.mkdir(parents=True, exist_ok=True)
        for formato in ("png", "svg"):
            self.fig.savefig(SALIDA / f"{nombre}.{formato}", dpi=DPI)
        plt.close(self.fig)
        registrar_medida(nombre, limite)


def dfd_nivel_0() -> None:
    """Diagrama de contexto: el sistema de inferencia como un solo proceso y sus tres actores."""
    L = LienzoDFD(6.5, 3.0)
    L.proceso("P0", 3.25, 0.95, "0", "Sistema experto de\ndiagnóstico de fallas\nde computadores", w=2.1, h=1.2)
    L.entidad("CL", 0.62, 0.95, "Cliente", 0.95, 0.5)
    L.entidad("TE", 5.88, 0.95, "Técnico", 0.95, 0.5)
    L.entidad("EX", 3.25, 2.52, "Experto", 0.95, 0.5)
    L.flujo([L.borde("CL", "e", 0.13), L.borde("P0", "w", 0.13)], "respuesta\nsí/no", pos=(1.66, 1.45))
    L.flujo([L.borde("P0", "w", -0.13), L.borde("CL", "e", -0.13)], "preguntas,\ndiagnóstico\ny solución", pos=(1.66, 0.36))
    L.flujo([L.borde("TE", "w", 0.13), L.borde("P0", "e", 0.13)], "seguimiento y\nvalidación", pos=(4.84, 1.45))
    L.flujo([L.borde("P0", "e", -0.13), L.borde("TE", "w", -0.13)], "caso\ndiagnosticado", pos=(4.84, 0.42))
    L.flujo([L.borde("EX", "s", -0.2), L.borde("P0", "n", -0.2)], "cambios al\nconocimiento", pos=(3.0, 1.9), ha="right")
    L.flujo([L.borde("P0", "n", 0.2), L.borde("EX", "s", 0.2)], "árbol, reglas\ny gránulos", pos=(3.5, 1.9), ha="left")
    L.guardar("dfd_nivel_0", VERTICAL)


def dfd_nivel_1() -> None:
    """Descomposición del proceso 0: subprocesos de la inferencia, la atención del caso y el conocimiento."""
    L = LienzoDFD(9.0, 5.3)
    ym, ys, yi = 2.95, 4.72, 1.5   # fila de procesos, fila superior, fila de almacenes inferiores
    # fila superior: conocimiento y salida al cliente
    L.entidad("EX", 0.5, ys, "Experto", 0.85, 0.46)
    L.proceso("P6", 2.3, ys, "6", "Mantener\nconocimiento")
    L.almacen("D1", 5.75, ys, "D1", "Base de conocimiento\n(hipótesis, síntomas, árbol y reglas)", 4.0)
    L.entidad("CL2", 8.45, ys, "Cliente", 0.9, 0.46, repetida=True)
    # fila central: cadena de inferencia
    L.entidad("CL", 0.5, ym, "Cliente", 0.85, 0.46)
    L.proceso("P1", 2.0, ym, "1", "Gestionar\nconsulta")
    L.proceso("P2", 3.95, ym, "2", "Seleccionar\nsiguiente\npregunta")
    L.proceso("P3", 5.9, ym, "3", "Evaluar\nreglas")
    L.proceso("P4", 7.85, ym, "4", "Emitir\ndiagnóstico")
    # fila inferior
    L.almacen("D2", 3.45, yi, "D2", "Casos, consultas\ny respuestas", 1.75)
    L.proceso("P5", 5.1, 0.74, "5", "Atender caso", w=1.2)
    L.almacen("D3", 7.6, 0.98, "D3", "Diagnósticos\ny seguimientos", 1.7, h=0.62)
    L.entidad("TE", 2.45, 0.74, "Técnico", 0.85, 0.46)

    # --- Cliente <-> proceso 1
    L.flujo([L.borde("CL", "e", 0.1), L.borde("P1", "w", 0.1)], "respuesta\nsí/no", pos=(1.175, 3.33))
    L.flujo([L.borde("P1", "w", -0.1), L.borde("CL", "e", -0.1)], "pregunta\nactual", pos=(1.175, 2.58))
    # --- cadena de inferencia
    L.flujo([L.borde("P1", "e", 0.12), L.borde("P2", "w", 0.12)], "nodo actual\ny respuesta", pos=(2.975, 3.3))
    L.flujo([L.borde("P2", "w", -0.12), L.borde("P1", "e", -0.12)], "siguiente\npregunta", pos=(2.975, 2.58))
    L.flujo([L.borde("P2", "e"), L.borde("P3", "w")], "hoja\nalcanzada", pos=(4.925, 3.19))
    L.flujo([L.borde("P3", "e"), L.borde("P4", "w")], "regla\ny FC", pos=(6.875, 3.19))
    # --- almacén de conocimiento hacia los procesos 2, 3 y 4
    L.flujo([(4.1, 4.49), L.borde("P2", "n", 0.15)], "nodo hijo\ny pregunta", pos=(4.17, 3.9), ha="left")
    L.flujo([(5.9, 4.49), L.borde("P3", "n")], "reglas y\ncondiciones", pos=(5.97, 3.9), ha="left")
    L.flujo([(7.55, 4.49), L.borde("P4", "n", -0.3)], "hipótesis\ny solución", pos=(7.48, 3.9), ha="right")
    # --- diagnóstico al cliente
    L.flujo([L.borde("P4", "n", 0.35), (8.2, 4.49)], "diagnóstico\ny solución", pos=(8.27, 3.9), ha="left")
    # --- conocimiento: experto -> proceso 6 -> D1
    L.flujo([L.borde("EX", "e", 0.1), L.borde("P6", "w", 0.1)], "cambios al\nconocimiento", pos=(1.26, 5.13))
    L.flujo([L.borde("P6", "w", -0.1), L.borde("EX", "e", -0.1)], "árbol, reglas\ny gránulos", pos=(1.26, 4.3))
    L.flujo([L.borde("P6", "e", 0.1), L.borde("D1", "w", 0.1)], "conocimiento\nactualizado", pos=(3.37, 5.13))
    L.flujo([L.borde("D1", "w", -0.1), L.borde("P6", "e", -0.1)], "conocimiento\nvigente", pos=(3.37, 4.3))
    # --- almacenes D2 y D3
    L.flujo([L.borde("P1", "s", 0.0), (2.0, yi), L.borde("D2", "w")], "respuesta\nregistrada", pos=(1.93, 2.0), ha="right")
    L.flujo([L.borde("D2", "e"), (5.65, yi), L.borde("P3", "s", -0.25)], "evidencia", pos=(4.85, yi + 0.15))
    L.flujo([L.borde("P4", "s", -0.3), (7.55, 1.29)], "diagnóstico\nemitido", pos=(7.48, 2.0), ha="right")
    L.flujo([(6.75, 1.1), (5.7, 1.1)], "diagnóstico\ndel caso", pos=(6.22, 1.37))
    L.flujo([(5.7, 0.82), (6.75, 0.82)], "confirmación", pos=(6.22, 0.64))
    L.flujo([L.borde("TE", "e", 0.12), L.borde("P5", "w", 0.12)], "seguimiento y\nvalidación", pos=(3.78, 1.12))
    L.flujo([L.borde("P5", "w", -0.12), L.borde("TE", "e", -0.12)], "caso\ndiagnosticado", pos=(3.78, 0.4))
    L.leyenda(0.1, 0.12)
    L.guardar("dfd_nivel_1_inferencia", HORIZONTAL)


def dfd() -> None:
    dfd_nivel_0()
    dfd_nivel_1()


# ====================================================================== clases DAO

def clase(nombre: str, atributos: list[str], metodos: list[str], estereotipo: str = "") -> str:
    def filas(items: list[str]) -> str:
        return "".join(f'<TR><TD ALIGN="LEFT">{esc(i)}</TD></TR>' for i in items) or '<TR><TD> </TD></TR>'
    cab = f'<FONT POINT-SIZE="8">{esc(estereotipo)}</FONT><BR/>' if estereotipo else ""
    cuerpo = f"<HR/>{filas(atributos)}" if atributos else ""
    cuerpo += f"<HR/>{filas(metodos)}" if metodos else ""
    return (f'{nombre} [shape=none, margin=0, fontsize=8.5, label=<<TABLE BORDER="1" CELLBORDER="0" '
            f'CELLSPACING="0" CELLPADDING="2"><TR><TD>{cab}<B>{esc(nombre)}</B></TD></TR>'
            f'{cuerpo}</TABLE>>];')


BASE_DAO = clase("BaseDAO", ["#conexion: Connection"],
                 ["#_uno(sql, parametros)", "#_todos(sql, parametros)", "#_ejecutar(sql, parametros)"],
                 "«abstracta»")


def diagrama_clases(nombre: str, daos: list[tuple[str, list[str]]], entidades: list[tuple[str, list[str], list[str]]],
                    pares: list[tuple[str, str]], separacion: str = "0.2") -> None:
    """Tres niveles: BaseDAO (arriba), un DAO por tabla (centro) y la entidad que cada DAO crea (abajo)."""
    lineas = ["digraph dao {", CABECERA, f"rankdir=TB; nodesep={separacion}; ranksep=0.42;", BASE_DAO]
    for dao, metodos in daos:
        lineas.append(clase(dao, [], metodos))
        lineas.append(f'BaseDAO -> {dao} [dir=back, arrowtail=empty];')
    for ent, atributos, metodos in entidades:
        lineas.append(clase(ent, atributos, metodos, "«entidad»"))
    for dao, ent in pares:
        lineas.append(f'{dao} -> {ent} [style=dashed, arrowhead=open, fontsize=8, label=" «crea»"];')
    lineas.append("{rank=same; " + "; ".join(d for d, _ in daos) + "}")
    lineas.append("{rank=same; " + "; ".join(e for e, _, _ in entidades) + "}")
    lineas.append("}")
    render(nombre, "\n".join(lineas), HORIZONTAL)


def clases_dao() -> None:
    diagrama_clases(
        "clases_dao_conocimiento",
        [("CategoriaDAO", ["+listar()"]),
         ("SintomaDAO", ["+listar()", "+obtener(id)", "+actualizar_pregunta(id, texto)"]),
         ("HipotesisDAO", ["+listar()", "+obtener(id)", "+obtener_por_codigo(codigo)",
                           "+listar_por_categoria(id)", "+actualizar(id, …)"]),
         ("NodoArbolDAO", ["+raiz()", "+obtener(id)", "+hijo(id, rama)", "+listar()", "+contar_hojas()"]),
         ("ReglaDAO", ["+listar()", "+obtener(id)", "+por_hipotesis(id)"])],
        [("Categoria", ["id", "codigo", "nombre", "descripcion"], []),
         ("Sintoma", ["id", "codigo", "pregunta"], []),
         ("Hipotesis", ["id", "codigo", "nombre", "categoria", "severidad", "factor_certeza", "solucion"], []),
         ("NodoArbol", ["id", "codigo", "padre_id", "rama", "sintoma_id", "hipotesis_id"], ["+es_hoja(): bool"]),
         ("Regla", ["id", "codigo", "hipotesis_id", "factor_certeza", "condiciones"], [])],
        [("CategoriaDAO", "Categoria"), ("SintomaDAO", "Sintoma"), ("HipotesisDAO", "Hipotesis"),
         ("NodoArbolDAO", "NodoArbol"), ("ReglaDAO", "Regla")])
    diagrama_clases(
        "clases_dao_usuarios_casos",
        [("RolDAO", ["+listar()", "+id_por_nombre(nombre)"]),
         ("UsuarioDAO", ["+crear(nombre, correo, hash, rol)", "+obtener(id)", "+obtener_credenciales(correo)",
                         "+listar()", "+listar_por_rol(rol)", "+cambiar_estado(id, activo)",
                         "+cambiar_rol(id, rol_id)", "+cambiar_clave(id, hash)"]),
         ("EquipoDAO", ["+crear(cliente, tipo, marca, …)", "+obtener(id)", "+listar_por_cliente(id)",
                        "+actualizar(id, …)", "+eliminar(id)", "+tiene_casos(id)"]),
         ("CasoDAO", ["+crear(equipo, cliente, texto)", "+obtener(id)", "+listar(cliente, tecnico, estado)",
                      "+cola_sin_tecnico()", "+cambiar_estado(id, estado)", "+asignar_tecnico(id, tecnico)",
                      "+contar_por_estado()"])],
        [("Rol", ["id", "nombre", "descripcion"], []),
         ("Usuario", ["id", "nombre", "correo", "rol", "activo"], []),
         ("Equipo", ["id", "cliente_id", "tipo", "marca", "modelo", "serial"], []),
         ("Caso", ["id", "equipo_id", "cliente_id", "tecnico_id", "descripcion", "estado"], [])],
        [("RolDAO", "Rol"), ("UsuarioDAO", "Usuario"), ("EquipoDAO", "Equipo"), ("CasoDAO", "Caso")])
    diagrama_clases(
        "clases_dao_consulta_diagnostico",
        [("ConsultaDAO", ["+crear(caso, nodo)", "+obtener(id)", "+ultima_por_caso(caso)",
                          "+mover_a_nodo(id, nodo)", "+finalizar(id, hoja)"]),
         ("RespuestaDAO", ["+registrar(consulta, nodo, …)", "+listar(consulta)", "+ultima(consulta)",
                           "+eliminar(id)"]),
         ("DiagnosticoDAO", ["+crear(consulta, hipotesis, regla, fc)", "+por_consulta(id)", "+por_caso(id)",
                             "+confirmar(id, correcto)", "+frecuencia_por_hipotesis()"]),
         ("SeguimientoDAO", ["+crear(caso, tecnico, observacion, accion)", "+listar_por_caso(id)"])],
        [("Consulta", ["id", "caso_id", "nodo_actual_id", "estado"], []),
         ("Respuesta", ["id", "consulta_id", "nodo_id", "sintoma_id", "valor", "orden"], []),
         ("Diagnostico", ["id", "consulta_id", "hipotesis_id", "regla_id", "factor_certeza", "confirmado"], []),
         ("Seguimiento", ["id", "caso_id", "tecnico_id", "observacion", "accion_realizada"], [])],
        [("ConsultaDAO", "Consulta"), ("RespuestaDAO", "Respuesta"), ("DiagnosticoDAO", "Diagnostico"),
         ("SeguimientoDAO", "Seguimiento")])


def main() -> None:
    k = json.loads(CONOCIMIENTO.read_text(encoding="utf-8"))
    (RAIZ / "docs" / "salidas").mkdir(parents=True, exist_ok=True)
    SALIDA.mkdir(parents=True, exist_ok=True)
    for viejo_archivo in SALIDA.glob("*.*"):   # se regenera todo: no quedan diagramas de versiones anteriores
        viejo_archivo.unlink()
    arbol = Arbol(k)
    dibujar_completo(arbol)
    dibujar_tronco(arbol)
    for nombre, raices in (("arbol_N02", ["N02"]), ("arbol_N06_N08", ["N06", "N08"]), ("arbol_N11", ["N11"]),
                           ("arbol_N16", ["N16"]), ("arbol_N20", ["N20"]), ("arbol_N25", ["N25"]),
                           ("arbol_N28_N30", ["N28", "N30"])):
        render(nombre, dot_subarbol(arbol, raices), HORIZONTAL)
    con = sqlite3.connect(BD)
    modelo_relacional(con)
    con.close()
    arquitectura()
    diagramas_casos_de_uso()
    dfd()
    clases_dao()
    (SALIDA / "medidas.json").write_text(json.dumps(MEDIDAS, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
