from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from api.models import Alertas, AreaProtegida


def grupos_de(usuario):
    return list(usuario.groups.values_list("name", flat=True))


class LoginSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["grupos"] = grupos_de(user)
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["usuario"] = {
            "id": self.user.id,
            "username": self.user.username,
            "nombre": self.user.get_full_name(),
            "grupos": grupos_de(self.user),
        }
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