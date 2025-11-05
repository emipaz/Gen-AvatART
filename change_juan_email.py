"""
Script para cambiar el email de Juan Martínez (productor) en la base de datos.
"""

import sqlite3

conn = sqlite3.connect(r'instance\gem_avatart.db')
cursor = conn.cursor()

# Cambiar el email de Juan Martínez (productor)
OLD_EMAIL = "juan.video@email.com"
NEW_EMAIL = "andreaberardimdp@gmail.com"

# Buscar el usuario
cursor.execute("""
    SELECT id, first_name, last_name, role
    FROM users
    WHERE email = ?
""", (OLD_EMAIL,))

user = cursor.fetchone()

if user:
    user_id, first_name, last_name, role = user
    
    print(f"✅ Usuario encontrado:")
    print(f"   ID: {user_id}")
    print(f"   Nombre: {first_name} {last_name}")
    print(f"   Rol: {role}")
    print(f"   Email actual: {OLD_EMAIL}")
    print()
    print(f"🔄 Cambiando email a: {NEW_EMAIL}")
    
    # Actualizar el email
    cursor.execute("""
        UPDATE users
        SET email = ?
        WHERE id = ?
    """, (NEW_EMAIL, user_id))
    
    conn.commit()
    
    # Verificar el cambio
    cursor.execute("SELECT email FROM users WHERE id = ?", (user_id,))
    result = cursor.fetchone()
    
    if result and result[0] == NEW_EMAIL:
        print(f"✅ Email actualizado correctamente!")
        print(f"   {first_name} {last_name} ahora tiene email: {NEW_EMAIL}")
        
        # Contar avatares del productor
        cursor.execute("""
            SELECT COUNT(*), 
                   SUM(CASE WHEN access_type = 'PREMIUM' THEN 1 ELSE 0 END) as premium_count
            FROM avatars
            WHERE created_by_id = ?
        """, (user_id,))
        
        total_avatars, premium_count = cursor.fetchone()
        print()
        print(f"📊 Este productor tiene:")
        print(f"   Total de avatares: {total_avatars}")
        print(f"   Avatares premium: {premium_count}")
        print()
        print(f"💡 Ahora cuando solicites permiso para sus avatares premium,")
        print(f"   el email llegará a: {NEW_EMAIL}")
    else:
        print("❌ Error al verificar el cambio")
else:
    print(f"❌ No se encontró usuario con email: {OLD_EMAIL}")
    print()
    print("📋 Usuarios productores disponibles:")
    cursor.execute("""
        SELECT id, email, first_name, last_name, role
        FROM users
        WHERE role IN ('producer', 'admin')
    """)
    for uid, email, fname, lname, urole in cursor.fetchall():
        print(f"   [{uid}] {fname} {lname} ({urole}) - {email}")

conn.close()
