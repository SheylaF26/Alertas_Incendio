"""Procesa un GeoTIFF del modelo de peligro (0-100 %) y llena alerta_incendios.peligro_zona.

Por cada área y cada nivel de nivel_peligro guarda dos versiones (columna incluye_buffer):
- false: píxeles y porcentaje solo dentro del límite oficial; polígono hasta el límite.
- true: píxeles y porcentaje dentro del buffer de 10 km; polígono hasta el buffer.
El nivel predominante de cada área lo calcula la vista v_peligro_resumen, solo con incluye_buffer = false.
"""
import logging
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import numpy as np
import tifffile
from django.db import connections, transaction
from shapely import box, contains_xy, from_wkt, make_valid, unary_union
from shapely.affinity import affine_transform
from shapely.geometry import MultiPolygon, Polygon

logger = logging.getLogger(__name__)
DB = "pronostico"
FECHA_EN_NOMBRE = re.compile(r"(\d{8}T\d{4})Z?")


@dataclass
class Raster:
    valores: np.ndarray      # float64, NaN donde no hay dato
    x0: float                # borde oeste
    y0: float                # borde norte
    dx: float
    dy: float
    metadatos: dict

    def centros(self):
        filas, cols = self.valores.shape
        xs = self.x0 + (np.arange(cols) + 0.5) * self.dx
        ys = self.y0 - (np.arange(filas) + 0.5) * self.dy
        return np.meshgrid(xs, ys)


def leer_tif(ruta: Path) -> Raster:
    with tifffile.TiffFile(ruta) as tif:
        pagina = tif.pages[0]
        tags = {t.code: t.value for t in pagina.tags}
        datos = pagina.asarray().astype("float64")
    if 33550 not in tags or 33922 not in tags:
        raise ValueError("El TIFF no tiene georreferencia (ModelPixelScale/ModelTiepoint).")
    dx, dy = tags[33550][0], tags[33550][1]
    x0, y0 = tags[33922][3], tags[33922][4]
    nodata = tags.get(42113)
    if nodata is not None:
        datos[datos == float(str(nodata).strip("\x00"))] = np.nan
    datos[~np.isfinite(datos) | (datos < -1e30)] = np.nan
    metadatos = {}
    if 42112 in tags:
        for item in ET.fromstring(tags[42112]).iter("Item"):
            metadatos[item.get("name")] = (item.text or "").strip()
    return Raster(datos, x0, y0, dx, dy, metadatos)


def fechas(ruta: Path, raster: Raster, vigencia_desde=None, vigencia_hasta=None):
    """Emisión y vigencia: primero los metadatos del TIFF; si no, el nombre del archivo."""
    m = raster.metadatos
    if m.get("FECHA_EMISION"):
        emision = datetime.fromisoformat(m["FECHA_EMISION"])
    else:
        hallado = FECHA_EN_NOMBRE.search(ruta.name)
        if not hallado:
            raise ValueError(f"No encuentro la fecha de emisión en los metadatos ni en el nombre: {ruta.name}")
        emision = datetime.strptime(hallado.group(1), "%Y%m%dT%H%M").replace(tzinfo=timezone.utc)
    desde = vigencia_desde or (datetime.fromisoformat(m["VIGENCIA_DESDE"]) if m.get("VIGENCIA_DESDE") else None)
    hasta = vigencia_hasta or (datetime.fromisoformat(m["VIGENCIA_HASTA"]) if m.get("VIGENCIA_HASTA") else None)
    if not desde or not hasta:
        raise ValueError("Falta la vigencia: no viene en el TIFF; pásala con --desde y --hasta.")
    return emision, desde, hasta


def poligono_de_mascara(mascara: np.ndarray, r: Raster):
    """Une los píxeles marcados en un (multi)polígono: tramos por fila y luego unión.

    La unión se hace en coordenadas enteras de la grilla (exacta) y después se lleva a
    lon/lat; uniendo directo en grados, los bordes compartidos difieren en el decimal 16
    y PostGIS ve autointersecciones (pasaba cerca de la línea ecuatorial).
    """
    cajas = []
    for i, fila in enumerate(mascara):
        if not fila.any():
            continue
        cambios = np.diff(np.concatenate(([0], fila.astype(np.int8), [0])))
        inicios, fines = np.flatnonzero(cambios == 1), np.flatnonzero(cambios == -1)
        for j0, j1 in zip(inicios, fines):
            cajas.append(box(int(j0), -(i + 1), int(j1), -i))
    if not cajas:
        return None
    return affine_transform(unary_union(cajas), [r.dx, 0, 0, r.dy, r.x0, r.y0])


def como_multipoligono(geom):
    geom = make_valid(geom)
    partes = [g for g in getattr(geom, "geoms", [geom]) if isinstance(g, (Polygon, MultiPolygon))]
    planas = []
    for p in partes:
        planas.extend(getattr(p, "geoms", [p]))
    return MultiPolygon(planas) if planas else None


