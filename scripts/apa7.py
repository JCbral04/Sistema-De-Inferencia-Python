"""Formato APA 7 (trabajo estudiantil, en español) para documentos Word hechos con python-docx.

Reglas que implementa (Publication Manual of the American Psychological Association, 7.ª ed.):
  * Letter, márgenes de 1 in, Times New Roman 12, interlineado doble y sangría de 0,5 in en cada párrafo.
  * Número de página en el encabezado, arriba a la derecha, en todas las páginas (también en la portada).
  * Portada de estudiante: título en negrita, autores, afiliación, curso, docente y fecha, centrados.
  * Títulos sin numerar: nivel 1 centrado en negrita; nivel 2 a la izquierda en negrita; nivel 3 a la
    izquierda en negrita cursiva.
  * Tablas: «Tabla N» en negrita, título en cursiva, solo filas horizontales (arriba, bajo los
    encabezados y abajo); figuras: «Figura N» en negrita y título en cursiva sobre la imagen; «Nota.» debajo.
  * Apéndices en página nueva, con etiqueta y título centrados en negrita; sus tablas y figuras se
    numeran A1, A2, B1…
  * Citas y referencias: cada cita usada se toma de un registro, y la lista de referencias se arma
    solo con lo citado, en orden alfabético y con sangría francesa.

Mini-lenguaje de marcas en los textos:
  **negrita**  *cursiva*  `código`  {t:id} tabla  {f:id} figura  {a:id} apéndice  {#t:id} {#f:id} solo el número
  {c:clave,clave} cita entre paréntesis   {n:clave} cita narrativa
  [[texto]] marcador amarillo (datos que debe completar la persona)
"""
from __future__ import annotations

import math
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import (WD_ALIGN_PARAGRAPH, WD_BREAK, WD_COLOR_INDEX, WD_TAB_ALIGNMENT,
                            WD_TAB_LEADER)
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

FUENTE = "Times New Roman"
FUENTE_CODIGO = "Courier New"
IDIOMA = "es-CO"
LINEA_DOBLE_PULG = 0.383      # alto de una línea con interlineado doble de Times New Roman 12 pt
TOKEN = re.compile(r"(`[^`]+`|\*\*[^*]+\*\*|\*[^*]+\*|\[\[[^\]]+\]\]|\{#?[tfacn]:[^}]+\})")
URL = re.compile(r"(https?://[^\s)]+)")


