from django.db import models


class GoesArchivo(models.Model):
    """Control de los NetCDF de GOES ya procesados, para no repetirlos y recuperar los que falten."""
    archivo = models.CharField(max_length=200, primary_key=True)
    inicio_escaneo = models.DateTimeField()
    focos = models.IntegerField()
    procesado_en = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'goes_archivo'
