"""
Módulo de modelo User para la aplicación Gem-AvatART.

Este módulo define el modelo base de usuarios y maneja toda la funcionalidad
relacionada con autenticación, autorización y gestión de usuarios en el sistema.
Implementa el patrón de roles jerárquicos donde cada tipo de usuario tiene
diferentes permisos y capacidades.

El módulo incluye:
    - Enum UserRole   : Roles de usuario disponibles en el sistema (ACTUALIZADO según README)
    - Enum UserStatus : Estados posibles de una cuenta de usuario
    - Clase User      : Modelo principal que implementa UserMixin de Flask-Login

Jerarquía de roles (ACTUALIZADA según README):
    - ADMIN       : Acceso completo al sistema, gestión de todos los usuarios
    - PRODUCER    : Creador de avatares, gestión de equipos, acceso a HeyGen
    - SUBPRODUCER : Creación de avatares y reels, invitado por un producer
    - FINAL_USER  : ✅ CAMBIO - Solo creación de reels con clones permitidos (era AFFILIATE)

Funcionalidades principales:
    - Autenticación segura con password hashing
    - Sistema de invitaciones y supervisión
    - Control de permisos basado en roles
    - Gestión de estados de cuenta
    - Integración con Flask-Login
    - Relaciones con productores y comisiones
"""

from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from enum import Enum
import secrets

class UserRole(Enum):
    """
    Enumeración que define los roles de usuario disponibles en el sistema.
    
    Roles disponibles (ACTUALIZADO según README):
        ADMIN      : Administrador con acceso completo al sistema
        PRODUCER   : Productor de contenido con API de HeyGen
        SUBPRODUCER : Sub-productor con capacidades limitadas
        FINAL_USER  : ✅ CAMBIO - Usuario final que usa clones permitidos (era AFFILIATE)
    """
    ADMIN       = "admin"       # Administrador del sistema
    PRODUCER    = "producer"    # Productor principal
    SUBPRODUCER = "subproducer" # Sub-productor
    FINAL_USER  = "final_user"  # ✅ CAMBIO - Usuario final (era AFFILIATE)
    AFFILIATE   = FINAL_USER    # Mantener para compatibilidad, pero usar FINAL_USER
class UserStatus(Enum):
    """
    Enumeración que define los estados posibles de una cuenta de usuario.
    
    Estados disponibles:
        PENDING   : Cuenta creada, pendiente de verificación
        ACTIVE    : Cuenta activa y operativa
        SUSPENDED : Cuenta suspendida temporalmente
        REJECTED  : Cuenta rechazada permanentemente
    """
    PENDING   = "pending"   # Pendiente de verificación
    ACTIVE    = "active"    # Cuenta activa
    SUSPENDED = "suspended" # Suspendida temporalmente
    REJECTED  = "rejected"  # Rechazada permanentemente

