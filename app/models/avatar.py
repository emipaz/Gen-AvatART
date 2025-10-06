from app import db
from datetime import datetime
from enum import Enum

class AvatarStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROCESSING = "processing"

class Avatar(db.Model):
    """Modelo para avatars creados con HeyGen"""
    __tablename__ = 'avatars'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relaciones
    producer_id = db.Column(db.Integer, db.ForeignKey('producers.id'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Información del avatar
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    avatar_type = db.Column(db.String(50))  # male, female, custom
    language = db.Column(db.String(10), default='es')  # Idioma principal
    
    # HeyGen data
    heygen_avatar_id = db.Column(db.String(100), unique=True)
    heygen_avatar_url = db.Column(db.String(500))
    preview_video_url = db.Column(db.String(500))
    thumbnail_url = db.Column(db.String(500))
    
    # Estado y configuración
    status = db.Column(db.Enum(AvatarStatus), nullable=False, default=AvatarStatus.PENDING)
    is_public = db.Column(db.Boolean, default=False)  # Si otros usuarios pueden usarlo
    is_premium = db.Column(db.Boolean, default=False)  # Si requiere plan premium
    
    # Configuración de uso
    max_daily_usage = db.Column(db.Integer, default=10)
    usage_count = db.Column(db.Integer, default=0)
    price_per_use = db.Column(db.Float, default=0.0)  # Precio por uso si es premium
    
    # Metadatos
    metadata = db.Column(db.JSON)  # Información adicional del avatar
    tags = db.Column(db.String(500))  # Tags separados por comas
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_at = db.Column(db.DateTime)
    last_used = db.Column(db.DateTime)
    
    # Relaciones
    created_by = db.relationship('User', foreign_keys=[created_by_id], backref='created_avatars')
    approved_by = db.relationship('User', foreign_keys=[approved_by_id], backref='approved_avatars')
    reels = db.relationship('Reel', backref='avatar', lazy='dynamic')
    
    def __repr__(self):
        return f'<Avatar {self.name}>'
    
    @property
    def creator_name(self):
        return self.created_by.full_name if self.created_by else 'Desconocido'
    
    @property
    def approver_name(self):
        return self.approved_by.full_name if self.approved_by else None
    
    @property
    def tag_list(self):
        """Devuelve las tags como lista"""
        return [tag.strip() for tag in (self.tags or '').split(',') if tag.strip()]
    
    def set_tags(self, tag_list):
        """Establece las tags desde una lista"""
        self.tags = ', '.join([tag.strip() for tag in tag_list if tag.strip()])
    
    def can_be_used_by(self, user):
        """Verifica si un usuario puede usar este avatar"""
        if self.status != AvatarStatus.APPROVED:
            return False
        
        # El creador siempre puede usar su avatar
        if self.created_by_id == user.id:
            return True
        
        # Si es público, cualquier usuario del mismo productor puede usarlo
        if self.is_public:
            user_producer = user.get_producer()
            return user_producer and user_producer.id == self.producer_id
        
        return False
    
    def increment_usage(self):
        """Incrementa el contador de uso"""
        self.usage_count += 1
        self.last_used = datetime.utcnow()
        db.session.commit()
    
    def approve(self, approved_by_user):
        """Aprueba el avatar"""
        self.status = AvatarStatus.APPROVED
        self.approved_by_id = approved_by_user.id
        self.approved_at = datetime.utcnow()
        db.session.commit()
    
    def reject(self):
        """Rechaza el avatar"""
        self.status = AvatarStatus.REJECTED
        db.session.commit()
    
    def reset_daily_usage(self):
        """Resetea el uso diario"""
        self.usage_count = 0
        db.session.commit()
    
    def to_dict(self):
        """Convertir a diccionario para JSON"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'avatar_type': self.avatar_type,
            'language': self.language,
            'status': self.status.value,
            'is_public': self.is_public,
            'is_premium': self.is_premium,
            'creator_name': self.creator_name,
            'approver_name': self.approver_name,
            'usage_count': self.usage_count,
            'max_daily_usage': self.max_daily_usage,
            'price_per_use': self.price_per_use,
            'tags': self.tag_list,
            'heygen_avatar_url': self.heygen_avatar_url,
            'preview_video_url': self.preview_video_url,
            'thumbnail_url': self.thumbnail_url,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'last_used': self.last_used.isoformat() if self.last_used else None
        }