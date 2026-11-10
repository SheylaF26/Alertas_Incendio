import logging
from datetime import timezone as dt_timezone

from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import Alertas, TipoEvento
from .permissions import CON_LOGIN, GUARDAPARQUES, grupo_requerido
from .serializers import (
    AlertaSerializer, AreaSerializer, ErrorSerializer, FocosErrorSerializer, FotoRespuestaSerializer,
    EstacionesRespuestaSerializer, FocosRespuestaSerializer, LoginEntradaSerializer,
    LoginRespuestaSerializer, LoginSerializer, RefreshEntradaSerializer, RefreshRespuestaSerializer,
    RegistroEntradaSerializer, RegistroSalidaSerializer, SerieRespuestaSerializer, TipoEventoSerializer,
    UsuarioSerializer, ValidarEntradaSerializer, datos_usuario,
)
from .services import fotos, registros, tiempo_real
from .services.areas import areas_geojson
from .services.alertas import alertas_por_id, areas_con_ultima_alerta, areas_de_alertas
from .services.focos_calor import HORAS_MAXIMAS, HORAS_POR_DEFECTO, consultar as consultar_focos

logger = logging.getLogger(__name__)

ERROR_401 = OpenApiExample(
    "Sin token o token vencido", status_codes=["401"],
    value={"detail": "Las credenciales de autenticación no se proveyeron."},
)
ORIGENES_ALERTA = ["modelo", "goes", "firms", "registro"]


# --------------------------------------------------------------------------
# Autenticación
# --------------------------------------------------------------------------

@extend_schema(
    tags=["Autenticación"],
    summary="Iniciar sesión",
    description=(
        "Valida `username` y `password` contra `seguridades.usuarios`.\n\n"
        "Solo entran usuarios **activos** que pertenezcan a algún grupo de la aplicación "
        "(guardaparques o brigadas). Cualquier otro caso responde 401 con el mismo mensaje.\n\n"
        "Guarda `access` y `refresh` en el front y envía el access en cada petición protegida:\n"
        "`Authorization: Bearer <access>`."
    ),
    request=LoginEntradaSerializer,
    responses={200: LoginRespuestaSerializer, 400: ErrorSerializer, 401: ErrorSerializer},
    examples=[
        OpenApiExample("Petición", request_only=True,
                       value={"username": "japolo", "password": "mi_clave"}),
        OpenApiExample("Login correcto", response_only=True, status_codes=["200"], value={
            "access": "eyJhbGciOiJIUzI1NiIs...", "refresh": "eyJhbGciOiJIUzI1NiIs...",
            "usuario": {"id": 1000, "username": "japolo", "first_name": "Juan",
                        "nombre": "Juan Apolo", "email": "correo@ejemplo.com",
                        "grupos": [{"id": 1, "nombre": "aplicacion incendios guardaparques"}]},
        }),
        OpenApiExample("Credenciales inválidas", response_only=True, status_codes=["401"],
                       value={"detail": "Credenciales inválidas o sin acceso a la aplicación."}),
    ],
    auth=[],
)
class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


@extend_schema(
    tags=["Autenticación"],
    summary="Renovar el token de acceso",
    description=(
        "Cuando el `access` vence (30 min) cualquier endpoint protegido responde 401. "
        "Llama aquí con el `refresh` para obtener un `access` nuevo sin pedir la clave otra vez.\n\n"
        "Si el `refresh` también venció (7 días) responde 401: hay que volver al login."
    ),
    request=RefreshEntradaSerializer,
    responses={200: RefreshRespuestaSerializer, 401: ErrorSerializer},
    auth=[],
)
class RefreshView(TokenRefreshView):
    pass


