"""Motor mínimo de diagramas: nodos y flechas -> HTML (SVG + cajas) -> PNG.

Cada diagrama se describe en diagramas.py con coordenadas explícitas, para que
el resultado sea estable y fácil de ajustar a mano. Se genera en dos temas:
  color -> repositorio y presentación
  bn    -> documento Word (blanco y negro)
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field

TEMAS = {
    "color": {
        "papel": "#f5f5f4", "tinta": "#2d3142", "suave": "#5b6478", "acento": "#e4672e",
        "azul": "#2f5aa8", "nucleo": "#f8ebe3", "servicio": "#ffffff", "datos": "#ebecee",
        "externo": "#e3e4e6", "borde_ext": "#9aa0aa", "limite": "#ececeb", "chip": "#ffffff",
    },
    "bn": {
        "papel": "#ffffff", "tinta": "#000000", "suave": "#333333", "acento": "#000000",
        "azul": "#000000", "nucleo": "#ffffff", "servicio": "#ffffff", "datos": "#ffffff",
        "externo": "#ffffff", "borde_ext": "#000000", "limite": "#ffffff", "chip": "#ffffff",
    },
}

MONO = "'DejaVu Sans Mono', ui-monospace, monospace"
SANS = "'Inter', 'DejaVu Sans', system-ui, sans-serif"


@dataclass
class Nodo:
    id: str
    x: int
    y: int
    titulo: str
    sub: str = ""
    tag: str = ""
    tipo: str = "servicio"  # nucleo | servicio | datos | externo
    w: int = 260
    h: int = 96


@dataclass
class Flecha:
    puntos: list[tuple[int, int]]
    etiqueta: str = ""
    estilo: str = "interna"  # externa | interna | asincrona | principal
    pos: tuple[int, int] | None = None  # posición manual de la etiqueta (centro)
    doble: bool = False


@dataclass
class Limite:
    x: int
    y: int
    w: int
    h: int
    etiqueta: str
    discontinuo: bool = True
    tono: str = "limite"  # limite | nucleo


@dataclass
class Diagrama:
    nombre: str
    ancho: int
    alto: int
    nodos: list[Nodo] = field(default_factory=list)
    flechas: list[Flecha] = field(default_factory=list)
    limites: list[Limite] = field(default_factory=list)
    notas: list[tuple[int, int, int, str]] = field(default_factory=list)  # x, y, ancho, texto
    leyenda: list[tuple[str, str]] = field(default_factory=list)


LEYENDA_BASE = [
    ("caja:nucleo", "Núcleo del sistema"),
    ("caja:servicio", "Servicio"),
    ("caja:datos", "Datos / almacenamiento"),
    ("caja:externo", "Usuarios / sistemas externos"),
    ("linea:externa", "Petición HTTPS externa"),
    ("linea:interna", "Llamada interna"),
    ("linea:principal", "Flujo principal / IA"),
    ("linea:asincrona", "Asíncrono / de apoyo"),
]


def _trazo(estilo: str, t: dict) -> tuple[str, float, str]:
    return {
        "externa": (t["azul"], 2.0, ""),
        "interna": (t["tinta"], 1.6, ""),
        "principal": (t["acento"], 2.2, ""),
        "asincrona": (t["suave"], 1.6, "6 5"),
    }[estilo]


def _caja(tipo: str, t: dict) -> tuple[str, str, str]:
    """fondo, borde, color del chip."""
    return {
        "nucleo": (t["nucleo"], t["acento"], t["acento"]),
        "servicio": (t["servicio"], t["tinta"], t["suave"]),
        "datos": (t["datos"], t["tinta"], t["suave"]),
        "externo": (t["externo"], t["borde_ext"], t["suave"]),
    }[tipo]


def _etiqueta_pos(f: Flecha) -> tuple[float, float]:
    if f.pos:
        return f.pos
    mejor, largo = (f.puntos[0], f.puntos[1]), -1
    for a, b in zip(f.puntos, f.puntos[1:], strict=False):
        d = abs(a[0] - b[0]) + abs(a[1] - b[1])
        if d > largo:
            mejor, largo = (a, b), d
    (x1, y1), (x2, y2) = mejor
    return (x1 + x2) / 2, (y1 + y2) / 2


def render_html(d: Diagrama, tema: str) -> str:
    t = TEMAS[tema]
    partes: list[str] = []
    svg: list[str] = []
    marcadores = []
    for est in ("externa", "interna", "principal", "asincrona"):
        color, _, _ = _trazo(est, t)
        marcadores.append(
            f'<marker id="m-{est}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
            f'orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{color}"/></marker>'
        )
    svg.append(f'<defs>{"".join(marcadores)}</defs>')

    for li in d.limites:
        fondo = t["nucleo"] if li.tono == "nucleo" else t["limite"]
        borde = t["acento"] if li.tono == "nucleo" else t["borde_ext"]
        dash = 'stroke-dasharray="6 5"' if li.discontinuo else ""
        opac = "0.55" if li.tono == "nucleo" and tema == "color" else "1"
        svg.append(
            f'<rect x="{li.x}" y="{li.y}" width="{li.w}" height="{li.h}" rx="14" fill="{fondo}" fill-opacity="{opac}" '
            f'stroke="{borde}" stroke-width="1.3" {dash}/>'
        )
        color_chip = t["acento"] if li.tono == "nucleo" else t["suave"]
        partes.append(
            f'<div class="limite" style="left:{li.x + 18}px;top:{li.y - 10}px;color:{color_chip};'
            f'background:{t["papel"] if li.tono != "nucleo" else t["papel"]}">{html.escape(li.etiqueta)}</div>'
        )

    for f in d.flechas:
        color, ancho, dash = _trazo(f.estilo, t)
        pts = " ".join(f"{x},{y}" for x, y in f.puntos)
        extra = f'stroke-dasharray="{dash}"' if dash else ""
        inicio = f'marker-start="url(#m-{f.estilo})"' if f.doble else ""
        svg.append(
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="{ancho}" {extra} '
            f'stroke-linejoin="round" marker-end="url(#m-{f.estilo})" {inicio}/>'
        )
        if f.etiqueta:
            x, y = _etiqueta_pos(f)
            partes.append(
                f'<div class="etq" style="left:{x}px;top:{y}px;color:{color}">{html.escape(f.etiqueta)}</div>'
            )

    for n in d.nodos:
        fondo, borde, chip = _caja(n.tipo, t)
        grosor = 2 if n.tipo == "nucleo" else 1.5
        tag = f'<div class="tag" style="color:{chip};border-color:{chip}">{html.escape(n.tag)}</div>' if n.tag else ""
        sub = f'<div class="sub">{n.sub}</div>' if n.sub else ""
        partes.append(
            f'<div class="nodo" style="left:{n.x}px;top:{n.y}px;width:{n.w}px;height:{n.h}px;'
            f'background:{fondo};border:{grosor}px solid {borde}">{tag}'
            f'<div class="tit">{html.escape(n.titulo)}</div>{sub}</div>'
        )

    for x, y, w, texto in d.notas:
        partes.append(f'<div class="nota" style="left:{x}px;top:{y}px;width:{w}px">{texto}</div>')

    if d.leyenda:
        items = []
        for clave, texto in d.leyenda:
            kind, val = clave.split(":")
            if kind == "caja":
                fondo, borde, _ = _caja(val, t)
                muestra = f'<span class="mc" style="background:{fondo};border:1.5px solid {borde}"></span>'
            else:
                color, ancho, dash = _trazo(val, t)
                da = f'stroke-dasharray="{dash}"' if dash else ""
                muestra = (
                    f'<svg width="44" height="12"><line x1="2" y1="6" x2="34" y2="6" stroke="{color}" '
                    f'stroke-width="{ancho}" {da}/><path d="M34,1 L43,6 L34,11 z" fill="{color}"/></svg>'
                )
            items.append(f'<span class="li">{muestra}{html.escape(texto)}</span>')
        partes.append(
            f'<div class="leyenda" style="top:{d.alto - 78}px;border-top:1px solid {t["borde_ext"]}">'
            f'<div class="leytit">LEYENDA</div><div class="leyitems">{"".join(items)}</div></div>'
        )

    css = f"""
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{background:{t["papel"]};}}
    .lienzo{{position:relative;width:{d.ancho}px;height:{d.alto}px;background:{t["papel"]};font-family:{SANS};color:{t["tinta"]}}}
    svg.capa{{position:absolute;left:0;top:0}}
    .nodo{{position:absolute;border-radius:10px;display:flex;flex-direction:column;align-items:center;justify-content:center;padding:22px 12px 10px;text-align:center}}
    .tag{{position:absolute;left:10px;top:9px;font:600 10px {MONO};letter-spacing:.06em;border:1px solid;border-radius:4px;padding:1px 6px;background:{t["chip"]}}}
    .tit{{font-weight:600;font-size:17px;line-height:1.2;color:{t["tinta"]}}}
    .sub{{font:11.5px/1.45 {MONO};color:{t["suave"]};margin-top:5px}}
    .etq{{position:absolute;transform:translate(-50%,-50%);font:600 10.5px {MONO};letter-spacing:.08em;text-transform:uppercase;background:{t["papel"]};padding:2px 6px;white-space:nowrap}}
    .limite{{position:absolute;font:500 10.5px {MONO};letter-spacing:.16em;text-transform:uppercase;padding:2px 8px}}
    .nota{{position:absolute;font-size:12.5px;line-height:1.5;color:{t["suave"]}}}
    .leyenda{{position:absolute;left:40px;right:40px;padding-top:12px}}
    .leytit{{font:500 10.5px {MONO};letter-spacing:.2em;color:{t["suave"]};margin-bottom:10px}}
    .leyitems{{display:flex;flex-wrap:wrap;gap:10px 28px;font-size:12.5px;color:{t["tinta"]}}}
    .li{{display:flex;align-items:center;gap:8px}}
    .mc{{display:inline-block;width:22px;height:14px;border-radius:3px}}
    """
    return (
        f'<!DOCTYPE html><html lang="es"><head><meta charset="utf-8"><title>{html.escape(d.nombre)}</title>'
        f"<style>{css}</style></head><body><div class=\"lienzo\">"
        f'<svg class="capa" width="{d.ancho}" height="{d.alto}">{"".join(svg)}</svg>'
        f'{"".join(partes)}</div></body></html>'
    )
