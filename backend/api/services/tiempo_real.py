"""Consultas de las estaciones automáticas en tiempo real. Solo lectura.

Las tablas tienen unos 16 millones de filas y casi todas solo están indexadas por
(id_estacion, fecha_toma_dato, instrumento): por eso siempre se consulta estación por estación
y con un rango de fechas. fecha_toma_dato está en UTC, sin zona horaria.
"""
from datetime import timedelta, timezone as dt_timezone
from zoneinfo import ZoneInfo

from django.core.cache import cache
from django.db import connections
from django.utils import timezone
from shapely import from_wkt, unary_union
from shapely.geometry import Point

from api.models import (
    DireccionVientoMax, DireccionVientoMin, Estacion, HumedadRelativaMax, HumedadRelativaMin,
    Precipitacion, TemperaturaMax, TemperaturaMin, VelocidadVientoMax, VelocidadVientoMin,
)

DB = "tiempo_real"
ZONA_ECUADOR = ZoneInfo("America/Guayaquil")
HORAS_POR_DEFECTO = 24
HORAS_MAXIMAS_ESTACIONES = 72
HORAS_MAXIMAS_SERIE = 168
CACHE_SEGUNDOS = 2 * 60

VARIABLES = {
    "precipitacion": Precipitacion,
    "temperatura_max": TemperaturaMax,
    "temperatura_min": TemperaturaMin,
    "humedad_relativa_max": HumedadRelativaMax,
    "humedad_relativa_min": HumedadRelativaMin,
    "velocidad_viento_max": VelocidadVientoMax,
    "velocidad_viento_min": VelocidadVientoMin,
    "direccion_viento_max": DireccionVientoMax,
    "direccion_viento_min": DireccionVientoMin,
}

# El mismo criterio de dato válido que usa el visor para las automáticas.
CALIDAD_SQL = "v.valor IS NOT NULL AND v.nivel_calidad >= 1 AND v.estado_calidad = 1"
ESTACIONES_SQL = ("SELECT id, cod_inamhi, nombre, provincia, canton, latitud, longitud, altitud "
                  "FROM public.estaciones "
                  "WHERE estado_estacion = 'OPERATIVA' AND categoria IN ('METEOROLOGICA', 'HIDRO - METEOROLOGICA') "
                  "AND latitud IS NOT NULL AND longitud IS NOT NULL AND latitud <> 0 AND longitud <> 0")
# Algunas estaciones tienen el reloj adelantado: lo que venga "del futuro" no se toma en cuenta.
AHORA_SQL = "(now() AT TIME ZONE 'UTC')"


def _fechas(fecha):
    fecha = fecha.replace(tzinfo=dt_timezone.utc) if timezone.is_naive(fecha) else fecha.astimezone(dt_timezone.utc)
    return {"fecha_utc": fecha.isoformat(), "fecha_local": fecha.astimezone(ZONA_ECUADOR).isoformat()}


def _ultimos_valores(horas):
    """(nombre de variable, id de estación, fecha, valor): el último dato válido de cada estación y variable."""
    partes, parametros = [], []
    for nombre, modelo in VARIABLES.items():
        partes.append(f"""
            SELECT %s::text AS variable, e.id, x.fecha_toma_dato, x.valor
            FROM ({ESTACIONES_SQL}) e
            CROSS JOIN LATERAL (
                SELECT v.fecha_toma_dato, v.valor
                FROM {modelo._meta.db_table} v
                WHERE v.id_estacion = e.id
                  AND v.fecha_toma_dato BETWEEN {AHORA_SQL} - make_interval(hours => %s) AND {AHORA_SQL}
                  AND {CALIDAD_SQL}
                ORDER BY v.fecha_toma_dato DESC
                LIMIT 1
            ) x""")
        parametros.extend([nombre, horas])
    with connections[DB].cursor() as cur:
        cur.execute(" UNION ALL ".join(partes), parametros)
        return cur.fetchall()


def _cargar_estaciones(horas):
    with connections[DB].cursor() as cur:
        cur.execute(ESTACIONES_SQL)
        catalogo = cur.fetchall()
    estaciones = {
        id_: {"id": id_, "codigo": codigo, "nombre": nombre, "provincia": provincia, "canton": canton,
              "latitud": latitud, "longitud": longitud, "altitud": altitud, "variables": {}}
        for id_, codigo, nombre, provincia, canton, latitud, longitud, altitud in catalogo
    }
    for variable, id_, fecha, valor in _ultimos_valores(horas):
        estaciones[id_]["variables"][variable] = {"valor": float(valor), **_fechas(fecha)}
    return [e for e in estaciones.values() if e["variables"]]


def _limite_del_area(area):
    """Geometría (límite + 10 km) de un área protegida, o None si no existe o no tiene geometría."""
    with connections["pronostico"].cursor() as cur:
        cur.execute("SELECT ST_AsText(geom_buffer) FROM alerta_incendios.area_protegida WHERE id = %s", [area])
        fila = cur.fetchone()
    return from_wkt(fila[0]) if fila and fila[0] else None


def _zona_de_todas_las_areas():
    """Unión de todas las áreas protegidas con sus 10 km."""
    with connections["pronostico"].cursor() as cur:
        cur.execute("SELECT ST_AsText(geom_buffer) FROM alerta_incendios.area_protegida WHERE geom_buffer IS NOT NULL")
        return unary_union([from_wkt(fila[0]) for fila in cur.fetchall()])


def estaciones_con_datos(horas=HORAS_POR_DEFECTO, area=None, solo_areas=False):
    """Estaciones con dato válido en las últimas `horas`.

    Con `area`, solo las de esa área y sus 10 km; con `solo_areas`, las de cualquier área y sus 10 km.
    Devuelve None si el área pedida no existe.
    """
    horas = max(1, min(horas, HORAS_MAXIMAS_ESTACIONES))
    estaciones = cache.get_or_set(f"tiempo_real_estaciones_{horas}", lambda: _cargar_estaciones(horas), CACHE_SEGUNDOS)
    if area is None and not solo_areas:
        return horas, estaciones
    zona = _limite_del_area(area) if area is not None else _zona_de_todas_las_areas()
    if zona is None:
        return horas, None
    return horas, [e for e in estaciones if zona.covers(Point(e["longitud"], e["latitud"]))]


def serie(estacion_id, variable, horas=HORAS_POR_DEFECTO):
    """Datos válidos de una variable en una estación, del más antiguo al más reciente.

    Devuelve None si la estación no existe.
    """
    estacion = Estacion.objects.filter(pk=estacion_id).first()
    if estacion is None:
        return None
    horas = max(1, min(horas, HORAS_MAXIMAS_SERIE))
    ahora = timezone.now()
    filas = (VARIABLES[variable].objects
             .filter(id_estacion=estacion_id, fecha_toma_dato__gte=ahora - timedelta(hours=horas),
                     fecha_toma_dato__lte=ahora, valor__isnull=False, nivel_calidad__gte=1, estado_calidad=1)
             .order_by("fecha_toma_dato", "instrumento")
             .values_list("fecha_toma_dato", "valor", "instrumento"))
    return {
        "estacion": {"id": estacion.id, "codigo": estacion.cod_inamhi, "nombre": estacion.nombre},
        "variable": variable,
        "horas": horas,
        "datos": [{**_fechas(fecha), "valor": float(valor), "instrumento": instrumento}
                  for fecha, valor, instrumento in filas],
    }
