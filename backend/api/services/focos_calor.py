"""Focos de calor: guarda en la base lo que llega de FIRMS y GOES, y lo consulta para el endpoint."""
import logging
from datetime import timedelta, timezone as dt_timezone
from pathlib import PurePosixPath
from zoneinfo import ZoneInfo

from django.db import connections, transaction
from django.utils import timezone

from api.models import FocoCalor, GoesArchivo

from . import goes, nasa_firms

logger = logging.getLogger(__name__)

DB = "pronostico"
HORAS_POR_DEFECTO = 24
HORAS_MAXIMAS = 168
DIAS_CONTROL_GOES = 7
ZONA_ECUADOR = ZoneInfo("America/Guayaquil")
PREFIJOS_FUENTE = {"viirs": "VIIRS", "goes": "GOES"}

INSERTAR = """
INSERT INTO alerta_incendios.foco_calor
  (fuente, fecha_deteccion, latitud, longitud, frp, temperatura, temperatura_ti5, area_fuego_m2,
   satelite, instrumento, confianza, codigo_calidad, dia_noche, area_protegida_id, es_volcan, geom)
VALUES (%(fuente)s, %(fecha)s, %(latitud)s, %(longitud)s, %(frp)s, %(temperatura)s, %(temperatura_ti5)s,
        %(area_fuego_m2)s, %(satelite)s, %(instrumento)s, %(confianza)s, %(codigo_calidad)s, %(dia_noche)s,
        (SELECT a.id FROM alerta_incendios.area_protegida a
         WHERE ST_Covers(a.geom, ST_SetSRID(ST_MakePoint(%(longitud)s, %(latitud)s), 4326))
         ORDER BY a.id LIMIT 1),
        EXISTS (SELECT 1 FROM alerta_incendios.volcan v
                WHERE v.en_erupcion
                  AND ST_DWithin(v.geom::geography,
                                 ST_SetSRID(ST_MakePoint(%(longitud)s, %(latitud)s), 4326)::geography,
                                 v.radio_km * 1000)),
        ST_SetSRID(ST_MakePoint(%(longitud)s, %(latitud)s), 4326))
ON CONFLICT (fuente, fecha_deteccion, latitud, longitud) DO NOTHING
"""


def guardar(focos):
    """Inserta los focos que aún no existen. Devuelve cuántos fueron nuevos."""
    nuevos = 0
    with connections[DB].cursor() as cur:
        for foco in focos:
            cur.execute(INSERTAR, foco)
            nuevos += cur.rowcount
    return nuevos


def actualizar_firms():
    focos = nasa_firms.descargar_focos()
    with transaction.atomic(using=DB):
        nuevos = guardar(focos)
    return {"recibidos": len(focos), "nuevos": nuevos}


def actualizar_goes():
    """Procesa los archivos GOES recientes que falten. Uno que falle se reintenta en la siguiente corrida."""
    claves = goes.archivos_recientes()
    nombres = {PurePosixPath(c).name: c for c in claves}
    hechos = set(GoesArchivo.objects.filter(archivo__in=nombres).values_list("archivo", flat=True))
    resumen = {"archivos": 0, "errores": 0, "recibidos": 0, "nuevos": 0}

    for nombre, clave in nombres.items():
        if nombre in hechos:
            continue
        try:
            focos = goes.leer_focos(goes.descargar(clave), clave)
            with transaction.atomic(using=DB):
                resumen["nuevos"] += guardar(focos)
                GoesArchivo.objects.create(archivo=nombre, inicio_escaneo=goes.inicio_escaneo(clave),
                                           focos=len(focos), procesado_en=timezone.now())
        except Exception:
            logger.exception("GOES: no se pudo procesar %s", nombre)
            resumen["errores"] += 1
            continue
        resumen["archivos"] += 1
        resumen["recibidos"] += len(focos)

    GoesArchivo.objects.filter(inicio_escaneo__lt=timezone.now() - timedelta(days=DIAS_CONTROL_GOES)).delete()
    return resumen


def _como_float(valor):
    return None if valor is None else float(valor)


def _a_dict(foco):
    fecha_utc = foco.fecha_deteccion.astimezone(dt_timezone.utc)
    return {
        "latitude": float(foco.latitud),
        "longitude": float(foco.longitud),
        "brightness": _como_float(foco.temperatura),
        "brightness_ti5": _como_float(foco.temperatura_ti5),
        "frp": _como_float(foco.frp),
        "area_fuego_m2": _como_float(foco.area_fuego_m2),
        "acq_date": fecha_utc.strftime("%Y-%m-%d"),
        "acq_time": fecha_utc.strftime("%H%M"),
        "fecha_utc": fecha_utc.isoformat(),
        "fecha_local": fecha_utc.astimezone(ZONA_ECUADOR).isoformat(),
        "satellite": foco.satelite,
        "instrument": foco.instrumento,
        "fuente": foco.fuente,
        "confidence": foco.codigo_calidad,
        "confianza": foco.confianza,
        "daynight": foco.dia_noche,
        "area_protegida_id": foco.area_protegida_id,
        "area_protegida": foco.area_protegida.nombre if foco.area_protegida_id else None,
        "es_volcan": foco.es_volcan,
        "detecciones": 1,
    }


def _agrupar(focos):
    """Una entrada por fuente y punto: su detección más reciente (focos ya viene ordenado) y cuántas hubo."""
    puntos = {}
    for foco in focos:
        clave = (foco["fuente"], foco["latitude"], foco["longitude"])
        if clave in puntos:
            puntos[clave]["detecciones"] += 1
        else:
            puntos[clave] = foco
    return list(puntos.values())


def consultar(horas=HORAS_POR_DEFECTO, fuente=None, area=None, agrupar=False):
    """Focos guardados de las últimas `horas`, del más reciente al más antiguo."""
    horas = max(1, min(horas, HORAS_MAXIMAS))
    qs = (FocoCalor.objects.filter(fecha_deteccion__gte=timezone.now() - timedelta(hours=horas))
          .select_related("area_protegida").order_by("-fecha_deteccion", "id"))
    if fuente:
        qs = qs.filter(fuente__startswith=PREFIJOS_FUENTE[fuente])
    if area:
        qs = qs.filter(area_protegida_id=area)
    focos = [_a_dict(foco) for foco in qs]
    return _agrupar(focos) if agrupar else focos
