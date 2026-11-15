import logging
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import tifffile
from django.test import SimpleTestCase

from api.services.peligro import comparar_con_clas, fechas, leer_tif, partes_del_nombre

UTC = timezone.utc
GEO = [(33550, 12, 3, (0.01, 0.01, 0.0), False), (33922, 12, 6, (0.0, 0.0, 0.0, -79.0, 1.0, 0.0), False)]


def escribir(ruta, datos, nodata):
    tifffile.imwrite(ruta, datos, extratags=GEO + [(42113, 2, 0, nodata, False)])


class NombreIPI(SimpleTestCase):
    def test_una_emision_al_dia(self):
        emision, desde, hasta, tipo = partes_del_nombre("IPI_20261113Z_20261114Z_cont.tif")
        self.assertEqual(emision, datetime(2026, 11, 13, tzinfo=UTC))
        self.assertEqual(desde, datetime(2026, 11, 14, tzinfo=UTC))
        self.assertEqual(hasta, datetime(2026, 11, 15, tzinfo=UTC))
        self.assertEqual(tipo, "cont")

    def test_varias_emisiones_al_dia(self):
        emision, desde, _, tipo = partes_del_nombre("IPI_2026111312Z_20261114Z_clas.tif")
        self.assertEqual(emision, datetime(2026, 11, 13, 12, tzinfo=UTC))
        self.assertEqual(desde, datetime(2026, 11, 14, tzinfo=UTC))
        self.assertEqual(tipo, "clas")

    def test_otros_nombres_no_son_ipi(self):
        for nombre in ("peligro_incendio_20261106T1700Z.tif", "IPI_20261113_20261114_cont.tif",
                       "IPI_20261113Z_20261114Z_otro.tif", "IPI_20261113Z_20261114Z_cont.shp"):
            self.assertIsNone(partes_del_nombre(nombre), nombre)

    def test_fechas_imposibles(self):
        with self.assertRaises(ValueError):
            partes_del_nombre("IPI_20261341Z_20261114Z_cont.tif")
        with self.assertRaises(ValueError):  # validez anterior a la corrida
            partes_del_nombre("IPI_20261115Z_20261114Z_cont.tif")


class LecturaYComparacion(SimpleTestCase):
    def setUp(self):
        carpeta = tempfile.TemporaryDirectory()
        self.addCleanup(carpeta.cleanup)
        self.carpeta = Path(carpeta.name)
        self.cont = self.carpeta / "IPI_20261114Z_20261115Z_cont.tif"
        self.clas = self.carpeta / "IPI_20261114Z_20261115Z_clas.tif"
        escribir(self.cont, np.array([[10, 30], [60, -9999]], dtype="float32"), "-9999")
        self.niveles = np.array([[1, 2], [3, 0]], dtype=np.int16)
        logging.disable(logging.WARNING)
        self.addCleanup(logging.disable, logging.NOTSET)

    def test_nodata_y_fechas_del_continuo(self):
        raster = leer_tif(self.cont)
        self.assertTrue(np.isnan(raster.valores[1, 1]))
        self.assertEqual(float(np.nanmax(raster.valores)), 60.0)
        emision, desde, hasta = fechas(self.cont, raster)
        self.assertEqual((emision, desde, hasta), (datetime(2026, 11, 14, tzinfo=UTC),
                                                   datetime(2026, 11, 15, tzinfo=UTC),
                                                   datetime(2026, 11, 16, tzinfo=UTC)))

    def test_el_clas_no_se_procesa_como_producto(self):
        escribir(self.clas, np.array([[1, 2], [3, 255]], dtype="uint8"), "255")
        with self.assertRaises(ValueError):
            fechas(self.clas, leer_tif(self.clas))

    def test_sin_clas_no_hay_comparacion(self):
        self.assertIsNone(comparar_con_clas(self.cont, leer_tif(self.cont), self.niveles))

    def test_clas_igual(self):
        escribir(self.clas, np.array([[1, 2], [3, 255]], dtype="uint8"), "255")
        self.assertEqual(comparar_con_clas(self.cont, leer_tif(self.cont), self.niveles), (3, 0))

    def test_clas_distinto(self):
        escribir(self.clas, np.array([[1, 3], [3, 1]], dtype="uint8"), "255")
        # Un nivel distinto y un píxel que para ellos tiene dato y para nosotros no
        self.assertEqual(comparar_con_clas(self.cont, leer_tif(self.cont), self.niveles), (4, 2))

    def test_clas_con_otra_malla(self):
        escribir(self.clas, np.array([[1, 2, 3]], dtype="uint8"), "255")
        with self.assertRaises(ValueError):
            comparar_con_clas(self.cont, leer_tif(self.cont), self.niveles)
