from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from flask_jwt_extended import JWTManager
from config import config_dict

# Inicializar extensiones
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()
mail = Mail()
jwt = JWTManager()

def create_app(config_name='default'):
    """Factory para crear la aplicación Flask"""
    app = Flask(__name__)
    
    # Cargar configuración
    app.config.from_object(config_dict[config_name])
    
    # Inicializar extensiones con la app
    db.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db)
    mail.init_app(app)
    jwt.init_app(app)
    
    # Configurar Flask-Login
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Por favor inicia sesión para acceder a esta página.'
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        from app.models.user import User
        return User.query.get(int(user_id))
    
    # Registrar blueprints
    from app.routes.auth import auth_bp
    from app.routes.admin import admin_bp
    from app.routes.producer import producer_bp
    from app.routes.subproducer import subproducer_bp
    from app.routes.affiliate import affiliate_bp
    from app.routes.main import main_bp
    from app.routes.api import api_bp
    
    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(admin_bp, url_prefix='/admin')
    app.register_blueprint(producer_bp, url_prefix='/producer')
    app.register_blueprint(subproducer_bp, url_prefix='/subproducer')
    app.register_blueprint(affiliate_bp, url_prefix='/affiliate')
    app.register_blueprint(api_bp, url_prefix='/api')
    
    # Handlers de errores
    @app.errorhandler(404)
    def not_found_error(error):
        from flask import render_template
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(500)
    def internal_error(error):
        from flask import render_template
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    # Context processors
    @app.context_processor
    def inject_user_role():
        from flask_login import current_user
        return dict(current_user=current_user)
    
    return app