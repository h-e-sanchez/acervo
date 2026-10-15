-- acervo — modelo relacional de Organización Ejemplo (100% sintética).
-- Convenciones: tablas en singular y snake_case; clave sustituta <tabla>_id; claves de negocio con UNIQUE;
-- fechas validadas con date(x) IS x: con "=", una fecha inválida da NULL y el CHECK la dejaría pasar;
-- dominios cerrados con CHECK; fechas ISO 8601 (TEXT); montos en pesos enteros; sin columnas derivadas.
-- Los datos de identidad y de salud viven en tablas propias de acceso restringido: el resto del modelo
-- solo conoce el identificador sustituto (seudonimización por diseño).
PRAGMA foreign_keys = ON;

-- Estructura ------------------------------------------------------------------------------------------

CREATE TABLE sede (
    sede_id      INTEGER PRIMARY KEY,
    codigo       TEXT    NOT NULL UNIQUE CHECK (codigo GLOB 'SE-[0-9][0-9]'),
    nombre       TEXT    NOT NULL,
    comuna       TEXT    NOT NULL,
    region       TEXT    NOT NULL
);

CREATE TABLE programa (
    programa_id  INTEGER PRIMARY KEY,
    codigo       TEXT    NOT NULL UNIQUE,
    nombre       TEXT    NOT NULL,
    tipo         TEXT    NOT NULL CHECK (tipo IN ('Servicio de día', 'Servicio residencial', 'Programa educativo', 'Programa de empleo')),
    sede_id      INTEGER NOT NULL REFERENCES sede (sede_id)
);

CREATE TABLE centro_costo (
    centro_costo_id INTEGER PRIMARY KEY,
    codigo          TEXT    NOT NULL UNIQUE,
    nombre          TEXT    NOT NULL,
    programa_id     INTEGER REFERENCES programa (programa_id)  -- NULL: centro de apoyo (administración central)
);

CREATE TABLE actividad (
    actividad_id INTEGER PRIMARY KEY,
    programa_id  INTEGER NOT NULL REFERENCES programa (programa_id),
    nombre       TEXT    NOT NULL,
    UNIQUE (programa_id, nombre)
);

-- Participantes ---------------------------------------------------------------------------------------

CREATE TABLE participante (
    participante_id INTEGER PRIMARY KEY,
    programa_id     INTEGER NOT NULL REFERENCES programa (programa_id),
    fecha_ingreso   TEXT    NOT NULL CHECK (date(fecha_ingreso) IS fecha_ingreso),
    fecha_egreso    TEXT    CHECK (fecha_egreso IS NULL OR fecha_egreso >= fecha_ingreso),
    tramo_edad      TEXT    NOT NULL CHECK (tramo_edad IN ('0-13', '14-17', '18-29', '30-44', '45-59', '60+')),
    comuna          TEXT    NOT NULL
);

CREATE TABLE participante_identidad (          -- restringida: identifica a la persona
    participante_id  INTEGER PRIMARY KEY REFERENCES participante (participante_id),
    rut              TEXT    NOT NULL UNIQUE CHECK (rut GLOB '[0-9]*-[0-9K]'),
    nombres          TEXT    NOT NULL,
    apellidos        TEXT    NOT NULL,
    fecha_nacimiento TEXT    NOT NULL CHECK (date(fecha_nacimiento) IS fecha_nacimiento),
    representante    TEXT                       -- NULL si la persona actúa por sí misma
);

CREATE TABLE participante_salud (              -- restringida: dato personal sensible
    participante_id       INTEGER PRIMARY KEY REFERENCES participante (participante_id),
    grado_apoyo           TEXT    NOT NULL CHECK (grado_apoyo IN ('Bajo', 'Medio', 'Alto', 'Muy alto')),
    condicion_cronica     INTEGER NOT NULL CHECK (condicion_cronica IN (0, 1)),
    observacion_clinica   TEXT
);

CREATE TABLE consentimiento (
    consentimiento_id INTEGER PRIMARY KEY,
    participante_id   INTEGER NOT NULL REFERENCES participante (participante_id),
    finalidad         TEXT    NOT NULL CHECK (finalidad IN ('Atención del programa', 'Registro fotográfico', 'Investigación y estadística')),
    otorgado_por      TEXT    NOT NULL CHECK (otorgado_por IN ('Titular', 'Representante legal')),
    fecha_otorgamiento TEXT   NOT NULL CHECK (date(fecha_otorgamiento) IS fecha_otorgamiento),
    fecha_revocacion  TEXT    CHECK (fecha_revocacion IS NULL OR fecha_revocacion >= fecha_otorgamiento),
    UNIQUE (participante_id, finalidad, fecha_otorgamiento)
);

CREATE TABLE asistencia (
    asistencia_id   INTEGER PRIMARY KEY,
    participante_id INTEGER NOT NULL REFERENCES participante (participante_id),
    actividad_id    INTEGER NOT NULL REFERENCES actividad (actividad_id),
    fecha           TEXT    NOT NULL CHECK (date(fecha) IS fecha),
    presente        INTEGER NOT NULL CHECK (presente IN (0, 1)),
    UNIQUE (participante_id, actividad_id, fecha)
);

