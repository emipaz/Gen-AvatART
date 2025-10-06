from app import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from enum import Enum

class UserRole(Enum):
    ADMIN       = "admin"
    PRODUCER    = "producer"
    SUBPRODUCER = "subproducer"
    AFFILIATE   = "affiliate"

class UserStatus(Enum):
    PENDING   = "pending"
    ACTIVE    = "active"
    SUSPENDED = "suspended"
    REJECTED  = "rejected"

class User(UserMixin, db.Model):
    """Modelo base para todos los usuarios"""
    __tablename__ = 'users'
    
    id            = db.Column(db.Integer, primary_key=True)
    email         = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username      = db.Column(db.String(80), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128), nullable=False)
    
    # Información personal
    first_name = db.Column(db.String(50), nullable=False)
    last_name  = db.Column(db.String(50), nullable=False)
    phone      = db.Column(db.String(20))
    avatar_url = db.Column(db.String(200))
    
    # Información del sistema
    role        = db.Column(db.Enum(UserRole), nullable=False, default=UserRole.AFFILIATE)
    status      = db.Column(db.Enum(UserStatus), nullable=False, default=UserStatus.PENDING)
    is_verified = db.Column(db.Boolean, default=False)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relaciones
    invited_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    invited_by    = db.relationship('User', remote_side=[id], backref='invited_users')
    
    # Relación con Producer (si es producer)
    producer_profile = db.relationship('Producer', backref='user', uselist=False, cascade='all, delete-orphan')
    
    # Relación con reels creados
    reels = db.relationship('Reel', foreign_keys='Reel.creator_id', backref='creator', lazy='dynamic')
    
    # Relación con comisiones
    commissions_earned = db.relationship('Commission', backref='user', lazy='dynamic')
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}"
    
    def set_password(self, password):
        """Establecer password hasheado"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Verificar password"""
        return check_password_hash(self.password_hash, password)
    
    def is_admin(self):
        return self.role == UserRole.ADMIN
    
    def is_producer(self):
        return self.role == UserRole.PRODUCER
    
    def is_subproducer(self):
        return self.role == UserRole.SUBPRODUCER
    
    def is_affiliate(self):
        return self.role == UserRole.AFFILIATE
    
    def can_create_avatars(self):
        """Determina si el usuario puede crear avatars"""
        return self.role in [UserRole.PRODUCER, UserRole.SUBPRODUCER]
    
    def can_create_reels(self):
        """Determina si el usuario puede crear reels"""
        return self.role in [UserRole.PRODUCER, UserRole.SUBPRODUCER, UserRole.AFFILIATE]
    
    def get_supervisor(self):
        """Obtiene el supervisor del usuario (quien lo invitó)"""
        if self.invited_by and self.invited_by.is_producer():
            return self.invited_by
        return None
    
    def get_producer(self):
        """Obtiene el producer asociado al usuario"""
        if self.is_producer():
            return self.producer_profile
        elif self.invited_by and self.invited_by.is_producer():
            return self.invited_by.producer_profile
        return None
    
    def to_dict(self):
        """Convertir a diccionario para JSON"""
        return {
            'id'         : self.id,
            'email'      : self.email,
            'username'   : self.username,
            'full_name'  : self.full_name,
            'role'       : self.role.value,
            'status'     : self.status.value,
            'is_verified': self.is_verified,
            'created_at' : self.created_at.isoformat() if self.created_at else None,
            'last_login' : self.last_login.isoformat() if self.last_login else None
        }