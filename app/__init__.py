"""
Módulo de inicialización de la aplicación Flask para Gen-AvatART.

Este módulo contiene la factory function para crear y configurar la aplicación Flask,
así como la inicialización de todas las extensiones necesarias para el funcionamiento
completo del sistema.

El módulo incluye:
    - Factory function create_app()    : Creación y configuración de la aplicación
    - Inicialización de extensiones    : SQLAlchemy, Login, Migrate, Mail, JWT
    - Configuración de Flask-Login     : Gestión de sesiones de usuario
    - Registro de blueprints           : Organización modular de rutas
    - Manejadores de errores           : 404, 403, 500 con templates personalizados
    - Context processors               : Variables globales para templates

Funcionalidades principales:
    - Patrón Application Factory para múltiples configuraciones
    - Gestión completa de autenticación y autorización
    - Sistema de migraciones de base de datos
    - Envío de correos electrónicos
    - API REST con autenticación JWT
    - Manejo elegante de errores HTTP
    - Inyección automática de contexto en templates

Extensiones inicializadas:
    - SQLAlchemy    : ORM para manejo de base de datos
    - LoginManager  : Gestión de sesiones de usuario
    - Migrate       : Control de versiones de BD
    - Mail          : Servicio de correo electrónico
    - JWTManager    : Tokens para autenticación API
"""

from flask import Flask
from flask import render_template
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_mail import Mail
from flask_jwt_extended import JWTManager
from config import config_dict

# Inicializar extensiones
db            = SQLAlchemy()     # ORM para base de datos    
login_manager = LoginManager()   # Gestión de autenticación de usuarios
migrate       = Migrate()        # Migraciones de base de datos
mail          = Mail()           # Envío de correos electrónicos
jwt           = JWTManager()     # Gestión de tokens JWT

