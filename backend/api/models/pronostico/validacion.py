from django.db import models
from .registro import Registro
from .estados import Estados

class Validacion(models.Model):
    id = models.BigAutoField(primary_key=True)
    usuario_id = models.BigIntegerField()
    registro = models.ForeignKey(Registro, models.DO_NOTHING)
    estado = models.ForeignKey(Estados, models.DO_NOTHING)
    fecha_validacion = models.DateTimeField()
    observacion = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'validacion'