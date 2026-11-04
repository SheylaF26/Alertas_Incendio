import os
import csv
import io
import json
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path
from functools import lru_cache
from zoneinfo import ZoneInfo

import requests
from django.core.cache import cache
from shapely.geometry import shape, Point


logger = logging.getLogger(__name__)

URL_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

# Satélites VIIRS (píxel de 375 m). Se consultan los tres porque pasan a
# horas distintas y alguno puede quedarse sin datos (p. ej. S-NPP en nov-2026).
FUENTES = ("VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT", "VIIRS_SNPP_NRT")

# Rectángulo de consulta que cubre Ecuador continental.
# El polígono GeoJSON realizará el filtro geográfico definitivo.
AREA_CONTINENTAL = "-81.1,-5.1,-75.1,1.5"

# Para FIRMS "1 día" es el día UTC en curso (vacío a primera hora UTC, que en
# Ecuador es la noche anterior). Se piden 2 días y se filtra por hora.
DIAS_CONSULTA = 2
HORAS_POR_DEFECTO = 24
HORAS_MAXIMAS = 48

# Todos los usuarios comparten la misma consulta: FIRMS solo se llama una vez
# cada CACHE_SEGUNDOS, sin importar cuántas personas abran el visor.
CACHE_CLAVE = "nasa_firms_focos"
CACHE_SEGUNDOS = 15 * 60

ZONA_ECUADOR = ZoneInfo("America/Guayaquil")

CONFIANZA_VIIRS = {"l": "baja", "n": "nominal", "h": "alta"}


@lru_cache(maxsize=1)
def cargar_poligono_ecuador():
    """
    Carga el GeoJSON de Ecuador y selecciona su parte continental.
    Se identifica como el polígono de mayor superficie.
    """
    ruta = Path(__file__).with_name("geojson_ecuador.json")

    if not ruta.exists():
        raise FileNotFoundError(
            f"No se encontró el archivo geográfico: {ruta}"
        )

    with open(ruta, encoding="utf-8") as archivo:
        datos = json.load(archivo)

    geometria = shape(datos["features"][0]["geometry"])

    if geometria.geom_type == "MultiPolygon":
        poligono = max(geometria.geoms, key=lambda parte: parte.area)
    elif geometria.geom_type == "Polygon":
        poligono = geometria
    else:
        raise ValueError(
            f"Tipo de geometría no esperado: {geometria.geom_type}"
        )

    return poligono


def _numero(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _fecha_deteccion(fila):
    """acq_date + acq_time (HHMM, en UTC) → datetime UTC."""
    hora = fila.get("acq_time", "").zfill(4)
    return datetime.strptime(
        f"{fila['acq_date']} {hora}", "%Y-%m-%d %H%M"
    ).replace(tzinfo=timezone.utc)


def _descargar_fuente(map_key, fuente, poligono):
    url = (
        f"{URL_BASE}/{map_key}/{fuente}/"
        f"{AREA_CONTINENTAL}/{DIAS_CONSULTA}"
    )

    respuesta = requests.get(url, timeout=30)
    respuesta.raise_for_status()

    # Con la clave inválida o sin cupo, FIRMS responde 200 con un texto de error
    if not respuesta.text.lstrip().startswith("latitude"):
        raise ValueError(f"{fuente}: {respuesta.text[:120]!r}")

    focos = []

    for fila in csv.DictReader(io.StringIO(respuesta.text)):

        if not fila.get("latitude") or not fila.get("longitude"):
            continue

        latitud = float(fila["latitude"])
        longitud = float(fila["longitude"])

        # Solo conservar detecciones dentro del Ecuador continental.
        if not poligono.covers(Point(longitud, latitud)):
            continue

        fecha_utc = _fecha_deteccion(fila)
        confianza = fila.get("confidence")

        focos.append({
            "latitude": latitud,
            "longitude": longitud,
            "brightness": _numero(fila.get("bright_ti4")),
            "brightness_ti5": _numero(fila.get("bright_ti5")),
            "frp": _numero(fila.get("frp")),
            "acq_date": fila.get("acq_date"),
            "acq_time": fila.get("acq_time"),
            # acq_date/acq_time vienen en UTC; fecha_local es hora de Ecuador
            "fecha_utc": fecha_utc.isoformat(),
            "fecha_local": fecha_utc.astimezone(ZONA_ECUADOR).isoformat(),
            "satellite": fila.get("satellite"),
            "instrument": fila.get("instrument"),
            "fuente": fuente,
            "confidence": confianza,
            "confianza": CONFIANZA_VIIRS.get(confianza, confianza),
            "daynight": fila.get("daynight"),
        })

    return focos


def _descargar_focos():
    """Focos de los últimos DIAS_CONSULTA días de todas las FUENTES."""

    map_key = os.getenv("NASA_FIRMS_MAP_KEY")

    if not map_key:
        raise ValueError(
            "No se encuentra configurada NASA_FIRMS_MAP_KEY"
        )

    poligono = cargar_poligono_ecuador()

    focos = []
    errores = []

    # Si un satélite falla se sigue con los demás
    for fuente in FUENTES:
        try:
            focos.extend(_descargar_fuente(map_key, fuente, poligono))
        except Exception as error:
            logger.warning("NASA FIRMS %s: %s", fuente, error)
            errores.append(fuente)

    if len(errores) == len(FUENTES):
        raise RuntimeError("Ninguna fuente de NASA FIRMS respondió")

    focos.sort(key=lambda foco: foco["fecha_utc"], reverse=True)
    return focos


def obtener_focos_calor(horas=HORAS_POR_DEFECTO):
    """
    Focos de calor de Ecuador continental detectados en las últimas `horas`
    (máximo HORAS_MAXIMAS), del más reciente al más antiguo.
    """
    horas = max(1, min(int(horas), HORAS_MAXIMAS))

    focos = cache.get(CACHE_CLAVE)
    if focos is None:
        focos = _descargar_focos()
        cache.set(CACHE_CLAVE, focos, CACHE_SEGUNDOS)

    desde = (datetime.now(timezone.utc) - timedelta(hours=horas)).isoformat()
    return [foco for foco in focos if foco["fecha_utc"] >= desde]
