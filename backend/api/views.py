from django.shortcuts import get_object_or_404
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from api.services.nasa_firms import obtener_focos_calor
from .models import Alertas
from .permissions import CON_LOGIN, grupo_requerido
from .serializers import (
    AlertaSerializer, AreaSerializer, LoginSerializer, grupos_de,
)
from .services.alertas import alertas_por_id, areas_con_ultima_alerta, areas_de_alertas


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer


class MeView(APIView):
    def get(self, request):
        u = request.user
        return Response({
            "id": u.id,
            "username": u.username,
            "nombre": u.get_full_name(),
            "email": u.email,
            "grupos": grupos_de(u),
        })


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
    """
    try:
        focos = obtener_focos_calor()

        return JsonResponse({
            "success": True,
            "total": len(focos),
            "focos": focos
        }, json_dumps_params={"ensure_ascii": False})

    except Exception as error:
        print(f"Error al consultar NASA FIRMS: {error}")

        return JsonResponse({
            "success": False,
            "mensaje": "No fue posible consultar los focos de calor."
        }, status=502)