class MeView(APIView):
    @extend_schema(
        tags=["Autenticación"],
        summary="Datos del usuario logueado",
        description=(
            "Devuelve el usuario y sus grupos **leídos de la base en ese momento**.\n\n"
            "Recomendado al abrir la app: si responde 200 la sesión sigue activa y los grupos "
            "están al día (si se le quitó un grupo, se refleja aquí aunque el token diga otra cosa); "
            "si responde 401, intenta `token/refresh/` y si falla, manda al login."
        ),
        responses={200: UsuarioSerializer, 401: ErrorSerializer},
        examples=[ERROR_401],
    )
    def get(self, request):
        return Response(datos_usuario(request.user))


# --------------------------------------------------------------------------
# Áreas protegidas (públicas)
# --------------------------------------------------------------------------

class AreaListView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Áreas protegidas"],
        summary="Listar áreas protegidas",
        description="Público. Cada área con su alerta más reciente (`alerta_actual`, o null). "
                    "Ordenadas por nombre.",
        responses={200: AreaSerializer(many=True)},
        auth=[],
    )
    def get(self, request):
        areas = list(areas_con_ultima_alerta())
        alertas = alertas_por_id(a.ultima_alerta_id for a in areas)
        return Response(AreaSerializer(areas, many=True, context={"alertas": alertas}).data)


class AreasGeoJsonView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Áreas protegidas"],
        summary="Contornos de las áreas protegidas (GeoJSON)",
        description="Público. Límite oficial de cada área, simplificado a unos 50 m para el mapa, "
                    "con su `bbox` (oeste, sur, este, norte) para hacer zoom.",
        responses={200: {"type": "object", "description": "GeoJSON FeatureCollection"}},
        auth=[],
    )
    def get(self, request):
        return Response(areas_geojson())


class AreaDetailView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Áreas protegidas"],
        summary="Detalle de un área protegida",
        description="Público. Responde 404 si el área no existe.",
        responses={200: AreaSerializer, 404: ErrorSerializer},
        auth=[],
    )
    def get(self, request, pk):
        area = get_object_or_404(areas_con_ultima_alerta(), pk=pk)
        alertas = alertas_por_id([area.ultima_alerta_id])
        return Response(AreaSerializer(area, context={"alertas": alertas}).data)


# --------------------------------------------------------------------------
# Alertas (requieren login + grupo)
# --------------------------------------------------------------------------

class AlertaListView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Alertas"],
        summary="Listar alertas",
        description="Público. Ordenadas de la más reciente a la más antigua.\n\n"
                    "`origen` dice qué la causó: `modelo`, `goes`, `firms` o `registro`. "
                    "Para consultar periódicamente, envía en `desde` la fecha de la última alerta recibida.",
        parameters=[
            OpenApiParameter("area", int, description="Filtra por id de área protegida."),
            OpenApiParameter("origen", str, enum=ORIGENES_ALERTA, description="Filtra por origen."),
            OpenApiParameter("desde", str, description="Solo alertas posteriores a esta fecha ISO 8601, "
                                                       "p. ej. `2026-11-09T14:00:00Z`."),
            OpenApiParameter("limite", int, description="Máximo de alertas (por defecto 100, tope 500)."),
        ],
        responses={200: AlertaSerializer(many=True), 400: FocosErrorSerializer},
        auth=[],
    )
    def get(self, request):
        qs = Alertas.objects.order_by("-fecha")
        try:
            area = _entero(request, "area")
        except ValueError:
            return _error("El parámetro area debe ser un número entero.")
        if area:
            qs = qs.filter(areaalerta__area_protegida=area)

        origen = request.query_params.get("origen")
        if origen:
            if origen not in ORIGENES_ALERTA:
                return _error(f"El parámetro origen debe ser uno de: {', '.join(ORIGENES_ALERTA)}.")
            qs = qs.filter(origen=origen)

        texto_desde = request.query_params.get("desde")
        if texto_desde:
            try:
                # En una URL sin codificar, el + de la zona horaria llega como espacio
                desde = parse_datetime(texto_desde.replace(" ", "+"))
            except ValueError:
                desde = None
            if desde is None:
                return _error("El parámetro desde debe ser una fecha ISO 8601.")
            qs = qs.filter(fecha__gt=desde if timezone.is_aware(desde) else timezone.make_aware(desde, dt_timezone.utc))

        try:
            limite = max(1, min(_entero(request, "limite", 100), 500))
        except ValueError:
            limite = 100
        alertas = list(qs[:limite])
        contexto = {"areas": areas_de_alertas(alertas)}
        return Response(AlertaSerializer(alertas, many=True, context=contexto).data)


