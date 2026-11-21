
import logging
import os
from pathlib import Path

import firebase_admin
from firebase_admin import credentials, messaging

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

logger = logging.getLogger(__name__)


def obtener_app_firebase():
    """
    Inicializa Firebase Admin una sola vez.

    Utiliza las credenciales privadas configuradas
    en el archivo .env del backend.
    """

    try:
        return firebase_admin.get_app()

    except ValueError:
        pass

    ruta_configurada = os.getenv(
        "FIREBASE_CREDENTIALS",
        ""
    ).strip()

    if not ruta_configurada:
        raise ImproperlyConfigured(
            "Falta FIREBASE_CREDENTIALS en .env"
        )

    ruta = Path(ruta_configurada)

    if not ruta.is_absolute():
        ruta = Path(settings.BASE_DIR) / ruta

    ruta = ruta.resolve()

    if not ruta.is_file():
        raise ImproperlyConfigured(
            "No se encontró el archivo de "
            f"credenciales Firebase: {ruta}"
        )

    credencial = credentials.Certificate(str(ruta))

    app = firebase_admin.initialize_app(
        credencial
    )

    logger.info(
        "Firebase Admin SDK inicializado."
    )

    return app


def enviar_notificacion(
    token,
    titulo,
    mensaje,
    datos=None,
):
    """
    Envía una notificación a un dispositivo.

    Esta función se utilizará después de
    implementar el registro de tokens FCM.
    """

    app = obtener_app_firebase()

    mensaje_fcm = messaging.Message(
        token=token,
        notification=messaging.Notification(
            title=titulo,
            body=mensaje,
        ),
        data={
            str(clave): str(valor)
            for clave, valor in (datos or {}).items()
        },
        android=messaging.AndroidConfig(
            priority="high",
        ),
    )

    return messaging.send(
        mensaje_fcm,
        app=app,
    )
