"""Crea las alertas a partir del modelo de peligro, los focos de calor y los reportes.

Reglas:
- Modelo: áreas cuyo nivel predominante sea Alto o Muy Alto. Una alerta por área, día pronosticado
  y nivel: si otra corrida repite el mismo nivel para ese día, no se vuelve a avisar.
- Focos: dentro de un área, no volcánicos y con confianza nominal o alta. Máximo una alerta por
  área y fuente cada HORAS_SIN_REPETIR, porque un mismo fuego se detecta cada 10 minutos.
- Reportes: cada reporte validado genera una alerta.
"""
from datetime import timedelta, timezone as zona
from zoneinfo import ZoneInfo
import logging

from django.db import connections, transaction
from django.utils import timezone

from api.models import Alertas, AreaAlerta, FocoCalor, NivelPeligro

# NUEVO: servicio Firebase
from api.services.notificaciones_fcm import enviar_alerta_por_area
from api.services.notificaciones_publicas import enviar_alerta_publica

logger = logging.getLogger(__name__)

DB = "pronostico"
HORAS_SIN_REPETIR = 6
NIVEL_MINIMO_MODELO = 3
CONFIANZAS_FOCO = ("nominal", "alta")
NIVEL_FOCO = "Alto"
NIVEL_REGISTRO = "Muy Alto"
ZONA_ECUADOR = ZoneInfo("America/Guayaquil")
UTC = zona.utc
FUENTES_FOCO = {
    "firms": ("VIIRS", "VIIRS (NASA FIRMS)"),
    "goes": ("GOES", "GOES-19"),
}


def _crear(origen, area_id, nivel, color, descripcion, **enlace):
    with transaction.atomic(using=DB):
        alerta = Alertas.objects.create(origen=origen, nivel_de_riesgo=nivel, color=color, descripcion=descripcion,
                                        fecha=timezone.now(), **enlace)
        AreaAlerta.objects.create(area_protegida_id=area_id, alerta=alerta)

        # NUEVO: enviar Firebase solo después de confirmar
        # la transacción de la base de datos.
        alerta_id = alerta.pk

        def notificar():
            try:
                enviar_alerta_por_area(
                    alerta_id=alerta_id,
                    area_id=area_id,
                    nivel=nivel,
                    descripcion=descripcion,
                    origen=origen,
                )
                # Enviar también a los usuarios públicos.
                enviar_alerta_publica(
                    alerta_id=alerta_id,
                    area_id=area_id,
                    nivel=nivel,
                    descripcion=descripcion,
                )
            except Exception:
                logger.exception(
                    "Error enviando FCM para la alerta %s",
                    alerta_id,
                )

        transaction.on_commit(
            notificar,
            using=DB,
            robust=True,
        )

    return alerta


def desde_modelo(producto_id):
    """Alertas de un producto ya procesado. Devuelve cuántas se crearon."""
    with connections[DB].cursor() as cur:
        cur.execute("""SELECT area_protegida_id, area, nivel_nombre, color, porcentaje_area, vigencia_desde
                       FROM alerta_incendios.v_peligro_resumen
                       WHERE producto_id = %s AND nivel >= %s""", [producto_id, NIVEL_MINIMO_MODELO])
        filas = cur.fetchall()
    creadas = 0
    for area_id, area, nivel, color, porcentaje, validez in filas:
        # Un mismo día llega en varias corridas (hoy, mañana y pasado): una sola alerta por área, día y nivel.
        if AreaAlerta.objects.filter(area_protegida_id=area_id, alerta__origen="modelo",
                                     alerta__nivel_de_riesgo=nivel,
                                     alerta__producto__vigencia_desde=validez).exists():
            continue
        dia = validez.astimezone(UTC).strftime("%d/%m/%Y")
        descripcion = f"El modelo de peligro indica nivel {nivel} en {area} para el {dia} ({porcentaje} % del área)."
        _crear("modelo", area_id, nivel, color, descripcion, producto_id=producto_id)
        creadas += 1
    return creadas


def desde_focos(origen):
    """Alertas de los focos recientes de una fuente ('firms' o 'goes'). Devuelve cuántas se crearon."""
    prefijo, nombre = FUENTES_FOCO[origen]
    corte = timezone.now() - timedelta(hours=HORAS_SIN_REPETIR)
    focos = (FocoCalor.objects
             .filter(fuente__startswith=prefijo, fecha_deteccion__gte=corte, area_protegida__isnull=False,
                     es_volcan=False, confianza__in=CONFIANZAS_FOCO)
             .select_related("area_protegida")
             .order_by("area_protegida_id", "-fecha_deteccion")
             .distinct("area_protegida_id"))
    color = NivelPeligro.objects.get(nombre=NIVEL_FOCO).color
    creadas = 0
    for foco in focos:
        if AreaAlerta.objects.filter(area_protegida_id=foco.area_protegida_id, alerta__origen=origen,
                                     alerta__fecha__gte=corte).exists():
            continue
        hora = foco.fecha_deteccion.astimezone(ZONA_ECUADOR).strftime("%H:%M del %d/%m/%Y")
        descripcion = f"{nombre} detectó un foco de calor en {foco.area_protegida.nombre} a las {hora}."
        _crear(origen, foco.area_protegida_id, NIVEL_FOCO, color, descripcion, foco_calor=foco)
        creadas += 1
    return creadas


def desde_registro(registro):
    """Alerta de un reporte validado. Debe llamarse en la misma transacción que la validación."""
    nivel = NivelPeligro.objects.get(nombre=NIVEL_REGISTRO)
    descripcion = f"{registro.tipo_evento.nombre} reportado en {registro.area_protegida.nombre}."
    return _crear("registro", registro.area_protegida_id, nivel.nombre, nivel.color, descripcion, registro=registro)
