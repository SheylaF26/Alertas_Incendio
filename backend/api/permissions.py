from rest_framework.permissions import BasePermission

GUARDAPARQUES = "guardaparques"
BRIGADAS = "brigadas"
ENTIDADES = "entidades_publicas"
CON_LOGIN = (GUARDAPARQUES, BRIGADAS, ENTIDADES)


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