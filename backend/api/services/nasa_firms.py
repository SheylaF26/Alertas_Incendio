"""Descarga de focos de calor VIIRS desde NASA FIRMS."""
import csv
import io
import json
import logging
import os
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path

import requests
from shapely.geometry import Point, shape

logger = logging.getLogger(__name__)

URL_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

# Satélites VIIRS (píxel de 375 m). Se consultan los tres porque pasan a
# horas distintas y alguno puede quedarse sin datos (p. ej. S-NPP en nov-2026).
FUENTES = ("VIIRS_NOAA20_NRT", "VIIRS_NOAA21_NRT", "VIIRS_SNPP_NRT")

# Rectángulo de consulta que cubre Ecuador continental.
# El polígono GeoJSON realiza el filtro geográfico definitivo.
AREA_CONTINENTAL = "-81.1,-5.1,-75.1,1.5"

# Para FIRMS "1 día" es el día UTC en curso (vacío a primera hora UTC, que en
# Ecuador es la noche anterior). Se piden 2 días; lo repetido no se guarda dos veces.
DIAS_CONSULTA = 2

CONFIANZA_VIIRS = {"l": "baja", "n": "nominal", "h": "alta"}


@lru_cache(maxsize=1)
def cargar_poligono_ecuador():
    """Carga el GeoJSON de Ecuador y devuelve su parte continental (el polígono más grande)."""
    ruta = Path(__file__).with_name("geojson_ecuador.json")
    with open(ruta, encoding="utf-8") as archivo:
        datos = json.load(archivo)

    geometria = shape(datos["features"][0]["geometry"])
    if geometria.geom_type == "MultiPolygon":
        return max(geometria.geoms, key=lambda parte: parte.area)
    if geometria.geom_type == "Polygon":
        return geometria
    raise ValueError(f"Tipo de geometría no esperado: {geometria.geom_type}")


def _numero(valor):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return None


def _fecha_deteccion(fila):
    """acq_date + acq_time (HHMM, en UTC) → datetime UTC."""
    hora = fila.get("acq_time", "").zfill(4)
    return datetime.strptime(f"{fila['acq_date']} {hora}", "%Y-%m-%d %H%M").replace(tzinfo=timezone.utc)


def _descargar_fuente(map_key, fuente, poligono):
    url = f"{URL_BASE}/{map_key}/{fuente}/{AREA_CONTINENTAL}/{DIAS_CONSULTA}"
    respuesta = requests.get(url, timeout=30)
    respuesta.raise_for_status()

    # Con la clave inválida o sin cupo, FIRMS responde 200 con un texto de error
    if not respuesta.text.lstrip().startswith("latitude"):
        raise ValueError(f"{fuente}: {respuesta.text[:120]!r}")

    focos = []
    for fila in csv.DictReader(io.StringIO(respuesta.text)):
        if not fila.get("latitude") or not fila.get("longitude"):
            continue
        latitud, longitud = float(fila["latitude"]), float(fila["longitude"])
        if not poligono.covers(Point(longitud, latitud)):
            continue
        codigo = fila.get("confidence")
        focos.append({
            "fuente": fuente,
            "fecha": _fecha_deteccion(fila),
            "latitud": latitud,
            "longitud": longitud,
            "frp": _numero(fila.get("frp")),
            "temperatura": _numero(fila.get("bright_ti4")),
            "temperatura_ti5": _numero(fila.get("bright_ti5")),
            "area_fuego_m2": None,
            "satelite": fila.get("satellite"),
            "instrumento": fila.get("instrument"),
            "confianza": CONFIANZA_VIIRS.get(codigo, codigo),
            "codigo_calidad": codigo,
            "dia_noche": fila.get("daynight"),
        })
    return focos


def descargar_focos():
    """Focos de Ecuador continental de todas las FUENTES. Si un satélite falla se sigue con los demás."""
    map_key = os.getenv("NASA_FIRMS_MAP_KEY")
    if not map_key:
        raise ValueError("No se encuentra configurada NASA_FIRMS_MAP_KEY")

    poligono = cargar_poligono_ecuador()
    focos, errores = [], []
    for fuente in FUENTES:
        try:
            focos.extend(_descargar_fuente(map_key, fuente, poligono))
        except Exception as error:
            # El error puede traer la URL con la clave: solo se registra su tipo.
            logger.warning("NASA FIRMS %s: falló la descarga (%s)", fuente, type(error).__name__)
            errores.append(fuente)

    if len(errores) == len(FUENTES):
        raise RuntimeError("Ninguna fuente de NASA FIRMS respondió")
    return focos
