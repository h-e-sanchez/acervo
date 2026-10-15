"""Privacidad por diseño: seudonimización y extracción para estudios con consentimiento y minimización.

La seudonimización usa HMAC-SHA256 con una clave guardada aparte (variable de entorno
`ACERVO_CLAVE_SEUDONIMO`). Sin la clave no se puede volver del seudónimo al identificador, y la misma
clave produce siempre el mismo seudónimo, así que los estudios pueden cruzar periodos sin ver a nadie.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3

CLAVE_DEMO = "solo-para-la-demo-no-usar-en-produccion"


def clave() -> bytes:
    return os.environ.get("ACERVO_CLAVE_SEUDONIMO", CLAVE_DEMO).encode("utf-8")


def seudonimo(identificador: int | str, llave: bytes | None = None) -> str:
    return hmac.new(llave or clave(), str(identificador).encode("utf-8"), hashlib.sha256).hexdigest()[:16]


def extraccion_estudio(con: sqlite3.Connection, llave: bytes | None = None) -> list[dict]:
    """Datos para estadística e investigación: solo participantes con ese consentimiento vigente, seudonimizados
    y con lo mínimo necesario (programa, tramo de edad y tasa de asistencia; nada de identidad ni salud)."""
    filas = con.execute("""
        SELECT p.participante_id, pr.tipo, p.tramo_edad,
               ROUND(1.0 * SUM(a.presente) / COUNT(a.asistencia_id), 4) AS tasa_asistencia
        FROM participante p
        JOIN programa pr ON pr.programa_id = p.programa_id
        JOIN v_consentimiento_vigente c ON c.participante_id = p.participante_id AND c.finalidad = 'Investigación y estadística'
        LEFT JOIN asistencia a ON a.participante_id = p.participante_id
        WHERE p.fecha_egreso IS NULL
        GROUP BY p.participante_id, pr.tipo, p.tramo_edad
        ORDER BY p.participante_id""").fetchall()
    return [{"seudonimo": seudonimo(pid, llave), "tipo_programa": tipo, "tramo_edad": t, "tasa_asistencia": tasa}
            for pid, tipo, t, tasa in filas]
