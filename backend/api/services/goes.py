"""Lectura de focos de calor del producto GOES-19 ABI-L2-FDCF (NetCDF cada 10 min, píxel de 2 km).

Los archivos son públicos en el bucket de NOAA en AWS. Cada uno es una imagen del disco completo
con un código por píxel (Mask): aquí se conservan los códigos de fuego más confiables, se convierten
de la proyección geoestacionaria a lat/lon y se filtran a Ecuador continental.
"""
import io
import re
from datetime import datetime, timedelta, timezone

import h5py
import numpy as np
import requests
from shapely import contains_xy

from .nasa_firms import cargar_poligono_ecuador

BUCKET = "https://noaa-goes19.s3.amazonaws.com"
PRODUCTO = "ABI-L2-FDCF"
FUENTE = "GOES19_FDCF"

# Procesado y saturado, con y sin filtro temporal: lo que NOAA recomienda
# a quien tiene poca tolerancia a falsas alarmas.
CODIGOS_FUEGO = (10, 11, 30, 31)

# Si el proceso se detiene, al volver recupera los archivos de estas últimas horas.
HORAS_ATRAS = 3

INICIO_ESCANEO = re.compile(r"_s(\d{13})\d_")


def inicio_escaneo(clave):
    """Fecha UTC de inicio del escaneo, a partir del nombre del archivo (sYYYYJJJHHMMSSt)."""
    return datetime.strptime(INICIO_ESCANEO.search(clave).group(1), "%Y%j%H%M%S").replace(tzinfo=timezone.utc)


def archivos_recientes(horas=HORAS_ATRAS):
    """Claves del bucket de las últimas `horas`, de la más antigua a la más reciente."""
    ahora = datetime.now(timezone.utc)
    claves = []
    for atras in range(horas, -1, -1):
        hora = ahora - timedelta(hours=atras)
        respuesta = requests.get(BUCKET, params={"list-type": 2, "prefix": f"{PRODUCTO}/{hora:%Y/%j/%H}/"}, timeout=30)
        respuesta.raise_for_status()
        claves.extend(re.findall(r"<Key>([^<]+\.nc)</Key>", respuesta.text))
    limite = ahora - timedelta(hours=horas)
    return sorted((c for c in claves if inicio_escaneo(c) >= limite), key=inicio_escaneo)


def _attr(variable, nombre, defecto=None):
    valor = variable.attrs.get(nombre)
    return defecto if valor is None else float(np.ravel(valor)[0])


def _eje(archivo, nombre):
    variable = archivo[nombre]
    return variable[()] * _attr(variable, "scale_factor") + _attr(variable, "add_offset")


def _a_latlon(archivo, filas, columnas):
    """Convierte píxeles de la proyección geoestacionaria a lat/lon (GOES-R Product User Guide)."""
    proyeccion = archivo["goes_imager_projection"]
    r_eq, r_pol = _attr(proyeccion, "semi_major_axis"), _attr(proyeccion, "semi_minor_axis")
    h = _attr(proyeccion, "perspective_point_height") + r_eq
    lon_0 = np.radians(_attr(proyeccion, "longitude_of_projection_origin"))

    x, y = _eje(archivo, "x")[columnas], _eje(archivo, "y")[filas]
    sx, cx, sy, cy = np.sin(x), np.cos(x), np.sin(y), np.cos(y)
    razon = r_eq ** 2 / r_pol ** 2
    a = sx ** 2 + cx ** 2 * (cy ** 2 + razon * sy ** 2)
    b = -2 * h * cx * cy
    c = h ** 2 - r_eq ** 2
    r_s = (-b - np.sqrt(b ** 2 - 4 * a * c)) / (2 * a)
    s_x, s_y, s_z = r_s * cx * cy, -r_s * sx, r_s * cx * sy
    latitud = np.degrees(np.arctan(razon * s_z / np.sqrt((h - s_x) ** 2 + s_y ** 2)))
    longitud = np.degrees(lon_0 - np.arctan(s_y / (h - s_x)))
    return latitud, longitud


def _valores(archivo, nombre, filas, columnas):
    """Valores físicos de los píxeles pedidos; NaN donde la variable no tiene dato."""
    variable = archivo[nombre]
    crudo = variable[()][filas, columnas]
    valores = crudo.astype("float64")
    relleno = _attr(variable, "_FillValue")
    if relleno is not None:
        valores[crudo == relleno] = np.nan
    return valores * _attr(variable, "scale_factor", 1.0) + _attr(variable, "add_offset", 0.0)


def _o_none(valor):
    return None if np.isnan(valor) else float(valor)


def leer_focos(contenido, clave):
    """Focos de Ecuador continental contenidos en un NetCDF ya descargado."""
    fecha = inicio_escaneo(clave)
    with h5py.File(io.BytesIO(contenido), "r") as archivo:
        mascara = archivo["Mask"][()]
        filas, columnas = np.nonzero(np.isin(mascara, CODIGOS_FUEGO))
        if not filas.size:
            return []
        with np.errstate(invalid="ignore"):
            latitud, longitud = _a_latlon(archivo, filas, columnas)
        en_ecuador = contains_xy(cargar_poligono_ecuador(), longitud, latitud)
        if not en_ecuador.any():
            return []
        filas, columnas, latitud, longitud = filas[en_ecuador], columnas[en_ecuador], latitud[en_ecuador], longitud[en_ecuador]
        codigos = mascara[filas, columnas]
        potencia = _valores(archivo, "Power", filas, columnas)
        temperatura = _valores(archivo, "Temp", filas, columnas)
        area = _valores(archivo, "Area", filas, columnas)

    return [{
        "fuente": FUENTE,
        "fecha": fecha,
        "latitud": round(float(latitud[i]), 6),
        "longitud": round(float(longitud[i]), 6),
        "frp": _o_none(potencia[i]),
        "temperatura": _o_none(temperatura[i]),
        "temperatura_ti5": None,
        "area_fuego_m2": _o_none(area[i]),
        "satelite": "G19",
        "instrumento": "ABI",
        "confianza": "alta",
        "codigo_calidad": str(int(codigos[i])),
        "dia_noche": None,
    } for i in range(len(codigos))]


def descargar(clave):
    respuesta = requests.get(f"{BUCKET}/{clave}", timeout=60)
    respuesta.raise_for_status()
    return respuesta.content
