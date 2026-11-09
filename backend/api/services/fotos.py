"""Sube las fotos de evidencia al servidor de contenidos (contentx). En este backend no se guardan.

Las que pesan más de TAMANO_FINAL se comprimen antes de enviarlas: primero se baja la calidad y,
si no alcanza, también el tamaño de la imagen.
"""
import io
import logging
from uuid import uuid4

import requests
from django.conf import settings
from PIL import Image, ImageOps, UnidentifiedImageError
from rest_framework import status
from rest_framework.exceptions import APIException, ValidationError

logger = logging.getLogger(__name__)

TAMANO_MAXIMO = 10 * 1024 * 1024   # lo más grande que se acepta recibir
TAMANO_FINAL = 3 * 1024 * 1024     # lo más grande que se guarda
CALIDADES = (85, 70, 55, 40)
ESCALAS = (1, 0.75, 0.5, 0.35)
# Evita que una imagen pequeña en bytes pero enorme en píxeles agote la memoria.
Image.MAX_IMAGE_PIXELS = 50_000_000
ERRORES_IMAGEN = (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError)
# El tipo sale del contenido real del archivo, nunca del nombre que manda el cliente.
FIRMAS = ((b"\xff\xd8\xff", ".jpg", "image/jpeg"), (b"\x89PNG\r\n\x1a\n", ".png", "image/png"))
NO_ES_IMAGEN = {"foto": "El archivo debe ser una imagen JPG o PNG válida."}


class FotosNoDisponible(APIException):
    status_code = status.HTTP_502_BAD_GATEWAY
    default_detail = "No fue posible guardar la foto. Intenta de nuevo."


def _tipo(datos):
    for firma, extension, contenido in FIRMAS:
        if datos.startswith(firma):
            return extension, contenido
    raise ValidationError(NO_ES_IMAGEN)


def _comprimir(datos):
    """JPEG de máximo TAMANO_FINAL, con la mejor calidad y el mayor tamaño que quepan."""
    with Image.open(io.BytesIO(datos)) as original:
        imagen = ImageOps.exif_transpose(original).convert("RGB")
    ancho, alto = imagen.size
    for escala in ESCALAS:
        actual = imagen if escala == 1 else imagen.resize((round(ancho * escala), round(alto * escala)), Image.LANCZOS)
        for calidad in CALIDADES:
            salida = io.BytesIO()
            actual.save(salida, "JPEG", quality=calidad, optimize=True)
            if salida.tell() <= TAMANO_FINAL:
                return salida.getvalue()
    raise ValidationError({"foto": "No se pudo reducir la foto a 3 MB."})


def _preparar(archivo):
    """(bytes, extensión, tipo de contenido) listos para enviar."""
    if archivo.size > TAMANO_MAXIMO:
        raise ValidationError({"foto": "La foto no puede superar los 10 MB."})
    datos = archivo.read()
    extension, contenido = _tipo(datos)
    try:
        with Image.open(io.BytesIO(datos)) as imagen:
            imagen.verify()
        if len(datos) <= TAMANO_FINAL:
            return datos, extension, contenido
        return _comprimir(datos), ".jpg", "image/jpeg"
    except ERRORES_IMAGEN:
        raise ValidationError(NO_ES_IMAGEN)


def subir(archivo):
    """Valida la foto, la reduce si hace falta, la envía a contentx y devuelve su URL."""
    datos, extension, contenido = _preparar(archivo)
    nombre = f"incendios_{uuid4().hex}{extension}"
    try:
        respuesta = requests.post(settings.CONTENTX_URL_UPLOAD, headers={"Authorization": settings.CONTENTX_TOKEN},
                                  files={"images": (nombre, datos, contenido)}, timeout=60)
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
