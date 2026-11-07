from .base import MedicionTiempoReal


class HumedadRelativaMin(MedicionTiempoReal):
    class Meta:
        managed = False
        db_table = '"public"."_009010201h"'
