"""Genera las exportaciones sintéticas de los sistemas de Fundación Ejemplo, con errores sembrados.

Cada archivo imita el formato típico de su sistema de origen (RUT con puntos, fechas DD-MM-AAAA,
montos con separador de miles, "Sí"/"No" escritos a mano). Nada corresponde a personas reales.

El generador no importa el ETL. Siembra errores conocidos y los anota en `verdad.csv`; los tests
exigen que el ETL ponga en cuarentena exactamente esas filas, y que las reglas de calidad encuentren
exactamente los casos sembrados después de la carga.
"""

from __future__ import annotations

import csv
import json
import random
from datetime import date, timedelta
from pathlib import Path

AQUI = Path(__file__).resolve().parent
FUENTES = AQUI / "fuentes"
MAESTROS = json.loads((FUENTES / "maestros.json").read_text(encoding="utf-8"))
CORTE = date(2026, 9, 30)

NOMBRES = ["Camila", "Matías", "Valentina", "Benjamín", "Javiera", "Vicente", "Catalina", "Martín", "Antonia", "Joaquín",
           "Fernanda", "Tomás", "Isidora", "Diego", "Florencia", "Felipe", "Constanza", "Ignacio", "Josefa", "Cristóbal"]
APELLIDOS = ["González", "Muñoz", "Rojas", "Díaz", "Pérez", "Soto", "Contreras", "Silva", "Martínez", "Sepúlveda",
             "Morales", "Rodríguez", "López", "Fuentes", "Hernández", "Torres", "Araya", "Flores", "Espinoza", "Valenzuela"]
COMUNAS = ["Ñuñoa", "Macul", "Peñalolén", "La Florida", "Maipú", "Cerrillos", "Pudahuel", "Providencia", "Viña del Mar", "Quilpué"]
CARGOS = ["Educador(a) diferencial", "Terapeuta ocupacional", "Psicólogo(a)", "Técnico(a) en educación especial",
          "Asistente social", "Auxiliar de residencia", "Coordinador(a) de programa", "Analista contable"]
PRESUPUESTO = {"610101": (9_000_000, 22_000_000), "620101": (350_000, 900_000), "620201": (600_000, 2_400_000),
               "620301": (200_000, 1_100_000)}


def dv(numero: int) -> str:
    """Dígito verificador del RUT (módulo 11)."""
    suma, factor = 0, 2
    for d in reversed(str(numero)):
        suma += int(d) * factor
        factor = 2 if factor == 7 else factor + 1
    resto = 11 - suma % 11
    return {11: "0", 10: "K"}.get(resto, str(resto))


def rut(rng: random.Random, usados: set[int]) -> str:
    while True:
        n = rng.randint(33_000_000, 34_999_999)  # lejos de los RUT asignados hoy a personas naturales
        if n not in usados:
            usados.add(n)
            return f"{n:,}".replace(",", ".") + "-" + dv(n)


def dmy(d: date) -> str:
    return d.strftime("%d-%m-%Y")


def dv_errado(r: str) -> str:
    cuerpo, d = r.rsplit("-", 1)
    return f"{cuerpo}-{'1' if d != '1' else '2'}"


def escribir(nombre: str, filas: list[dict]) -> None:
    with open(FUENTES / nombre, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]), lineterminator="\n")
        w.writeheader()
        w.writerows(filas)


