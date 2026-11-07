from .base import MedicionTiempoReal


class DireccionVientoMin(MedicionTiempoReal):
    class Meta:
        managed = False
        db_table = '"public"."_004020201h"'
