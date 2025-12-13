from app import create_app, db
from app.models.avatar import Avatar

app = create_app()

with app.app_context():
    avatares = Avatar.query.all()
    print(f"\n{'='*60}")
    print(f"Total de avatares en la base de datos: {len(avatares)}")
    print(f"{'='*60}\n")
    
    for avatar in avatares:
        avatar_ref = avatar.avatar_ref or "❌ NO CONFIGURADO"
        print(f"ID: {avatar.id:3d} | {avatar.name:30s} | Avatar Ref: {avatar_ref}")
    
    print(f"\n{'='*60}")
    sin_heygen = [a for a in avatares if not a.avatar_ref]
    print(f"Avatares SIN avatar_ref: {len(sin_heygen)}")
    print(f"{'='*60}\n")
