from django.db import models


# Tabla PostgreSQL: _009010201h
class HumedadRelativaMin(models.Model):
    pk = models.CompositePrimaryKey("id_estacion", "fecha_toma_dato", "instrumento")
    id_usuario = models.IntegerField(blank=True, null=True)
    id_estacion = models.IntegerField()
    estacion = models.TextField()
    fecha_toma_dato = models.DateTimeField()
    fecha_ingreso = models.DateTimeField(blank=True, null=True)
    valor = models.DecimalField(max_digits=12, decimal_places=4)
    instrumento = models.IntegerField()
    nivel_calidad = models.IntegerField(blank=True, null=True)
    estado_calidad = models.IntegerField(blank=True, null=True)
    frecuencia_trans = models.IntegerField()
    estado_proceso = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = '_009010201h'