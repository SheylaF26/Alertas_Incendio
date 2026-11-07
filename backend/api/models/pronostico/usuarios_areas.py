from django.db import models
from .area_protegida import AreaProtegida


class UsuariosAreas(models.Model):
    id = models.BigAutoField(primary_key=True)
    usuario_id = models.BigIntegerField()  # seguridades.usuarios.id (otra base, sin FK); el rol lo da el grupo
    area_protegida = models.ForeignKey(
        AreaProtegida,
        models.DO_NOTHING
    )

    class Meta:
        managed = False
        db_table = 'usuarios_areas'