"""Diagrama entidad-relación en SVG, generado desde el esquema real (PRAGMA de SQLite).

El diagrama no se dibuja a mano: si cambia `modelo/esquema.sql`, se regenera y un test exige que el
SVG publicado esté al día. Los colores usan las variables CSS del sitio, con valores por defecto para
cuando el SVG se abre solo.
"""

from __future__ import annotations

from html import escape

COLUMNAS = [
    ["sede", "programa", "centro_costo", "actividad"],
    ["participante", "participante_identidad", "participante_salud"],
    ["consentimiento", "asistencia", "solicitud_derecho"],
    ["colaborador", "colaborador_identidad", "movimiento_contable", "cuarentena"],
]
ANCHO, FILA, CABECERA, SEP_X, SEP_Y, MARGEN = 262, 17, 24, 70, 26, 12


def svg(esquema: dict, restringidas: set[str]) -> str:
    pos: dict[str, tuple[int, int, int]] = {}
    alto_total = 0
    for i, tablas in enumerate(COLUMNAS):
        y = MARGEN
        for t in tablas:
            alto = CABECERA + FILA * len(esquema[t]["columnas"]) + 6
            pos[t] = (MARGEN + i * (ANCHO + SEP_X), y, alto)
            y += alto + SEP_Y
        alto_total = max(alto_total, y)
    ancho_total = MARGEN * 2 + len(COLUMNAS) * ANCHO + (len(COLUMNAS) - 1) * SEP_X

    lineas, cajas = [], []
    for t, (x, y, alto) in pos.items():
        cols = esquema[t]["columnas"]
        fks = {f["columna"]: f["tabla"] for f in esquema[t]["fks"]}
        clase = "tabla restringida" if t in restringidas else "tabla"
        partes = [f'<g class="{clase}"><rect x="{x}" y="{y}" width="{ANCHO}" height="{alto}" rx="6"/>',
                  f'<text class="nombre" x="{x + 10}" y="{y + 17}">{escape(t)}{" 🔒" if t in restringidas else ""}</text>',
                  f'<line class="div" x1="{x}" y1="{y + CABECERA}" x2="{x + ANCHO}" y2="{y + CABECERA}"/>']
        for k, c in enumerate(cols):
            cy = y + CABECERA + FILA * (k + 1) - 4
            marca = "PK" if c["pk"] else ("FK" if c["nombre"] in fks else "")
            partes.append(f'<text class="col" x="{x + 10}" y="{cy}">{escape(c["nombre"])}</text>')
            partes.append(f'<text class="meta" x="{x + ANCHO - 10}" y="{cy}" text-anchor="end">'
                          f'{escape(c["tipo"].lower())}{"" if c["nulo"] else " ·"} {marca}</text>')
            if c["nombre"] in fks and fks[c["nombre"]] in pos:
                destino = fks[c["nombre"]]
                dx, dy, _ = pos[destino]
                hacia_derecha = dx > x
                x1 = x + ANCHO if hacia_derecha else x
                x2 = dx if hacia_derecha else dx + ANCHO
                if dx == x:  # misma columna: el conector sale y vuelve por la izquierda
                    x1, x2 = x, x
                    curva = -46
                else:
                    curva = (x2 - x1) / 2
                y2 = dy + 13
                lineas.append(f'<path class="fk" d="M{x1},{cy - 4} C{x1 + curva},{cy - 4} {x2 - curva if dx != x else x2 + curva},{y2} '
                              f'{x2},{y2}"/><circle class="fk-fin" cx="{x2}" cy="{y2}" r="3"/>')
        partes.append("</g>")
        cajas.append("".join(partes))
    estilo = ("<style>.tabla rect{fill:var(--surface-2,#f4f4f2);stroke:var(--border-strong,#bbb)}"
              ".tabla.restringida rect{stroke:var(--alerta,#b7791f);stroke-width:1.5}"
              ".nombre{font:600 13px var(--mono,monospace);fill:var(--text,#222)}"
              ".col{font:12px var(--mono,monospace);fill:var(--text,#222)}"
              ".meta{font:10.5px var(--mono,monospace);fill:var(--muted,#777)}"
              ".div{stroke:var(--border,#ddd)}.fk{fill:none;stroke:var(--accent,#1d6b47);stroke-width:1.2;opacity:.7}"
              ".fk-fin{fill:var(--accent,#1d6b47)}</style>")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {ancho_total} {alto_total}" role="img" '
            f'aria-label="Diagrama entidad-relación del modelo de acervo">{estilo}'
            + "".join(lineas) + "".join(cajas) + "</svg>\n")
