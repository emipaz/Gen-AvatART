import os
from decouple import config

class Config:
    """Configuración base de la aplicación"""
    SECRET_KEY = config('SECRET_KEY', default='dev-secret-key-change-in-production')
    SQLALCHEMY_DATABASE_URI = config(
        'DATABASE_URL', 
        default='sqlite:///gem_avatart.db'
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # HeyGen API Configuration
    HEYGEN_BASE_URL = config('HEYGEN_BASE_URL', default='https://api.heygen.com')
    
    # Mail Configuration
    MAIL_SERVER = config('MAIL_SERVER', default='smtp.gmail.com')
    MAIL_PORT = int(config('MAIL_PORT', default=587))
    MAIL_USE_TLS = config('MAIL_USE_TLS', default=True, cast=bool)
    MAIL_USERNAME = config('MAIL_USERNAME', default='')
    MAIL_PASSWORD = config('MAIL_PASSWORD', default='')
    
    # JWT Configuration
    JWT_SECRET_KEY = config('JWT_SECRET_KEY', default='jwt-secret-change-in-production')
    JWT_ACCESS_TOKEN_EXPIRES = int(config('JWT_ACCESS_TOKEN_EXPIRES', default=3600))  # 1 hora
    
    # Upload Configuration
    UPLOAD_FOLDER = config('UPLOAD_FOLDER', default='app/static/uploads')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    
    # Pagination
    ITEMS_PER_PAGE = int(config('ITEMS_PER_PAGE', default=10))
    
    # Commission rates
    PRODUCER_COMMISSION_RATE = float(config('PRODUCER_COMMISSION_RATE', default=0.15))  # 15%
    SUBPRODUCER_COMMISSION_RATE = float(config('SUBPRODUCER_COMMISSION_RATE', default=0.10))  # 10%
    AFFILIATE_COMMISSION_RATE = float(config('AFFILIATE_COMMISSION_RATE', default=0.05))  # 5%

class DevelopmentConfig(Config):
    """Configuración para desarrollo"""
    DEBUG = True
    SQLALCHEMY_ECHO = True

class ProductionConfig(Config):
    """Configuración para producción"""
    DEBUG = False
    SQLALCHEMY_ECHO = False

class TestingConfig(Config):
    """Configuración para testing"""
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    WTF_CSRF_ENABLED = False

# Configuraciones disponibles
config_dict = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'testing': TestingConfig,
    'default': DevelopmentConfig
}