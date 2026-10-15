"""ETL: valida las exportaciones de cada sistema y las carga al modelo relacional (SQLite).

Cada fuente pasa por las mismas etapas: leer con tolerancia (separador, fechas DD-MM-AAAA o
DD/MM/AAAA, miles con punto), validar contra reglas explícitas y cargar. Lo que no pasa queda en la
tabla `cuarentena` con la fuente, la fila y el motivo, nunca con el contenido de la fila. La identidad
y la salud se separan al cargar: el resto del modelo solo conoce el identificador sustituto.

Solo biblioteca estándar (csv, sqlite3, json).
"""

from __future__ import annotations

import csv
import io
import json
import re
import sqlite3
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
ESQUEMA = RAIZ / "modelo" / "esquema.sql"
FUENTES = RAIZ / "datos" / "fuentes"
MARCAS = {"sí": 1, "si": 1, "s": 1, "x": 1, "1": 1, "presente": 1, "no": 0, "n": 0, "0": 0, "ausente": 0}
TRAMOS = ((13, "0-13"), (17, "14-17"), (29, "18-29"), (44, "30-44"), (59, "45-59"), (200, "60+"))


# --- utilidades -----------------------------------------------------------------------------------------

def normalizar_rut(texto: str) -> str | None:
    """'12.345.678-5' -> '12345678-5'; None si el formato o el dígito verificador no son válidos."""
    limpio = re.sub(r"[.\s]", "", (texto or "").upper())
    m = re.fullmatch(r"(\d{6,8})-?([\dK])", limpio)
    if not m or digito_verificador(int(m.group(1))) != m.group(2):
        return None
    return f"{int(m.group(1))}-{m.group(2)}"


def digito_verificador(numero: int) -> str:
    suma, factor = 0, 2
    for d in reversed(str(numero)):
        suma += int(d) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - suma % 11
    return {11: "0", 10: "K"}.get(resto, str(resto))


def fecha(texto: str) -> date | None:
    texto = (texto or "").strip()
    if not texto:
        return None
    m = re.fullmatch(r"(\d{1,2})[-/](\d{1,2})[-/](\d{4})", texto)
    return date(int(m.group(3)), int(m.group(2)), int(m.group(1))) if m else date.fromisoformat(texto[:10])


def entero(texto: str) -> int:
    limpio = (texto or "0").strip().replace("$", "").replace(".", "").replace(" ", "")
    return int(limpio.replace(",", ".").split(".")[0] or 0)


def edad(nacimiento: date, al: date) -> int:
    return al.year - nacimiento.year - ((al.month, al.day) < (nacimiento.month, nacimiento.day))


def tramo(anios: int) -> str:
    return next(t for tope, t in TRAMOS if anios <= tope)


def filas(texto: str) -> list[dict]:
    sep = ";" if texto[:2000].count(";") > texto[:2000].count(",") else ","
    return [{(k or "").strip().lower(): (v or "").strip() for k, v in f.items()}
            for f in csv.DictReader(io.StringIO(texto.lstrip("﻿")), delimiter=sep)]


# --- carga ----------------------------------------------------------------------------------------------

