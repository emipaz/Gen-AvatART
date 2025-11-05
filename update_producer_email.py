import sqlite3

conn = sqlite3.connect(r'instance\gem_avatart.db')
cursor = conn.cursor()

# Listar todos los usuarios productores
cursor.execute("""
    SELECT u.id, u.email, u.first_name, u.last_name, u.role
    FROM users u
    WHERE u.role IN ('producer', 'admin')
    ORDER BY u.role, u.id
""")

users = cursor.fetchall()

print("👥 Usuarios Productores/Admins actuales:\n")
for user_id, email, first_name, last_name, role in users:
    print(f"[{user_id}] {first_name} {last_name}")
    print(f"    Email actual: {email}")
    print(f"    Rol: {role}")
    print()

print("="*70)
print("\n🔧 Para cambiar el email de un usuario, ingresa:")
print("   - ID del usuario")
print("   - Nuevo email (o presiona Enter para cancelar)")
print()

user_id_input = input("ID del usuario a actualizar: ").strip()

if user_id_input:
    try:
        user_id = int(user_id_input)
        new_email = input("Nuevo email: ").strip()
        
        if new_email and '@' in new_email:
            cursor.execute("""
                UPDATE users 
                SET email = ? 
                WHERE id = ?
            """, (new_email, user_id))
            
            conn.commit()
            
            print(f"\n✅ Email actualizado correctamente!")
            print(f"   Usuario ID: {user_id}")
            print(f"   Nuevo email: {new_email}")
            
            # Verificar
            cursor.execute("SELECT first_name, last_name, email FROM users WHERE id = ?", (user_id,))
            result = cursor.fetchone()
            if result:
                print(f"   Nombre: {result[0]} {result[1]}")
        else:
            print("\n❌ Email inválido. Operación cancelada.")
    except ValueError:
        print("\n❌ ID inválido. Operación cancelada.")
else:
    print("\n⏹️ Operación cancelada.")

conn.close()
