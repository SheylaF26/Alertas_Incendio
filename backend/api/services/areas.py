"""Contornos de las áreas protegidas para dibujarlas en el mapa del visor."""
import json

from django.core.cache import cache
from django.db import connections

# Unos 50 m: suficiente para el mapa y el archivo queda liviano
TOLERANCIA_GRADOS = 0.0005
CACHE_SEGUNDOS = 10 * 60


def _cargar():
    with connections["pronostico"].cursor() as cur:
        cur.execute("""SELECT id, codigo, nombre,
                              ST_AsGeoJSON(ST_SimplifyPreserveTopology(geom, %s), 5),
                              ST_XMin(geom), ST_YMin(geom), ST_XMax(geom), ST_YMax(geom)
                       FROM alerta_incendios.area_protegida
                       WHERE geom IS NOT NULL
                       ORDER BY nombre""", [TOLERANCIA_GRADOS])
        filas = cur.fetchall()
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "id": id_,
            "geometry": json.loads(geometria),
            "properties": {"id": id_, "codigo": codigo, "nombre": nombre,
                           "bbox": [round(x1, 5), round(y1, 5), round(x2, 5), round(y2, 5)]},
        } for id_, codigo, nombre, geometria, x1, y1, x2, y2 in filas],
    }


def areas_geojson():
    return cache.get_or_set("areas_geojson", _cargar, CACHE_SEGUNDOS)
