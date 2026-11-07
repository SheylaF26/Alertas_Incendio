from .base import MedicionTiempoReal


class HumedadRelativaMax(MedicionTiempoReal):
    class Meta:
        managed = False
        db_table = '"public"."_009010101h"'
