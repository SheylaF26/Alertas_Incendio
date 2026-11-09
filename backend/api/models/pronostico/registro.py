from django.db import models
from .area_protegida import AreaProtegida
from .tipo_evento import TipoEvento


class Registro(models.Model):
    """Reporte enviado desde la app por un guardaparques o un aledaño (grupo brigadas)."""
    id = models.BigAutoField(primary_key=True)
    usuario_id = models.BigIntegerField()  # seguridades.usuarios.id (otra base, sin FK)
    fecha_registro = models.DateTimeField()
    latitud = models.DecimalField(max_digits=9, decimal_places=6)
    longitud = models.DecimalField(max_digits=9, decimal_places=6)
    descripcion = models.TextField(blank=True, null=True)
    evidencia = models.CharField(max_length=500, blank=True, null=True)  # URL de la foto
    tipo_evento = models.ForeignKey(TipoEvento, models.DO_NOTHING)
    area_protegida = models.ForeignKey(AreaProtegida, models.DO_NOTHING)

    class Meta:
        managed = False
        db_table = 'registro'
