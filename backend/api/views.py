import logging

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .models import Alertas
from .permissions import CON_LOGIN, grupo_requerido
from .serializers import (
    AlertaSerializer, AreaSerializer, ErrorSerializer, FocosErrorSerializer,
    FocosRespuestaSerializer, LoginEntradaSerializer, LoginRespuestaSerializer,
    LoginSerializer, RefreshEntradaSerializer, RefreshRespuestaSerializer,
    UsuarioSerializer, datos_usuario,
)
from .services.alertas import alertas_por_id, areas_con_ultima_alerta, areas_de_alertas
from .services.nasa_firms import HORAS_MAXIMAS, HORAS_POR_DEFECTO, obtener_focos_calor

logger = logging.getLogger(__name__)

ERROR_401 = OpenApiExample(
    "Sin token o token vencido", status_codes=["401"],
    value={"detail": "Las credenciales de autenticación no se proveyeron."},
)
ERROR_403 = OpenApiExample(
    "Sin grupo permitido", status_codes=["403"],
    value={"detail": "No tienes permiso para esta acción."},
)


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
    permission_classes = [grupo_requerido(*CON_LOGIN)]

    @extend_schema(
        tags=["Alertas"],
        summary="Listar alertas",
        description="Requiere token y pertenecer a guardaparques o brigadas. "
                    "Ordenadas de la más reciente a la más antigua.",
        parameters=[
            OpenApiParameter("area", int, description="Filtra por id de área protegida."),
            OpenApiParameter("limite", int, description="Máximo de alertas (por defecto 100, tope 500)."),
        ],
        responses={200: AlertaSerializer(many=True), 401: ErrorSerializer, 403: ErrorSerializer},
        examples=[ERROR_401, ERROR_403],
    )
    def get(self, request):
        qs = Alertas.objects.order_by("-fecha")
        area = request.query_params.get("area")
        if area:
            qs = qs.filter(areaalerta__area_protegida=area)
        try:
            limite = min(int(request.query_params.get("limite", 100)), 500)
        except ValueError:
            limite = 100
        alertas = list(qs[:limite])
        contexto = {"areas": areas_de_alertas(alertas)}
        return Response(AlertaSerializer(alertas, many=True, context=contexto).data)


class AlertaDetailView(APIView):
    permission_classes = [grupo_requerido(*CON_LOGIN)]

    @extend_schema(
        tags=["Alertas"],
        summary="Detalle de una alerta",
        description="Requiere token y pertenecer a guardaparques o brigadas.",
        responses={200: AlertaSerializer, 401: ErrorSerializer, 403: ErrorSerializer,
                   404: ErrorSerializer},
        examples=[ERROR_401, ERROR_403],
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
            "Público. Detecciones de los satélites VIIRS (NOAA-20, NOAA-21 y S-NPP) de NASA FIRMS "
            "dentro de Ecuador continental, de la más reciente a la más antigua.\n\n"
            "Los datos se consultan a NASA como máximo cada 15 minutos (caché compartida)."
        ),
        parameters=[
            OpenApiParameter("horas", int, description=f"Últimas N horas (1–{HORAS_MAXIMAS}, "
                             f"por defecto {HORAS_POR_DEFECTO}). Valores fuera del rango se ajustan."),
        ],
        responses={200: FocosRespuestaSerializer, 400: FocosErrorSerializer,
                   502: FocosErrorSerializer},
        examples=[
            OpenApiExample("Parámetro inválido", status_codes=["400"], response_only=True,
                           value={"success": False,
                                  "mensaje": "El parámetro horas debe ser un número entero."}),
            OpenApiExample("NASA FIRMS no responde", status_codes=["502"], response_only=True,
                           value={"success": False,
                                  "mensaje": "No fue posible consultar los focos de calor."}),
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

        try:
            focos = obtener_focos_calor(horas)
        except Exception:
            logger.exception("Error al consultar NASA FIRMS")
            return Response({
                "success": False,
                "mensaje": "No fue posible consultar los focos de calor.",
            }, status=502)

        return Response({
            "success": True,
            "horas": max(1, min(horas, HORAS_MAXIMAS)),
            "total": len(focos),
            "focos": focos,
        })
