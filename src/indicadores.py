"""Cliente de la API REST pública de mindicador.cl (UF, UTM, dólar y otros indicadores de Chile).

Buenas prácticas de integración que aplica:
- tiempo de espera explícito y reintentos con espera exponencial ante errores de red o 5xx (no ante 4xx);
- validación del esquema de la respuesta antes de usarla: si cambia el contrato, falla con un mensaje claro;
- caché local con vencimiento, para no consultar de más un servicio gratuito;
- respaldo explícito: si el servicio no responde, se usa la última muestra guardada y se dice que es una muestra;
- el transporte es inyectable, así los tests corren sin red.

    python -m src.indicadores uf utm dolar
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

BASE = "https://mindicador.cl/api"
CACHE = Path(__file__).resolve().parent.parent / ".cache"
AGENTE = "acervo/1.0 (+https://github.com/h-e-sanchez/acervo)"
RESPALDO = Path(__file__).resolve().parent.parent / "sitio" / "indicadores_muestra.json"

Transporte = Callable[[str, float], tuple[int, bytes]]


class ErrorIndicador(Exception):
    pass


@dataclass
class Valor:
    codigo: str
    nombre: str
    unidad: str
    fecha: str
    valor: float


def http(url: str, espera: float) -> tuple[int, bytes]:
    pedido = urllib.request.Request(url, headers={"User-Agent": AGENTE, "Accept": "application/json"})
    try:
        with urllib.request.urlopen(pedido, timeout=espera) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def validar(datos: dict, codigo: str) -> Valor:
    try:
        assert datos["codigo"] == codigo, f"se pidió {codigo} y llegó {datos['codigo']}"
        serie = datos["serie"]
        assert isinstance(serie, list) and serie, "serie vacía"
        ultimo = serie[0]
        valor = float(ultimo["valor"])
        assert valor > 0, "valor no positivo"
        return Valor(codigo, datos["nombre"], datos["unidad_medida"], ultimo["fecha"][:10], valor)
    except (KeyError, TypeError, ValueError, AssertionError) as e:
        raise ErrorIndicador(f"Respuesta de {codigo} fuera de contrato: {e}") from e


def obtener(codigo: str, transporte: Transporte = http, intentos: int = 3, espera: float = 10.0,
            cache: Path | None = CACHE, vigencia_s: int = 6 * 3600, dormir: Callable[[float], None] = time.sleep) -> Valor:
    """Último valor del indicador `codigo` (uf, utm, dolar, euro, ipc…)."""
    archivo = cache / f"{codigo}.json" if cache else None
    if archivo and archivo.exists() and time.time() - archivo.stat().st_mtime < vigencia_s:
        return validar(json.loads(archivo.read_text(encoding="utf-8")), codigo)
    ultimo_error = ""
    for intento in range(intentos):
        try:
            estado, cuerpo = transporte(f"{BASE}/{codigo}", espera)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            estado, cuerpo, ultimo_error = 0, b"", str(e)
        if estado == 200:
            datos = json.loads(cuerpo)
            valor = validar(datos, codigo)
            if archivo:
                archivo.parent.mkdir(exist_ok=True)
                archivo.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
            return valor
        if 400 <= estado < 500:
            raise ErrorIndicador(f"{codigo}: la API respondió {estado}; no se reintenta un error del cliente")
        ultimo_error = ultimo_error or f"HTTP {estado}"
        if intento < intentos - 1:
            dormir(2 ** intento)
    raise ErrorIndicador(f"{codigo}: sin respuesta tras {intentos} intentos ({ultimo_error})")


def obtener_o_respaldo(codigo: str, respaldo: Path = RESPALDO, **kwargs) -> tuple[Valor, bool]:
    """El valor en vivo o, si la API falla, el de la última muestra guardada. El bool dice si es en vivo."""
    try:
        return obtener(codigo, **kwargs), True
    except ErrorIndicador:
        return validar(json.loads(respaldo.read_text(encoding="utf-8"))[codigo], codigo), False


def guardar_muestra(codigos: list[str], destino: Path = RESPALDO, **kwargs) -> dict:
    """Refresca la muestra de respaldo con respuestas completas de la API (solo las que llegaron bien)."""
    muestra = json.loads(destino.read_text(encoding="utf-8")) if destino.exists() else {}
    for codigo in codigos:
        try:
            obtener(codigo, cache=CACHE, vigencia_s=0, **kwargs)  # vigencia 0: siempre consulta y deja la respuesta en caché
            datos = json.loads((CACHE / f"{codigo}.json").read_text(encoding="utf-8"))
            datos["serie"] = datos["serie"][:5]
            muestra[codigo] = datos
        except ErrorIndicador as e:
            print(f"aviso: {e}", file=sys.stderr)
    destino.write_text(json.dumps(muestra, ensure_ascii=False, indent=1), encoding="utf-8")
    return muestra


def main(argv: list[str]) -> int:
    for codigo in argv or ["uf", "utm", "dolar"]:
        v, en_vivo = obtener_o_respaldo(codigo)
        texto = f"{v.nombre}: ${v.valor:,.2f} al {v.fecha}".replace(",", "X").replace(".", ",").replace("X", ".")
        print(texto + ("" if en_vivo else "  (muestra guardada: la API no respondió)"))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