class AlertaDetailView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Alertas"],
        summary="Detalle de una alerta",
        description="Público.",
        responses={200: AlertaSerializer, 404: ErrorSerializer},
        auth=[],
    )
    def get(self, request, pk):
        alerta = get_object_or_404(Alertas, pk=pk)
        contexto = {"areas": areas_de_alertas([alerta])}
        return Response(AlertaSerializer(alerta, context=contexto).data)


# --------------------------------------------------------------------------
# Focos de calor (NASA FIRMS, público)
# --------------------------------------------------------------------------

class FocosCalorView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Focos de calor"],
        summary="Focos de calor de Ecuador continental",
        description=(
            "Público. Detecciones de calor en todo Ecuador continental, de la más reciente a la más "
            "antigua. No se limita a las áreas protegidas: `area_protegida` viene con el nombre si el "
            "foco cae dentro de una, o null.\n\n"
            "Los datos salen de la base del sistema, que se actualiza sola:\n"
            "- **VIIRS** (NOAA-20, NOAA-21 y S-NPP, vía NASA FIRMS): píxel de 375 m, pocas pasadas al "
            "día; se consulta cada 12 minutos.\n"
            "- **GOES-19** (`GOES19_FDCF`): píxel de 2 km, imagen nueva cada 10 minutos. Solo se guardan "
            "los códigos de fuego más confiables (10, 11, 30 y 31).\n\n"
            "Un mismo fuego activo aparece una vez por cada imagen en la que se detecte. Los focos con "
            "`es_volcan = true` están junto a un volcán en erupción y probablemente no son incendios."
        ),
        parameters=[
            OpenApiParameter("horas", int, description=f"Últimas N horas (1–{HORAS_MAXIMAS}, "
                             f"por defecto {HORAS_POR_DEFECTO}). Valores fuera del rango se ajustan."),
            OpenApiParameter("fuente", str, enum=["viirs", "goes"],
                             description="Solo una fuente. Sin este parámetro devuelve las dos."),
            OpenApiParameter("area", int, description="Solo los focos dentro de esta área protegida (id)."),
            OpenApiParameter("agrupar", bool, description="Si es true, cada punto sale una sola vez con su "
                             "detección más reciente; `detecciones` dice cuántas veces se detectó en el periodo. "
                             "Recomendado para pintar el mapa."),
        ],
        responses={200: FocosRespuestaSerializer, 400: FocosErrorSerializer},
        examples=[
            OpenApiExample("Parámetro inválido", status_codes=["400"], response_only=True,
                           value={"success": False,
                                  "mensaje": "El parámetro horas debe ser un número entero."}),
        ],
        auth=[],
    )
    def get(self, request):
        try:
            horas = int(request.query_params.get("horas", HORAS_POR_DEFECTO))
        except ValueError:
            return Response({
                "success": False,
                "mensaje": "El parámetro horas debe ser un número entero.",
            }, status=400)

        fuente = request.query_params.get("fuente") or None
        if fuente not in (None, "viirs", "goes"):
            return Response({"success": False, "mensaje": "El parámetro fuente debe ser viirs o goes."}, status=400)

        try:
            area = int(request.query_params.get("area") or 0) or None
        except ValueError:
            return Response({"success": False, "mensaje": "El parámetro area debe ser un número entero."}, status=400)

        agrupar = (request.query_params.get("agrupar") or "false").lower()
        if agrupar not in ("true", "false"):
            return Response({"success": False, "mensaje": "El parámetro agrupar debe ser true o false."}, status=400)

        focos = consultar_focos(horas, fuente, area, agrupar == "true")

        return Response({
            "success": True,
            "horas": max(1, min(horas, HORAS_MAXIMAS)),
            "total": len(focos),
            "focos": focos,
        })


