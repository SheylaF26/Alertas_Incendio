from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    AlertaDetailView, AlertaListView, AreaDetailView, AreaListView,
    LoginView, MeView, focos_calor,
)

urlpatterns = [
    path("login/", LoginView.as_view(), name="login"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("me/", MeView.as_view(), name="me"),

    path("areas/", AreaListView.as_view(), name="areas"),
    path("areas/<int:pk>/", AreaDetailView.as_view(), name="area_detalle"),
    path("alertas/", AlertaListView.as_view(), name="alertas"),
    path("alertas/<int:pk>/", AlertaDetailView.as_view(), name="alerta_detalle"),

    path("focos-calor/", focos_calor, name="focos_calor"),
]
