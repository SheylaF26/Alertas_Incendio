from django.db import models
from .area_protegida import AreaProtegida


class GuardaparquesAreas(models.Model):
    id = models.BigAutoField(primary_key=True)
    usuario_id = models.BigIntegerField()
    area_protegida = models.ForeignKey(
        AreaProtegida,
        models.DO_NOTHING
    )

    class Meta:
        managed = False
        db_table = 'guardaparques_areas'