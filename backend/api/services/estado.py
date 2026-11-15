"""Vigilancia: dice si cada fuente de datos sigue llegando, para avisar cuando una se detiene.

- GOES: cada archivo procesado se anota en goes_archivo, tenga focos o no. Llega cada 10 minutos.
- FIRMS: solo queda rastro cuando hay focos nuevos, así que el límite es amplio.
- Modelo: debe haber un pronóstico cuya validez cubra el momento actual.
"""
from django.db.models import Max
from django.utils import timezone

from api.models import FocoCalor, GoesArchivo, ProductoModelo

LIMITE_HORAS = {"goes": 1, "firms": 48}


def _fuente(ultimo, limite_horas, detalle):
    horas = None if ultimo is None else round((timezone.now() - ultimo).total_seconds() / 3600, 1)
    return {
        "ok": horas is not None and horas <= limite_horas,
        "ultimo_dato": ultimo,
        "horas_sin_datos": horas,
        "limite_horas": limite_horas,
        "detalle": detalle,
    }


def consultar():
    ahora = timezone.now()
    goes = GoesArchivo.objects.aggregate(u=Max("procesado_en"))["u"]
    firms = FocoCalor.objects.filter(fuente__startswith="VIIRS").aggregate(u=Max("registrado_en"))["u"]
    vigente = (ProductoModelo.objects.filter(vigencia_desde__lte=ahora, vigencia_hasta__gt=ahora)
               .order_by("-fecha_emision").first())
    ultimo = vigente or ProductoModelo.objects.order_by("-vigencia_desde", "-fecha_emision").first()
    fuentes = {
        "goes": _fuente(goes, LIMITE_HORAS["goes"], "Último archivo de GOES-19 procesado (llega cada 10 minutos)."),
        "firms": _fuente(firms, LIMITE_HORAS["firms"],
                         "Último foco de VIIRS (NASA FIRMS) guardado. Solo se guarda cuando hay focos nuevos."),
        "modelo": {
            "ok": vigente is not None,
            "archivo": ultimo.archivo if ultimo else None,
            "emitido": ultimo.fecha_emision if ultimo else None,
            "valido_desde": ultimo.vigencia_desde if ultimo else None,
            "valido_hasta": ultimo.vigencia_hasta if ultimo else None,
            "detalle": "Pronóstico del modelo de peligro válido para este momento; "
                       "si no hay, se muestra el más reciente y ok es false.",
        },
    }
    return {"ok": all(f["ok"] for f in fuentes.values()), "consultado": ahora, "fuentes": fuentes}
