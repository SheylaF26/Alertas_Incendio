
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models.pronostico.dispositivos_fcm import DispositivoFCM
from .permissions import CON_LOGIN, grupo_requerido


DB = "pronostico"


# =====================================================
# SERIALIZER: REGISTRAR DISPOSITIVO
# =====================================================

class RegistrarFCMSerializer(serializers.Serializer):
    token = serializers.CharField(
        max_length=512,
        trim_whitespace=True,
        allow_blank=False,
    )

    plataforma = serializers.ChoiceField(
        choices=["android", "ios"],
    )

    dispositivo_id = serializers.CharField(
        max_length=128,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )


# =====================================================
# SERIALIZER: DESREGISTRAR DISPOSITIVO
# =====================================================

class DesregistrarFCMSerializer(serializers.Serializer):
    token = serializers.CharField(
        max_length=512,
        trim_whitespace=True,
        allow_blank=False,
    )

    dispositivo_id = serializers.CharField(
        max_length=128,
        required=False,
        allow_blank=True,
        trim_whitespace=True,
    )


# =====================================================
# REGISTRAR TOKEN FCM
# =====================================================

class RegistrarFCMView(APIView):
    """
    Registra un dispositivo FCM para el usuario
    autenticado.

    Seguridad:
    - El usuario se obtiene del JWT.
    - No se acepta usuario_id desde Flutter.
    - Desactiva tokens anteriores de la misma
      instalación, incluso si pertenecían a
      otra cuenta.
    - Reactiva el token actual cuando corresponda.
    """

    permission_classes = [
        grupo_requerido(*CON_LOGIN)
    ]

    def post(self, request):
        serializer = RegistrarFCMSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        datos = serializer.validated_data

        token = datos["token"]
        plataforma = datos["plataforma"]

        dispositivo_id = (
            datos.get("dispositivo_id") or None
        )

        usuario_id = request.user.id
        ahora = timezone.now()

        with transaction.atomic(using=DB):

            # =========================================
            # DESACTIVAR REGISTROS ANTERIORES
            # =========================================

            if dispositivo_id:
                # La instalación puede haber sido
                # utilizada por otra cuenta.
                #
                # Desactivar todos los tokens
                # diferentes al token actual.
                DispositivoFCM.objects.using(
                    DB
                ).filter(
                    dispositivo_id=dispositivo_id,
                    activo=True,
                ).exclude(
                    token=token,
                ).update(
                    activo=False,
                    ultima_actividad=ahora,
                )

            # =========================================
            # GUARDAR TOKEN ACTUAL
            # =========================================

            dispositivo, creado = (
                DispositivoFCM.objects.using(
                    DB
                ).update_or_create(
                    token=token,
                    defaults={
                        "usuario_id": usuario_id,
                        "plataforma": plataforma,
                        "dispositivo_id": dispositivo_id,
                        "activo": True,
                        "ultima_actividad": ahora,
                    }
                )
            )

        return Response(
            {
                "success": True,
                "mensaje": (
                    "Dispositivo registrado correctamente"
                ),
                "dispositivo_id": dispositivo.id,
                "usuario_id": usuario_id,
                "creado": creado,
            },
            status=(
                status.HTTP_201_CREATED
                if creado
                else status.HTTP_200_OK
            ),
        )


# =====================================================
# DESREGISTRAR TOKEN FCM
# =====================================================

class DesregistrarFCMView(APIView):
    """
    Desactiva los registros institucionales
    del usuario que está cerrando sesión.

    Si se proporciona dispositivo_id, también
    desactiva otros tokens de esa instalación
    que pertenezcan al mismo usuario.

    Nunca desactiva tokens de otros usuarios.
    """

    permission_classes = [
        grupo_requerido(*CON_LOGIN)
    ]

    def post(self, request):
        serializer = DesregistrarFCMSerializer(
            data=request.data
        )
        serializer.is_valid(raise_exception=True)

        token = serializer.validated_data["token"]

        dispositivo_id = (
            serializer.validated_data.get(
                "dispositivo_id"
            ) or None
        )

        usuario_id = request.user.id
        ahora = timezone.now()

        condiciones = Q(token=token)

        if dispositivo_id:
            condiciones |= Q(
                dispositivo_id=dispositivo_id
            )

        with transaction.atomic(using=DB):

            actualizados = (
                DispositivoFCM.objects.using(
                    DB
                ).filter(
                    condiciones,
                    usuario_id=usuario_id,
                    activo=True,
                ).update(
                    activo=False,
                    ultima_actividad=ahora,
                )
            )

        return Response(
            {
                "success": True,
                "mensaje": (
                    "Token desactivado correctamente"
                ),
                "desactivados": actualizados,
            },
            status=status.HTTP_200_OK,
        )
