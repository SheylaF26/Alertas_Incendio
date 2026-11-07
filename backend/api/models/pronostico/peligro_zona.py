from django.db import models
from .area_protegida import AreaProtegida
from .nivel_peligro import NivelPeligro
from .producto_modelo import ProductoModelo


class PeligroZona(models.Model):
    """Polígono disuelto de un nivel dentro de un área, para un producto.

    geom (MultiPolygon 4326) existe en la base; se escribe por SQL y se publica en GeoServer.
    """
    id = models.BigAutoField(primary_key=True)
    producto = models.ForeignKey(ProductoModelo, models.CASCADE)
    area_protegida = models.ForeignKey(AreaProtegida, models.DO_NOTHING)
    nivel = models.ForeignKey(NivelPeligro, models.DO_NOTHING, db_column='nivel')
    pixeles = models.IntegerField()
    porcentaje_area = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        managed = False
        db_table = 'peligro_zona'
        unique_together = (('producto', 'area_protegida', 'nivel'),)
