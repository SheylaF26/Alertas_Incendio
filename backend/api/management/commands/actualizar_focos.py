from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from api.services.focos_calor import actualizar_firms, actualizar_goes


class Command(BaseCommand):
    help = "Trae los focos de calor de NASA FIRMS y/o GOES-19 y guarda en la base los que falten."

    def add_arguments(self, parser):
        parser.add_argument("--fuente", choices=["firms", "goes", "todas"], default="todas")

    def handle(self, *args, **o):
        procesos = {"firms": actualizar_firms, "goes": actualizar_goes}
        elegidos = procesos if o["fuente"] == "todas" else {o["fuente"]: procesos[o["fuente"]]}
        fallidos = []
        for nombre, proceso in elegidos.items():
            try:
                self.stdout.write(f"{timezone.now():%Y-%m-%d %H:%M} {nombre}: {proceso()}")
            except Exception as error:
                # El mensaje de requests puede traer la URL con la clave: solo se muestra el tipo.
                self.stderr.write(f"{timezone.now():%Y-%m-%d %H:%M} {nombre}: falló ({type(error).__name__})")
                fallidos.append(nombre)
        if fallidos:
            raise CommandError(f"Fallaron: {', '.join(fallidos)}")
