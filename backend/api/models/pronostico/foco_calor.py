from django.db import models
from .area_protegida import AreaProtegida


class FocoCalor(models.Model):
    """Una detección de calor en Ecuador continental (VIIRS de FIRMS o GOES-19).

    geom (Point 4326) existe en la base; se escribe por SQL.
    """
    id = models.BigAutoField(primary_key=True)
    fuente = models.CharField(max_length=30)
    fecha_deteccion = models.DateTimeField()
    latitud = models.DecimalField(max_digits=9, decimal_places=6)
    longitud = models.DecimalField(max_digits=9, decimal_places=6)
    frp = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    temperatura = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)
    temperatura_ti5 = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)
    area_fuego_m2 = models.DecimalField(max_digits=12, decimal_places=2, blank=True, null=True)
    satelite = models.CharField(max_length=10, blank=True, null=True)
    instrumento = models.CharField(max_length=10, blank=True, null=True)
    confianza = models.CharField(max_length=10, blank=True, null=True)
    codigo_calidad = models.CharField(max_length=10, blank=True, null=True)
    dia_noche = models.CharField(max_length=1, blank=True, null=True)
    area_protegida = models.ForeignKey(AreaProtegida, models.DO_NOTHING, blank=True, null=True)
    es_volcan = models.BooleanField()
    registrado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'foco_calor'
        unique_together = (('fuente', 'fecha_deteccion', 'latitud', 'longitud'),)