# --------------------------------------------------------------------------
# Tiempo real (estaciones automáticas, público)
# --------------------------------------------------------------------------

def _entero(request, nombre, defecto=None):
    """Entero de la query string. Lanza ValueError si no lo es."""
    valor = request.query_params.get(nombre)
    return defecto if valor in (None, "") else int(valor)


def _error(mensaje, estado=400):
    return Response({"success": False, "mensaje": mensaje}, status=estado)


class EstacionesTiempoRealView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Tiempo real"],
        summary="Último dato de cada estación",
        description=(
            "Público. Estaciones meteorológicas automáticas operativas de todo el país que tienen algún "
            "dato válido en el periodo, con su ubicación y el último valor de cada variable. "
            "Pensado para pintar el mapa. Se actualiza como máximo cada 2 minutos."
        ),
        parameters=[
            OpenApiParameter("horas", int, description=f"Antigüedad máxima del dato (1–{tiempo_real.HORAS_MAXIMAS_ESTACIONES}, "
                             f"por defecto {tiempo_real.HORAS_POR_DEFECTO})."),
            OpenApiParameter("area", int, description="Solo las estaciones dentro de esta área protegida o a menos de 10 km."),
            OpenApiParameter("solo_areas", bool, description="Si es true, solo las estaciones dentro de alguna área protegida o a menos de 10 km."),
        ],
        responses={200: EstacionesRespuestaSerializer, 400: FocosErrorSerializer, 404: FocosErrorSerializer},
        auth=[],
    )
    def get(self, request):
        try:
            horas = _entero(request, "horas", tiempo_real.HORAS_POR_DEFECTO)
            area = _entero(request, "area")
        except ValueError:
            return _error("Los parámetros horas y area deben ser números enteros.")

        solo_areas = (request.query_params.get("solo_areas") or "false").lower()
        if solo_areas not in ("true", "false"):
            return _error("El parámetro solo_areas debe ser true o false.")

        horas, estaciones = tiempo_real.estaciones_con_datos(horas, area, solo_areas == "true")
        if estaciones is None:
            return _error("El área protegida no existe.", 404)
        return Response({"success": True, "horas": horas, "total": len(estaciones), "estaciones": estaciones})


class SerieTiempoRealView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        tags=["Tiempo real"],
        summary="Historial de una variable en una estación",
        description="Público. Datos válidos de una variable, del más antiguo al más reciente. Pensado para gráficos.",
        parameters=[
            OpenApiParameter("estacion", int, required=True, description="Id de la estación (`id` en `tiempo-real/estaciones/`)."),
            OpenApiParameter("variable", str, required=True, enum=list(tiempo_real.VARIABLES)),
            OpenApiParameter("horas", int, description=f"Últimas N horas (1–{tiempo_real.HORAS_MAXIMAS_SERIE}, "
                             f"por defecto {tiempo_real.HORAS_POR_DEFECTO})."),
        ],
        responses={200: SerieRespuestaSerializer, 400: FocosErrorSerializer, 404: FocosErrorSerializer},
        auth=[],
    )
    def get(self, request):
        variable = request.query_params.get("variable")
        if variable not in tiempo_real.VARIABLES:
            return _error(f"El parámetro variable debe ser uno de: {', '.join(tiempo_real.VARIABLES)}.")
        try:
            estacion = _entero(request, "estacion")
            horas = _entero(request, "horas", tiempo_real.HORAS_POR_DEFECTO)
        except ValueError:
            return _error("Los parámetros estacion y horas deben ser números enteros.")
        if estacion is None:
            return _error("El parámetro estacion es obligatorio.")

        resultado = tiempo_real.serie(estacion, variable, horas)
        if resultado is None:
            return _error("La estación no existe.", 404)
        return Response({"success": True, "total": len(resultado["datos"]), **resultado})


