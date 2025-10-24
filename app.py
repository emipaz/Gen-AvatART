"""
Punto de entrada principal para la aplicación Gen-AvatART.

Este módulo es responsable de inicializar y ejecutar la aplicación Flask
que gestiona la plataforma de creación y distribución de avatares digitales
con integración a HeyGen API.

El módulo incluye:
    - Configuración de la aplicación Flask usando factory pattern
    - Inicialización automática de la base de datos
    - Configuración de migración de base de datos para despliegue
    - Punto de entrada para ejecutar la aplicación en modo desarrollo

Funcionalidades principales:
    - Carga automática de configuración desde variables de entorno
    - Creación de tablas de base de datos si no existen
    - Configuración para desarrollo con debug habilitado
    - Soporte para despliegue con migraciones automáticas
    - Servidor accesible desde cualquier IP (0.0.0.0) en puerto 5000
"""

import os
from app import create_app
from flask_migrate import upgrade

def deploy():
    """
    Ejecuta tareas de despliegue de la aplicación.
    
    Esta función es utilizada en entornos de producción para realizar
    las migraciones de base de datos necesarias antes de iniciar la aplicación.
    
    Note:
        - Ejecuta automáticamente las migraciones pendientes
        - Debe ser llamada antes del primer despliegue
        - Utiliza Flask-Migrate para gestionar cambios de esquema
    """
    # Crear/actualizar tablas de base de datos con migraciones
    upgrade()

if __name__ == '__main__':
    """
    Punto de entrada principal cuando se ejecuta directamente el script.
    
    Inicializa la aplicación Flask con la configuración apropiada y
    ejecuta el servidor de desarrollo con las opciones necesarias
    para el entorno local.
    
    Configuración aplicada:
        - Carga configuración desde FLASK_CONFIG o usa 'default'
        - Crea todas las tablas de modelos si no existen
        - Ejecuta en modo debug para desarrollo
        - Servidor accesible desde cualquier IP (0.0.0.0)
        - Puerto 5000 por defecto
    
    Models incluidos en la inicialización:
        - User             : Gestión de usuarios del sistema
        - Producer         : Productores y subproductores
        - Avatar           : Avatares/clones digitales
        - Reel             : Videos generados con avatares
        - Commission       : Sistema de comisiones
        - clone_permission : Permisos asociados a clones digitales
    """
    # Crear instancia de la aplicación Flask con configuración
    app = create_app(os.getenv('FLASK_CONFIG') or 'default')
    
    # Configurar logging mejorado para debug
    import logging
    logging.basicConfig(level=logging.DEBUG)
    app.logger.setLevel(logging.DEBUG)
    
    # Crear tablas de base de datos si no existen
    with app.app_context():
        # Importar todos los modelos para registro en SQLAlchemy
        from app.models import User, Producer, Avatar, Reel, Commission, clone_permission
        from app import db
        
        # Crear todas las tablas definidas en los modelos
        db.create_all()
    
    # Ejecutar servidor de desarrollo
    app.run(
        debug=True,        # Modo debug para desarrollo con recarga automática
        host='0.0.0.0',    # Accesible desde cualquier IP de la red local
        port=5000          # Puerto estándar para desarrollo Flask
    )