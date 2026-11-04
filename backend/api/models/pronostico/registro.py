from django.db import models


class Registro(models.Model):
    id = models.BigAutoField(primary_key=True)
    fecha_registro = models.DateTimeField()
    nombre = models.CharField(max_length=200, blank=True, null=True)
    latitud = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    longitud = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    descripcion = models.TextField(blank=True, null=True)
    evidencia = models.CharField(max_length=500, blank=True, null=True)
    tipo_evento = models.CharField(max_length=100, blank=True, null=True)
    actualizacion = models.DateTimeField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'registro'