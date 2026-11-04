from django.db.models import OuterRef, Subquery

from api.models import AreaAlerta, AreaProtegida, Alertas


def areas_con_ultima_alerta():
    """Cada área con el id de su alerta más reciente (o None)."""
    ultima = (
        AreaAlerta.objects
        .filter(area_protegida=OuterRef("pk"))
        .order_by("-alerta__fecha")
        .values("alerta_id")[:1]
    )
    return AreaProtegida.objects.annotate(ultima_alerta_id=Subquery(ultima)).order_by("nombre")


def alertas_por_id(ids):
    return Alertas.objects.in_bulk([i for i in ids if i])


def areas_de_alertas(alertas):
    """{alerta_id: [{'id': .., 'nombre': ..}, ...]} para una lista de alertas."""
    ids = [a.id for a in alertas]
    filas = (
        AreaAlerta.objects
        .filter(alerta_id__in=ids)
        .values_list("alerta_id", "area_protegida_id", "area_protegida__nombre")
    )
    resultado = {}
    for alerta_id, area_id, nombre in filas:
        resultado.setdefault(alerta_id, []).append({"id": area_id, "nombre": nombre})
    return resultado