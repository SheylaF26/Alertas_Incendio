"""Reportes de incendio enviados desde la app y su validación.

- Un guardaparques reporta: queda validado de inmediato.
- Un aledaño (grupo brigadas) reporta: queda pendiente hasta que un guardaparques asignado a esa área decida.
- Pendiente significa que el reporte todavía no tiene fila en validacion.
"""
from django.contrib.auth import get_user_model
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework import status
from rest_framework.exceptions import APIException, NotFound, PermissionDenied, ValidationError

from api.models import Estados, Registro, UsuariosAreas, Validacion
from api.permissions import GUARDAPARQUES

from . import generar_alertas

DB = "pronostico"
VALIDADO = "Validado"
RECHAZADO = "Rechazado"


class YaDecidido(APIException):
    status_code = status.HTTP_409_CONFLICT
    default_detail = "Este reporte ya fue validado o rechazado."


def _areas_de(usuario):
    return set(UsuariosAreas.objects.filter(usuario_id=usuario.id).values_list("area_protegida_id", flat=True))


def _nombres(usuario_ids):
    """Nombre de quienes reportaron. usuarios está en otra base y solo se lee."""
    usuarios = get_user_model().objects.filter(id__in=set(usuario_ids))
    return {u.id: u.get_full_name() or u.username for u in usuarios}


def _a_dict(registro, estado, nombres):
    return {
        "id": registro.id,
        "usuario_id": registro.usuario_id,
        "reportado_por": nombres.get(registro.usuario_id),
        "fecha_registro": registro.fecha_registro,
        "latitud": float(registro.latitud),
        "longitud": float(registro.longitud),
        "descripcion": registro.descripcion,
        "evidencia": registro.evidencia,
        "tipo_evento": {"id": registro.tipo_evento_id, "nombre": registro.tipo_evento.nombre},
        "area_protegida": {"id": registro.area_protegida_id, "nombre": registro.area_protegida.nombre},
        "estado": estado,
    }


def _elegir_area(usuario, pedida):
    areas = _areas_de(usuario)
    if not areas:
        raise PermissionDenied("No tienes un área protegida asignada.")
    if pedida is not None:
        if pedida not in areas:
            raise PermissionDenied("No estás asignado a esa área protegida.")
        return pedida
    if len(areas) > 1:
        raise ValidationError({"area_protegida_id": "Tienes varias áreas asignadas: indica cuál."})
    return next(iter(areas))


def crear(usuario, datos):
    area_id = _elegir_area(usuario, datos.get("area_protegida_id"))
    es_guardaparques = usuario.groups.filter(name=GUARDAPARQUES).exists()
    ahora = timezone.now()
    with transaction.atomic(using=DB):
        registro = Registro.objects.create(
            usuario_id=usuario.id, fecha_registro=ahora,
            latitud=round(datos["latitud"], 6), longitud=round(datos["longitud"], 6),
            descripcion=datos.get("descripcion"), evidencia=datos.get("evidencia"),
            tipo_evento=datos["tipo_evento"], area_protegida_id=area_id,
        )
        if es_guardaparques:
            Validacion.objects.create(
                usuario_id=usuario.id, registro=registro, estado=Estados.objects.get(nombre=VALIDADO),
                fecha_validacion=ahora, observacion="Validado automáticamente: lo reportó un guardaparques.",
            )
            generar_alertas.desde_registro(registro)
    return _a_dict(registro, "validado" if es_guardaparques else "pendiente", _nombres([usuario.id]))


def pendientes(usuario):
    """Reportes sin decidir de las áreas asignadas al guardaparques, del más reciente al más antiguo."""
    registros = list(Registro.objects.filter(area_protegida__in=_areas_de(usuario), validacion__isnull=True)
                     .select_related("tipo_evento", "area_protegida").order_by("-fecha_registro"))
    nombres = _nombres(r.usuario_id for r in registros)
    return [_a_dict(r, "pendiente", nombres) for r in registros]


def decidir(usuario, registro_id, estado, observacion=None):
    registro = (Registro.objects.select_related("tipo_evento", "area_protegida").filter(pk=registro_id).first())
    if registro is None:
        raise NotFound("El reporte no existe.")
    if registro.area_protegida_id not in _areas_de(usuario):
        raise PermissionDenied("Solo pueden decidir los guardaparques asignados a esa área.")
    if Validacion.objects.filter(registro=registro).exists():
        raise YaDecidido()
    nombre_estado = VALIDADO if estado == "validado" else RECHAZADO
    try:
        with transaction.atomic(using=DB):
            Validacion.objects.create(
                usuario_id=usuario.id, registro=registro, estado=Estados.objects.get(nombre=nombre_estado),
                fecha_validacion=timezone.now(), observacion=observacion,
            )
            if estado == "validado":
                generar_alertas.desde_registro(registro)
    except IntegrityError:   # otro guardaparques decidió al mismo tiempo
        raise YaDecidido()
    return _a_dict(registro, estado, _nombres([registro.usuario_id]))
