"""
script para encontrar usuarios con emails reales en la base de datos.
"""

import sqlite3

conn = sqlite3.connect(r'instance\gem_avatart.db')
cursor = conn.cursor()

# Email real que puedes verificar
REAL_EMAIL = "continuidadped5y6ep62@gmail.com"

# Buscar usuarios con ese email o similares
cursor.execute("""
    SELECT id, email, first_name, last_name, role
    FROM users
    WHERE email LIKE '%continuidadped5y6ep62%' OR email LIKE '%gmail.com%'
""")

print("👤 Usuarios con emails reales:\n")
users = cursor.fetchall()
for user_id, email, first_name, last_name, role in users:
    print(f"[{user_id}] {first_name} {last_name} - {role}")
    print(f"    Email: {email}")
    
    # Buscar avatares creados por este usuario
    cursor.execute("""
        SELECT id, name, access_type, status
        FROM avatars
        WHERE created_by_id = ?
        ORDER BY access_type
    """, (user_id,))
    
    avatars = cursor.fetchall()
    if avatars:
        print(f"    Avatares ({len(avatars)}):")
        for av_id, av_name, av_type, av_status in avatars:
            emoji = "🌍" if av_type == "PUBLIC" else "💎" if av_type == "PREMIUM" else "🔒"
            print(f"      {emoji} [{av_id}] {av_name} - {av_type} ({av_status})")
    else:
        print(f"    ⚠️ No tiene avatares creados")
    print()

print("="*70)
print("\n💡 Sugerencias:")
print("   1. Actualiza el email de un productor existente al tuyo con: python update_producer_email.py")
print("   2. O crea nuevos avatares premium con el usuario que tiene email real")
print("   3. O usa el panel de admin para cambiar el email desde la web")

conn.close()
