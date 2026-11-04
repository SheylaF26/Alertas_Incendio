
from django.db import models

class Alertas(models.Model):
    id = models.BigAutoField(primary_key=True)
    nivel_de_riesgo = models.CharField(max_length=50)
    descripcion = models.TextField(blank=True, null=True)
    color = models.CharField(max_length=20, blank=True, null=True)
    fecha = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'alertas'
