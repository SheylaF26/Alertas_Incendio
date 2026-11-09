from django.db import models


class Estacion(models.Model):
    """Catálogo de estaciones de la base de tiempo real. Solo lectura."""
    id = models.IntegerField(primary_key=True)
    cod_inamhi = models.CharField(max_length=20, blank=True, null=True)
    nombre = models.CharField(max_length=200, blank=True, null=True)
    categoria = models.CharField(max_length=50, blank=True, null=True)
    provincia = models.CharField(max_length=100, blank=True, null=True)
    canton = models.CharField(max_length=100, blank=True, null=True)
    latitud = models.FloatField(blank=True, null=True)
    longitud = models.FloatField(blank=True, null=True)
    altitud = models.FloatField(blank=True, null=True)
    estado_estacion = models.CharField(max_length=50, blank=True, null=True)

    class Meta:
        managed = False
        db_table = '"public"."estaciones"'
