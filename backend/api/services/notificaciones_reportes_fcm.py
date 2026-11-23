
"""
Notificaciones FCM de reportes pendientes.

- Solo notifica a guardaparques activos.
- Solo a guardaparques asignados al area del reporte.
- Solo utiliza dispositivos FCM activos.
- No modifica reportes ni validaciones.
"""

import logging

from django.contrib.auth import get_user_model

from api.models import UsuariosAreas
from api.models.pronostico.dispositivos_fcm import (
    DispositivoFCM,
)
from api.permissions import GUARDAPARQUES

from .firebase_service import enviar_notificacion


logger = logging.getLogger(__name__)

DB = "pronostico"
DB_USUARIOS = "default"


def notificar_reporte_pendiente(
    *,
    registro_id,
    area_id,
    nombre_area,
    tipo_evento,
):
    """
    Envia notificaciones a los guardaparques
    de un area protegida.

    Devuelve el numero de envios aceptados
    por Firebase.
    """

    # 1. Buscar usuarios asignados al area.
    usuarios_area = set(
        UsuariosAreas.objects.using(DB)
        .filter(
            area_protegida_id=area_id,
        )
        .values_list(
            "usuario_id",
            flat=True,
        )
    )

    if not usuarios_area:
        logger.info(
            "FCM reporte %s: area %s sin "
            "usuarios asignados",
            registro_id,
            area_id,
        )
        return 0

    # 2. Solo guardaparques activos.
    Usuario = get_user_model()

    guardaparques = list(
        Usuario.objects.using(DB_USUARIOS)
        .filter(
            id__in=usuarios_area,
            estado="1",
            groups__name=GUARDAPARQUES,
        )
        .values_list("id", flat=True)
        .distinct()
    )

    if not guardaparques:
        logger.info(
            "FCM reporte %s: no hay "
            "guardaparques activos en area %s",
            registro_id,
            area_id,
        )
        return 0

    # 3. Obtener los tokens FCM activos.
    tokens = list(
        DispositivoFCM.objects.using(DB)
        .filter(
            usuario_id__in=guardaparques,
            activo=True,
        )
        .exclude(token="")
        .values_list("token", flat=True)
        .distinct()
    )

    if not tokens:
        logger.info(
            "FCM reporte %s: guardaparques "
            "sin dispositivos registrados",
            registro_id,
        )
        return 0

    # 4. Preparar el mensaje.
    titulo = "INAMHI - Nuevo reporte pendiente"

    cuerpo = (
        f"{tipo_evento} reportado en "
        f"{nombre_area}. Pendiente de validacion."
    )

    datos = {
        "tipo": "reporte_pendiente",
        "registro_id": str(registro_id),
        "area_id": str(area_id),
    }

    # 5. Enviar a cada dispositivo.
    enviados = 0

    for token in tokens:
        try:
            enviar_notificacion(
                token=token,
                titulo=titulo,
                mensaje=cuerpo,
                datos=datos,
            )

            enviados += 1

        except Exception:
            logger.exception(
                "FCM: fallo al notificar un "
                "dispositivo del reporte %s",
                registro_id,
            )

    logger.info(
        "FCM: reporte %s, area %s, "
        "guardaparques %s, "
        "dispositivos %s, "
        "envios aceptados %s",
        registro_id,
        area_id,
        len(guardaparques),
        len(tokens),
        enviados,
    )

    return enviados