class User(UserMixin, db.Model):
    """
    Modelo base para todos los usuarios del sistema.
    
    Esta clase implementa UserMixin de Flask-Login para proporcionar
    funcionalidad de autenticación y manejo de sesiones. Maneja todos
    los tipos de usuarios mediante un sistema de roles.
    
    Attributes:
        id (int)              : Identificador único del usuario
        email (str)           : Dirección de correo electrónico (único)
        username (str)        : Nombre de usuario (único)
        password_hash (str)   : Hash seguro de la contraseña
        first_name (str)      : Nombre del usuario
        last_name (str)       : Apellido del usuario
        phone (str)           : Número de teléfono
        avatar_url (str)      : URL de la imagen de perfil
        role (UserRole)       : Rol del usuario en el sistema
        status (UserStatus)   : Estado actual de la cuenta
        is_verified (bool)    : Si el email ha sido verificado
        country (str)         : País del usuario
        city (str)            : Ciudad del usuario
        professional_info (str): Información profesional adicional
        
        email_verified (bool)                 : Si el email ha sido verificado
        email_verification_token (str)        : Token para verificación de email
        email_verification_sent_at (datetime) : Fecha de envío del token
        
        created_at (datetime) : Fecha de registro
        updated_at (datetime) : Fecha de última actualización
        last_login (datetime) : Fecha del último inicio de sesión
        invited_by_id (int)   : ID del usuario que invitó a este usuario
    """
    __tablename__ = 'users'
    
    # Clave primaria
    id            = db.Column(db.Integer, primary_key = True)
    is_owner      = db.Column(db.Boolean, default=False)  # Solo uno puede ser True
    is_admin      = db.Column(db.Boolean, default=False)  # Puede haber varios
    email         = db.Column(db.String(120), unique = True, nullable = False, index = True)
    username      = db.Column(db.String(80),  unique = True, nullable = False, index = True)
    password_hash = db.Column(db.String(128), nullable = False)
    
    # Credenciales de acceso (únicos e indexados para consultas rápidas)
    first_name = db.Column(db.String(50), nullable = False)
    last_name  = db.Column(db.String(50), nullable = False)
    phone      = db.Column(db.String(20))
    avatar_url = db.Column(db.String(200))
    
    # Información personal del usuario
    role        = db.Column(db.Enum(UserRole),   nullable = False, default = UserRole.FINAL_USER)
    status      = db.Column(db.Enum(UserStatus), nullable = False, default = UserStatus.PENDING)
    is_verified = db.Column(db.Boolean, default = False)

    # Información adicional del perfil
    country           = db.Column(db.String(100))
    city              = db.Column(db.String(100))
    professional_info = db.Column(db.Text)

    # Verificación de email
    email_verified             = db.Column(db.Boolean, default=False)
    email_verification_token   = db.Column(db.String(100), unique=True, nullable=True)
    email_verification_sent_at = db.Column(db.DateTime, nullable=True)

    # Información adicional del perfil
    country           = db.Column(db.String(100))
    city              = db.Column(db.String(100))
    professional_info = db.Column(db.Text)

    # Verificación de email
    email_verified             = db.Column(db.Boolean, default=False)
    email_verification_token   = db.Column(db.String(100), unique=True, nullable=True)
    email_verification_sent_at = db.Column(db.DateTime, nullable=True)
      
    
    # Campos de auditoría y timestamps
    created_at = db.Column(db.DateTime, default = datetime.utcnow)
    updated_at = db.Column(db.DateTime, default = datetime.utcnow, onupdate = datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Sistema de invitaciones y jerarquía
    # Relación con el usuario que lo invitó (si aplica)
    invited_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable = True)
    invited_by    = db.relationship('User', remote_side = [id], backref = 'invited_users')
    
    # Relación uno-a-uno con Producer (solo si el rol es PRODUCER)
    producer_profile = db.relationship('Producer', backref = 'user', uselist = False, cascade = 'all, delete-orphan')
    
    # Relación con reels creados por este usuario
    reels = db.relationship('Reel', foreign_keys = 'Reel.creator_id', backref = 'creator_user', lazy = 'dynamic')

    # Relación con comisiones ganadas por el usuario
    commissions_earned = db.relationship('Commission', backref = 'user', lazy='dynamic')
    
    def generate_verification_token(self):
        """
        Genera un token único para la verificación del correo electrónico.
        
        Crea un token seguro utilizando secrets.token_urlsafe() y lo
        almacena junto con la fecha de generación para implementar
        expiración y tracking de envíos.
        
        Returns:
            str: Token único generado para verificación
            
        Note:
            - El token se guarda automáticamente en la BD con commit()
            - Se actualiza email_verification_sent_at para tracking
            - Token tiene 32 bytes de entropía (URL-safe base64)
        """
        import secrets
        self.email_verification_token   = secrets.token_urlsafe(32)
        self.email_verification_sent_at = datetime.utcnow()
        db.session.add(self)
        db.session.commit()
        return self.email_verification_token
     
    def __repr__(self):
        """
        Representación en string del objeto User.
        
        Returns:
            str: Representación legible del usuario con su username
        """
        return f'<User {self.username}>'
    
    @property
    def full_name(self):
        """
        Obtiene el nombre completo del usuario.
        
        Returns:
            str: Nombre y apellido concatenados
        """
        return f"{self.first_name} {self.last_name}"
    
    def set_password(self, password):
        """
        Establece una nueva contraseña para el usuario.
        
        Utiliza werkzeug para generar un hash seguro de la contraseña
        que se almacena en la base de datos. Nunca se almacena la
        contraseña en texto plano.
        
        Args:
            password (str): Contraseña en texto plano a hashear
        
        Note:
            No realiza commit automático, debe hacerse manualmente
        """
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """
        Verifica si una contraseña coincide con la almacenada.
        
        Compara el hash almacenado con el hash de la contraseña
        proporcionada para verificar la autenticidad.
        
        Args:
            password (str): Contraseña en texto plano a verificar
        
        Returns:
            bool: True si la contraseña es correcta, False en caso contrario
        """
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        """
        Verifica si el usuario tiene rol de administrador.
        
        Returns:
            bool: True si es administrador, False en caso contrario
        """
        return self.role == UserRole.ADMIN
    
    def is_producer(self):
        """
        Verifica si el usuario tiene rol de productor.
        
        Returns:
            bool: True si es productor, False en caso contrario
        """
        return self.role == UserRole.PRODUCER
    
    def is_subproducer(self):
        """
        Verifica si el usuario tiene rol de subproductor.
        
        Returns:
            bool: True si es subproductor, False en caso contrario
        """
        return self.role == UserRole.SUBPRODUCER
    
    def is_final_user(self):
        """
        Verifica si el usuario tiene rol de usuario final.
        
        Returns:
            bool: True si es usuario final, False en caso contrario
        
        Note:
            ✅ NUEVO - Reemplaza is_affiliate() según README
        """
        return self.role == UserRole.FINAL_USER
    
    # alias temporal para compatibilidad
    is_affiliate = is_final_user
    
    def can_create_avatars(self):
        """
        Determina si el usuario tiene permisos para crear avatares.
        
        Solo los productores y subproductores pueden crear avatares
        digitales usando la integración con HeyGen.
        
        Returns:
            bool: True si puede crear avatares, False en caso contrario
        """
        return self.role in [UserRole.PRODUCER, UserRole.SUBPRODUCER]
    
    def can_create_reels(self):
        """
        Determina si el usuario tiene permisos para crear reels.
        
        Todos los roles excepto admin pueden crear reels/videos.
        Los reels son el producto principal de la plataforma.
        
        Returns:
            bool: True si puede crear reels, False en caso contrario
        """
        return self.role in [UserRole.PRODUCER, 
                             UserRole.SUBPRODUCER, 
                             UserRole.FINAL_USER] 
        
    def can_invite_users(self):
        """
        Determina si el usuario puede invitar a otros usuarios.
        
        Solo los productores pueden invitar subproductores y afiliados
        para formar su equipo de trabajo.
        
        Returns:
            bool: True si puede invitar usuarios, False en caso contrario
        """
        return self.role == UserRole.PRODUCER
    
    def can_manage_system(self):
        """
        Determina si el usuario tiene permisos de gestión del sistema.
        
        Solo los administradores pueden gestionar el sistema completo,
        aprobar usuarios, configurar parámetros, etc.
        
        Returns:
            bool: True si puede gestionar el sistema, False en caso contrario
        """
        return self.role == UserRole.ADMIN
    
    def get_supervisor(self):
        """
        Obtiene el supervisor del usuario (quien lo invitó).
        
        En la jerarquía del sistema, el supervisor es el productor
        que invitó a este usuario al sistema.
        
        Returns:
            User or None: Usuario supervisor si existe y es productor, None en caso contrario
        """
        if self.invited_by and self.invited_by.is_producer():
            return self.invited_by
        return None
    
    def get_producer(self):
        """
        Obtiene el productor asociado al usuario.
        
        Si el usuario es productor, retorna su propio perfil.
        Si es subproductor o afiliado, retorna el perfil del productor que lo invitó.
        
        Returns:
            Producer or None: Instancia de Producer asociada o None si no existe
        """
        if self.is_producer():
            return self.producer_profile
        elif self.invited_by and self.invited_by.is_producer():
            return self.invited_by.producer_profile
        return None
    
    def activate(self):
        """
        Activa la cuenta del usuario.
        
        Cambia el estado a ACTIVE permitiendo el acceso completo
        a las funcionalidades del sistema.
        
        Note:
            Realiza commit automático a la base de datos
        """
        self.status = UserStatus.ACTIVE
        db.session.commit()
    
    def suspend(self):
        """
        Suspende temporalmente la cuenta del usuario.
        
        Cambia el estado a SUSPENDED impidiendo el acceso al sistema
        pero manteniendo los datos para una posible reactivación.
        
        Note:
            Realiza commit automático a la base de datos
        """
        self.status = UserStatus.SUSPENDED
        db.session.commit()
    
    def reject(self):
        """
        Rechaza permanentemente la cuenta del usuario.
        
        Cambia el estado a REJECTED impidiendo definitivamente
        el acceso al sistema.
        
        Note:
            Realiza commit automático a la base de datos
        """
        self.status = UserStatus.REJECTED
        db.session.commit()
    
    def update_last_login(self):
        """
        Actualiza la fecha del último inicio de sesión.
        
        Este método debe llamarse cada vez que el usuario
        inicia sesión exitosamente en el sistema.
        
        Note:
            Realiza commit automático a la base de datos
        """
        self.last_login = datetime.utcnow()
        db.session.commit()
    
    def get_total_earnings(self):
        """
        Calcula el total de ganancias del usuario.
        
        Suma todas las comisiones pagadas al usuario para obtener
        sus ganancias totales acumuladas.
        
        Returns:
            float: Total de ganancias en la moneda del sistema
        """
        from app.models.commission import CommissionStatus
        paid_commissions = self.commissions_earned.filter_by(status=CommissionStatus.PAID)
        return sum([commission.amount for commission in paid_commissions])
      
    def to_dict(self):
        """
        Convierte el objeto User a un diccionario para serialización JSON.
        
        Incluye la información básica del usuario sin datos sensibles
        como el hash de la contraseña.
        
        Returns:
            dict: Diccionario con los campos públicos del usuario
        
        Note:
            Las fechas se convierten a formato ISO para compatibilidad JSON
        """
        return {
            'id'         : self.id,
            'email'      : self.email,
            'username'   : self.username,
            'full_name'  : self.full_name,
            'first_name' : self.first_name,
            'last_name'  : self.last_name,
            'phone'      : self.phone,
            'avatar_url' : self.avatar_url,
            'role'       : self.role.value,
            'status'     : self.status.value,
            'is_verified': self.is_verified,
            'created_at' : self.created_at.isoformat() if self.created_at else None,
            'last_login' : self.last_login.isoformat() if self.last_login else None
        }
        