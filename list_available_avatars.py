"""Script para listar avatares públicos disponibles con la API key actual"""
from app import create_app
from app.services.heygen_service import HeyGenService
from flask import current_app

app = create_app()
app.app_context().push()

# Obtener API key configurada
api_key = current_app.config.get('HEYGEN_OWNER_API_KEY')

if not api_key:
    print("❌ No hay API key configurada en HEYGEN_OWNER_API_KEY")
    exit(1)

print(f"\n{'='*70}")
print(f"AVATARES PÚBLICOS DISPONIBLES CON TU API KEY")
print(f"{'='*70}\n")

# Inicializar servicio
service = HeyGenService(api_key=api_key)

# Obtener avatares públicos disponibles
try:
    avatares = service.list_avatars()
    
    if avatares:
        print(f"✅ Encontrados {len(avatares)} avatares disponibles:\n")
        for i, av in enumerate(avatares[:10], 1):  # Mostrar primeros 10
            print(f"{i}. ID: {av.get('avatar_id')}")
            print(f"   Nombre: {av.get('avatar_name', 'Sin nombre')}")
            print(f"   Preview: {av.get('preview_video_url', 'No disponible')[:60]}...")
            print()
    else:
        print("❌ No se encontraron avatares disponibles")
        
except Exception as e:
    print(f"❌ Error obteniendo avatares: {str(e)}")

print(f"{'='*70}\n")
print("💡 Puedes importar estos avatares a tu base de datos para que")
print("   los usuarios puedan usarlos.")
print(f"{'='*70}\n")
