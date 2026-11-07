from .base import MedicionTiempoReal


class VelocidadVientoMax(MedicionTiempoReal):
    class Meta:
        managed = False
        db_table = '"public"."_037110101h"'