CREATE TABLE solicitud_derecho (
    solicitud_id     INTEGER PRIMARY KEY,
    participante_id  INTEGER REFERENCES participante (participante_id),
    derecho          TEXT    NOT NULL CHECK (derecho IN ('Acceso', 'Rectificación', 'Supresión', 'Oposición', 'Portabilidad', 'Bloqueo')),
    fecha_recepcion  TEXT    NOT NULL CHECK (date(fecha_recepcion) IS fecha_recepcion),
    fecha_respuesta  TEXT    CHECK (fecha_respuesta IS NULL OR fecha_respuesta >= fecha_recepcion),
    estado           TEXT    NOT NULL CHECK (estado IN ('Recibida', 'En curso', 'Respondida', 'Rechazada'))
);

-- Personas y finanzas -----------------------------------------------------------------------------------

CREATE TABLE colaborador (
    colaborador_id  INTEGER PRIMARY KEY,
    centro_costo_id INTEGER NOT NULL REFERENCES centro_costo (centro_costo_id),
    cargo           TEXT    NOT NULL,
    fecha_ingreso   TEXT    NOT NULL CHECK (date(fecha_ingreso) IS fecha_ingreso),
    jornada_horas   INTEGER NOT NULL CHECK (jornada_horas BETWEEN 1 AND 44)
);

CREATE TABLE colaborador_identidad (           -- restringida: identifica a la persona
    colaborador_id INTEGER PRIMARY KEY REFERENCES colaborador (colaborador_id),
    rut            TEXT    NOT NULL UNIQUE CHECK (rut GLOB '[0-9]*-[0-9K]'),
    nombre         TEXT    NOT NULL,
    correo         TEXT    NOT NULL UNIQUE CHECK (correo LIKE '%_@_%')
);

CREATE TABLE movimiento_contable (
    movimiento_id   INTEGER PRIMARY KEY,
    fecha           TEXT    NOT NULL CHECK (date(fecha) IS fecha),
    cuenta          TEXT    NOT NULL CHECK (length(cuenta) = 6),
    centro_costo_id INTEGER NOT NULL REFERENCES centro_costo (centro_costo_id),
    monto           INTEGER NOT NULL CHECK (monto <> 0),
    glosa           TEXT    NOT NULL,
    comprobante     TEXT    NOT NULL,
    UNIQUE (comprobante, cuenta, centro_costo_id)
);

CREATE TABLE cuarentena (                      -- filas de las fuentes que no pasaron la validación
    cuarentena_id INTEGER PRIMARY KEY,
    fuente        TEXT    NOT NULL,
    fila          INTEGER NOT NULL,
    motivo        TEXT    NOT NULL,
    UNIQUE (fuente, fila, motivo)
);

-- Índices para las consultas de los tableros ---------------------------------------------------------------

CREATE INDEX ix_asistencia_actividad_fecha ON asistencia (actividad_id, fecha);
CREATE INDEX ix_movimiento_centro_fecha ON movimiento_contable (centro_costo_id, fecha);
CREATE INDEX ix_participante_programa ON participante (programa_id);

-- Capa analítica: vistas sin identidad ni salud, lo único que consumen los tableros -----------------------

CREATE VIEW v_asistencia_mensual AS
SELECT p.programa_id,
       pr.nombre                      AS programa,
       substr(a.fecha, 1, 7)          AS mes,
       COUNT(DISTINCT a.participante_id) AS participantes,
       SUM(a.presente)                AS asistencias,
       COUNT(*)                       AS sesiones_programadas,
       ROUND(1.0 * SUM(a.presente) / COUNT(*), 4) AS tasa_asistencia
FROM asistencia a
JOIN participante p  ON p.participante_id = a.participante_id
JOIN programa pr     ON pr.programa_id = p.programa_id
GROUP BY p.programa_id, pr.nombre, substr(a.fecha, 1, 7);

CREATE VIEW v_gasto_programa AS
SELECT COALESCE(pr.nombre, 'Administración central') AS programa,
       substr(m.fecha, 1, 7)  AS mes,
       SUM(m.monto)           AS gasto
FROM movimiento_contable m
JOIN centro_costo cc    ON cc.centro_costo_id = m.centro_costo_id
LEFT JOIN programa pr   ON pr.programa_id = cc.programa_id
WHERE m.cuenta LIKE '6%'
GROUP BY COALESCE(pr.nombre, 'Administración central'), substr(m.fecha, 1, 7);

CREATE VIEW v_costo_por_participante AS
SELECT g.programa, g.mes, g.gasto, a.participantes,
       CAST(ROUND(1.0 * g.gasto / a.participantes) AS INTEGER) AS costo_por_participante
FROM v_gasto_programa g
JOIN v_asistencia_mensual a ON a.programa = g.programa AND a.mes = g.mes;

CREATE VIEW v_consentimiento_vigente AS
SELECT participante_id, finalidad, otorgado_por, fecha_otorgamiento
FROM consentimiento
WHERE fecha_revocacion IS NULL;