def procesar(ruta, capa_geoserver=None, vigencia_desde=None, vigencia_hasta=None):
    ruta = Path(ruta)
    r = leer_tif(ruta)
    emision, desde, hasta = fechas(ruta, r, vigencia_desde, vigencia_hasta)
    validos = ~np.isnan(r.valores)
    v = r.valores[validos]
    fuera = int(((v < 0) | (v > 100)).sum())
    if fuera:
        logger.warning("%s: %d píxeles fuera de 0-100; se recortan al rango.", ruta.name, fuera)
    valores = np.clip(np.round(r.valores, 2), 0, 100)
    X, Y = r.centros()

    with connections[DB].cursor() as cur:
        cur.execute("SELECT nivel, valor_min, valor_max FROM alerta_incendios.nivel_peligro ORDER BY nivel")
        niveles = cur.fetchall()
        cur.execute("SELECT id, codigo, ST_AsText(geom), ST_AsText(geom_buffer) FROM alerta_incendios.area_protegida "
                    "WHERE geom IS NOT NULL AND geom_buffer IS NOT NULL ORDER BY id")
        areas = cur.fetchall()
    if not areas:
        raise ValueError("Ninguna área tiene geom_buffer cargado.")

    nivel_px = np.zeros(valores.shape, dtype=np.int16)
    for n, vmin, vmax in niveles:
        nivel_px[validos & (valores >= float(vmin)) & (valores <= float(vmax))] = n
    sin_nivel = int((validos & (nivel_px == 0)).sum())
    if sin_nivel:
        logger.warning("%s: %d píxeles no caen en ningún rango de nivel_peligro.", ruta.name, sin_nivel)

    # Cada área se guarda dos veces: solo adentro del límite (es lo que decide el nivel y la alerta)
    # y con el buffer de 10 km. En cada versión, los números y el dibujo cubren lo mismo.
    filas = []
    for area_id, codigo, limite_wkt, buffer_wkt in areas:
        limite, buffer = from_wkt(limite_wkt), from_wkt(buffer_wkt)
        con_dato = nivel_px > 0
        en_limite = contains_xy(limite, X, Y) & con_dato
        en_buffer = contains_xy(buffer, X, Y) & con_dato
        if not en_limite.any():
            logger.warning("%s: el área %s no tiene píxeles con dato dentro de su límite.", ruta.name, codigo)
            continue
        versiones = ((False, en_limite, limite), (True, en_buffer, buffer))
        for n, _, _ in niveles:
            del_nivel = nivel_px == n
            if not (en_buffer & del_nivel).any():
                continue
            # Se parte de los píxeles del buffer para que, al cortar por el límite, el dibujo llegue
            # hasta el borde: con solo los píxeles de centro adentro quedaría dentado.
            poligono = poligono_de_mascara(en_buffer & del_nivel, r)
            for incluye_buffer, mascara, recorte in versiones:
                px = int((mascara & del_nivel).sum())
                if not px:
                    continue
                geom = como_multipoligono(poligono.intersection(recorte))
                if geom is None or geom.is_empty:
                    continue
                pct = round(Decimal(px * 100) / int(mascara.sum()), 2)
                filas.append((area_id, n, incluye_buffer, px, pct, geom.wkt))

    with transaction.atomic(using=DB), connections[DB].cursor() as cur:
        cur.execute(
            """INSERT INTO alerta_incendios.producto_modelo
                 (archivo, fecha_emision, vigencia_desde, vigencia_hasta, capa_geoserver,
                  valor_min, valor_max, valor_medio, procesado_en)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, now())
               ON CONFLICT (archivo) DO UPDATE SET
                 fecha_emision = EXCLUDED.fecha_emision, vigencia_desde = EXCLUDED.vigencia_desde,
                 vigencia_hasta = EXCLUDED.vigencia_hasta,
                 capa_geoserver = COALESCE(EXCLUDED.capa_geoserver, alerta_incendios.producto_modelo.capa_geoserver),
                 valor_min = EXCLUDED.valor_min, valor_max = EXCLUDED.valor_max,
                 valor_medio = EXCLUDED.valor_medio, procesado_en = now()
               RETURNING id""",
            [ruta.name, emision, desde, hasta, capa_geoserver,
             round(float(np.nanmin(valores)), 2), round(float(np.nanmax(valores)), 2),
             round(float(np.nanmean(valores)), 2)])
        producto_id = cur.fetchone()[0]
        cur.execute("DELETE FROM alerta_incendios.peligro_zona WHERE producto_id = %s", [producto_id])
        for area_id, n, incluye_buffer, px, pct, wkt in filas:
            cur.execute(
                """INSERT INTO alerta_incendios.peligro_zona
                     (producto_id, area_protegida_id, nivel, incluye_buffer, pixeles, porcentaje_area, geom)
                   VALUES (%s, %s, %s, %s, %s, %s,
                           ST_Multi(ST_CollectionExtract(ST_MakeValid(ST_GeomFromText(%s, 4326)), 3)))""",
                [producto_id, area_id, n, incluye_buffer, px, pct, wkt])
    return producto_id, len(filas)
