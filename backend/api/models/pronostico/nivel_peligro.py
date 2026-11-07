from django.db import models


class NivelPeligro(models.Model):
    """Catálogo de niveles 1-4; los cortes (valor_min/valor_max, %) se usan para reclasificar el TIFF."""
    nivel = models.SmallIntegerField(primary_key=True)
    nombre = models.CharField(max_length=30, unique=True)
    valor_min = models.DecimalField(max_digits=5, decimal_places=2)
    valor_max = models.DecimalField(max_digits=5, decimal_places=2)
    color = models.CharField(max_length=7)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'nivel_peligro'
