from django.db import models


class AreaProtegida(models.Model):
    id = models.BigAutoField(primary_key=True)
    nombre = models.CharField(max_length=200)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'area_protegida'