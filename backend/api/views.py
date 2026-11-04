import logging

from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .services.nasa_firms import HORAS_MAXIMAS, HORAS_POR_DEFECTO, obtener_focos_calor
from .models import Alertas
from .permissions import CON_LOGIN, grupo_requerido
from .serializers import (
    AlertaSerializer, AreaSerializer, LoginSerializer, datos_usuario,
)
from .services.alertas import alertas_por_id, areas_con_ultima_alerta, areas_de_alertas

logger = logging.getLogger(__name__)


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


class MeView(APIView):
    """Datos del usuario logueado y sus grupos (leídos de la BD en cada llamada)."""
    def get(self, request):
        return Response(datos_usuario(request.user))


class AreaListView(APIView):
    """Público: no pide login."""
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request):
        areas = list(areas_con_ultima_alerta())
        alertas = alertas_por_id(a.ultima_alerta_id for a in areas)
        return Response(AreaSerializer(areas, many=True, context={"alertas": alertas}).data)


class AreaDetailView(APIView):
    authentication_classes = []
    permission_classes = [AllowAny]

    def get(self, request, pk):
        area = get_object_or_404(areas_con_ultima_alerta(), pk=pk)
        alertas = alertas_por_id([area.ultima_alerta_id])
        return Response(AreaSerializer(area, context={"alertas": alertas}).data)


class AlertaListView(APIView):
    permission_classes = [grupo_requerido(*CON_LOGIN)]

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

    def get(self, request, pk):
        alerta = get_object_or_404(Alertas, pk=pk)
        contexto = {"areas": areas_de_alertas([alerta])}
        return Response(AlertaSerializer(alerta, context=contexto).data)


@require_GET
def focos_calor(request):
    """
    Devuelve los focos de calor de Ecuador continental.
    ?horas=N limita a las últimas N horas (1–48, por defecto 24).
    """
    try:
        horas = int(request.GET.get("horas", HORAS_POR_DEFECTO))
    except ValueError:
        return JsonResponse({
            "success": False,
            "mensaje": "El parámetro horas debe ser un número entero."
        }, status=400)

    try:
        focos = obtener_focos_calor(horas)

        return JsonResponse({
            "success": True,
            "horas": max(1, min(horas, HORAS_MAXIMAS)),
            "total": len(focos),
            "focos": focos
        }, json_dumps_params={"ensure_ascii": False})

    except Exception:
        logger.exception("Error al consultar NASA FIRMS")

        return JsonResponse({
            "success": False,
            "mensaje": "No fue posible consultar los focos de calor."
        }, status=502)