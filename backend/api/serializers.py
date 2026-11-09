from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from api.models import Alertas, AreaProtegida, TipoEvento


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
        fields = ["id", "origen", "nivel_de_riesgo", "color", "descripcion", "fecha"]


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
        fields = ["id", "origen", "nivel_de_riesgo", "color", "descripcion", "fecha", "areas",
                  "producto", "foco_calor", "registro"]

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
    detecciones = serializers.IntegerField(help_text="Veces que se detectó este punto en el periodo. "
                                                     "Con agrupar=false siempre es 1.")
    primera_deteccion_utc = serializers.DateTimeField(help_text="Primera vez que se detectó este punto dentro del "
                                                                "periodo pedido. Con agrupar=false es igual a fecha_utc.")
    primera_deteccion_local = serializers.DateTimeField(help_text="Lo mismo, en hora de Ecuador.")


class FocosRespuestaSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    horas = serializers.IntegerField(help_text="Horas consultadas (ajustado a 1–168).")
    total = serializers.IntegerField()
    focos = FocoSerializer(many=True)


class TipoEventoSerializer(serializers.ModelSerializer):
    class Meta:
        model = TipoEvento
        fields = ["id", "nombre", "descripcion"]


class RegistroEntradaSerializer(serializers.Serializer):
    latitud = serializers.FloatField(min_value=-90, max_value=90)
    longitud = serializers.FloatField(min_value=-180, max_value=180)
    tipo_evento_id = serializers.PrimaryKeyRelatedField(
        queryset=TipoEvento.objects.all(), source="tipo_evento", help_text="Id de `tipos-evento/`.")
    descripcion = serializers.CharField(required=False, allow_blank=True)
    evidencia = serializers.URLField(required=False, allow_null=True, max_length=500, help_text="URL de la foto.")
    area_protegida_id = serializers.IntegerField(
        required=False, help_text="Solo es obligatorio si el usuario tiene varias áreas asignadas.")


class FotoRespuestaSerializer(serializers.Serializer):
    url = serializers.URLField(help_text="URL de la foto: se envía en `evidencia` al crear el reporte.")


class ValidarEntradaSerializer(serializers.Serializer):
    estado = serializers.ChoiceField(choices=["validado", "rechazado"])
    observacion = serializers.CharField(required=False, allow_blank=True)


class RegistroSalidaSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    usuario_id = serializers.IntegerField()
    reportado_por = serializers.CharField(allow_null=True)
    fecha_registro = serializers.DateTimeField()
    latitud = serializers.FloatField()
    longitud = serializers.FloatField()
    descripcion = serializers.CharField(allow_null=True)
    evidencia = serializers.CharField(allow_null=True)
    tipo_evento = AreaResumenSerializer()
    area_protegida = AreaResumenSerializer()
    estado = serializers.ChoiceField(choices=["pendiente", "validado", "rechazado"])


class ValorActualSerializer(serializers.Serializer):
    valor = serializers.FloatField()
    fecha_utc = serializers.DateTimeField()
    fecha_local = serializers.DateTimeField(help_text="Hora de Ecuador (America/Guayaquil).")


class VariablesActualesSerializer(serializers.Serializer):
    precipitacion = ValorActualSerializer(required=False)
    temperatura_max = ValorActualSerializer(required=False)
    temperatura_min = ValorActualSerializer(required=False)
    humedad_relativa_max = ValorActualSerializer(required=False)
    humedad_relativa_min = ValorActualSerializer(required=False)
    velocidad_viento_max = ValorActualSerializer(required=False)
    velocidad_viento_min = ValorActualSerializer(required=False)
    direccion_viento_max = ValorActualSerializer(required=False)
    direccion_viento_min = ValorActualSerializer(required=False)


class EstacionActualSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    codigo = serializers.CharField(allow_null=True, help_text="Código INAMHI, p. ej. M0146.")
    nombre = serializers.CharField(allow_null=True)
    provincia = serializers.CharField(allow_null=True)
    canton = serializers.CharField(allow_null=True)
    latitud = serializers.FloatField()
    longitud = serializers.FloatField()
    altitud = serializers.FloatField(allow_null=True)
    variables = VariablesActualesSerializer(help_text="Último dato válido de cada variable; las que no tienen dato no aparecen.")


class EstacionesRespuestaSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    horas = serializers.IntegerField(help_text="Horas consultadas (ajustado a 1–72).")
    total = serializers.IntegerField()
    estaciones = EstacionActualSerializer(many=True)


class DatoSerieSerializer(serializers.Serializer):
    fecha_utc = serializers.DateTimeField()
    fecha_local = serializers.DateTimeField()
    valor = serializers.FloatField()
    instrumento = serializers.IntegerField()


class EstacionResumenSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    codigo = serializers.CharField(allow_null=True)
    nombre = serializers.CharField(allow_null=True)


class SerieRespuestaSerializer(serializers.Serializer):
    success = serializers.BooleanField()
    estacion = EstacionResumenSerializer()
    variable = serializers.CharField()
    horas = serializers.IntegerField(help_text="Horas consultadas (ajustado a 1–168).")
    total = serializers.IntegerField()
    datos = DatoSerieSerializer(many=True)


class FocosErrorSerializer(serializers.Serializer):
    success = serializers.BooleanField(default=False)
    mensaje = serializers.CharField()