from .base import MedicionTiempoReal


class TemperaturaMax(MedicionTiempoReal):
    class Meta:
        managed = False
        db_table = '"public"."_029030101h"'
