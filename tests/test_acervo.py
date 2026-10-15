"""El ETL, el catálogo, las políticas y lo publicado se prueban contra la verdad sembrada."""

from __future__ import annotations

import copy
import csv
import json
import sqlite3
from pathlib import Path

import pytest

from src import construir, etl, gobernanza, privacidad

RAIZ = Path(__file__).resolve().parent.parent
CATALOGO = json.loads((RAIZ / "catalogo/catalogo.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def carga() -> etl.Carga:
    return etl.cargar()


@pytest.fixture(scope="module")
def verdad() -> list[dict]:
    with open(RAIZ / "datos/verdad.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# --- ETL ------------------------------------------------------------------------------------------------

def test_cuarentena_coincide_con_la_verdad(carga, verdad):
    esperado = {(v["fuente"], int(v["fila"]), v["motivo"]) for v in verdad if v["tipo"] == "cuarentena"}
    hallado = set(carga.con.execute("SELECT fuente, fila, motivo FROM cuarentena").fetchall())
    assert hallado == esperado


def test_reglas_de_calidad_encuentran_lo_sembrado(carga, verdad):
    esperado = {v["fuente"]: int(v["fila"]) for v in verdad if v["tipo"] == "calidad"}
    hallado = {r["id"]: r["casos"] for r in gobernanza.ejecutar_reglas(carga.con, CATALOGO, carga.corte.isoformat())}
    assert hallado == esperado


def test_integridad_referencial(carga):
    assert carga.con.execute("PRAGMA foreign_keys").fetchone()[0] == 1
    assert carga.con.execute("PRAGMA foreign_key_check").fetchall() == []


def test_identidad_y_salud_son_uno_a_uno_con_participante(carga):
    n = carga.con.execute("SELECT COUNT(*) FROM participante").fetchone()[0]
    for t in ("participante_identidad", "participante_salud"):
        assert carga.con.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0] == n


@pytest.mark.parametrize(("texto", "esperado"), [("12.345.678-5", "12345678-5"), ("12345678-5", "12345678-5"),
                                                 ("12.345.678-4", None), ("6.789.012-k", None), ("abc", None)])
def test_normalizar_rut(texto, esperado):
    assert etl.normalizar_rut(texto) == esperado


def test_rut_con_k():
    numero = next(n for n in range(10_000_000, 10_001_000) if etl.digito_verificador(n) == "K")
    assert etl.normalizar_rut(f"{numero:,}".replace(",", ".") + "-k") == f"{numero}-K"


def test_restricciones_del_esquema_rechazan_datos_invalidos(carga):
    con = sqlite3.connect(":memory:")
    con.executescript((RAIZ / "modelo/esquema.sql").read_text(encoding="utf-8"))
    con.execute("INSERT INTO sede (codigo, nombre, comuna, region) VALUES ('SE-01', 'x', 'y', 'z')")
    con.execute("INSERT INTO centro_costo (codigo, nombre) VALUES ('CC-1', 'x')")  # así la fecha es lo único inválido
    for sql in ("INSERT INTO sede (codigo, nombre, comuna, region) VALUES ('SEDE1', 'x', 'y', 'z')",  # código fuera de patrón
                "INSERT INTO programa (codigo, nombre, tipo, sede_id) VALUES ('P', 'x', 'Otro', 1)",  # tipo fuera del dominio
                "INSERT INTO programa (codigo, nombre, tipo, sede_id) VALUES ('P', 'x', 'Residencia', 99)",  # FK inexistente
                ("INSERT INTO movimiento_contable (fecha, cuenta, centro_costo_id, monto, glosa, comprobante) "
                "VALUES ('2026-13-01', '610101', 1, 10, 'g', 'c')")):  # fecha inválida
        with pytest.raises(sqlite3.IntegrityError):
            con.execute(sql)


# --- gobierno de datos ---------------------------------------------------------------------------------

def test_catalogo_cubre_el_esquema_sin_problemas(carga):
    assert gobernanza.verificar_catalogo(carga.con, CATALOGO) == []
    assert gobernanza.verificar_accesos(CATALOGO) == []


def test_catalogo_detecta_columna_sin_documentar_y_dato_sensible_mal_ubicado(carga):
    cat = copy.deepcopy(CATALOGO)
    sede = next(d for d in cat["datasets"] if d["nombre"] == "sede")
    del sede["columnas"]["region"]
    vista = next(d for d in cat["datasets"] if d["nombre"] == "v_gasto_programa")
    vista["columnas"]["gasto"][1] = "Sensible"
    problemas = gobernanza.verificar_catalogo(carga.con, cat)
    assert "sede.region: columna sin documentar" in problemas
    assert any(p.startswith("v_gasto_programa.gasto: dato sensible en la capa Analítica") for p in problemas)


def test_rol_sin_autorizacion_no_puede_leer_salud():
    cat = copy.deepcopy(CATALOGO)
    analista = next(p for p in cat["perfiles"] if p["rol"] == "Analista de datos y BI")
    analista["accede"].append("participante_salud")
    assert gobernanza.verificar_accesos(cat) == [
        "Analista de datos y BI lee participante_salud, que tiene datos sensibles, sin estar autorizado"]


def test_capa_analitica_no_expone_identificadores_de_personas(carga):
    esquema = gobernanza.esquema(carga.con)
    for d in CATALOGO["datasets"]:
        if d["capa"] == "Analítica":
            assert "participante_id" not in [c["nombre"] for c in esquema[d["nombre"]]["columnas"]], d["nombre"]


# --- privacidad ----------------------------------------------------------------------------------------

def test_extraccion_estudio_respeta_consentimiento_y_minimizacion(carga):
    filas = privacidad.extraccion_estudio(carga.con, b"clave-de-prueba")
    con_consentimiento = {r[0] for r in carga.con.execute(
        "SELECT c.participante_id FROM v_consentimiento_vigente c JOIN participante p USING (participante_id) "
        "WHERE c.finalidad = 'Investigación y estadística' AND p.fecha_egreso IS NULL")}
    assert len(filas) == len(con_consentimiento) > 0
    assert set(filas[0]) == {"seudonimo", "tipo_programa", "tramo_edad", "tasa_asistencia"}
    assert {f["seudonimo"] for f in filas} == {privacidad.seudonimo(pid, b"clave-de-prueba") for pid in con_consentimiento}


def test_seudonimo_es_estable_y_depende_de_la_clave():
    assert privacidad.seudonimo(7, b"a") == privacidad.seudonimo(7, b"a")
    assert privacidad.seudonimo(7, b"a") != privacidad.seudonimo(7, b"b")
    assert privacidad.seudonimo(7, b"a") != privacidad.seudonimo(8, b"a")


# --- lo publicado --------------------------------------------------------------------------------------

def test_sitio_publicado_esta_al_dia():
    for nombre, texto in construir.construir().items():
        assert (RAIZ / "sitio" / nombre).read_text(encoding="utf-8") == texto, f"sitio/{nombre} desactualizado: python -m src.construir"


def test_diagrama_incluye_todas_las_tablas(carga):
    svg = (RAIZ / "sitio/erd.svg").read_text(encoding="utf-8")
    for t, info in gobernanza.esquema(carga.con).items():
        if info["tipo"] == "tabla":
            assert f">{t}<" in svg or f">{t} 🔒<" in svg, t


def test_los_rut_publicados_estan_en_el_rango_sintetico():
    for archivo, columna in (("participantes.csv", "rut"), ("colaboradores.csv", "rut")):
        with open(RAIZ / "datos/fuentes" / archivo, encoding="utf-8") as f:
            for fila in csv.DictReader(f):
                numero = int(fila[columna].split("-")[0].replace(".", ""))
                assert 33_000_000 <= numero < 35_000_000, (archivo, numero)
