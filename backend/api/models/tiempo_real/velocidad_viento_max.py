from .base import MedicionTiempoReal


class VelocidadVientoMax(MedicionTiempoReal):
    class Meta:
        managed = False
        db_table = "_037110101h"
