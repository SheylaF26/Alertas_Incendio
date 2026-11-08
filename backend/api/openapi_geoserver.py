"""Agrega a Swagger los servicios públicos de GeoServer con las capas de peligro de incendio.

No son endpoints de esta API: los sirve GeoServer directamente, sin token. Se documentan aquí para
que quien consuma la API tenga todo en un solo lugar.
"""
GEOSERVER = "https://geoservicios.inamhi.gob.ec/geoserver"
SERVIDOR = [{"url": GEOSERVER, "description": "GeoServer INAMHI (público, sin token)"}]

RASTER = "geonode:prueba_peligro_incendio"
RESUMEN = "geonode:prueba_peligro_resumen"
DETALLE = "geonode:prueba_peligro_detalle"
DETALLE_BUFFER = "geonode:prueba_peligro_detalle_buffer"

CAPAS_VECTOR = [RESUMEN, DETALLE, DETALLE_BUFFER]
BBOX_ECUADOR = "-81.5,-5.1,-75,1.7"

TABLA_CAPAS = f"""
| capa | qué muestra |
|---|---|
| `{RASTER}` | GeoTIFF con 10 km alrededor de cada área. Estilos: `geonode:prueba_peligro_incendio_continuo` (0–100 %) y `geonode:prueba_peligro_incendio_niveles` (niveles 1–4). Solo WMS. |
| `{RESUMEN}` | Cada área de un color: su nivel predominante, calculado solo con los píxeles dentro del límite. |
| `{DETALLE}` | Polígonos por nivel solo dentro del área. `pixeles` y `porcentaje_area` son del interior. |
| `{DETALLE_BUFFER}` | Polígonos por nivel hasta 10 km alrededor del área. `pixeles` y `porcentaje_area` incluyen el buffer. |

Niveles: 1 Bajo (0–25), 2 Medio (25.01–50), 3 Alto (50.01–75), 4 Muy Alto (75.01–100).

El prefijo `prueba_` es provisional: se quitará cuando las capas pasen a producción.
"""


def _param(nombre, descripcion, defecto=None, enum=None, tipo="string"):
    esquema = {"type": tipo}
    if defecto is not None:
        esquema["default"] = defecto
    if enum:
        esquema["enum"] = enum
    return {"name": nombre, "in": "query", "required": False, "description": descripcion, "schema": esquema}


def _wms():
    return {
        "get": {
            "servers": SERVIDOR,
            "operationId": "geoserver_wms",
            "tags": ["GeoServer"],
            "summary": "Mapa de una capa (WMS)",
            "description": (
                "Público, sin token. Devuelve la imagen PNG de la capa para pintarla en el mapa.\n\n"
                "Sin `time` responde con el producto más reciente." + TABLA_CAPAS + "\n"
                "Para consultar qué hay en un punto del mapa, usa `request=GetFeatureInfo` agregando "
                "`query_layers`, `x`, `y` e `info_format=application/json`."
            ),
            "parameters": [
                _param("service", "Siempre WMS.", "WMS", ["WMS"]),
                _param("version", "Versión del servicio.", "1.1.1"),
                _param("request", "`GetCapabilities` lista las capas, estilos y fechas disponibles.",
                       "GetMap", ["GetMap", "GetCapabilities", "GetFeatureInfo"]),
                _param("layers", "Capa a pintar.", RESUMEN, [RASTER, *CAPAS_VECTOR]),
                _param("styles", "Vacío usa el estilo por defecto de la capa.", ""),
                _param("bbox", "oeste,sur,este,norte. Por defecto, Ecuador continental.", BBOX_ECUADOR),
                _param("width", "Ancho en píxeles.", 768, tipo="integer"),
                _param("height", "Alto en píxeles.", 768, tipo="integer"),
                _param("srs", "Sistema de coordenadas.", "EPSG:4326"),
                _param("format", "Formato de imagen.", "image/png"),
                _param("transparent", "Fondo transparente.", "true", ["true", "false"]),
                _param("time", "Fecha de emisión del producto en UTC, p. ej. `2026-11-07T17:00:00.000Z`."),
            ],
            "responses": {
                "200": {
                    "description": "Imagen de la capa, o XML/JSON según `request`.",
                    "content": {"image/png": {"schema": {"type": "string", "format": "binary"}}},
                },
            },
            "security": [],
        },
    }


def _wfs():
    return {
        "get": {
            "servers": SERVIDOR,
            "operationId": "geoserver_wfs",
            "tags": ["GeoServer"],
            "summary": "Datos de una capa en GeoJSON (WFS)",
            "description": (
                "Público, sin token y solo lectura. Devuelve los polígonos con sus atributos.\n\n"
                "A diferencia de WMS, sin filtro devuelve **todas las fechas**: usa `cql_filter` para "
                "pedir una sola." + TABLA_CAPAS + "\n"
                "Códigos de área: `cayambe_coca`, `chimborazo`, `cotacachi_cayapas`, `ilinizas`, "
                "`podocarpus`, `sangay`."
            ),
            "parameters": [
                _param("service", "Siempre WFS.", "WFS", ["WFS"]),
                _param("version", "Versión del servicio.", "2.0.0"),
                _param("request", "Operación.", "GetFeature", ["GetFeature", "GetCapabilities"]),
                _param("typeNames", "Capa a consultar.", RESUMEN, CAPAS_VECTOR),
                _param("outputFormat", "Formato de salida.", "application/json"),
                _param("count", "Máximo de registros.", 10, tipo="integer"),
                _param("propertyName", "Atributos a devolver, separados por coma. Si no incluye `geom`, "
                                       "la respuesta no trae polígonos y pesa mucho menos."),
                _param("cql_filter", "Filtro, p. ej. `codigo='sangay' AND fecha_emision='2026-11-07T17:00:00Z'`."),
            ],
            "responses": {
                "200": {
                    "description": "GeoJSON FeatureCollection.",
                    "content": {"application/json": {
                        "schema": {"type": "object"},
                        "example": {
                            "type": "FeatureCollection",
                            "totalFeatures": 1,
                            "features": [{
                                "type": "Feature",
                                "geometry": None,
                                "properties": {
                                    "codigo": "cayambe_coca",
                                    "area": "Parque Nacional Cayambe-Coca",
                                    "nivel": 4,
                                    "nivel_nombre": "Muy Alto",
                                    "porcentaje_area": 64.53,
                                    "fecha_emision": "2026-11-06T17:00:00Z",
                                },
                            }],
                        },
                    }},
                },
            },
            "security": [],
        },
    }


def agregar_geoserver(result, generator, request, public):
    result["paths"]["/wms"] = _wms()
    result["paths"]["/wfs"] = _wfs()
    return result
