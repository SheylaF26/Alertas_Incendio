from .base import MedicionTiempoReal


class HumedadRelativaMin(MedicionTiempoReal):
    class Meta:
        managed = False
        db_table = "_009010201h"
