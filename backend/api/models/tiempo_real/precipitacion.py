from .base import MedicionTiempoReal


class Precipitacion(MedicionTiempoReal):
    class Meta:
        managed = False
        db_table = "_017140801h"
