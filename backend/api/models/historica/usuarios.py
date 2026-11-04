"""
Base histórica (alias 'default'), esquema `seguridades`.

`usuarios` es compartida con otros sistemas: esta app solo la lee.
El acceso a la app se controla con `grupos` y `usuarios_groups`.
"""
import hashlib
import hmac

from django.contrib.auth.base_user import AbstractBaseUser
from django.contrib.auth.models import UserManager
from django.db import models
from django.utils import timezone


def password_valida(password_plano, hash_guardado):
    """Compara contra el SHA-256 (hex, sin sal) guardado en seguridades.usuarios."""
    if not password_plano or not hash_guardado:
        return False
    calculado = hashlib.sha256(password_plano.encode("utf-8")).hexdigest()
    return hmac.compare_digest(calculado, hash_guardado.strip().lower())


class Grupo(models.Model):
    name = models.CharField(max_length=150, unique=True)

    class Meta:
        managed = False
        db_table = '"seguridades"."grupos"'

    def __str__(self):
        return self.name


class Usuario(AbstractBaseUser):
    id = models.BigAutoField(primary_key=True)
    username = models.CharField(max_length=150, unique=True)
    password = models.CharField(max_length=128, null=True, blank=True)
    email = models.CharField(max_length=100, unique=True)
    persona_fk = models.BigIntegerField(null=True, blank=True)
    estado = models.CharField(max_length=1, null=True, blank=True, default="1")
    conv = models.BooleanField(default=True)
    date_joined = models.DateTimeField(null=True, blank=True, default=timezone.now)
    first_name = models.CharField(max_length=150, blank=True)
    last_name = models.CharField(max_length=150, blank=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)

    groups = models.ManyToManyField(
        Grupo, through="UsuarioGroups", blank=True, related_name="usuarios",
    )

    objects = UserManager()

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = ["email"]

    class Meta:
        managed = False
        db_table = '"seguridades"."usuarios"'

    @property
    def is_active(self):
        return self.estado == "1"

    # Solo valida: Django por defecto re-hashearía y guardaría la contraseña,
    # lo que modificaría la tabla compartida.
    def check_password(self, raw_password):
        return password_valida(raw_password, self.password)

    def set_password(self, raw_password):
        raise NotImplementedError("Las contraseñas se gestionan fuera de esta aplicación.")

    def get_full_name(self):
        return f"{self.first_name} {self.last_name}".strip()

    def has_perm(self, perm, obj=None):
        return self.is_active and self.is_superuser

    def has_module_perms(self, app_label):
        return self.is_active and self.is_superuser


class UsuarioGroups(models.Model):
    usuario = models.ForeignKey(Usuario, on_delete=models.CASCADE, db_column="usuario_id")
    group = models.ForeignKey(Grupo, on_delete=models.CASCADE, db_column="group_id")

    class Meta:
        managed = False
        db_table = '"seguridades"."usuarios_groups"'
