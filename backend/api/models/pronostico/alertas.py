from django.db import models

from .foco_calor import FocoCalor
from .producto_modelo import ProductoModelo
from .registro import Registro


class Alertas(models.Model):
    """Alerta de incendio. `origen` dice qué la causó y solo se llena el enlace correspondiente."""
    id = models.BigAutoField(primary_key=True)
    nivel_de_riesgo = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True, null=True)
    color = models.CharField(max_length=20, blank=True, null=True)
    fecha = models.DateTimeField()
    origen = models.CharField(max_length=20)  # modelo, goes, firms o registro
    producto = models.ForeignKey(ProductoModelo, models.DO_NOTHING, blank=True, null=True)
    foco_calor = models.ForeignKey(FocoCalor, models.DO_NOTHING, blank=True, null=True)
    registro = models.ForeignKey(Registro, models.DO_NOTHING, blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'alertas'
