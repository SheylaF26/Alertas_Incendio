from django.urls import path
from drf_spectacular.views import SpectacularAPIView, SpectacularRedocView, SpectacularSwaggerView

from .views import (
    AlertaDetailView, AlertaListView, AreaDetailView, AreaListView,
    FocosCalorView, LoginView, MeView, RefreshView,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("token/refresh/", RefreshView.as_view(), name="token_refresh"),
    path("me/", MeView.as_view(), name="me"),

    path("areas/", AreaListView.as_view(), name="areas"),
    path("areas/<int:pk>/", AreaDetailView.as_view(), name="area_detalle"),
    path("alertas/", AlertaListView.as_view(), name="alertas"),
    path("alertas/<int:pk>/", AlertaDetailView.as_view(), name="alerta_detalle"),

    path("focos-calor/", FocosCalorView.as_view(), name="focos_calor"),

    # Documentación
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger"),
    path("redoc/", SpectacularRedocView.as_view(url_name="schema"), name="redoc"),
]
