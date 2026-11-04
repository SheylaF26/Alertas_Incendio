from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from api.models import Alertas, AreaProtegida


def grupos_de(usuario):
    return [
        {"id": g.id, "nombre": g.name}
        for g in usuario.groups.order_by("id")
    ]


def datos_usuario(usuario):
    return {
        "id": usuario.id,
        "username": usuario.username,
        "first_name": usuario.first_name,
        "nombre": usuario.get_full_name(),
        "email": usuario.email,
        "grupos": grupos_de(usuario),
    }


class LoginSerializer(TokenObtainPairSerializer):
    default_error_messages = {
        "no_active_account": "Credenciales inválidas o sin acceso a la aplicación.",
    }

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["first_name"] = user.first_name
        token["grupos"] = [g["id"] for g in grupos_de(user)]
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["usuario"] = datos_usuario(self.user)
        return data


class AlertaResumenSerializer(serializers.ModelSerializer):
    class Meta:
        model = Alertas
        fields = ["id", "nivel_de_riesgo", "color", "descripcion", "fecha"]


class AreaSerializer(serializers.ModelSerializer):
    alerta_actual = serializers.SerializerMethodField()

    class Meta:
        model = AreaProtegida
        fields = ["id", "nombre", "descripcion", "alerta_actual"]

    def get_alerta_actual(self, obj):
        alerta = self.context.get("alertas", {}).get(obj.ultima_alerta_id)
        return AlertaResumenSerializer(alerta).data if alerta else None


class AlertaSerializer(serializers.ModelSerializer):
    areas = serializers.SerializerMethodField()

    class Meta:
        model = Alertas
        fields = ["id", "nivel_de_riesgo", "color", "descripcion", "fecha", "areas"]

    def get_areas(self, obj):
        return self.context.get("areas", {}).get(obj.id, [])