from drf_spectacular.utils import extend_schema_field
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


class AreaResumenSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    nombre = serializers.CharField()


class AreaSerializer(serializers.ModelSerializer):
    alerta_actual = serializers.SerializerMethodField(
        help_text="Alerta más reciente del área, o null si no tiene."
    )

    class Meta:
        model = AreaProtegida
        fields = ["id", "nombre", "descripcion", "alerta_actual"]

    @extend_schema_field(AlertaResumenSerializer(allow_null=True))
    def get_alerta_actual(self, obj):
        alerta = self.context.get("alertas", {}).get(obj.ultima_alerta_id)
        return AlertaResumenSerializer(alerta).data if alerta else None


class AlertaSerializer(serializers.ModelSerializer):
    areas = serializers.SerializerMethodField(help_text="Áreas protegidas afectadas por la alerta.")

    class Meta:
        model = Alertas
        fields = ["id", "nivel_de_riesgo", "color", "descripcion", "fecha", "areas"]

    @extend_schema_field(AreaResumenSerializer(many=True))
    def get_areas(self, obj):
        return self.context.get("areas", {}).get(obj.id, [])


# ---------------------------------------------------------------------------
# Serializers solo para documentar (Swagger): describen entradas y respuestas.
# ---------------------------------------------------------------------------

class GrupoSerializer(serializers.Serializer):
    id = serializers.IntegerField(help_text="1 = guardaparques, 2 = brigadas.")
    nombre = serializers.CharField()


class UsuarioSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    first_name = serializers.CharField()
    nombre = serializers.CharField(help_text="Nombre completo (first_name + last_name).")
    email = serializers.CharField()
    grupos = GrupoSerializer(many=True, help_text="Grupos de la app a los que pertenece.")


class LoginEntradaSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(style={"input_type": "password"})


class LoginRespuestaSerializer(serializers.Serializer):
    access = serializers.CharField(
        help_text="JWT de acceso (30 min). Enviar en el header: Authorization: Bearer <access>. "
                  "Claims extra: first_name y grupos (lista de ids)."
    )
    refresh = serializers.CharField(help_text="JWT para pedir un nuevo access (7 días).")
    usuario = UsuarioSerializer()


class RefreshEntradaSerializer(serializers.Serializer):
    refresh = serializers.CharField()


class RefreshRespuestaSerializer(serializers.Serializer):
    access = serializers.CharField(help_text="Nuevo JWT de acceso (30 min).")


class ErrorSerializer(serializers.Serializer):
    detail = serializers.CharField()


class FocoSerializer(serializers.Serializer):
    latitude = serializers.FloatField()
    longitude = serializers.FloatField()
    brightness = serializers.FloatField(allow_null=True, help_text="Temperatura en K: de brillo I4 (VIIRS) o del fuego (GOES).")
    brightness_ti5 = serializers.FloatField(allow_null=True, help_text="Temperatura de brillo canal I5 (K). Solo VIIRS.")
    frp = serializers.FloatField(allow_null=True, help_text="Potencia radiativa del fuego (MW).")
    area_fuego_m2 = serializers.FloatField(allow_null=True, help_text="Área estimada del fuego (m²). Solo GOES.")
    acq_date = serializers.CharField(help_text="Fecha de detección en UTC (YYYY-MM-DD).")
    acq_time = serializers.CharField(help_text="Hora de detección en UTC (HHMM).")
    fecha_utc = serializers.DateTimeField()
    fecha_local = serializers.DateTimeField(help_text="Hora de Ecuador (America/Guayaquil).")
    satellite = serializers.CharField()
    instrument = serializers.CharField()
    fuente = serializers.CharField(help_text="VIIRS_NOAA20_NRT, VIIRS_NOAA21_NRT, VIIRS_SNPP_NRT o GOES19_FDCF.")
    confidence = serializers.CharField(help_text="Código original: l, n o h (VIIRS); 10, 11, 30 o 31 (GOES).")
    confianza = serializers.CharField(help_text="baja, nominal o alta.")
    daynight = serializers.CharField(allow_null=True, help_text="D = día, N = noche. Solo VIIRS.")
    area_protegida_id = serializers.IntegerField(allow_null=True, help_text="Área protegida donde cae, o null.")
    area_protegida = serializers.CharField(allow_null=True, help_text="Nombre del área protegida, o null.")
    es_volcan = serializers.BooleanField(help_text="True si está a menos de 5 km de un volcán en erupción: "
                                                   "probablemente es calor volcánico y no un incendio.")


class FocosRespuestaSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    horas = serializers.IntegerField(help_text="Horas consultadas (ajustado a 1–168).")
    total = serializers.IntegerField()
    focos = FocoSerializer(many=True)


class FocosErrorSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=False)
    mensaje = serializers.CharField()