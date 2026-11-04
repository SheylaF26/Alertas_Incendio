from django.db import models
from .area_protegida import AreaProtegida
from .alertas import Alertas


class AreaAlerta(models.Model):
    pk = models.CompositePrimaryKey('area_protegida_id', 'alerta_id')
    area_protegida = models.ForeignKey(AreaProtegida, models.DO_NOTHING)
    alerta = models.ForeignKey(Alertas, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'area_alerta'