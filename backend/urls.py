from django.urls import include, path

# Prefijo del proyecto: nginx de srvbackend enruta /api_incendios/ -> 127.0.0.1:8011
urlpatterns = [
    path("api_incendios/", include("api.urls")),
]
