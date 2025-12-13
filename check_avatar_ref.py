"""Script para verificar avatar_ref específico"""
from app import create_app, db
from app.models.avatar import Avatar

app = create_app()
app.app_context().push()

avatar_ref = '6ada99be8eb54aa2b700d50b7eb7b755'
avatar = Avatar.query.filter_by(avatar_ref=avatar_ref).first()

if avatar:
    print(f"\n{'='*60}")
    print(f"AVATAR ENCONTRADO EN BASE DE DATOS")
    print(f"{'='*60}")
    print(f"Nombre: {avatar.name}")
    print(f"ID: {avatar.id}")
    print(f"Avatar Ref: {avatar.avatar_ref}")
    print(f"Status: {avatar.status.value}")
    print(f"Access Type: {avatar.access_type.value}")
    print(f"Producer ID: {avatar.producer_id}")
    print(f"{'='*60}\n")
    
    # Verificar si tiene preview
    print(f"Preview Video URL: {avatar.preview_video_url or 'No configurado'}")
    print(f"Thumbnail URL: {avatar.thumbnail_url or 'No configurado'}")
else:
    print(f"\n❌ Avatar con avatar_ref '{avatar_ref}' NO encontrado en la base de datos")

# Listar algunos avatares públicos disponibles
print(f"\n{'='*60}")
print(f"AVATARES PÚBLICOS DISPONIBLES (primeros 5)")
print(f"{'='*60}")
public_avatars = Avatar.query.filter_by(access_type='PUBLIC').limit(5).all()
for av in public_avatars:
    print(f"- {av.name} (ID: {av.id}, Ref: {av.avatar_ref})")
print(f"{'='*60}\n")
