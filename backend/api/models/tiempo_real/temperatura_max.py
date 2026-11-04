from .base import MedicionTiempoReal


class TemperaturaMax(MedicionTiempoReal):
    class Meta:
        managed = False
        db_table = "_029030101h"
