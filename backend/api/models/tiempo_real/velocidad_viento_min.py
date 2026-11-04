from .base import MedicionTiempoReal


class VelocidadVientoMin(MedicionTiempoReal):
    class Meta:
        managed = False
        db_table = "_037110201h"