# --------------------------------------------------------------------------
# Reportes de incendio desde la app
# --------------------------------------------------------------------------

class TiposEventoView(APIView):
    permission_classes = [grupo_requerido(*CON_LOGIN)]

    @extend_schema(
        tags=["Reportes"],
        summary="Tipos de evento que se pueden reportar",
        responses={200: TipoEventoSerializer(many=True), 401: ErrorSerializer, 403: ErrorSerializer},
    )
    def get(self, request):
        return Response(TipoEventoSerializer(TipoEvento.objects.order_by("id"), many=True).data)


class RegistrosView(APIView):
    permission_classes = [grupo_requerido(*CON_LOGIN)]

    @extend_schema(
        tags=["Reportes"],
        summary="Enviar un reporte",
        description=(
            "Requiere login. El usuario sale del token.\n\n"
            "- **Guardaparques:** el reporte queda `validado` de inmediato.\n"
            "- **Aledaño (grupo brigadas):** queda `pendiente` hasta que decida un guardaparques "
            "asignado a esa área.\n\n"
            "El área es la asignada al usuario; si tiene varias, hay que enviar `area_protegida_id`. "
            "`evidencia` es la URL de la foto, que se sube a otro servidor."
        ),
        request=RegistroEntradaSerializer,
        responses={201: RegistroSalidaSerializer, 400: ErrorSerializer, 401: ErrorSerializer, 403: ErrorSerializer},
    )
    def post(self, request):
        entrada = RegistroEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        return Response(registros.crear(request.user, entrada.validated_data), status=201)


class FotoRegistroView(APIView):
    permission_classes = [grupo_requerido(*CON_LOGIN)]
    parser_classes = [MultiPartParser]

    @extend_schema(
        tags=["Reportes"],
        summary="Subir la foto de un reporte",
        description="Requiere login. Envía `foto` como multipart (JPG o PNG, máximo 10 MB). Si pesa más de "
                    "3 MB, se comprime hasta quedar en ese peso. "
                    "Devuelve la URL que luego se manda en `evidencia` al crear el reporte.",
        request={"multipart/form-data": {"type": "object", "required": ["foto"],
                                         "properties": {"foto": {"type": "string", "format": "binary"}}}},
        responses={201: FotoRespuestaSerializer, 400: ErrorSerializer, 401: ErrorSerializer,
                   403: ErrorSerializer, 502: ErrorSerializer},
    )
    def post(self, request):
        archivo = request.FILES.get("foto")
        if archivo is None:
            raise ValidationError({"foto": "Envía el archivo en el campo foto."})
        return Response({"url": fotos.subir(archivo)}, status=201)


class RegistrosPendientesView(APIView):
    permission_classes = [grupo_requerido(GUARDAPARQUES)]

    @extend_schema(
        tags=["Reportes"],
        summary="Reportes pendientes de validar",
        description="Solo guardaparques. Devuelve los reportes sin decidir de las áreas que tiene asignadas.",
        responses={200: RegistroSalidaSerializer(many=True), 401: ErrorSerializer, 403: ErrorSerializer},
    )
    def get(self, request):
        return Response(registros.pendientes(request.user))


class ValidarRegistroView(APIView):
    permission_classes = [grupo_requerido(GUARDAPARQUES)]

    @extend_schema(
        tags=["Reportes"],
        summary="Validar o rechazar un reporte",
        description="Solo guardaparques asignados al área del reporte. Cada reporte se decide una sola vez (409 si ya se decidió).",
        request=ValidarEntradaSerializer,
        responses={200: RegistroSalidaSerializer, 400: ErrorSerializer, 401: ErrorSerializer,
                   403: ErrorSerializer, 404: ErrorSerializer, 409: ErrorSerializer},
    )
    def post(self, request, pk):
        entrada = ValidarEntradaSerializer(data=request.data)
        entrada.is_valid(raise_exception=True)
        datos = entrada.validated_data
        return Response(registros.decidir(request.user, pk, datos["estado"], datos.get("observacion")))
