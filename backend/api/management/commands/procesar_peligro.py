from datetime import datetime

from django.core.management.base import BaseCommand, CommandError

from api.services.peligro import procesar


class Command(BaseCommand):
    help = ("Procesa uno o más GeoTIFF del modelo de peligro (0-100 %): registra el producto y "
            "llena peligro_zona con los polígonos por área y nivel.")

    def add_arguments(self, parser):
        parser.add_argument("tifs", nargs="+", help="Rutas de los GeoTIFF")
        parser.add_argument("--capa", help="Capa de GeoServer donde está publicado (p. ej. Prueba:peligro_incendio)")
        parser.add_argument("--desde", type=datetime.fromisoformat, help="Vigencia desde (ISO 8601), si el TIFF no la trae")
        parser.add_argument("--hasta", type=datetime.fromisoformat, help="Vigencia hasta (ISO 8601), si el TIFF no la trae")

    def handle(self, *args, **o):
        for ruta in o["tifs"]:
            try:
                producto_id, n = procesar(ruta, o["capa"], o["desde"], o["hasta"])
            except (ValueError, OSError) as e:
                raise CommandError(f"{ruta}: {e}")
            self.stdout.write(self.style.SUCCESS(f"{ruta}: producto {producto_id}, {n} polígonos (área × nivel, con y sin buffer)"))
