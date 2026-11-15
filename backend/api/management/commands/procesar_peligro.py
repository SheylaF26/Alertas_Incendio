from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from pathlib import Path

from api.services.peligro import partes_del_nombre, procesar


class Command(BaseCommand):
    help = ("Procesa uno o más GeoTIFF del modelo de peligro (0-100 %): registra el producto y "
            "llena peligro_zona con los polígonos por área y nivel. Acepta archivos o carpetas con "
            "IPI_<inicialización>Z_<validez>Z_cont.tif; los _clas solo se usan para comparar.")

    def add_arguments(self, parser):
        parser.add_argument("tifs", nargs="+", help="Rutas de los GeoTIFF o de carpetas que los contienen")
        parser.add_argument("--capa", help="Capa de GeoServer donde está publicado (p. ej. Prueba:peligro_incendio)")
        parser.add_argument("--desde", type=datetime.fromisoformat, help="Vigencia desde (ISO 8601), si el TIFF no la trae")
        parser.add_argument("--hasta", type=datetime.fromisoformat, help="Vigencia hasta (ISO 8601), si el TIFF no la trae")

    def handle(self, *args, **o):
        rutas = []
        for entrada in map(Path, o["tifs"]):
            rutas += sorted(entrada.glob("*.tif")) if entrada.is_dir() else [entrada]
        # Los reclasificados no se procesan: los lee el continuo de su mismo nombre para comparar.
        rutas = [r for r in rutas if (partes_del_nombre(r.name) or (0, 0, 0, "cont"))[3] != "clas"]
        if not rutas:
            raise CommandError("No hay ningún GeoTIFF continuo que procesar.")
        for ruta in rutas:
            try:
                producto_id, n, comparacion = procesar(ruta, o["capa"], o["desde"], o["hasta"])
            except (ValueError, OSError) as e:
                raise CommandError(f"{ruta}: {e}")
            if comparacion is None:
                clas = "sin clas para comparar"
            elif comparacion[1]:
                clas = f"{comparacion[1]} de {comparacion[0]} píxeles NO coinciden con el clas"
            else:
                clas = f"coincide con el clas ({comparacion[0]} píxeles)"
            estilo = self.style.WARNING if comparacion and comparacion[1] else self.style.SUCCESS
            self.stdout.write(estilo(f"{ruta.name}: producto {producto_id}, {n} polígonos "
                                     f"(área × nivel, con y sin buffer); {clas}"))
