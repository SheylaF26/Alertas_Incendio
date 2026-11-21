
from django.db import models
from django.utils import timezone


class DispositivoFCM(models.Model):
    id = models.BigAutoField(primary_key=True)

    # ID del usuario institucional.
    # No usamos ForeignKey porque los usuarios
    # pertenecen a otra base de datos.
    usuario_id = models.BigIntegerField(
        db_index=True
    )

    # Token generado por Firebase en Flutter.
    token = models.CharField(
        max_length=512,
        unique=True
    )

    # Identificador de instalacion de la app.
    dispositivo_id = models.CharField(
        max_length=128,
        null=True,
        blank=True
    )

    plataforma = models.CharField(
        max_length=10,
        choices=[
            ("android", "Android"),
            ("ios", "iOS"),
        ]
    )

    activo = models.BooleanField(
        default=True
    )

    fecha_registro = models.DateTimeField(
        default=timezone.now
    )

    ultima_actividad = models.DateTimeField(
        default=timezone.now
    )

    class Meta:
        managed = False
        db_table = (
            '"alerta_incendios"."dispositivos_fcm"'
        )
        indexes = [
            models.Index(
                fields=["usuario_id"],
                name="idx_dispositivos_fcm_usuario"
            ),
        ]

    def __str__(self):
        return (
            f"Usuario {self.usuario_id} "
            f"- {self.plataforma}"
        )
