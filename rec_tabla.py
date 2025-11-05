"""
Script para recrear la tabla avatars sin la columna access_type,
manteniendo los datos existentes.
"""


import sqlite3

DB_PATH = "instance/gem_avatart_emi_2.db"  # Cambia si tu base tiene otro nombre

# 1. Conectar y hacer backup de los datos (sin access_type)
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# Obtén los nombres de las columnas excepto access_type
cur.execute("PRAGMA table_info(avatars);")
columns = [row[1] for row in cur.fetchall() if row[1] != "access_type"]
columns_str = ", ".join(columns)

# Backup de los datos
cur.execute(f"SELECT {columns_str} FROM avatars;")
data = cur.fetchall()

# 2. Renombra la tabla original
cur.execute("ALTER TABLE avatars RENAME TO avatars_old;")

# 3. Crea la nueva tabla avatars (sin access_type)
cur.execute("""
CREATE TABLE avatars (
    id INTEGER PRIMARY KEY,
    producer_id INTEGER NOT NULL,
    created_by_id INTEGER NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    avatar_type VARCHAR(50),
    language VARCHAR(10) DEFAULT 'es',
    avatar_ref VARCHAR(100) NOT NULL,
    preview_video_url VARCHAR(500),
    thumbnail_url VARCHAR(500),
    status VARCHAR(20) NOT NULL,
    meta_data JSON,
    tags VARCHAR(500),
    created_at DATETIME,
    updated_at DATETIME,
    last_used DATETIME,
    enabled_by_admin BOOLEAN DEFAULT 0,
    enabled_by_producer BOOLEAN DEFAULT 0,
    enabled_by_subproducer BOOLEAN DEFAULT 0
);
""")

# 4. Restaura los datos
placeholders = ", ".join(["?"] * len(columns))
cur.executemany(f"INSERT INTO avatars ({columns_str}) VALUES ({placeholders})", data)

# 5. Borra la tabla vieja
cur.execute("DROP TABLE avatars_old;")

conn.commit()
conn.close()

print("¡Tabla avatars recreada sin access_type y datos restaurados!")