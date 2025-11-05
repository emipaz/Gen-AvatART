"""

Script para migrar datos de la tabla avatars de gem_avatar.db a gem_avatar_emi.db,   

"""


import sqlite3

SRC_DB = "instance/gem_avatar.db"
DST_DB = "instance/gem_avatar_emi.db"

# Conexiones
src_conn = sqlite3.connect(SRC_DB)
dst_conn = sqlite3.connect(DST_DB)
src_cur = src_conn.cursor()
dst_cur = dst_conn.cursor()

# Obtén columnas de destino (incluyendo access_type)
dst_cur.execute("PRAGMA table_info(avatars);")
columns = [row[1] for row in dst_cur.fetchall()]
columns_str = ", ".join(columns)

# Obtén columnas de origen (puede que no tenga access_type)
src_cur.execute("PRAGMA table_info(avatars);")
src_columns = [row[1] for row in src_cur.fetchall()]
src_columns_str = ", ".join([col for col in src_columns if col != "access_type"])

# Lee los datos de origen
src_cur.execute(f"SELECT {src_columns_str} FROM avatars;")
rows = src_cur.fetchall()

# Prepara los datos para insertar en destino (agrega 'private' como access_type)
data_to_insert = []
for row in rows:
    row = list(row)
    # Inserta 'private' en la posición correcta para access_type
    insert_row = []
    src_idx = 0
    for col in columns:
        if col == "access_type":
            insert_row.append("private")
        else:
            insert_row.append(row[src_idx])
            src_idx += 1
    data_to_insert.append(tuple(insert_row))

# Inserta en la base de destino
placeholders = ", ".join(["?"] * len(columns))
dst_cur.executemany(f"INSERT INTO avatars ({columns_str}) VALUES ({placeholders})", data_to_insert)
dst_conn.commit()

src_conn.close()
dst_conn.close()

print("¡Datos migrados! access_type='private' en todos los registros de avatars.")