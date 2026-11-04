class DatabaseRouter:
    """
    Enruta cada modelo según su carpeta dentro de api/models/:
      - tiempo_real -> base de tiempo real
      - pronostico  -> base de pronósticos
      - historica y apps de Django (auth, admin...) -> default
    """

    RUTAS = {
        "api.models.tiempo_real": "tiempo_real",
        "api.models.pronostico": "pronostico",
    }

    def _get_database(self, model):
        for ruta, base in self.RUTAS.items():
            if model.__module__.startswith(ruta):
                return base
        return "default"

    def db_for_read(self, model, **hints):
        return self._get_database(model)

    def db_for_write(self, model, **hints):
        return self._get_database(model)

    def allow_relation(self, obj1, obj2, **hints):
        db1, db2 = obj1._state.db, obj2._state.db
        if db1 and db2:
            return db1 == db2
        return None

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return db == "default"