def main() -> None:
    rng = random.Random(21719)
    usados: set[int] = set()
    verdad: list[dict] = []

    def sembrar(fuente: str, fila: int, motivo: str) -> None:
        verdad.append({"tipo": "cuarentena", "fuente": fuente, "fila": fila, "motivo": motivo})

    # --- fichas de participantes (sistema de gestión de participantes) ---
    programas = [p["codigo"] for p in MAESTROS["programas"]]
    fichas = []
    for i in range(150):
        prog = programas[i % len(programas)]
        tipo = next(p["tipo"] for p in MAESTROS["programas"] if p["codigo"] == prog)
        edad = rng.randint(6, 17) if tipo == "Escuela especial" else rng.randint(18, 68)
        nacimiento = CORTE - timedelta(days=edad * 365 + rng.randint(0, 364))
        ingreso = CORTE - timedelta(days=rng.randint(60, 2500))
        egreso = ingreso + timedelta(days=rng.randint(30, 400)) if rng.random() < 0.08 else None
        if egreso and egreso > CORTE:
            egreso = None
        fichas.append({"rut": rut(rng, usados), "nombres": f"{rng.choice(NOMBRES)} {rng.choice(NOMBRES)}",
                       "apellidos": f"{rng.choice(APELLIDOS)} {rng.choice(APELLIDOS)}", "fecha_nacimiento": dmy(nacimiento),
                       "comuna": rng.choice(COMUNAS), "programa": prog, "fecha_ingreso": dmy(ingreso),
                       "fecha_egreso": dmy(egreso) if egreso else "",
                       "representante": f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)}" if edad < 18 or rng.random() < 0.4 else "",
                       "grado_apoyo": rng.choice(["Intermitente", "Limitado", "Extenso", "Generalizado"]),
                       "credencial": rng.choice(["S", "N", "S"]), "observacion": ""})
    validos = list(fichas)
    # errores sembrados en las fichas
    malo = dict(fichas[10], rut=dv_errado(fichas[10]["rut"]))
    fichas[10] = malo
    sembrar("participantes", 11, "RUT con dígito verificador inválido")
    fichas[25] = dict(fichas[25], fecha_egreso=dmy(date(2019, 1, 1)), fecha_ingreso=dmy(date(2020, 3, 2)))
    sembrar("participantes", 26, "Fecha de egreso anterior al ingreso")
    fichas.append(dict(fichas[40], nombres="Registro duplicado"))
    sembrar("participantes", len(fichas), "RUT duplicado")
    excluidos = {validos[10]["rut"], validos[25]["rut"]}
    activos = [f for f in validos if f["rut"] not in excluidos and not f["fecha_egreso"]]
    escribir("participantes.csv", fichas)

    # --- consentimientos ---
    consentimientos = []
    sin_consentimiento = {activos[3]["rut"], activos[17]["rut"]}
    for f in validos:
        if f["rut"] in excluidos:
            continue
        otorga = "Representante legal" if f["representante"] else "Titular"
        base = {"rut": f["rut"], "otorgado_por": otorga, "fecha_otorgamiento": f["fecha_ingreso"], "fecha_revocacion": ""}
        if f["rut"] not in sin_consentimiento:
            consentimientos.append(dict(base, finalidad="Atención del programa"))
        if rng.random() < 0.4:
            consentimientos.append(dict(base, finalidad="Registro fotográfico",
                                        fecha_revocacion=dmy(CORTE - timedelta(days=20)) if rng.random() < 0.15 else ""))
        if rng.random() < 0.35 and not f["fecha_egreso"]:
            consentimientos.append(dict(base, finalidad="Investigación y estadística"))
    egresado = next(f for f in validos if f["rut"] not in excluidos and f["fecha_egreso"]
                    and (CORTE - date(*map(int, reversed(f["fecha_egreso"].split("-"))))).days > 365)
    consentimientos.append({"rut": egresado["rut"], "otorgado_por": "Representante legal" if egresado["representante"] else "Titular",
                            "fecha_otorgamiento": egresado["fecha_ingreso"], "fecha_revocacion": "",
                            "finalidad": "Investigación y estadística"})
    verdad.append({"tipo": "calidad", "fuente": "R3", "fila": 1, "motivo": "Consentimiento de investigación con participante egresado"})
    nino = next(f for f in activos if f["rut"] not in sin_consentimiento
                and (CORTE.year - int(f["fecha_nacimiento"][-4:])) <= 12)
    consentimientos.append({"rut": nino["rut"], "otorgado_por": "Titular", "fecha_otorgamiento": dmy(CORTE - timedelta(days=5)),
                            "fecha_revocacion": "", "finalidad": "Registro fotográfico"})
    sembrar("consentimientos", len(consentimientos), "Consentimiento de niño o niña sin representante legal")
    escribir("consentimientos.csv", consentimientos)
    verdad += [{"tipo": "calidad", "fuente": "R1", "fila": 2, "motivo": "Participante activo sin consentimiento de atención"}]

    # --- planilla de asistencia (planilla compartida, llenada a mano) ---
    actividades = MAESTROS["actividades"]
    dias = [CORTE - timedelta(days=d) for d in range(29, -1, -1)]
    dias = [d for d in dias if d.weekday() < 5]
    asistencia = []
    for f in activos:
        act = rng.choice(actividades[f["programa"]])
        for d in dias:
            if d.weekday() in (0, 3) or (f["programa"] == "PR-RE1" and d.weekday() == 2):
                marca = "Sí" if rng.random() < 0.84 else "No"
                asistencia.append({"rut_participante": f["rut"], "programa": f["programa"], "actividad": act,
                                   "fecha": d.strftime("%d/%m/%Y"), "asistio": rng.choice([marca, marca, marca.lower()])})
    asistencia.insert(5, {"rut_participante": rut(rng, usados), "programa": "PR-CD1", "actividad": "Taller de cocina",
                          "fecha": dias[3].strftime("%d/%m/%Y"), "asistio": "Sí"})
    sembrar("asistencia", 6, "Participante no registrado")
    asistencia.insert(30, dict(asistencia[29], fecha=(CORTE + timedelta(days=8)).strftime("%d/%m/%Y")))
    sembrar("asistencia", 31, "Fecha posterior al corte")
    asistencia.insert(60, dict(asistencia[59], asistio="tal vez"))
    sembrar("asistencia", 61, "Marca de asistencia no reconocida")
    asistencia.insert(90, dict(asistencia[88]))
    sembrar("asistencia", 91, "Fila duplicada")
    asistencia.insert(120, dict(asistencia[119], actividad="Taller de astronomía"))
    sembrar("asistencia", 121, "Actividad inexistente en el programa")
    escribir("asistencia.csv", asistencia)

    # --- colaboradores (sistema de RR.HH.) ---
    centros = [c["codigo"] for c in MAESTROS["centros_costo"]]
    colaboradores = []
    for i in range(64):
        nombre = f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)}"
        colaboradores.append({"rut": rut(rng, usados), "nombre": nombre,
                              "email": f"colaborador{i + 1:03d}@fundacion-ejemplo.cl", "cargo": rng.choice(CARGOS),
                              "centro_costo": centros[i % len(centros)],
                              "fecha_ingreso": dmy(CORTE - timedelta(days=rng.randint(30, 4000))),
                              "jornada": rng.choice([44, 44, 44, 30, 22])})
    colaboradores[7] = dict(colaboradores[7], rut=dv_errado(colaboradores[7]["rut"]))
    sembrar("colaboradores", 8, "RUT con dígito verificador inválido")
    colaboradores[20] = dict(colaboradores[20], centro_costo="CC-999")
    sembrar("colaboradores", 21, "Centro de costo inexistente")
    colaboradores[33] = dict(colaboradores[33], email=colaboradores[32]["email"])
    sembrar("colaboradores", 34, "Correo duplicado")
    escribir("colaboradores.csv", colaboradores)

    # --- movimientos contables (ERP contable) ---
    movimientos = []
    folio = 7000
    for mes in (7, 8, 9):
        for cc in centros:
            folio += 1
            for cuenta, (lo, hi) in PRESUPUESTO.items():
                if cc in ("CC-100", "CC-110") and cuenta == "620201":
                    continue
                monto = rng.randrange(lo, hi, 1_000) // (3 if cc in ("CC-100", "CC-110") else 1)
                movimientos.append({"comprobante": f"CT-{folio}", "fecha": f"31/{mes:02d}/2026" if mes != 9 else "30/09/2026",
                                    "cuenta": cuenta, "centro_costo": cc, "debe": f"{monto:,}".replace(",", "."), "haber": "0",
                                    "glosa": f"Gasto {cuenta} {mes:02d}-2026"})
            if cc not in ("CC-100", "CC-110"):
                sub = rng.randrange(8_000_000, 20_000_000, 1_000)
                movimientos.append({"comprobante": f"CT-{folio}", "fecha": f"15/{mes:02d}/2026", "cuenta": "410101",
                                    "centro_costo": cc, "debe": "0", "haber": f"{sub:,}".replace(",", "."),
                                    "glosa": f"Subvención {mes:02d}-2026"})
    movimientos[12] = dict(movimientos[12], debe="0", haber="0")
    sembrar("contabilidad", 13, "Movimiento sin monto")
    movimientos[44] = dict(movimientos[44], centro_costo="CC-207")
    sembrar("contabilidad", 45, "Centro de costo inexistente")
    escribir("contabilidad.csv", movimientos)

    # --- solicitudes de derechos (formulario web) ---
    derechos = ["Acceso", "Rectificación", "Supresión", "Oposición", "Portabilidad", "Bloqueo", "Acceso", "Rectificación"]
    solicitudes = []
    for i, derecho in enumerate(derechos):
        recep = CORTE - timedelta(days=rng.randint(5, 25))
        respondida = i % 3 != 0
        solicitudes.append({"folio": f"SD-{2026}-{i + 1:03d}", "rut": rng.choice(activos)["rut"], "derecho": derecho,
                            "fecha_recepcion": dmy(recep),
                            "fecha_respuesta": dmy(recep + timedelta(days=rng.randint(2, 12))) if respondida else "",
                            "estado": "Respondida" if respondida else "En curso"})
    solicitudes.append({"folio": "SD-2026-009", "rut": activos[50]["rut"], "derecho": "Supresión",
                        "fecha_recepcion": dmy(CORTE - timedelta(days=47)), "fecha_respuesta": "", "estado": "Recibida"})
    verdad.append({"tipo": "calidad", "fuente": "R2", "fila": 1, "motivo": "Solicitud de derechos abierta sobre el umbral interno"})
    escribir("solicitudes.csv", solicitudes)

    with open(AQUI / "verdad.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["tipo", "fuente", "fila", "motivo"], lineterminator="\n")
        w.writeheader()
        w.writerows(verdad)
    print(f"{len(fichas)} fichas, {len(consentimientos)} consentimientos, {len(asistencia)} asistencias, "
          f"{len(colaboradores)} colaboradores, {len(movimientos)} movimientos, {len(solicitudes)} solicitudes, "
          f"{len(verdad)} filas de verdad")


if __name__ == "__main__":
    main()
