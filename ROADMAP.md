# ROADMAP

Estado al **2026-10-15**. Este archivo se edita a mano.

## Hecho

- [x] Modelo relacional en SQLite con restricciones, índices, vistas analíticas y diagrama ER generado
- [x] Generador de seis fuentes sintéticas con errores sembrados y `verdad.csv`
- [x] ETL con cuarentena (fuente, fila y motivo) y reglas de calidad en SQL desde el catálogo
- [x] Privacidad: tablas restringidas, consentimiento por finalidad, extracción seudonimizada, perfiles de acceso y registro de tratamientos
- [x] Cliente de mindicador.cl con reintentos, validación de contrato, caché y respaldo
- [x] Catálogo navegable (`catalogo.html`) verificado contra el esquema
- [ ] CI con `ruff` + `pytest` en GitHub Actions: `.github/` queda fuera del repo hasta que el token tenga el permiso `workflow`

## Próximo

- [ ] Historial de cambios (SCD tipo 2) para el programa de cada participante
- [ ] Bitácora de accesos a las tablas restringidas y su revisión mensual
- [ ] El mismo modelo en BigQuery (DDL y carga) y un tablero en Power BI sobre las vistas analíticas
- [ ] Evaluación de impacto de ejemplo para el tratamiento de datos de salud
