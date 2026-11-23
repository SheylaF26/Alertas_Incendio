
import logging

from firebase_admin import messaging

from .firebase_service import obtener_app_firebase


logger = logging.getLogger(__name__)

TOPICO_PUBLICO = "alertas_publicas_inamhi"


def enviar_alerta_publica(
    alerta_id,
    area_id,
    nivel,
    descripcion,
):
    """
    Envia una alerta general a las instalaciones
    suscritas al tema publico de Firebase.

    No incluye informacion privada de reportantes.
    """

    mensaje = messaging.Message(
        topic=TOPICO_PUBLICO,
        notification=messaging.Notification(
            title=f"INAMHI - Peligro {nivel}",
            body=str(descripcion),
        ),
        data={
            "tipo": "alerta",
            "alerta_id": str(alerta_id),
            "area_id": str(area_id),
        },
    )

    try:
        return messaging.send(
            mensaje,
            app=obtener_app_firebase(),
        )

    except Exception:
        logger.exception(
            "Error enviando alerta publica %s",
            alerta_id,
        )

        return None
