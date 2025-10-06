"""
Módulo de inicialización de modelos de la aplicación Gem-AvatART.

Este módulo centraliza la importación y exportación de todos los modelos
de datos de la aplicación, facilitando su uso desde otras partes del código.
Actúa como punto de entrada único para acceder a los modelos de SQLAlchemy.

Modelos incluidos:
    - User: Gestión de usuarios y autenticación
    - Producer: Productores de contenido
    - Avatar: Avatares digitales creados
    - Reel: Videos/reels generados
    - Commission: Sistema de comisiones

Cada modelo incluye sus respectivos enums para estados y roles.
"""

# Importaciones de modelos principales y sus enums asociados

# Modelo de usuarios con roles y estados
from .user import User, UserRole, UserStatus

# Modelo de productores de contenido
from .producer import Producer

# Modelo de avatares digitales con estados
from .avatar import Avatar, AvatarStatus

# Modelo de reels/videos con estados de procesamiento
from .reel import Reel, ReelStatus

# Modelo de comisiones con estados de pago
from .commission import Commission, CommissionStatus

# Lista explícita de todos los símbolos exportados por este módulo
# Esto controla qué elementos están disponibles cuando se hace:
# from app.models import *
__all__ = [
    'User', 
    'UserRole', 
    'UserStatus',
    'Producer',
    'Avatar', 
    'AvatarStatus',
    'Reel', 
    'ReelStatus',
    'Commission', 
    'CommissionStatus'
]

# Nota: Al usar __all__, se mejora la legibilidad del código y se previene
# la importación accidental de símbolos internos o dependencias no deseadas