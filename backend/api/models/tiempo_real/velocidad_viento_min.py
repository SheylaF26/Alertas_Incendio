from .base import MedicionTiempoReal


class VelocidadVientoMin(MedicionTiempoReal):
    class Meta:
        managed = False
        db_table = '"public"."_037110201h"'
