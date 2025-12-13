from app import create_app, db
from app.models.reel import Reel

app = create_app()

with app.app_context():
    # Obtener el último reel creado
    ultimo_reel = Reel.query.order_by(Reel.created_at.desc()).first()
    
    if ultimo_reel:
        print(f"\n{'='*60}")
        print(f"ÚLTIMO REEL CREADO")
        print(f"{'='*60}")
        print(f"ID: {ultimo_reel.id}")
        print(f"Título: {ultimo_reel.title}")
        print(f"Estado: {ultimo_reel.status.name}")
        print(f"HeyGen Job ID: {ultimo_reel.heygen_job_id or 'No asignado'}")
        print(f"HeyGen Video ID: {ultimo_reel.heygen_video_id or 'No asignado'}")
        print(f"Video URL: {ultimo_reel.video_url or 'Aún no generado'}")
        print(f"Error: {ultimo_reel.error_message or 'Sin errores'}")
        print(f"Creado: {ultimo_reel.created_at}")
        print(f"{'='*60}\n")
    else:
        print("No hay reels en la base de datos")
