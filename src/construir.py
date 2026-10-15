"""Construye lo que publica el sitio a partir de las fuentes, el esquema y el catálogo.

    python -m src.construir              # sitio/datos.json, sitio/catalogo.json, sitio/erd.svg y salida/acervo.db
    python -m src.construir --indicadores # además refresca la muestra de respaldo de la API

Los archivos de `sitio/` se versionan: un test reconstruye todo en memoria y falla si difieren.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

from src import erd, etl, gobernanza, indicadores, privacidad

RAIZ = Path(__file__).resolve().parent.parent
SITIO = RAIZ / "sitio"
CATALOGO = RAIZ / "catalogo" / "catalogo.json"


def construir(con: sqlite3.Connection | None = None) -> dict[str, str]:
    """Devuelve el contenido de cada archivo publicado (ruta relativa a sitio/ -> texto)."""
    carga = etl.cargar(con=con)
    con = carga.con
    catalogo = json.loads(CATALOGO.read_text(encoding="utf-8"))
    real = gobernanza.esquema(con)
    corte = carga.corte.isoformat()

    publicado = {k: v for k, v in catalogo.items() if k != "datasets"}
    publicado["datasets"] = []
    for d in catalogo["datasets"]:
        r = real[d["nombre"]]
        fks = {f["columna"]: f"{f['tabla']}.{f['referencia'] or f['tabla'] + '_id'}" for f in r["fks"]}
        columnas = [{"nombre": c["nombre"], "descripcion": d["columnas"][c["nombre"]][0], "nivel": d["columnas"][c["nombre"]][1],
                     "tipo": c["tipo"], "nulo": c["nulo"], "pk": c["pk"], "fk": fks.get(c["nombre"], "")}
                    for c in r["columnas"]]
        usado_por = [tr["id"] for tr in catalogo["tratamientos"] if d["nombre"] in tr["tablas"]]
        publicado["datasets"].append({**{k: v for k, v in d.items() if k != "columnas"}, "tipo": r["tipo"],
                                      "nivel": gobernanza.nivel_maximo(d), "tratamientos": usado_por, "columnas": columnas})
    publicado["registro"] = gobernanza.registro_tratamientos(catalogo)
    publicado["acceso"] = gobernanza.matriz_acceso(catalogo)

    cuenta = lambda sql, *p: con.execute(sql, p).fetchone()[0]
    cuarentena = [{"fuente": f, "motivo": m, "filas": n} for f, m, n in con.execute(
        "SELECT fuente, motivo, COUNT(*) FROM cuarentena GROUP BY fuente, motivo ORDER BY fuente, motivo")]
    leidas = {f: len(etl.filas((etl.FUENTES / a).read_text(encoding="utf-8"))) for f, a in etl.ORDEN}
    estudio = privacidad.extraccion_estudio(con)
    datos = {
        "corte": corte,
        "tablas": {t: cuenta(f"SELECT COUNT(*) FROM {t}") for t, info in real.items() if info["tipo"] == "tabla"},
        "fuentes": [{"fuente": f, "leidas": leidas[f], "cuarentena": sum(c["filas"] for c in cuarentena if c["fuente"] == f)}
                    for f, _ in etl.ORDEN],
        "cuarentena": cuarentena,
        "calidad": gobernanza.ejecutar_reglas(con, catalogo, corte),
        "catalogo": {"problemas": gobernanza.verificar_catalogo(con, catalogo) + gobernanza.verificar_accesos(catalogo),
                     "datasets": len(catalogo["datasets"]), "columnas": sum(len(d["columnas"]) for d in catalogo["datasets"])},
        "estudio": {"filas": len(estudio), "columnas": list(estudio[0]) if estudio else [], "muestra": estudio[:3]},
        "vistas": {v: [dict(zip([c[0] for c in cur.description], fila)) for fila in cur.fetchall()]
                   for v in ("v_asistencia_mensual", "v_costo_por_participante")
                   for cur in [con.execute(f"SELECT * FROM {v} ORDER BY 1, 2")]},
    }
    restringidas = {d["nombre"] for d in catalogo["datasets"] if d["capa"] == "Restringida"}
    return {"datos.json": json.dumps(datos, ensure_ascii=False, indent=1) + "\n",
            "catalogo.json": json.dumps(publicado, ensure_ascii=False, indent=1) + "\n",
            "erd.svg": erd.svg(real, restringidas)}


def main(argv: list[str]) -> int:
    if "--indicadores" in argv:
        indicadores.guardar_muestra(["uf", "utm", "dolar"])
    salida = RAIZ / "salida"
    salida.mkdir(exist_ok=True)
    db = salida / "acervo.db"
    db.unlink(missing_ok=True)
    archivos = construir(sqlite3.connect(db))
    for nombre, texto in archivos.items():
        (SITIO / nombre).write_text(texto, encoding="utf-8", newline="\n")
    datos = json.loads(archivos["datos.json"])
    print(f"Corte {datos['corte']}: {sum(f['leidas'] for f in datos['fuentes'])} filas leídas, "
          f"{sum(f['cuarentena'] for f in datos['fuentes'])} en cuarentena; "
          f"{len(datos['catalogo']['problemas'])} problemas de catálogo; base en {db}")
    return 1 if datos["catalogo"]["problemas"] else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
