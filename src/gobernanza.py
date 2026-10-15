"""Gobierno de datos: el catálogo se contrasta con la base real, y las políticas se verifican como código.

- `verificar_catalogo`: cada tabla, vista y columna del esquema está documentada (y nada documentado
  falta en el esquema), con un nivel de clasificación válido y coherente con su capa.
- `matriz_acceso`: qué rol puede leer cada dataset, derivada de los perfiles del catálogo.
- `registro_tratamientos`: el registro de actividades de tratamiento, con las categorías de datos de
  cada tratamiento calculadas desde las columnas que usa.
- `ejecutar_reglas`: corre las reglas de calidad del catálogo (SQL) sobre la base cargada.
"""

from __future__ import annotations

import sqlite3

NIVELES = ("Público", "Interno", "Personal", "Sensible")
CAPAS_SIN_PERSONAS = ("Maestro", "Analítica", "Control")


def esquema(con: sqlite3.Connection) -> dict[str, dict]:
    """Tablas y vistas del modelo con sus columnas, tipos, nulabilidad, PK y FK, leídas de SQLite."""
    salida = {}
    for nombre, tipo in con.execute("SELECT name, type FROM sqlite_master WHERE type IN ('table', 'view') "
                                    "AND name NOT LIKE 'sqlite_%' ORDER BY name"):
        cols = [{"nombre": c[1], "tipo": c[2] or "—", "nulo": not c[3] and not c[5], "pk": bool(c[5])}
                for c in con.execute(f"PRAGMA table_info({nombre})")]
        fks = [{"columna": f[3], "tabla": f[2], "referencia": f[4]} for f in con.execute(f"PRAGMA foreign_key_list({nombre})")]
        salida[nombre] = {"tipo": "vista" if tipo == "view" else "tabla", "columnas": cols, "fks": fks}
    return salida


def verificar_catalogo(con: sqlite3.Connection, catalogo: dict) -> list[str]:
    """Problemas de cobertura y coherencia; una lista vacía significa que el catálogo está al día."""
    real = esquema(con)
    doc = {d["nombre"]: d for d in catalogo["datasets"]}
    problemas = [f"Sin documentar: {t}" for t in sorted(set(real) - set(doc))]
    problemas += [f"Documentado pero no existe: {t}" for t in sorted(set(doc) - set(real))]
    for nombre in sorted(set(real) & set(doc)):
        d = doc[nombre]
        cols_reales = [c["nombre"] for c in real[nombre]["columnas"]]
        problemas += [f"{nombre}.{c}: columna sin documentar" for c in cols_reales if c not in d["columnas"]]
        problemas += [f"{nombre}.{c}: documentada pero no existe" for c in d["columnas"] if c not in cols_reales]
        for col, (descripcion, nivel) in d["columnas"].items():
            if nivel not in NIVELES:
                problemas.append(f"{nombre}.{col}: nivel desconocido «{nivel}»")
            if not descripcion.strip():
                problemas.append(f"{nombre}.{col}: sin descripción")
            if d["capa"] in CAPAS_SIN_PERSONAS and nivel in ("Personal", "Sensible"):
                problemas.append(f"{nombre}.{col}: dato {nivel.lower()} en la capa {d['capa']}")
            if nivel == "Sensible" and d["capa"] != "Restringida":
                problemas.append(f"{nombre}.{col}: dato sensible fuera de una tabla restringida")
        if not d.get("dueno") or not d.get("custodio"):
            problemas.append(f"{nombre}: sin dueño o custodio")
    tablas_tratadas = {t for tr in catalogo["tratamientos"] for t in tr["tablas"]}
    for d in catalogo["datasets"]:
        personal = any(nivel in ("Personal", "Sensible") for _, nivel in d["columnas"].values())
        if personal and d["nombre"] not in tablas_tratadas:
            problemas.append(f"{d['nombre']}: tiene datos personales y no figura en ningún tratamiento")
    problemas += [f"Tratamiento {tr['id']}: la tabla {t} no existe" for tr in catalogo["tratamientos"] for t in tr["tablas"] if t not in doc]
    return problemas


def nivel_maximo(dataset: dict) -> str:
    return max((nivel for _, nivel in dataset["columnas"].values()), key=NIVELES.index)


def matriz_acceso(catalogo: dict) -> dict:
    """Para cada rol, los datasets que puede leer: por capa completa o por nombre de dataset."""
    datasets = catalogo["datasets"]
    filas = []
    for p in catalogo["perfiles"]:
        lee = {d["nombre"] for d in datasets if d["capa"] in p["accede"] or d["nombre"] in p["accede"]}
        filas.append({"rol": p["rol"], "descripcion": p["descripcion"], "sensible": bool(p.get("sensible")), "lee": sorted(lee)})
    return {"datasets": [{"nombre": d["nombre"], "capa": d["capa"], "nivel": nivel_maximo(d)} for d in datasets], "roles": filas}


def verificar_accesos(catalogo: dict) -> list[str]:
    """Solo los roles marcados `sensible` pueden leer datasets con datos sensibles."""
    niveles = {d["nombre"]: nivel_maximo(d) for d in catalogo["datasets"]}
    return [f"{r['rol']} lee {t}, que tiene datos sensibles, sin estar autorizado"
            for r in matriz_acceso(catalogo)["roles"] for t in r["lee"] if niveles[t] == "Sensible" and not r["sensible"]]


def registro_tratamientos(catalogo: dict) -> list[dict]:
    doc = {d["nombre"]: d for d in catalogo["datasets"]}
    registro = []
    for tr in catalogo["tratamientos"]:
        niveles = {nivel for t in tr["tablas"] for _, nivel in doc[t]["columnas"].values()}
        registro.append({**tr, "categorias": [n for n in NIVELES if n in niveles],
                         "sistemas": sorted({doc[t]["fuente"]["sistema"] for t in tr["tablas"]}),
                         "retencion": sorted({doc[t]["retencion"] for t in tr["tablas"]})})
    return registro


def ejecutar_reglas(con: sqlite3.Connection, catalogo: dict, corte: str) -> list[dict]:
    resultado = []
    for regla in catalogo["reglas_calidad"]:
        params = {"corte": corte} if ":corte" in regla["sql"] else {}
        casos = len(con.execute(regla["sql"], params).fetchall())
        resultado.append({"id": regla["id"], "nombre": regla["nombre"], "descripcion": regla["descripcion"], "casos": casos})
    return resultado
