from django.db import models


class MedicionTiempoReal(models.Model):
    """Estructura común de las tablas de variables en tiempo real (esquema convencionales)."""
    pk = models.CompositePrimaryKey("id_estacion", "fecha_toma_dato", "instrumento")
    id_usuario = models.IntegerField(blank=True, null=True)
    id_estacion = models.IntegerField()
    estacion = models.TextField(blank=True, null=True)
    fecha_toma_dato = models.DateTimeField()
    fecha_ingreso = models.DateTimeField(blank=True, null=True)
    valor = models.DecimalField(max_digits=12, decimal_places=4, blank=True, null=True)
    instrumento = models.IntegerField()
    nivel_calidad = models.IntegerField(blank=True, null=True)
    estado_calidad = models.IntegerField(blank=True, null=True)
    frecuencia_trans = models.IntegerField(blank=True, null=True)
    estado_proceso = models.TextField(blank=True, null=True)

    class Meta:
        abstract = True
        managed = False
