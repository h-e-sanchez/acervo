"""El cliente de la API se prueba sin red: el transporte es inyectable."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from src import indicadores as ind

RAIZ = Path(__file__).resolve().parent.parent
MUESTRA = json.loads((RAIZ / "sitio/indicadores_muestra.json").read_text(encoding="utf-8"))


def transporte(respuestas: list):
    llamadas = []

    def t(url: str, espera: float):
        llamadas.append(url)
        r = respuestas.pop(0)
        if isinstance(r, Exception):
            raise r
        return r
    t.llamadas = llamadas
    return t


def test_devuelve_el_ultimo_valor_validado():
    t = transporte([(200, json.dumps(MUESTRA["uf"]).encode())])
    v = ind.obtener("uf", transporte=t, cache=None)
    assert v.codigo == "uf" and v.valor == MUESTRA["uf"]["serie"][0]["valor"]
    assert t.llamadas == [f"{ind.BASE}/uf"]


def test_reintenta_ante_5xx_y_errores_de_red_con_espera_exponencial():
    esperas = []
    t = transporte([(503, b""), TimeoutError("lento"), (200, json.dumps(MUESTRA["utm"]).encode())])
    v = ind.obtener("utm", transporte=t, cache=None, dormir=esperas.append)
    assert v.valor == MUESTRA["utm"]["serie"][0]["valor"]
    assert esperas == [1, 2]


def test_no_reintenta_un_error_del_cliente():
    t = transporte([(404, b"{}")])
    with pytest.raises(ind.ErrorIndicador, match="404"):
        ind.obtener("noexiste", transporte=t, cache=None, dormir=lambda s: None)
    assert len(t.llamadas) == 1


def test_rechaza_una_respuesta_fuera_de_contrato():
    roto = dict(MUESTRA["dolar"], serie=[{"fecha": "2026-10-15", "valor": "abc"}])
    with pytest.raises(ind.ErrorIndicador, match="fuera de contrato"):
        ind.obtener("dolar", transporte=transporte([(200, json.dumps(roto).encode())]), cache=None)


def test_usa_la_cache_vigente_sin_llamar_a_la_api(tmp_path):
    (tmp_path / "uf.json").write_text(json.dumps(MUESTRA["uf"]), encoding="utf-8")
    t = transporte([])
    assert ind.obtener("uf", transporte=t, cache=tmp_path).valor > 0
    assert t.llamadas == []


def test_respaldo_cuando_la_api_no_responde():
    t = transporte([(500, b""), (500, b""), (500, b"")])
    v, en_vivo = ind.obtener_o_respaldo("utm", transporte=t, cache=None, dormir=lambda s: None)
    assert not en_vivo and v.valor == MUESTRA["utm"]["serie"][0]["valor"]