def create_app(config_name='default'):
    """
    Factory function para crear y configurar la aplicación Flask.
    
    Esta función implementa el patrón Application Factory, permitiendo
    crear múltiples instancias de la aplicación con diferentes configuraciones.
    Útil para testing, desarrollo y producción.
    
    Args:
        config_name (str, opcional): Nombre de la configuración a usar.
                                   Debe coincidir con una clave en config_dict.
                                   Opciones: 'development', 'production', 'testing', 'default'.
                                   Por defecto es 'default'.
    
    Returns:
        Flask: Instancia de la aplicación Flask completamente configurada
               con todas las extensiones, blueprints y handlers inicializados.
    
    Raises:
        KeyError: Si config_name no existe en config_dict.
    
    Note:
        - La aplicación se configura según el entorno especificado
        - Todas las extensiones se inicializan automáticamente
        - Los blueprints se registran con sus prefijos correspondientes
        - Los manejadores de error se configuran para una UX consistente
    """
    app = Flask(__name__)
    
    # Cargar configuración
    app.config.from_object(config_dict[config_name])
    
    # Inicializar extensiones con la app
    db.init_app(app)             # Configurar SQLAlchemy con la app
    login_manager.init_app(app)  # Configurar gestión de login
    migrate.init_app(app, db)    # Configurar migraciones con app y db
    mail.init_app(app)           # Configurar servicio de email
    jwt.init_app(app)            # Configurar JWT para API authentication
    
    # Configurar Flask-Login para la gestión de sesiones
    # Vista por defecto para login
    login_manager.login_view  = 'auth.login'
    # mensaje mostrado al intentar acceder a una vista protegida sin estar autenticado
    login_manager.login_message  = 'Por favor inicia sesión para acceder a esta página.'
    # Categoría Bootstrap para mensajes
    login_manager.login_message_category = 'info'
    
    @login_manager.user_loader
    def load_user(user_id):
        """
        Función callback para cargar un usuario desde la base de datos.
        
        Flask-Login usa esta función para recargar el objeto usuario
        desde el ID de usuario almacenado en la sesión.
        
        Args:
            user_id (str): ID del usuario a cargar desde la sesión.
        
        Returns:
            User: Objeto usuario si existe, None si no se encuentra.
        
        Note:
            Esta función debe devolver None (no lanzar excepción) si el
            user_id no es válido o el usuario no existe.
        """
        from app.models.user import User
        return User.query.get(int(user_id))
    
    # Registrar todos los blueprints de la aplicación
    # Importación tardía para evitar circular imports
    from app.routes.auth import auth_bp                # Rutas de autenticación
    from app.routes.admin import admin_bp              # Rutas de administración
    from app.routes.producer import producer_bp        # Rutas de productores
    from app.routes.subproducer import subproducer_bp  # Rutas de subproductores
    from app.routes.affiliate import affiliate_bp      # Rutas de afiliados
    from app.routes.main import main_bp                # Rutas principales
    from app.routes.api import api_bp                  # Rutas de API
    from app.routes.user import user_bp                # Rutas de gestión de usuarios
    
    # Registrar blueprints con sus prefijos de URL correspondientes
    app.register_blueprint(main_bp)  # Rutas sin prefijo (página principal)
    app.register_blueprint(auth_bp, url_prefix='/auth')               # /auth/*
    app.register_blueprint(admin_bp, url_prefix='/admin')             # /admin/*
    app.register_blueprint(producer_bp, url_prefix='/producer')       # /producer/*
    app.register_blueprint(subproducer_bp, url_prefix='/subproducer') # /subproducer/*
    app.register_blueprint(affiliate_bp, url_prefix='/affiliate')     # /affiliate/*
    app.register_blueprint(api_bp, url_prefix='/api')                 # /api/*
    app.register_blueprint(user_bp, url_prefix='/user')               # /user/*   
    
    # Handlers de errores
    @app.errorhandler(404)
    def not_found_error(error):
        """
        Manejador personalizado para errores 404 (Página no encontrada).
        
        Se ejecuta cuando el usuario accede a una URL que no existe
        en la aplicación, proporcionando una experiencia de usuario
        consistente con el diseño de la aplicación.
        
        Args:
            error: Objeto de error proporcionado por Flask.
        
        Returns:
            tuple: Tupla con (template_renderizado, código_estado_http)
        
        Note:
            - Renderiza template personalizado para mantener la UX
            - Retorna código HTTP 404 estándar
        """
        
        return render_template('errors/404.html'), 404
    
    @app.errorhandler(403)
    def forbidden_error(error):
        """
        Manejador personalizado para errores 403 (Acceso Prohibido).
        
        Se ejecuta cuando un usuario autenticado intenta acceder a un
        recurso para el cual no tiene permisos suficientes. Común en
        sistemas con roles y permisos granulares.
        
        Args:
            error: Objeto de error proporcionado por Flask.
        
        Returns:
            tuple: Tupla con (template_renderizado, código_estado_http)
        
        Note:
            - Importante para sistema de roles (admin, producer, etc.)
            - Proporciona feedback claro sobre restricciones de acceso
        """
        return render_template('errors/403.html'), 403

    @app.errorhandler(500)
    def internal_error(error):
        """
        Manejador personalizado para errores 500 (Error interno del servidor).
        
        Se ejecuta cuando ocurre una excepción no manejada en el servidor.
        Realiza rollback de la sesión de base de datos para evitar
        estados inconsistentes y proporciona una página de error elegante.
        
        Args:
            error: Objeto de error proporcionado por Flask.
        
        Returns:
            tuple: Tupla con (template_renderizado, código_estado_http)
        
        Note:
            - Realiza rollback automático de BD para evitar corrupción
            - Template de error no debe depender de BD
            - Útil para ocultar detalles técnicos en producción
        """
        db.session.rollback()
        return render_template('errors/500.html'), 500
    
    # Context processors
    @app.context_processor
    def inject_user_role():
        """
        Procesador de contexto para inyectar variables globales en templates.
        
        Hace que 'current_user' esté disponible en todos los templates
        sin necesidad de pasarlo explícitamente desde cada vista.
        Simplifica la lógica de plantillas y mejora la consistencia.
        
        Returns:
            dict: Diccionario con variables a inyectar en el contexto de templates.
                 Las claves se convierten en variables disponibles en Jinja2.
        
        Note:
            - Se ejecuta automáticamente en cada renderizado de template
            - Útil para información que se necesita en múltiples vistas
            - Evita repetir código en cada función de vista
        """
        from flask_login import current_user
        return dict(current_user=current_user)
    
    return app