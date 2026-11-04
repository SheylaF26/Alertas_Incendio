
import os
import csv
import io
import json
from pathlib import Path
from functools import lru_cache

import requests
from shapely.geometry import shape, Point


URL_BASE = "https://firms.modaps.eosdis.nasa.gov/api/area/csv"

FUENTE = "VIIRS_SNPP_NRT"

# Rectángulo de consulta que cubre Ecuador continental.
# El polígono GeoJSON realizará el filtro geográfico definitivo.
AREA_CONTINENTAL = "-81.1,-5.1,-75.1,1.5"


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


def obtener_focos_calor():

    map_key = os.getenv("NASA_FIRMS_MAP_KEY")

    if not map_key:
        raise ValueError(
            "No se encuentra configurada NASA_FIRMS_MAP_KEY"
        )

    poligono = cargar_poligono_ecuador()

    url = (
        f"{URL_BASE}/{map_key}/{FUENTE}/"
        f"{AREA_CONTINENTAL}/1"
    )

    respuesta = requests.get(url, timeout=30)
    respuesta.raise_for_status()

    lector = csv.DictReader(io.StringIO(respuesta.text))

    focos = []

    for fila in lector:

        if not fila.get("latitude") or not fila.get("longitude"):
            continue

        latitud = float(fila["latitude"])
        longitud = float(fila["longitude"])

        punto = Point(longitud, latitud)

        # Solo conservar detecciones dentro del Ecuador continental.
        if not poligono.covers(punto):
            continue

        foco = {
            "latitude": latitud,
            "longitude": longitud,
            "brightness": fila.get("bright_ti4"),
            "brightness_ti5": fila.get("bright_ti5"),
            "acq_date": fila.get("acq_date"),
            "acq_time": fila.get("acq_time"),
            "satellite": fila.get("satellite"),
            "instrument": fila.get("instrument"),
            "confidence": fila.get("confidence"),
            "frp": fila.get("frp"),
            "daynight": fila.get("daynight"),
        }

        focos.append(foco)

    return focos
