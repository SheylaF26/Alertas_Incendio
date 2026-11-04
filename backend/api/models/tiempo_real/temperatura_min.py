from .base import MedicionTiempoReal


class TemperaturaMin(MedicionTiempoReal):
    class Meta:
        managed = False
        db_table = "_029030201h"
