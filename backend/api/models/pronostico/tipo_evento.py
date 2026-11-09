from django.db import models


class TipoEvento(models.Model):
    """Catálogo de lo que se puede reportar (incendio forestal, humo...). Se administra en la base."""
    id = models.SmallAutoField(primary_key=True)
    nombre = models.CharField(max_length=100, unique=True)
    descripcion = models.TextField(blank=True, null=True)

    class Meta:
        managed = False
        db_table = 'tipo_evento'