def _sin_acentos(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def _texto_plano(texto: str) -> str:
    """Quita las marcas del mini-lenguaje (para medir longitudes y armar índices)."""
    texto = re.sub(r"\{#?[tfacn]:[^}]+\}", "X", texto)
    return re.sub(r"[`*]|\[\[|\]\]", "", texto)


class DocumentoAPA:
    def __init__(self, referencias: dict, previo: dict | None = None, titulo: str = "", autores: str = "",
                 asunto: str = ""):
        self.refs = referencias
        self.previo = previo or {}
        self.doc = Document()
        self.horizontal = False
        self.etiquetas: dict[str, str] = {}      # id -> «Tabla 3»
        self.contadores = {"Tabla": 0, "Figura": 0}
        self.contador_apendice: dict[str, dict[str, int]] = {}
        self.apendice_actual: str | None = None
        self.encabezados: list[dict] = []        # nivel, texto, marcador
        self.rotulos: list[dict] = []            # tipo, etiqueta, titulo, marcador
        self.citas: list[str] = []               # claves en orden de primera aparición
        self._id_marcador = 0
        self._evento = 0
        self.usos: list[tuple[int, str]] = []    # (evento, "t:clave") de cada mención en el texto
        self.creados: dict[str, int] = {}        # "t:clave" -> evento en que se creó el rótulo
        self._configurar(titulo, autores, asunto)

    # ------------------------------------------------------------------ configuración
    def _configurar(self, titulo: str, autores: str, asunto: str) -> None:
        doc = self.doc
        seccion = doc.sections[0]
        self._dimensiones(seccion, horizontal=False)
        seccion.header_distance = Inches(0.5)
        propiedades = doc.core_properties
        propiedades.title, propiedades.author, propiedades.subject = titulo, autores, asunto
        propiedades.language, propiedades.last_modified_by = IDIOMA, autores
        propiedades.comments = "Formato APA 7.ª edición"
        # La plantilla de python-docx trae fechas de 2013; se reemplazan por la fecha real de generación.
        propiedades.created = propiedades.modified = datetime.now(timezone.utc).replace(microsecond=0, tzinfo=None)

        estilos = doc.styles
        defaults = estilos.element.find(qn("w:docDefaults")).find(qn("w:rPrDefault")).find(qn("w:rPr"))
        self._fuente(defaults, FUENTE)
        for etiqueta in ("w:sz", "w:szCs"):
            elemento = defaults.find(qn(etiqueta))
            if elemento is None:
                elemento = OxmlElement(etiqueta)
                defaults.append(elemento)
            elemento.set(qn("w:val"), "24")
        self._idioma(defaults)

        normal = estilos["Normal"]
        self._estilo_base(normal, tam=12, doble=True)
        normal.paragraph_format.widow_control = True

        self._estilo("Texto APA", base="Normal", sangria=0.5)
        self._estilo("Titulo del documento", base="Normal", negrita=True, alinear=WD_ALIGN_PARAGRAPH.CENTER)
        self._estilo("Nota APA", base="Normal")
        self._estilo("Rotulo APA", base="Normal", negrita=True, juntar=True)
        self._estilo("Titulo de rotulo APA", base="Normal", cursiva=True, juntar=True)
        self._estilo("Referencia APA", base="Normal", izquierda=0.5, sangria=-0.5)
        self._estilo("Imagen APA", base="Normal", alinear=WD_ALIGN_PARAGRAPH.CENTER, doble=False, juntar=True)
        self._estilo("Texto de tabla", base="Normal", doble=False, antes=2, despues=2, tam=10)
        codigo = self._estilo("Codigo APA", base="Normal", doble=False, tam=10, fuente=FUENTE_CODIGO,
                              izquierda=0.05)
        sombreado = OxmlElement("w:shd")
        sombreado.set(qn("w:val"), "clear")
        sombreado.set(qn("w:color"), "auto")
        sombreado.set(qn("w:fill"), "F2F2F2")
        codigo.element.get_or_add_pPr().find(qn("w:spacing")).addprevious(sombreado)
        self._estilo("Numero de pagina", base="Normal", doble=False, alinear=WD_ALIGN_PARAGRAPH.RIGHT)
        self._estilo("Titulo de indice", base="Normal", negrita=True, alinear=WD_ALIGN_PARAGRAPH.CENTER,
                     juntar=True)
        for nivel in (1, 2, 3):
            estilo = self._estilo(f"Entrada de indice {nivel}", base="Normal", doble=False, despues=2,
                                  izquierda=0.3 * nivel, sangria=-0.3)
            estilo.paragraph_format.right_indent = Inches(0.45)
            estilo.paragraph_format.tab_stops.add_tab_stop(Inches(6.5), WD_TAB_ALIGNMENT.RIGHT,
                                                           WD_TAB_LEADER.DOTS)

        for nombre, alinear, negrita, cursiva in (("Heading 1", WD_ALIGN_PARAGRAPH.CENTER, True, False),
                                                  ("Heading 2", WD_ALIGN_PARAGRAPH.LEFT, True, False),
                                                  ("Heading 3", WD_ALIGN_PARAGRAPH.LEFT, True, True)):
            estilo = estilos[nombre]
            self._estilo_base(estilo, tam=12, doble=True)
            estilo.font.bold, estilo.font.italic = negrita, cursiva
            estilo.paragraph_format.alignment = alinear
            estilo.paragraph_format.keep_with_next = True
            estilo.paragraph_format.keep_together = True
            estilo.paragraph_format.first_line_indent = Inches(0)

        pie = doc.sections[0].header
        parrafo = pie.paragraphs[0]
        parrafo.style = estilos["Numero de pagina"]
        self._campo(parrafo, "PAGE", "1")

    @staticmethod
    def _dimensiones(seccion, horizontal: bool) -> None:
        ancho, alto = (11.0, 8.5) if horizontal else (8.5, 11.0)
        seccion.orientation = WD_ORIENT.LANDSCAPE if horizontal else WD_ORIENT.PORTRAIT
        seccion.page_width, seccion.page_height = Inches(ancho), Inches(alto)
        for lado in ("left_margin", "right_margin", "top_margin", "bottom_margin"):
            setattr(seccion, lado, Inches(1))

    @staticmethod
    def _fuente(rpr, nombre: str) -> None:
        rfonts = rpr.get_or_add_rFonts()
        for atributo in ("ascii", "hAnsi", "eastAsia", "cs"):
            rfonts.set(qn(f"w:{atributo}"), nombre)
        for atributo in ("asciiTheme", "hAnsiTheme", "eastAsiaTheme", "cstheme"):
            rfonts.attrib.pop(qn(f"w:{atributo}"), None)

    @staticmethod
    def _idioma(rpr) -> None:
        lang = rpr.find(qn("w:lang"))
        if lang is None:
            lang = OxmlElement("w:lang")
            rpr.append(lang)
        lang.set(qn("w:val"), IDIOMA)
        lang.set(qn("w:eastAsia"), IDIOMA)
        lang.set(qn("w:bidi"), "ar-SA")

    def _estilo_base(self, estilo, tam: float, doble: bool, fuente: str = FUENTE) -> None:
        self._fuente(estilo.element.get_or_add_rPr(), fuente)
        estilo.font.size = Pt(tam)
        estilo.font.color.rgb = RGBColor(0, 0, 0)
        formato = estilo.paragraph_format
        formato.space_before = formato.space_after = Pt(0)
        formato.line_spacing = 2.0 if doble else 1.0

    def _estilo(self, nombre: str, base: str, negrita: bool = False, cursiva: bool = False,
                alinear=None, sangria: float = 0.0, izquierda: float = 0.0, doble: bool = True,
                antes: float = 0, despues: float = 0, tam: float = 12, fuente: str = FUENTE,
                juntar: bool = False):
        estilo = self.doc.styles.add_style(nombre, WD_STYLE_TYPE.PARAGRAPH)
        estilo.base_style = self.doc.styles[base]
        estilo.quick_style = True
        self._estilo_base(estilo, tam, doble, fuente)
        estilo.font.bold, estilo.font.italic = (True if negrita else None), (True if cursiva else None)
        formato = estilo.paragraph_format
        formato.space_before, formato.space_after = Pt(antes), Pt(despues)
        formato.first_line_indent = Inches(sangria)
        formato.left_indent = Inches(izquierda)
        formato.alignment = alinear if alinear is not None else WD_ALIGN_PARAGRAPH.LEFT
        formato.keep_with_next = juntar
        return estilo

    # ------------------------------------------------------------------ campos y marcadores
    @staticmethod
    def _campo(parrafo, instruccion: str, resultado: str, negrita: bool | None = None,
               cursiva: bool | None = None):
        """Campo de Word (begin, instrucción, separate, resultado, end); devuelve su primer y último w:r."""
        def ejecutar():
            r = parrafo.add_run()
            r.bold, r.italic = negrita, cursiva
            return r

        elementos = []
        for tipo in ("begin", "instr", "separate", "texto", "end"):
            r = ejecutar()
            elementos.append(r._r)
            if tipo == "instr":
                elemento = OxmlElement("w:instrText")
                elemento.set(qn("xml:space"), "preserve")
                elemento.text = f" {instruccion} "
                r._r.append(elemento)
            elif tipo == "texto":
                r.text = resultado
            else:
                elemento = OxmlElement("w:fldChar")
                elemento.set(qn("w:fldCharType"), tipo)
                r._r.append(elemento)
        return elementos[0], elementos[-1]

    def _marcador(self, parrafo, nombre: str, desde=None, hasta=None) -> None:
        """Marcador sobre todo el párrafo o, si se indican, entre dos runs (elementos w:r)."""
        self._id_marcador += 1
        inicio = OxmlElement("w:bookmarkStart")
        inicio.set(qn("w:id"), str(self._id_marcador))
        inicio.set(qn("w:name"), nombre)
        fin = OxmlElement("w:bookmarkEnd")
        fin.set(qn("w:id"), str(self._id_marcador))
        p = parrafo._p
        if desde is not None:
            desde.addprevious(inicio)
            hasta.addnext(fin)
            return
        propiedades = p.find(qn("w:pPr"))
        if propiedades is not None:
            propiedades.addnext(inicio)
        else:
            p.insert(0, inicio)
        p.append(fin)

    def _enlace(self, parrafo, url: str, negrita=None, cursiva=None, tam=None) -> None:
        r_id = parrafo.part.relate_to(url, RT.HYPERLINK, is_external=True)
        enlace = OxmlElement("w:hyperlink")
        enlace.set(qn("r:id"), r_id)
        enlace.set(qn("w:history"), "1")
        run = parrafo.add_run(url)
        run.bold, run.italic = negrita, cursiva
        if tam:
            run.font.size = Pt(tam)
        enlace.append(run._r)
        parrafo._p.append(enlace)

    # ------------------------------------------------------------------ citas
    def _cita(self, clave: str, narrativa: bool) -> str:
        """Forma de la cita; el autor corporativo con sigla se presenta completo la primera vez."""
        ref = self.refs[clave]
        primera = clave not in self.citas
        if primera:
            self.citas.append(clave)
        autor, anio, sigla = ref["cita"], ref["anio"], ref.get("abrev")
        if sigla:
            if primera:
                return f"{autor} ({sigla}, {anio})" if narrativa else f"{autor} [{sigla}], {anio}"
            return f"{sigla} ({anio})" if narrativa else f"{sigla}, {anio}"
        return f"{autor} ({anio})" if narrativa else f"{autor}, {anio}"

    def _expandir_cita(self, marca: str) -> str:
        tipo, contenido = marca[1], marca[3:-1]
        claves = [c.strip() for c in contenido.split(",")]
        if tipo == "n":
            return self._cita(claves[0], narrativa=True)
        claves = sorted(claves, key=lambda k: (_sin_acentos(self.refs[k]["cita"]).lower(), self.refs[k]["anio"]))
        return "(" + "; ".join(self._cita(c, narrativa=False) for c in claves) + ")"

    # ------------------------------------------------------------------ texto enriquecido
    def _runs(self, parrafo, texto: str, negrita: bool | None = None, cursiva: bool | None = None,
              tam: float | None = None) -> None:
        for trozo in TOKEN.split(texto):
            if not trozo:
                continue
            if trozo.startswith("`"):
                r = parrafo.add_run(trozo[1:-1])
                r.bold, r.italic = negrita, cursiva
                self._fuente(r._r.get_or_add_rPr(), FUENTE_CODIGO)
                r.font.size = Pt(10 if not tam else min(tam, 10))
            elif trozo.startswith("**"):
                self._runs(parrafo, trozo[2:-2], True, cursiva, tam)
            elif trozo.startswith("*"):
                self._runs(parrafo, trozo[1:-1], negrita, True, tam)
            elif trozo.startswith("[["):
                r = parrafo.add_run(f"[{trozo[2:-2]}]")
                r.bold, r.italic = negrita, cursiva
                r.font.highlight_color = WD_COLOR_INDEX.YELLOW
                if tam:
                    r.font.size = Pt(tam)
            elif trozo[0] == "{" and trozo[1] == "#":
                tipo, clave = trozo[2], trozo[4:-1]
                self._evento += 1
                self.usos.append((self._evento, f"{tipo}:{clave}"))
                etiqueta = self.previo.get("etiquetas", {}).get(f"{tipo}:{clave}", "?")
                self._campo(parrafo, f"REF _Num_{tipo}_{clave} \\h \\* MERGEFORMAT", etiqueta.split(" ", 1)[-1],
                            negrita, cursiva)
            elif trozo[0] == "{" and trozo[1] in "tfa":
                clave = trozo[3:-1]
                self._evento += 1
                self.usos.append((self._evento, f"{trozo[1]}:{clave}"))
                etiqueta = self.previo.get("etiquetas", {}).get(f"{trozo[1]}:{clave}", "?")
                self._campo(parrafo, f"REF _Ref_{trozo[1]}_{clave} \\h \\* MERGEFORMAT", etiqueta, negrita, cursiva)
            elif trozo[0] == "{":
                self._runs(parrafo, self._expandir_cita(trozo), negrita, cursiva, tam)
            else:
                for parte in URL.split(trozo):
                    if URL.fullmatch(parte):
                        self._enlace(parrafo, parte, negrita, cursiva, tam)
                    elif parte:
                        r = parrafo.add_run(parte)
                        r.bold, r.italic = negrita, cursiva
                        if tam:
                            r.font.size = Pt(tam)

    def _parrafo(self, texto: str = "", estilo: str = "Texto APA", **kw):
        parrafo = self.doc.add_paragraph(style=estilo)
        if texto:
            self._runs(parrafo, texto, **kw)
        return parrafo

    # ------------------------------------------------------------------ estructura
    def portada(self, titulo: str, autores: str, lineas: list[str]) -> None:
        for _ in range(3):
            self._parrafo(estilo="Normal")
        p = self._parrafo(titulo, "Titulo del documento")
        self._parrafo(estilo="Normal")
        for texto in [autores] + lineas:
            p = self._parrafo(texto, "Normal")
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER

    def titulo_inicial(self, titulo: str, nueva_pagina: bool = True) -> None:
        p = self._parrafo(titulo, "Titulo del documento")
        p.paragraph_format.page_break_before = nueva_pagina

    def _encabezado(self, nivel: int, texto: str, marcador: str | None, nueva_pagina: bool):
        self.vertical()
        p = self.doc.add_paragraph(style=f"Heading {nivel}")
        self._runs(p, texto)
        p.paragraph_format.page_break_before = nueva_pagina
        nombre = marcador or f"_Enc_{len(self.encabezados) + 1}"
        self._marcador(p, nombre)
        self.encabezados.append({"nivel": nivel, "texto": _texto_plano(texto), "marcador": nombre})
        return p

    def h1(self, texto: str, marcador: str | None = None, nueva_pagina: bool = False):
        return self._encabezado(1, texto, marcador, nueva_pagina)

    def h2(self, texto: str, marcador: str | None = None):
        return self._encabezado(2, texto, marcador, False)

    def h3(self, texto: str, marcador: str | None = None):
        return self._encabezado(3, texto, marcador, False)

    def p(self, texto: str):
        self.vertical()
        return self._parrafo(texto)

    def sin_sangria(self, texto: str):
        return self._parrafo(texto, "Normal")

    def numerada(self, items: list[str]) -> None:
        for n, texto in enumerate(items, 1):
            self._parrafo(f"{n}. {texto}")

    def seccion(self, horizontal: bool) -> None:
        nueva = self.doc.add_section(WD_SECTION.NEW_PAGE)
        self._dimensiones(nueva, horizontal)
        self.horizontal = horizontal

    def vertical(self) -> None:
        """Vuelve a una página vertical si la sección actual es horizontal (el texto y las tablas son verticales)."""
        if self.horizontal:
            self.seccion(False)

    def salto_de_pagina(self) -> None:
        self.doc.add_paragraph(style="Normal").add_run().add_break(WD_BREAK.PAGE)

    # ------------------------------------------------------------------ rótulos de tablas y figuras
    def _nuevo_rotulo(self, tipo: str, clave: str) -> tuple[str, str]:
        prefijo = "t" if tipo == "Tabla" else "f"
        if self.apendice_actual:
            cuenta = self.contador_apendice[self.apendice_actual]
            cuenta[tipo] = cuenta.get(tipo, 0) + 1
            etiqueta = f"{tipo} {self.apendice_actual}{cuenta[tipo]}"
        else:
            self.contadores[tipo] += 1
            etiqueta = f"{tipo} {self.contadores[tipo]}"
        self.etiquetas[f"{prefijo}:{clave}"] = etiqueta
        return etiqueta, f"_Ref_{prefijo}_{clave}"

    def _rotulo(self, tipo: str, clave: str, titulo: str) -> None:
        etiqueta, marcador = self._nuevo_rotulo(tipo, clave)
        etiqueta_clave = f"{'t' if tipo == 'Tabla' else 'f'}:{clave}"
        p = self.doc.add_paragraph(style="Rotulo APA")
        numero = etiqueta.split(" ", 1)[1]
        p.add_run(f"{tipo} ")
        if self.apendice_actual:
            corrida = p.add_run(numero)
            desde = hasta = corrida._r
        else:
            desde, hasta = self._campo(p, f"SEQ {tipo} \\* ARABIC", numero)
        self._marcador(p, marcador)
        self._marcador(p, marcador.replace("_Ref_", "_Num_", 1), desde, hasta)
        self._evento += 1
        self.creados[etiqueta_clave] = self._evento
        t = self.doc.add_paragraph(style="Titulo de rotulo APA")
        self._runs(t, titulo)
        self.rotulos.append({"tipo": tipo, "etiqueta": etiqueta, "titulo": _texto_plano(titulo),
                             "marcador": marcador})

    def _nota(self, texto: str | None) -> None:
        if texto:
            p = self.doc.add_paragraph(style="Nota APA")
            r = p.add_run("Nota. ")
            r.italic = True
            self._runs(p, texto)

    # ------------------------------------------------------------------ tablas
    @staticmethod
    def _bordes_horizontales(tabla) -> None:
        propiedades = tabla._tbl.tblPr
        bordes = OxmlElement("w:tblBorders")
        for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
            borde = OxmlElement(f"w:{lado}")
            visible = lado in ("top", "bottom")
            borde.set(qn("w:val"), "single" if visible else "nil")
            if visible:
                borde.set(qn("w:sz"), "6")
                borde.set(qn("w:space"), "0")
                borde.set(qn("w:color"), "000000")
            bordes.append(borde)
        for hermano in ("w:shd", "w:tblLayout", "w:tblCellMar", "w:tblLook"):
            siguiente = propiedades.find(qn(hermano))
            if siguiente is not None:
                siguiente.addprevious(bordes)
                break
        else:
            propiedades.append(bordes)

    def tabla(self, clave: str, titulo: str, encabezados: list[str], filas: list[list], anchos: list[float],
              alineacion: str | None = None, nota: str | None = None, tam: float = 10,
              juntas: bool | None = None) -> None:
        self.vertical()
        columnas = len(encabezados)
        alineacion = alineacion or "l" * columnas
        juntas = len(filas) <= 14 if juntas is None else juntas
        self._rotulo("Tabla", clave, titulo)
        tabla = self.doc.add_table(rows=1, cols=columnas)
        tabla.alignment = WD_TABLE_ALIGNMENT.CENTER
        tabla.autofit = False
        self._bordes_horizontales(tabla)
        mapa = {"l": WD_ALIGN_PARAGRAPH.LEFT, "c": WD_ALIGN_PARAGRAPH.CENTER, "r": WD_ALIGN_PARAGRAPH.RIGHT}

        def escribir(celda, texto, alinear, seguir=False):
            lineas = str(texto).split("\n")
            for n, linea in enumerate(lineas):
                parrafo = celda.paragraphs[0] if n == 0 else celda.add_paragraph()
                parrafo.style = self.doc.styles["Texto de tabla"]
                if tam <= 9:      # tablas largas de apéndice: filas más compactas para que no sobre una página
                    parrafo.paragraph_format.space_before = Pt(1)
                    parrafo.paragraph_format.space_after = Pt(1)
                parrafo.alignment = alinear
                parrafo.paragraph_format.keep_with_next = seguir
                self._runs(parrafo, linea, tam=tam)

        for n, texto in enumerate(encabezados):
            celda = tabla.rows[0].cells[n]
            escribir(celda, texto, WD_ALIGN_PARAGRAPH.CENTER, seguir=True)
            bordes = OxmlElement("w:tcBorders")
            inferior = OxmlElement("w:bottom")
            for atributo, valor in (("val", "single"), ("sz", "6"), ("space", "0"), ("color", "000000")):
                inferior.set(qn(f"w:{atributo}"), valor)
            bordes.append(inferior)
            celda._tc.get_or_add_tcPr().append(bordes)
        fila_cabecera = tabla.rows[0]._tr.get_or_add_trPr()
        repetir = OxmlElement("w:tblHeader")
        repetir.set(qn("w:val"), "true")
        fila_cabecera.append(repetir)

        for numero, datos in enumerate(filas):
            fila = tabla.add_row()
            ultima = numero == len(filas) - 1
            for n, texto in enumerate(datos):
                escribir(fila.cells[n], texto, mapa[alineacion[n]],
                         seguir=(juntas and not ultima) or (ultima and bool(nota)))
            indivisible = OxmlElement("w:cantSplit")
            indivisible.set(qn("w:val"), "true")
            fila._tr.get_or_add_trPr().append(indivisible)

        ancho_total = tabla._tbl.tblPr.find(qn("w:tblW"))
        ancho_total.set(qn("w:type"), "dxa")
        ancho_total.set(qn("w:w"), str(int(round(sum(anchos) * 1440))))
        for columna, ancho in enumerate(anchos):
            tabla.columns[columna].width = Inches(ancho)
            for fila in tabla.rows:
                fila.cells[columna].width = Inches(ancho)
        self._nota(nota)
        if not nota:
            self._parrafo(estilo="Normal")

    # ------------------------------------------------------------------ figuras
    def _tamano_figura(self, ancho: float, alto: float, lineas_nota: int) -> tuple[float, float]:
        ancho_util = 9.0 if self.horizontal else 6.5
        alto_util = (6.5 if self.horizontal else 9.0) - LINEA_DOBLE_PULG * (2 + lineas_nota) - 0.2
        escala = min(1.0, ancho_util / ancho, alto_util / alto)
        return ancho * escala, alto * escala

    def figura(self, clave: str, titulo: str, imagen: Path, tamano_nativo: tuple[float, float],
               nota: str | None = None, alt: str = "", ancho_maximo: float | None = None) -> None:
        """Figura; si no cabe en 6,5 in de ancho, va en una página horizontal (se cambia de sección sola)."""
        if (tamano_nativo[0] > 6.51) != self.horizontal:
            self.seccion(tamano_nativo[0] > 6.51)
        self._rotulo("Figura", clave, titulo)
        caracteres = 125 if self.horizontal else 88
        lineas_nota = math.ceil((len(_texto_plano(nota)) + 6) / caracteres) if nota else 0
        ancho, alto = self._tamano_figura(*tamano_nativo, lineas_nota)
        if ancho_maximo and ancho > ancho_maximo:
            alto, ancho = alto * ancho_maximo / ancho, ancho_maximo
        parrafo = self.doc.add_paragraph(style="Imagen APA")
        parrafo.paragraph_format.keep_with_next = bool(nota)
        forma = parrafo.add_run().add_picture(str(imagen), width=Inches(ancho))
        forma._inline.docPr.set("descr", alt or titulo)
        forma._inline.docPr.set("name", f"Figura {clave}")
        self._nota(nota)
        if not nota:
            self._parrafo(estilo="Normal")

    def figura_codigo(self, clave: str, titulo: str, codigo: str, nota: str | None = None,
                      juntas: bool = True) -> None:
        """Código como figura: monoespaciado a 10 pt, interlineado sencillo y fondo gris claro."""
        self.vertical()
        self._rotulo("Figura", clave, titulo)
        lineas = codigo.rstrip("\n").split("\n")
        for n, linea in enumerate(lineas):
            p = self.doc.add_paragraph(style="Codigo APA")
            p.paragraph_format.keep_with_next = (juntas and n < len(lineas) - 1) or (n == len(lineas) - 1 and bool(nota))
            p.paragraph_format.keep_together = True
            p.add_run(linea if linea else " ")
        self._nota(nota)
        if not nota:
            self._parrafo(estilo="Normal")

    # ------------------------------------------------------------------ apéndices
    def apendice(self, letra: str, titulo: str) -> None:
        """Apéndice en página nueva: etiqueta y título centrados en negrita."""
        self.vertical()
        self.apendice_actual = letra
        self.contador_apendice[letra] = {}
        p = self.doc.add_paragraph(style="Heading 1")
        p.paragraph_format.page_break_before = True
        etiqueta = f"Apéndice {letra}"
        run_etiqueta = p.add_run(etiqueta)
        p.add_run().add_break()
        self._runs(p, titulo)
        marcador = f"_Ref_a_{letra}"
        self._marcador(p, marcador, run_etiqueta._r, run_etiqueta._r)
        self.etiquetas[f"a:{letra}"] = etiqueta
        self.encabezados.append({"nivel": 1, "texto": f"{etiqueta}. {_texto_plano(titulo)}", "marcador": marcador,
                                 "busqueda": etiqueta})

    # ------------------------------------------------------------------ índices
    def _entrada(self, estilo: str, texto: str, marcador: str, pagina: str) -> None:
        p = self.doc.add_paragraph(style=estilo)
        enlace = OxmlElement("w:hyperlink")
        enlace.set(qn("w:anchor"), marcador)
        enlace.set(qn("w:history"), "1")
        p._p.append(enlace)
        primero = p.add_run(_texto_plano(texto))
        enlace.append(primero._r)
        tabulacion = p.add_run()
        tabulacion.add_tab()
        enlace.append(tabulacion._r)
        self._campo(p, f"PAGEREF {marcador} \\h", pagina)

    def indice(self, titulo: str, entradas: list[dict], paginas: dict, nueva_pagina: bool = True) -> None:
        t = self._parrafo(titulo, "Titulo de indice")
        t.paragraph_format.page_break_before = nueva_pagina
        t.paragraph_format.space_before = Pt(0 if nueva_pagina else 18)
        t.paragraph_format.space_after = Pt(6)
        for entrada in entradas:
            estilo = f"Entrada de indice {min(entrada.get('nivel', 1), 3)}"
            self._entrada(estilo, entrada["texto"], entrada["marcador"], str(paginas.get(entrada["marcador"], "0")))

    # ------------------------------------------------------------------ referencias
    def referencias(self) -> list[str]:
        self.vertical()
        p = self.doc.add_paragraph(style="Heading 1")
        p.paragraph_format.page_break_before = True
        p.add_run("Referencias")
        self._marcador(p, "_Enc_referencias")
        self.encabezados.append({"nivel": 1, "texto": "Referencias", "marcador": "_Enc_referencias"})
        claves = sorted(self.citas, key=lambda k: re.sub(r"[^a-z0-9]", "", _sin_acentos(self.refs[k]["texto"]).lower()))
        for clave in claves:
            self._parrafo(self.refs[clave]["texto"], "Referencia APA")
        return claves

    # ------------------------------------------------------------------ cierre
    def verificar(self) -> list[str]:
        """Errores si una mención apunta a algo inexistente; avisos si las tablas o figuras no se
        mencionan en el texto antes de aparecer (APA: se numeran en el orden en que se mencionan)."""
        problemas = []
        for _, clave in self.usos:
            if clave not in self.etiquetas:
                problemas.append(f"ERROR: se menciona «{clave}», que no existe")
        primeras: dict[str, int] = {}
        for evento, clave in self.usos:
            primeras.setdefault(clave, evento)
        for clave, evento in self.creados.items():
            if clave not in primeras:
                problemas.append(f"aviso: {self.etiquetas[clave]} ({clave}) nunca se menciona en el texto")
            elif primeras[clave] > evento:
                problemas.append(f"aviso: {self.etiquetas[clave]} ({clave}) aparece antes de su primera mención")
        for tipo in ("t", "f"):
            orden_mencion = [c for c, _ in sorted(((c, e) for c, e in primeras.items() if c.startswith(tipo + ":")),
                                                  key=lambda x: x[1]) if c in self.creados]
            orden_creacion = [c for c in self.creados if c.startswith(tipo + ":") and c in primeras]
            if orden_mencion != orden_creacion:
                problemas.append(f"aviso: el orden de mención de «{tipo}» difiere del orden de aparición")
        return problemas

    def _actualizar_campos_al_abrir(self) -> None:
        """Pide a Word que actualice los campos al abrir: así los índices quedan con las páginas exactas."""
        ajustes = self.doc.settings.element
        if ajustes.find(qn("w:updateFields")) is not None:
            return
        elemento = OxmlElement("w:updateFields")
        elemento.set(qn("w:val"), "true")
        for hermano in ("w:hdrShapeDefaults", "w:footnotePr", "w:endnotePr", "w:compat", "w:docVars", "w:rsids",
                        "m:mathPr", "w:attachedSchema", "w:themeFontLang", "w:clrSchemeMapping",
                        "w:doNotIncludeSubdocsInStats", "w:doNotAutoCompressPictures", "w:forceUpgrade",
                        "w:captions", "w:readModeInkLockDown", "w:smartTagType", "w:schemaLibrary",
                        "w:shapeDefaults", "w:doNotEmbedSmartTags", "w:decimalSymbol", "w:listSeparator"):
            siguiente = ajustes.find(qn(hermano))
            if siguiente is not None:
                siguiente.addprevious(elemento)
                return
        ajustes.append(elemento)

    def guardar(self, ruta: Path) -> dict:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        self._actualizar_campos_al_abrir()
        self.doc.save(ruta)
        return {"etiquetas": self.etiquetas, "encabezados": self.encabezados, "rotulos": self.rotulos,
                "citas": list(self.citas)}
