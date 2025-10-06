import os
from app import create_app
from flask_migrate import upgrade

def deploy():
    """Run deployment tasks."""
    # Create database tables
    upgrade()

if __name__ == '__main__':
    app = create_app(os.getenv('FLASK_CONFIG') or 'default')
    
    # Crear tablas de base de datos si no existen
    with app.app_context():
        from app.models import User, Producer, Avatar, Reel, Commission
        from app import db
        db.create_all()
    
    app.run(debug=True, host='0.0.0.0', port=5000)