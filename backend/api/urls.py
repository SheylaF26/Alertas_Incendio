from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from .views import (
    AlertaDetailView, AlertaListView, AreaDetailView, AreaListView, AreasGeoJsonView, EstacionesTiempoRealView,
    FocosCalorView, FotoRegistroView, LoginView, MeView, RefreshView, RegistrosPendientesView, RegistrosView,
    SerieTiempoRealView, TiposEventoView, ValidarRegistroView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("token/refresh/", RefreshView.as_view(), name="token_refresh"),
    path("me/", MeView.as_view(), name="me"),

    path("areas/", AreaListView.as_view(), name="areas"),
    path("areas/geojson/", AreasGeoJsonView.as_view(), name="areas_geojson"),
    path("areas/<int:pk>/", AreaDetailView.as_view(), name="area_detalle"),
    path("alertas/", AlertaListView.as_view(), name="alertas"),
    path("alertas/<int:pk>/", AlertaDetailView.as_view(), name="alerta_detalle"),

    path("focos-calor/", FocosCalorView.as_view(), name="focos_calor"),

    path("tiempo-real/estaciones/", EstacionesTiempoRealView.as_view(), name="tiempo_real_estaciones"),
    path("tiempo-real/serie/", SerieTiempoRealView.as_view(), name="tiempo_real_serie"),

    path("tipos-evento/", TiposEventoView.as_view(), name="tipos_evento"),
    path("registros/", RegistrosView.as_view(), name="registros"),
    path("registros/foto/", FotoRegistroView.as_view(), name="registro_foto"),
    path("registros/pendientes/", RegistrosPendientesView.as_view(), name="registros_pendientes"),
    path("registros/<int:pk>/validar/", ValidarRegistroView.as_view(), name="registro_validar"),

    # Documentación
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
