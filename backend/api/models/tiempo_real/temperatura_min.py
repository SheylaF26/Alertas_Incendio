from .base import MedicionTiempoReal


class TemperaturaMin(MedicionTiempoReal):
    class Meta:
        managed = False
        db_table = '"public"."_029030201h"'
