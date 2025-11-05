"""
Script para listar todos los usuarios en la base de datos junto con sus avatares.
"""


import sqlite3

conn = sqlite3.connect(r'instance\gem_avatart.db')
cursor = conn.cursor()

print("👥 TODOS LOS USUARIOS EN LA BASE DE DATOS:\n")

cursor.execute("""
    SELECT id, email, first_name, last_name, role
    FROM users
    ORDER BY role, id
""")

users = cursor.fetchall()

for user_id, email, first_name, last_name, role in users:
    emoji = "👑" if role == "admin" else "🏭" if role == "producer" else "👤"
    print(f"{emoji} [{user_id}] {first_name} {last_name}")
    print(f"   Email: {email}")
    print(f"   Rol: {role}")
    
    # Contar avatares
    cursor.execute("""
        SELECT COUNT(*), 
               SUM(CASE WHEN access_type = 'PUBLIC' THEN 1 ELSE 0 END),
               SUM(CASE WHEN access_type = 'PREMIUM' THEN 1 ELSE 0 END),
               SUM(CASE WHEN access_type = 'PRIVATE' THEN 1 ELSE 0 END)
        FROM avatars
        WHERE created_by_id = ?
    """, (user_id,))
    
    result = cursor.fetchone()
    total, public, premium, private = result if result else (0, 0, 0, 0)
    
    if total and total > 0:
        print(f"   Avatares: {total} total (🌍 {public or 0} públicos, 💎 {premium or 0} premium, 🔒 {private or 0} privados)")
    
    print()

print("="*70)
print("\n💡 ¿Qué email quieres cambiar?")

conn.close()
