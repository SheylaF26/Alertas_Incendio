from django.db import models


class ProductoModelo(models.Model):
    """Un registro por cada GeoTIFF (0-100 %) entregado por el modelo de peligro."""
    id = models.BigAutoField(primary_key=True)
    archivo = models.CharField(max_length=300, unique=True)
    fecha_emision = models.DateTimeField()
    vigencia_desde = models.DateTimeField()
    vigencia_hasta = models.DateTimeField()
    capa_geoserver = models.CharField(max_length=200, blank=True, null=True)
    valor_min = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    valor_max = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    valor_medio = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    procesado_en = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'producto_modelo'
