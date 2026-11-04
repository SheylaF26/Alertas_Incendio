# from django.db import connections
# with connections["default"].cursor() as c:
#     c.execute("select estado, count(*) from seguridades.usuarios group by estado")
#     print(c.fetchall())
#     c.execute("""select column_name, is_nullable, column_default from information_schema.columns
#                  where table_schema='seguridades' and table_name='usuarios' order by ordinal_position""")
#     for f in c.fetchall(): print(f)
#     c.execute("""select table_schema, table_name from information_schema.tables
#                  where table_name in ('auth_group','auth_permission','django_migrations','django_content_type')""")
#     print(c.fetchall())


from .usuarios import Grupo, Usuario, UsuarioGroups