# Análisis BESS — Mercado eléctrico español

Plataforma de análisis del mercado eléctrico español orientada a baterías (BESS):
precios del mercado diario, ingresos de arbitraje por duración de batería y su
evolución. Estado actual: **fase 1** (datos de OMIE, cálculo diario y una página
de comprobación).

## Requisitos

- Windows 11 con PowerShell
- Python 3.14 y Git

> **Nota sobre Smart App Control (Windows):** en el equipo de desarrollo está activado y
> bloquea una DLL de pandas 3.x ("Una directiva de Control de aplicaciones bloqueó este
> archivo"). Por eso `requirements.txt` fija `pandas>=2.3,<3`, que funciona correctamente.

## Instalación

Desde la carpeta del proyecto, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

No hace falta "activar" el entorno: todos los comandos de abajo llaman directamente a
`.\.venv\Scripts\python.exe`.

## Uso

**1. Descargar precios de OMIE** (por defecto, el último año hasta mañana):

```powershell
.\.venv\Scripts\python.exe -m scripts.backfill_prices
.\.venv\Scripts\python.exe -m scripts.backfill_prices --start 2025-09-28 --end 2026-09-29
```

Los ficheros originales se guardan en `data/raw/omie/` y se reutilizan: repetir el
comando no vuelve a descargar lo que ya existe. Si falta algún día pasado en OMIE,
el script lo avisa al final (no rellena datos).

**2. Calcular los ingresos diarios de arbitraje** (tabla `bess_daily`):

```powershell
.\.venv\Scripts\python.exe -m scripts.compute_bess_daily
```

**3. Arrancar la web en local:**

```powershell
.\.venv\Scripts\python.exe -m streamlit run app/Inicio.py
```

Se abre en <http://localhost:8501>. Para pararla: `Ctrl + C` en la terminal.

La página **Calculadora BESS** permite elegir el periodo y las características de la
batería (potencia, capacidad, eficiencia, ciclos máximos al día, estado de carga
mínimo y máximo, coste de degradación) y calcula al momento el arbitraje óptimo con
los precios guardados.

**Tests:**

```powershell
.\.venv\Scripts\python.exe -m pytest
```

## Estructura

```
src/
  bess_arbitrage.py   Cálculo de arbitraje (métodos óptimo y simple)
  ingest/omie.py      Descarga y normalización de precios de OMIE
  analytics/          Cálculos derivados (bess_daily)
  db/                 Conexión, esquema y lectura/escritura de la base de datos
app/
  Inicio.py           Página de inicio de Streamlit
  pages/              Resto de páginas
  branding.toml       Marca: nombre, logo, colores y enlace de contacto
  i18n.py             Textos en español e inglés
scripts/              Backfill histórico y cálculo de bess_daily
tests/                Tests (fixtures/ contiene ficheros reales de OMIE)
data/                 Base de datos y descargas (no se sube a Git; se regenera)
```

## Base de datos

- Por defecto, SQLite en `data/bess.db` (se puede cambiar con la variable `BESS_DB_PATH`).
- Si se definen las variables de entorno `TURSO_URL` y `TURSO_TOKEN`, se usará Turso
  (libSQL) sin cambiar el resto del código (habrá que instalar `libsql`).
- Todas las horas se guardan en **UTC** (`ts_utc` = inicio del periodo) y se muestran en
  hora de Madrid.

| Tabla | Contenido | Clave única |
|---|---|---|
| `prices` | Precio por periodo, mercado (`ES`, `PT`), resolución (60/15 min) y fichero de origen | `ts_utc, market` |
| `bess_daily` | Ingreso diario de arbitraje por duración (1, 2, 4 h), rte, método y ciclos/día | `date, duration_h, rte, method, max_cycles_per_day` |

## Fuentes de datos

**OMIE — precio marginal del mercado diario** (formato verificado en el
[manual de ficheros de OMIE v1.36](https://www.omie.es/sites/default/files/2025-03/formato_ficheros_inf_pub_136.pdf),
apartado 6.18, y con ficheros reales):

- URL: `https://www.omie.es/es/file-download?parents=marginalpdbc&filename=marginalpdbc_AAAAMMDD.v`
- Contenido: `año;mes;día;periodo;precio_PT;precio_ES;` (**Portugal va antes que España**).
- Hasta el 30-09-2025, periodos horarios (23/24/25 al día); desde el 01-10-2025,
  cuartohorarios (92/96/100 al día).
- `v` es la versión del fichero. OMIE solo conserva la última: si corrige un día, la
  `.1` desaparece y queda la `.2`, `.3`... La ingesta busca la versión vigente.

## Metodología y limitaciones

- **Método óptimo** (el que se publica): optimización lineal que respeta el estado de
  carga periodo a periodo.
- **Método simple**: el mismo problema sin orden temporal. Es una **cota superior**
  garantizada del óptimo (se comprueba en los tests y en todo el histórico).
- Batería de referencia: 1 MW, eficiencia 88 %, 1 ciclo/día, SoC entre 5 % y 95 %.
- Solo arbitraje en el mercado diario con previsión perfecta; no incluye intradía,
  servicios de ajuste, peajes ni degradación real.

*Arbitraje en el mercado diario con previsión perfecta. Resultados orientativos, no
constituyen asesoramiento de inversión.*
