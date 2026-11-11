"""Genera en Word, con formato APA 7, los dos documentos de la entrega.

    python scripts/generar_documentos.py              # escribe docs/entregables/*.docx
    python scripts/generar_documentos.py --pdf CARPETA   # además deja los PDF de revisión en CARPETA

El contenido sale de la misma base de datos que usa la aplicación (se crea una temporal con el esquema y el
archivo JSON del conocimiento), de modo que las cifras, las reglas y las consultas del manual siempre coinciden
con el sistema. LibreOffice (soffice) y pdftotext se usan solo para saber en qué página cae cada título, tabla y
figura y completar así la tabla de contenido y las listas; lo que se entrega es el archivo .docx.
Requiere python-docx, Graphviz/matplotlib ya ejecutados (docs/diagramas) y las capturas de docs/capturas.
"""
from __future__ import annotations

import argparse
import re
import sys
import tempfile
from pathlib import Path

import documento_formulacion
import documento_manual
from documentos_comun import DESTINO, REFERENCIAS, cargar_datos, construir_estable

DOCUMENTOS = [("1_Formulacion_del_proyecto.docx", documento_formulacion),
              ("2_Manual_tecnico.docx", documento_manual)]
SIN_RESOLVER = re.compile(r"(?:Tabla|Figura|Apéndice) \?|\.{3,}\s*0\s*$", re.MULTILINE)


def main() -> int:
    analizador = argparse.ArgumentParser(description="Genera los documentos de la entrega en formato APA 7.")
    analizador.add_argument("--pdf", type=Path, help="carpeta donde dejar los PDF de revisión")
    argumentos = analizador.parse_args()

    datos = cargar_datos()
    citadas: set[str] = set()
    problemas: list[str] = []
    with tempfile.TemporaryDirectory() as temporal:
        carpeta_pdf = argumentos.pdf or Path(temporal)
        for nombre, modulo in DOCUMENTOS:
            print(f"\n== {nombre}")
            documento, registro, _, paginas = construir_estable(
                lambda previo, m=modulo: m.construir(previo, datos), DESTINO / nombre, carpeta_pdf)
            texto = "\n".join(paginas)
            hallazgos = documento.verificar()
            hallazgos += [f"referencia sin resolver en el PDF: {m.group(0).strip()!r}"
                          for m in SIN_RESOLVER.finditer(texto)]
            tablas = sum(1 for r in registro["rotulos"] if r["tipo"] == "Tabla")
            figuras = len(registro["rotulos"]) - tablas
            print(f"  {len(paginas)} páginas, {tablas} tablas, {figuras} figuras, {len(registro['encabezados'])} "
                  f"títulos; citas: {', '.join(sorted(registro['citas'])) or 'ninguna'}")
            for hallazgo in hallazgos:
                print(f"  ! {hallazgo}")
            problemas += [f"{nombre}: {h}" for h in hallazgos]
            citadas.update(registro["citas"])
    sin_usar = sorted(set(REFERENCIAS) - citadas)
    if sin_usar:
        print(f"\nReferencias registradas que ningún documento cita (no aparecen en las listas): {', '.join(sin_usar)}")
    print("\n" + ("Hay hallazgos por revisar." if problemas else "Sin hallazgos."))
    return 1 if problemas else 0


if __name__ == "__main__":
    sys.exit(main())
