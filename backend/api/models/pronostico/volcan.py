from django.db import models


class Volcan(models.Model):
    """Volcanes activos de Ecuador continental. Un foco a menos de radio_km de uno en erupción se marca es_volcan."""
    id = models.SmallAutoField(primary_key=True)
    numero_gvp = models.IntegerField(unique=True)
    nombre = models.CharField(max_length=50, unique=True)
    latitud = models.DecimalField(max_digits=9, decimal_places=6)
    longitud = models.DecimalField(max_digits=9, decimal_places=6)
    elevacion_m = models.IntegerField(blank=True, null=True)
    ultima_erupcion = models.IntegerField(blank=True, null=True)
    en_erupcion = models.BooleanField()
    radio_km = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'volcan'
