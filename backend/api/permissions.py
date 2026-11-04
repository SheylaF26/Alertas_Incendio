from rest_framework.permissions import BasePermission

GUARDAPARQUES = "aplicacion incendios guardaparques"
BRIGADAS = "aplicacion incendios brigadas"
CON_LOGIN = (GUARDAPARQUES, BRIGADAS)


def grupo_requerido(*nombres):
    """Permite el acceso a usuarios de alguno de los grupos indicados."""
    class Permiso(BasePermission):
        message = "No tienes permiso para esta acción."

        def has_permission(self, request, view):
            u = request.user
            if not (u and u.is_authenticated):
                return False
            return u.is_superuser or u.groups.filter(name__in=nombres).exists()

    return Permiso