"""Las páginas usan lo que publica el build y las cifras escritas a mano siguen siendo ciertas."""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
DATOS = json.loads((RAIZ / "sitio/datos.json").read_text(encoding="utf-8"))


def _ids_usados(js: str) -> set[str]:
    return set(re.findall(r'\$\("([\w-]+)"\)', js))


def test_los_ids_que_usa_cada_script_existen_en_su_pagina():
    for pagina, script in (("index.html", "app.js"), ("catalogo.html", "catalogo.js")):
        html = (RAIZ / pagina).read_text(encoding="utf-8")
        for id_ in _ids_usados((RAIZ / script).read_text(encoding="utf-8")):
            assert f'id="{id_}"' in html, f"{script} usa #{id_}, que no está en {pagina}"


def test_los_archivos_que_piden_los_scripts_existen():
    for script in ("app.js", "catalogo.js"):
        for ruta in re.findall(r'"(sitio/[\w.]+)"', (RAIZ / script).read_text(encoding="utf-8")):
            assert (RAIZ / ruta).exists(), ruta


def test_cifras_escritas_en_el_index():
    html = (RAIZ / "index.html").read_text(encoding="utf-8")
    cuarentena = sum(f["cuarentena"] for f in DATOS["fuentes"])
    assert f"quedan {cuarentena} filas en cuarentena" in html
    tablas = len(DATOS["tablas"])
    vistas = len(re.findall(r"^CREATE VIEW", (RAIZ / "modelo/esquema.sql").read_text(encoding="utf-8"), re.MULTILINE))
    palabras = {4: "cuatro", 14: "Catorce"}
    assert f"{palabras[tablas]} tablas" in html and f"{palabras[vistas]} vistas" in html
    tests_api = [n for n in ast.walk(ast.parse((RAIZ / "tests/test_indicadores.py").read_text(encoding="utf-8")))
                 if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")]
    assert len(tests_api) == 6 and "sus seis tests" in html


def test_las_pruebas_citadas_en_buenas_practicas_existen():
    html = (RAIZ / "index.html").read_text(encoding="utf-8")
    codigo = (RAIZ / "tests/test_acervo.py").read_text(encoding="utf-8")
    for nombre in re.findall(r'<span class="prueba">(test_\w+)</span>', html):
        assert f"def {nombre}(" in codigo, nombre
