
from django.db import transaction
from django.utils import timezone

from rest_framework import serializers, status
from rest_framework.response import Response
from rest_framework.views import APIView

from .models.pronostico.dispositivos_fcm import DispositivoFCM
from .permissions import CON_LOGIN, grupo_requerido


class RegistrarFCMSerializer(serializers.Serializer):
    token = serializers.CharField(
        max_length=512,
        trim_whitespace=True
    )

    plataforma = serializers.ChoiceField(
        choices=["android", "ios"]
    )

    dispositivo_id = serializers.CharField(
        max_length=128,
        required=False,
        allow_blank=True,
        trim_whitespace=True
    )


class DesregistrarFCMSerializer(serializers.Serializer):
    token = serializers.CharField(
        max_length=512,
        trim_whitespace=True
    )


class RegistrarFCMView(APIView):
    """
    Registra un token FCM para el usuario autenticado.

    El usuario se obtiene desde el JWT.
    No se acepta usuario_id enviado por el cliente.
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
        dispositivo_id = datos.get(
            "dispositivo_id"
        ) or None

        usuario_id = request.user.id

        with transaction.atomic(using="pronostico"):

            # Si la instalacion ya tenia otro token,
            # desactivarlo para evitar duplicados.
            if dispositivo_id:
                DispositivoFCM.objects.using(
                    "pronostico"
                ).filter(
                    usuario_id=usuario_id,
                    dispositivo_id=dispositivo_id
                ).exclude(
                    token=token
                ).update(
                    activo=False
                )

            dispositivo, creado = (
                DispositivoFCM.objects.using(
                    "pronostico"
                ).update_or_create(
                    token=token,
                    defaults={
                        "usuario_id": usuario_id,
                        "plataforma": plataforma,
                        "dispositivo_id": dispositivo_id,
                        "activo": True,
                        "ultima_actividad": timezone.now(),
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
            )
        )


class DesregistrarFCMView(APIView):
    """
    Desactiva un token FCM cuando
    el usuario cierra sesion.
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

        actualizados = (
            DispositivoFCM.objects.using(
                "pronostico"
            ).filter(
                usuario_id=request.user.id,
                token=token,
                activo=True
            ).update(
                activo=False,
                ultima_actividad=timezone.now()
            )
        )

        return Response({
            "success": True,
            "mensaje": "Token desactivado correctamente",
            "desactivados": actualizados,
        })
