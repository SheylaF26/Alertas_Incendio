
import logging

from django.contrib.auth import get_user_model
from firebase_admin import messaging

from api.models.pronostico.usuarios_areas import UsuariosAreas
from api.models.pronostico.dispositivos_fcm import DispositivoFCM
from api.permissions import CON_LOGIN

from .firebase_service import obtener_app_firebase


logger = logging.getLogger(__name__)

DB = "pronostico"
MAX_TOKENS = 500


def enviar_alerta_por_area(
    *,
    alerta_id,
    area_id,
    nivel,
    descripcion,
    origen,
):
    """
    Envia una alerta FCM solamente a los usuarios
    activos asignados al area protegida indicada.

    Los usuarios institucionales estan en la base
    default, mientras las areas y dispositivos
    estan en pronostico.
    """

    # 1. Buscar usuarios asignados al area.
    usuarios_area = set(
        UsuariosAreas.objects.using(DB)
        .filter(area_protegida_id=area_id)
        .values_list("usuario_id", flat=True)
    )

    if not usuarios_area:
        logger.info(
            "FCM: Area %s sin usuarios asignados",
            area_id,
        )
        return 0

    # 2. Verificar usuarios activos y autorizados.
    Usuario = get_user_model()

    usuarios_autorizados = list(
        Usuario.objects.using("default")
        .filter(
            id__in=usuarios_area,
            estado="1",
            groups__name__in=CON_LOGIN,
        )
        .values_list("id", flat=True)
        .distinct()
    )

    if not usuarios_autorizados:
        logger.info(
            "FCM: Area %s sin usuarios autorizados",
            area_id,
        )
        return 0

    # 3. Obtener exclusivamente tokens activos.
    tokens = list(
        DispositivoFCM.objects.using(DB)
        .filter(
            usuario_id__in=usuarios_autorizados,
            activo=True,
        )
        .values_list("token", flat=True)
        .distinct()
    )

    tokens = [t for t in tokens if t]

    if not tokens:
        logger.info(
            "FCM: No hay dispositivos activos "
            "para el area %s",
            area_id,
        )
        return 0

    # 4. Preparar la notificacion.
    titulo = f"INAMHI - Peligro {nivel}"

    datos = {
        "tipo": "alerta",
        "alerta_id": str(alerta_id),
        "area_id": str(area_id),
        "origen": str(origen),
    }

    app = obtener_app_firebase()
    enviados = 0

    # 5. Enviar en lotes de hasta 500 tokens.
    for inicio in range(0, len(tokens), MAX_TOKENS):
        lote = tokens[inicio:inicio + MAX_TOKENS]

        mensaje = messaging.MulticastMessage(
            tokens=lote,
            notification=messaging.Notification(
                title=titulo,
                body=str(descripcion),
            ),
            data=datos,
            android=messaging.AndroidConfig(
                priority="high",
                notification=messaging.AndroidNotification(
                    channel_id="alertas_incendios",
                    sound="default",
                ),
            ),
            apns=messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        sound="default",
                    )
                )
            ),
        )

        try:
            resultado = messaging.send_each_for_multicast(
                mensaje,
                app=app,
            )

            enviados += resultado.success_count

            for indice, respuesta in enumerate(
                resultado.responses
            ):
                if not respuesta.success:
                    logger.warning(
                        "FCM: Fallo de entrega del "
                        "dispositivo indice %s: %s",
                        inicio + indice,
                        type(respuesta.exception).__name__,
                    )

        except Exception:
            logger.exception(
                "FCM: Error enviando alertas "
                "para el area %s",
                area_id,
            )

    logger.info(
        "FCM: Alerta %s, area %s, "
        "%s de %s envios aceptados",
        alerta_id,
        area_id,
        enviados,
        len(tokens),
    )

    return enviados
