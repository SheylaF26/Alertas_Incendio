"""Sube las fotos de evidencia al servidor de contenidos (contentx). En este backend no se guardan."""
import logging
from uuid import uuid4

import requests
from django.conf import settings
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

logger = logging.getLogger(__name__)

TAMANO_MAXIMO = 10 * 1024 * 1024
# El tipo sale del contenido real del archivo, nunca del nombre que manda el cliente.
FIRMAS = ((b"\xff\xd8\xff", ".jpg", "image/jpeg"), (b"\x89PNG\r\n\x1a\n", ".png", "image/png"))


class FotosNoDisponible(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "No fue posible guardar la foto. Intenta de nuevo."


def _tipo(archivo):
    cabecera = archivo.read(8)
    archivo.seek(0)
    for firma, extension, contenido in FIRMAS:
        if cabecera.startswith(firma):
            return extension, contenido
    raise ValidationError({"foto": "El archivo debe ser una imagen JPG o PNG."})


def subir(archivo):
    """Valida la foto, la envía a contentx y devuelve su URL."""
    if archivo.size > TAMANO_MAXIMO:
        raise ValidationError({"foto": "La foto no puede superar los 10 MB."})
    extension, contenido = _tipo(archivo)
    nombre = f"incendios_{uuid4().hex}{extension}"
    try:
        respuesta = requests.post(settings.CONTENTX_URL_UPLOAD, headers={"Authorization": settings.CONTENTX_TOKEN},
                                  files={"images": (nombre, archivo, contenido)}, timeout=60)
    except requests.RequestException as error:
        logger.error("contentx: falló la subida (%s)", type(error).__name__)
        raise FotosNoDisponible()
    try:
        return respuesta.json()[0]["url"] if respuesta.status_code == 201 else _sin_url(respuesta)
    except (ValueError, KeyError, IndexError, TypeError):
        return _sin_url(respuesta)


def _sin_url(respuesta):
    logger.error("contentx: respuesta inesperada (HTTP %s)", respuesta.status_code)
    raise FotosNoDisponible()
