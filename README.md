# acervo

> *Gobierno de datos de punta a punta para una organización que atiende personas: modelo relacional que no deja entrar datos inválidos, protección de datos personales desde el diseño para la Ley 21.719, integración resiliente con una API REST pública y un catálogo de metadatos que se contrasta con el esquema real en cada carga.*

**Demo:** <https://h-e-sanchez.github.io/acervo/> · **Catálogo:** <https://h-e-sanchez.github.io/acervo/catalogo.html>

Parte del portafolio **Control de gestión, construido como software**, de Hernán Elías Sánchez. El caso es
**Fundación Ejemplo**, una fundación ficticia con 3 sedes, 6 programas y datos 100% sintéticos.

## Características de ingeniería

- **Modelo relacional verificable:** 14 tablas en 3FN y 4 vistas en SQLite (`modelo/esquema.sql`), con claves sustitutas y de negocio, dominios cerrados con `CHECK`, claves foráneas activas y fechas validadas. El diagrama ER se genera desde el esquema (`sitio/erd.svg`) y un test exige que esté al día.
- **ETL con cuarentena:** seis fuentes con sus formatos reales (RUT con puntos y dígito verificador, fechas `DD-MM-AAAA`, montos con miles, "Sí" escrito a mano). Lo inválido queda en cuarentena con fuente, fila y motivo, sin copiar su contenido. Los tests exigen encontrar exactamente los errores sembrados en `datos/verdad.csv`.
- **Privacidad por diseño (Ley 21.719):** identidad y salud en tablas restringidas, tramo de edad en lugar de fecha de nacimiento, consentimiento por finalidad (el de un niño o niña exige representante), registro de tratamientos, perfiles de acceso verificados como código y extracción seudonimizada (HMAC-SHA256) para estudios.
- **Catálogo y API, probados sin red:** el catálogo (`catalogo/catalogo.json`) documenta dueño, custodio, origen, retención, tratamientos y nivel de cada columna, y falla si diverge del esquema. El cliente de [mindicador.cl](https://mindicador.cl/) (`src/indicadores.py`) usa tiempo de espera, reintentos con espera exponencial, validación de contrato, caché y una muestra de respaldo.

## Guía de uso rápido

```bash
pip install -r requirements-dev.txt          # solo pytest y ruff: el código usa la biblioteca estándar
python datos/generar_fuentes.py              # exportaciones sintéticas de las seis fuentes y la verdad sembrada
python -m src.construir                      # carga, valida y publica sitio/*.json y sitio/erd.svg; deja salida/acervo.db
python -m src.construir --indicadores        # además refresca la muestra de respaldo de la API
python -m src.indicadores uf utm dolar       # UF, UTM y dólar del día
python -m pytest -q
ruff check .
python -m http.server 8000                   # la página en http://localhost:8000
```

```bash
sqlite3 salida/acervo.db "SELECT * FROM v_costo_por_participante;"
```

| Carpeta | Contenido |
|---|---|
| `modelo/` | El DDL: tablas, restricciones, índices y vistas analíticas |
| `datos/fuentes/` | Las exportaciones sintéticas y la configuración institucional (`maestros.json`) |
| `catalogo/` | El catálogo de metadatos: datasets, columnas, tratamientos, perfiles, reglas de calidad y glosario |
| `src/` | ETL, gobierno de datos, privacidad, cliente de la API, diagrama ER y build |
| `sitio/` | Lo que publica el build y consume la página (versionado y verificado por test) |

Los RUT de los datos son sintéticos: tienen dígito verificador válido, pero están en el rango de 33 a 35 millones, lejos de los asignados hoy a personas naturales. La extracción para estudios usa la clave de la variable de entorno `ACERVO_CLAVE_SEUDONIMO`; la clave de
demostración del código no sirve para datos reales. El resumen de la Ley 21.719 de la página está hecho
sobre el texto publicado en LeyChile y no es asesoría legal.

## English

A data governance showcase by Hernán Elías Sánchez for a fictitious Chilean foundation: a normalized
relational model with constraints and an auto-generated ER diagram, an ETL that quarantines invalid rows,
privacy by design for Chile's data protection law (Law 21,719), a resilient client for a public REST API,
and a metadata catalog checked against the real schema on every load. Standard library only; all data is
synthetic.

---

Diseñamos `acervo` con una idea simple: un dato que identifica a una persona se ordena, se protege y se documenta antes de llegar a cualquier tablero.
