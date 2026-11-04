from django.contrib.auth.backends import BaseBackend

from api.models import Usuario


class Sha256Backend(BaseBackend):
    """
    Login contra seguridades.usuarios (contraseña en SHA-256 sin sal).
    Se ingresa con el username. Solo entra quien esté activo (estado='1')
    y pertenezca a algún grupo de la aplicación de incendios.
    Nunca escribe en seguridades.usuarios.
    """

    def authenticate(self, request, username=None, password=None, **kwargs):
        username = (username or "").strip()
        if not username or not password:
            return None
        usuario = Usuario.objects.filter(username=username).first()
        if usuario is None:
            Usuario(password="0" * 64).check_password(password)  # mismo tiempo exista o no
            return None
        if not usuario.check_password(password):
            return None
        if not usuario.is_active or not usuario.groups.exists():
            return None
        return usuario

    def get_user(self, user_id):
        return Usuario.objects.filter(pk=user_id).first()
