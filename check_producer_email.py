import sqlite3

conn = sqlite3.connect(r'instance\gem_avatart.db')
cursor = conn.cursor()

# Buscar el avatar que se solicitó (Avatar 9766bb8a78a847969301aaff6de86e6f)
cursor.execute("""
    SELECT id, name, created_by_id, producer_id
    FROM avatars
    WHERE name LIKE '%9766bb8a78a847969301aaff6de86e6f%'
""")
avatar = cursor.fetchone()

if avatar:
    avatar_id, avatar_name, created_by_id, producer_id = avatar
    print(f"🎭 Avatar encontrado:")
    print(f"   ID: {avatar_id}")
    print(f"   Nombre: {avatar_name}")
    print(f"   Creado por (user_id): {created_by_id}")
    print(f"   Producer ID: {producer_id}")
    print()
    
    # Buscar el usuario creador
    cursor.execute("""
        SELECT id, email, first_name, last_name, role
        FROM users
        WHERE id = ?
    """, (created_by_id,))
    creator = cursor.fetchone()
    
    if creator:
        user_id, email, first_name, last_name, role = creator
        print(f"👤 Usuario Creador:")
        print(f"   ID: {user_id}")
        print(f"   Nombre: {first_name} {last_name}")
        print(f"   Email: {email}")
        print(f"   Rol: {role}")
    else:
        print(f"❌ No se encontró el usuario con ID {created_by_id}")
    
    print()
    print("="*60)
    
    # Buscar todos los avatares PREMIUM
    cursor.execute("""
        SELECT id, name, created_by_id, access_type
        FROM avatars
        WHERE access_type = 'PREMIUM'
    """)
    premium_avatars = cursor.fetchall()
    
    print(f"\n📋 Lista de avatares PREMIUM ({len(premium_avatars)} encontrados):")
    for av in premium_avatars:
        av_id, av_name, av_creator_id, av_type = av
        
        # Buscar creador
        cursor.execute("""
            SELECT email, first_name, last_name
            FROM users
            WHERE id = ?
        """, (av_creator_id,))
        av_creator = cursor.fetchone()
        
        creator_info = f"{av_creator[1]} {av_creator[2]} ({av_creator[0]})" if av_creator else "Desconocido"
        
        print(f"   [{av_id}] {av_name}")
        print(f"       Creador: {creator_info}")
        print()

else:
    print("❌ Avatar no encontrado")

conn.close()
