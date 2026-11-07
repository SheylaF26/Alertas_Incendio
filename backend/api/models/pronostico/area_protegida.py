from django.db import models


class AreaProtegida(models.Model):
    id = models.BigAutoField(primary_key=True)
    codigo = models.CharField(max_length=50, unique=True, blank=True, null=True)
    nombre = models.CharField(max_length=200)
    # geom (MultiPolygon 4326) existe en la base; se usa por SQL/GeoServer, no por Django.
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'area_protegida'