class Carga:
    """Carga las fuentes en orden (maestros, participantes, consentimientos, asistencia, personas, finanzas)."""

    def __init__(self, maestros: dict, con: sqlite3.Connection | None = None):
        self.con = con or sqlite3.connect(":memory:")
        self.con.executescript(ESQUEMA.read_text(encoding="utf-8"))
        self.corte = date.fromisoformat(maestros["fecha_corte"])
        self.ids: dict[str, dict[str, int]] = {"sede": {}, "programa": {}, "centro_costo": {}, "actividad": {}, "participante": {}}
        self._maestros(maestros)

    def rechazar(self, fuente: str, fila: int, motivo: str) -> None:
        self.con.execute("INSERT INTO cuarentena (fuente, fila, motivo) VALUES (?, ?, ?)", (fuente, fila, motivo))

    def _insertar(self, tabla: str, valores: dict) -> int:
        cols = ", ".join(valores)
        marcas = ", ".join("?" for _ in valores)
        return self.con.execute(f"INSERT INTO {tabla} ({cols}) VALUES ({marcas})", list(valores.values())).lastrowid

    def _maestros(self, m: dict) -> None:
        for s in m["sedes"]:
            self.ids["sede"][s["codigo"]] = self._insertar("sede", s)
        for p in m["programas"]:
            self.ids["programa"][p["codigo"]] = self._insertar(
                "programa", {"codigo": p["codigo"], "nombre": p["nombre"], "tipo": p["tipo"], "sede_id": self.ids["sede"][p["sede"]]})
        for c in m["centros_costo"]:
            self.ids["centro_costo"][c["codigo"]] = self._insertar(
                "centro_costo", {"codigo": c["codigo"], "nombre": c["nombre"],
                                 "programa_id": self.ids["programa"][c["programa"]] if c["programa"] else None})
        for prog, nombres in m["actividades"].items():
            for n in nombres:
                self.ids["actividad"][f"{prog}|{n}"] = self._insertar("actividad", {"programa_id": self.ids["programa"][prog], "nombre": n})

    def participantes(self, texto: str) -> None:
        for n, f in enumerate(filas(texto), 1):
            r = normalizar_rut(f["rut"])
            ingreso, egreso, nac = fecha(f["fecha_ingreso"]), fecha(f.get("fecha_egreso", "")), fecha(f["fecha_nacimiento"])
            if r is None:
                self.rechazar("participantes", n, "RUT con dígito verificador inválido")
            elif r in self.ids["participante"]:
                self.rechazar("participantes", n, "RUT duplicado")
            elif f["programa"] not in self.ids["programa"]:
                self.rechazar("participantes", n, "Programa inexistente")
            elif egreso and egreso < ingreso:
                self.rechazar("participantes", n, "Fecha de egreso anterior al ingreso")
            else:
                pid = self._insertar("participante", {
                    "programa_id": self.ids["programa"][f["programa"]], "fecha_ingreso": ingreso.isoformat(),
                    "fecha_egreso": egreso.isoformat() if egreso else None, "tramo_edad": tramo(edad(nac, self.corte)),
                    "comuna": f["comuna"]})
                self.ids["participante"][r] = pid
                self._insertar("participante_identidad", {"participante_id": pid, "rut": r, "nombres": f["nombres"],
                                                          "apellidos": f["apellidos"], "fecha_nacimiento": nac.isoformat(),
                                                          "representante": f.get("representante") or None})
                self._insertar("participante_salud", {"participante_id": pid, "grado_apoyo": f["grado_apoyo"],
                                                      "condicion_cronica": int(f.get("condicion_cronica", "N").upper() == "S"),
                                                      "observacion_clinica": f.get("observacion") or None})

    def consentimientos(self, texto: str) -> None:
        for n, f in enumerate(filas(texto), 1):
            pid = self.ids["participante"].get(normalizar_rut(f["rut"]) or "")
            if pid is None:
                self.rechazar("consentimientos", n, "Participante no registrado")
                continue
            otorgado = fecha(f["fecha_otorgamiento"])
            nac = date.fromisoformat(self.con.execute("SELECT fecha_nacimiento FROM participante_identidad WHERE participante_id = ?",
                                                      (pid,)).fetchone()[0])
            if f["otorgado_por"] == "Titular" and edad(nac, otorgado) < 14:
                self.rechazar("consentimientos", n, "Consentimiento de niño o niña sin representante legal")
                continue
            revocado = fecha(f.get("fecha_revocacion", ""))
            self._insertar("consentimiento", {"participante_id": pid, "finalidad": f["finalidad"], "otorgado_por": f["otorgado_por"],
                                              "fecha_otorgamiento": otorgado.isoformat(),
                                              "fecha_revocacion": revocado.isoformat() if revocado else None})

    def asistencia(self, texto: str) -> None:
        vistos: set[tuple] = set()
        for n, f in enumerate(filas(texto), 1):
            pid = self.ids["participante"].get(normalizar_rut(f["rut_participante"]) or "")
            act = self.ids["actividad"].get(f"{f['programa']}|{f['actividad']}")
            dia = fecha(f["fecha"])
            marca = MARCAS.get(f["asistio"].strip().lower())
            if pid is None:
                self.rechazar("asistencia", n, "Participante no registrado")
            elif act is None:
                self.rechazar("asistencia", n, "Actividad inexistente en el programa")
            elif dia > self.corte:
                self.rechazar("asistencia", n, "Fecha posterior al corte")
            elif marca is None:
                self.rechazar("asistencia", n, "Marca de asistencia no reconocida")
            elif (pid, act, dia) in vistos:
                self.rechazar("asistencia", n, "Fila duplicada")
            else:
                vistos.add((pid, act, dia))
                self._insertar("asistencia", {"participante_id": pid, "actividad_id": act, "fecha": dia.isoformat(), "presente": marca})

    def colaboradores(self, texto: str) -> None:
        ruts: set[str] = set()
        correos: set[str] = set()
        for n, f in enumerate(filas(texto), 1):
            r = normalizar_rut(f["rut"])
            correo = f["email"].lower()
            if r is None:
                self.rechazar("colaboradores", n, "RUT con dígito verificador inválido")
            elif r in ruts:
                self.rechazar("colaboradores", n, "RUT duplicado")
            elif f["centro_costo"] not in self.ids["centro_costo"]:
                self.rechazar("colaboradores", n, "Centro de costo inexistente")
            elif correo in correos:
                self.rechazar("colaboradores", n, "Correo duplicado")
            else:
                ruts.add(r)
                correos.add(correo)
                cid = self._insertar("colaborador", {"centro_costo_id": self.ids["centro_costo"][f["centro_costo"]], "cargo": f["cargo"],
                                                     "fecha_ingreso": fecha(f["fecha_ingreso"]).isoformat(),
                                                     "jornada_horas": int(f["jornada"])})
                self._insertar("colaborador_identidad", {"colaborador_id": cid, "rut": r, "nombre": f["nombre"], "correo": correo})

    def contabilidad(self, texto: str) -> None:
        for n, f in enumerate(filas(texto), 1):
            monto = entero(f["debe"]) - entero(f["haber"])
            if f["centro_costo"] not in self.ids["centro_costo"]:
                self.rechazar("contabilidad", n, "Centro de costo inexistente")
            elif monto == 0:
                self.rechazar("contabilidad", n, "Movimiento sin monto")
            else:
                self._insertar("movimiento_contable", {"fecha": fecha(f["fecha"]).isoformat(), "cuenta": f["cuenta"],
                                                       "centro_costo_id": self.ids["centro_costo"][f["centro_costo"]], "monto": monto,
                                                       "glosa": f["glosa"], "comprobante": f["comprobante"]})

    def solicitudes(self, texto: str) -> None:
        for f in filas(texto):
            respuesta = fecha(f.get("fecha_respuesta", ""))
            self._insertar("solicitud_derecho", {"participante_id": self.ids["participante"].get(normalizar_rut(f.get("rut", "")) or ""),
                                                 "derecho": f["derecho"], "fecha_recepcion": fecha(f["fecha_recepcion"]).isoformat(),
                                                 "fecha_respuesta": respuesta.isoformat() if respuesta else None, "estado": f["estado"]})


ORDEN = (("participantes", "participantes.csv"), ("consentimientos", "consentimientos.csv"), ("asistencia", "asistencia.csv"),
         ("colaboradores", "colaboradores.csv"), ("contabilidad", "contabilidad.csv"), ("solicitudes", "solicitudes.csv"))


def cargar(fuentes: Path = FUENTES, con: sqlite3.Connection | None = None) -> Carga:
    """Carga todas las fuentes de la carpeta en una base SQLite (en memoria si no se pasa conexión)."""
    carga = Carga(json.loads((fuentes / "maestros.json").read_text(encoding="utf-8")), con)
    for metodo, archivo in ORDEN:
        getattr(carga, metodo)((fuentes / archivo).read_text(encoding="utf-8"))
    carga.con.commit()
    return carga
