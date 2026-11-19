"""Construye el documento del proyecto (Markdown y Word en blanco y negro).

    python -m scripts.construir_documento

Entrada:  docs/fuente/documento.md + docs/adr/adrs.py + docs/diagramas/*.png
Salida:   docs/documento-proyecto.md y docs/Documento_Proyecto_Final_Computacion_Nube.docx
Requiere: pandoc y python-docx.
"""
from __future__ import annotations

import importlib.util
import os
import subprocess

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

RAIZ = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOCS = os.path.join(RAIZ, "docs")
NEGRO = RGBColor(0, 0, 0)


def _adrs():
    spec = importlib.util.spec_from_file_location("adrs", os.path.join(DOCS, "adr", "adrs.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def markdown() -> str:
    m = _adrs()
    resumen = ["| ID | Decisión | Alternativas evaluadas | Estado |", "|---|---|---|---|"]
    resumen += [f"| {a['id']} | {a['titulo']} | {a['alternativas']} | {a['estado']} |" for a in m.ADRS]
    seccion = (
        "# 5. Registro de decisiones de arquitectura (ADR)\n\n"
        f"Se documentan {len(m.ADRS)} decisiones. Cada una registra contexto, alternativas, justificación técnica "
        "y criterio FinOps. También están como archivos individuales en `docs/adr/`.\n\n"
        + "\n".join(resumen) + "\n\n" + m.detalle()
    )
    with open(os.path.join(DOCS, "fuente", "documento.md"), encoding="utf-8") as f:
        texto = f.read().replace("<!-- ADRS -->", seccion)
    with open(os.path.join(DOCS, "documento-proyecto.md"), "w", encoding="utf-8") as f:
        f.write(texto)
    return os.path.join(DOCS, "documento-proyecto.md")


def _bordes(tabla) -> None:
    tblPr = tabla._tbl.tblPr
    for viejo in tblPr.findall(qn("w:tblBorders")):
        tblPr.remove(viejo)
    bordes = OxmlElement("w:tblBorders")
    for lado in ("top", "left", "bottom", "right", "insideH", "insideV"):
        e = OxmlElement(f"w:{lado}")
        e.set(qn("w:val"), "single")
        e.set(qn("w:sz"), "6")
        e.set(qn("w:color"), "000000")
        bordes.append(e)
    tblPr.append(bordes)


def _sin_sombreado(celda) -> None:
    tcPr = celda._tc.get_or_add_tcPr()
    for s in tcPr.findall(qn("w:shd")):
        tcPr.remove(s)
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), "FFFFFF")
    tcPr.append(shd)


def word(md: str) -> str:
    salida = os.path.join(DOCS, "Documento_Proyecto_Final_Computacion_Nube.docx")
    subprocess.run(
        ["pandoc", md, "-o", salida, "--toc", "--toc-depth=2", f"--resource-path={DOCS}", "-M", "toc-title=Contenido"],
        check=True,
    )
    doc = Document(salida)
    for sec in doc.sections:
        sec.page_width, sec.page_height = Cm(21.59), Cm(27.94)  # carta
        sec.left_margin = sec.right_margin = Cm(2.2)
        sec.top_margin = sec.bottom_margin = Cm(2.0)
    ancho = doc.sections[0].page_width - doc.sections[0].left_margin - doc.sections[0].right_margin

    for estilo in doc.styles:
        if estilo.type == 1 and estilo.font is not None:  # estilos de párrafo
            estilo.font.color.rgb = NEGRO
            estilo.font.name = "Arial"
    for nombre, tam in (("Normal", 11), ("Body Text", 11), ("First Paragraph", 11), ("Compact", 10),
                        ("Heading 1", 15), ("Heading 2", 12.5), ("Heading 3", 11.5), ("Title", 20), ("Subtitle", 13)):
        estilo = {s.name: s for s in doc.styles}.get(nombre)
        if estilo is not None:
            estilo.font.size = Pt(tam)
            estilo.font.color.rgb = NEGRO
            if nombre.startswith("Heading") or nombre == "Title":
                estilo.font.bold = True

    for p in doc.paragraphs:
        for r in p.runs:
            r.font.color.rgb = NEGRO
            r.font.name = "Arial"
        if p.style.name in ("Title", "Subtitle", "Author", "Date"):
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if p.style.name in ("Body Text", "First Paragraph"):
            p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        for etiqueta in ("wp:extent", "a:ext"):  # imágenes al ancho útil de la página (máx. 60 % de alto)
            for img in p._p.iter(qn(etiqueta)):
                cx, cy = int(img.get("cx")), int(img.get("cy"))
                escala = min(ancho / cx, (doc.sections[0].page_height * 0.6) / cy)
                img.set("cx", str(int(cx * escala)))
                img.set("cy", str(int(cy * escala)))

    for t in doc.tables:
        _bordes(t)
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        for i, fila in enumerate(t.rows):
            for celda in fila.cells:
                _sin_sombreado(celda)
                for p in celda.paragraphs:
                    for r in p.runs:
                        r.font.size = Pt(9)
                        r.font.color.rgb = NEGRO
                        r.font.name = "Arial"
                        if i == 0:
                            r.font.bold = True
    # Word actualiza la tabla de contenido al abrir el archivo
    ajustes = doc.settings.element
    upd = OxmlElement("w:updateFields")
    upd.set(qn("w:val"), "true")
    ajustes.append(upd)
    doc.save(salida)
    return salida


if __name__ == "__main__":
    md = markdown()
    print("Markdown:", md)
    print("Word:", word(md))
