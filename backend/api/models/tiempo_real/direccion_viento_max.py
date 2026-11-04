from .base import MedicionTiempoReal


class DireccionVientoMax(MedicionTiempoReal):
    class Meta:
        managed = False
        db_table = "_004020101h"
