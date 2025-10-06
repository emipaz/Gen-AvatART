"""
Módulo de modelo Avatar para la aplicación Gem-AvatART.

Este módulo define el modelo de datos para los avatares digitales creados
mediante la integración con HeyGen. Los avatares son personajes digitales
que pueden ser utilizados para generar videos y contenido multimedia.

El módulo incluye:
    - Enum AvatarStatus: Estados posibles de un avatar
    - Clase Avatar: Modelo principal con toda la funcionalidad

Funcionalidades principales:
    - Gestión de estados de aprobación de avatares
    - Control de uso y límites diarios
    - Integración con HeyGen API
    - Sistema de permisos y acceso público/privado
    - Metadata y configuración personalizable
"""

from app import db
from datetime import datetime
from enum import Enum

class AvatarStatus(Enum):
    """
    Enumeración que define los estados posibles de un avatar.
    
    Estados disponibles:
        PENDING    : Avatar recién creado, pendiente de aprobación
        APPROVED   : Avatar aprobado y listo para usar
        REJECTED   : Avatar rechazado por administrador
        PROCESSING : Avatar en proceso de creación en HeyGen
    """
    PENDING    = "pending"
    APPROVED   = "approved"
    REJECTED   = "rejected"
    PROCESSING = "processing"

class Avatar(db.Model):
    """
    Modelo de datos para avatares digitales creados con HeyGen.
    
    Este modelo gestiona toda la información relacionada con los avatares
    digitales, incluyendo su estado, configuración, permisos y metadatos.
    
    Attributes:
        id (int)                : Identificador único del avatar
        producer_id (int)       : ID del productor propietario
        created_by_id (int)     : ID del usuario que creó el avatar
        approved_by_id (int)    : ID del usuario que aprobó el avatar
        name (str)              : Nombre descriptivo del avatar
        description (str)       : Descripción detallada del avatar
        avatar_type (str)       : Tipo de avatar (male, female, custom)
        language (str)          : Idioma principal del avatar
        heygen_avatar_id (str)  : ID único en HeyGen
        heygen_avatar_url (str) : URL del avatar en HeyGen
        preview_video_url (str) : URL del video de preview
        thumbnail_url (str)     : URL de la imagen miniatura
        status (AvatarStatus)   : Estado actual del avatar
        is_public (bool)        : Si otros usuarios pueden usarlo
        is_premium (bool)       : Si requiere plan premium
        max_daily_usage (int)   : Límite de uso diario
        usage_count (int)       : Contador de uso actual
        price_per_use (float)   : Precio por uso si es premium
        meta_data (dict)        : Información adicional en formato JSON
        tags (str)              : Etiquetas separadas por comas
        created_at (datetime)   : Fecha de creación
        updated_at (datetime)   : Fecha de última actualización
        approved_at (datetime)  : Fecha de aprobación
        last_used (datetime)    : Fecha de último uso
    """
    __tablename__ = 'avatars'
    
    # Clave primaria
    id = db.Column(db.Integer, primary_key=True)
    
    # Relaciones con otras tablas
    producer_id    = db.Column(db.Integer, db.ForeignKey('producers.id'), nullable=False)
    created_by_id  = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Información básica del avatar
    name        = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    avatar_type = db.Column(db.String(50))  # male, female, custom
    language    = db.Column(db.String(10), default='es')  # Idioma principal
    
    # Datos de integración con HeyGen
    heygen_avatar_id  = db.Column(db.String(100), unique=True)
    heygen_avatar_url = db.Column(db.String(500))
    preview_video_url = db.Column(db.String(500))
    thumbnail_url     = db.Column(db.String(500))
    
    # Estado y configuración de acceso
    status     = db.Column(db.Enum(AvatarStatus), nullable=False, default=AvatarStatus.PENDING)
    is_public  = db.Column(db.Boolean, default=False)  # Si otros usuarios pueden usarlo
    is_premium = db.Column(db.Boolean, default=False)  # Si requiere plan premium
    
    # Configuración de límites y uso
    max_daily_usage = db.Column(db.Integer, default=10)
    usage_count     = db.Column(db.Integer, default=0)
    price_per_use   = db.Column(db.Float, default=0.0)  # Precio por uso si es premium
    
    # Metadatos y etiquetas
    # se usa meta_data por que metadata es palabra reservada en SQLAlchemy
    meta_data = db.Column(db.JSON)         # Información adicional del avatar
    tags      = db.Column(db.String(500))  # Tags separados por comas
    
    # Campos de auditoría y timestamps
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_at = db.Column(db.DateTime)
    last_used   = db.Column(db.DateTime)
    
    # Definición de relaciones con otros modelos
    created_by  = db.relationship('User', foreign_keys = [created_by_id] , backref = 'created_avatars')
    approved_by = db.relationship('User', foreign_keys = [approved_by_id], backref = 'approved_avatars')
    reels       = db.relationship('Reel', backref = 'avatar', lazy = 'dynamic')
    
    def __repr__(self):
        """
        Representación en string del objeto Avatar.
        
        Returns:
            str: Representación legible del avatar
        """
        return f'<Avatar {self.name}>'
    
    @property
    def creator_name(self):
        """
        Obtiene el nombre completo del creador del avatar.
        
        Returns:
            str: Nombre completo del usuario creador o 'Desconocido'
        """
        return self.created_by.full_name if self.created_by else 'Desconocido'
    
    @property
    def approver_name(self):
        """
        Obtiene el nombre completo del usuario que aprobó el avatar.
        
        Returns:
            str or None: Nombre completo del aprobador o None si no está aprobado
        """
        return self.approved_by.full_name if self.approved_by else None
    
    @property
    def tag_list(self):
        """
        Convierte el string de tags en una lista.
        
        Returns:
            list: Lista de etiquetas limpias (sin espacios extra)
        """
        return [ tag.strip() 
                 for tag in (self.tags or '').split(',') 
                    if tag.strip()
                ]
    
    def set_tags(self, tag_list):
        """
        Establece las etiquetas desde una lista.
        
        Args:
            tag_list (list): Lista de strings con las etiquetas
        """
        self.tags = ', '.join([
                                tag.strip() 
                                for tag in tag_list 
                                    if tag.strip()
                                ])

    def can_be_used_by(self, user):
        """
        Verifica si un usuario específico puede utilizar este avatar.
        
        Args:
            user (User): Usuario a verificar
        
        Returns:
            bool: True si el usuario puede usar el avatar, False en caso contrario
        
        Note:
            - El avatar debe estar aprobado
            - El creador siempre puede usar su avatar
            - Si es público, cualquier usuario del mismo productor puede usarlo
        """
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
        """
        Incrementa el contador de uso del avatar y actualiza la fecha de último uso.
        
        Note:
            Realiza commit automático a la base de datos
        """
        self.usage_count += 1
        self.last_used = datetime.utcnow()
        # from app import db
        db.session.commit()
    
    def approve(self, approved_by_user):
        """
        Aprueba el avatar para su uso.
        
        Args:
            approved_by_user (User): Usuario que aprueba el avatar
        
        Note:
            Cambia el estado a APPROVED y registra quién y cuándo lo aprobó
        """
        self.status = AvatarStatus.APPROVED
        self.approved_by_id = approved_by_user.id
        self.approved_at = datetime.utcnow()
        # from app import db
        db.session.commit()
    
    def reject(self):
        """
        Rechaza el avatar.
        
        Note:
            Cambia el estado a REJECTED. El avatar no podrá ser utilizado
        """
        self.status = AvatarStatus.REJECTED
        # from app import db
        db.session.commit()
    
    def reset_daily_usage(self):
        """
        Resetea el contador de uso diario del avatar.
        
        Note:
            Útil para tareas programadas que resetean límites diarios
        """
        self.usage_count = 0
        # from app import db
        db.session.commit()

    def to_dict(self):
        """
        Convierte el objeto Avatar a un diccionario para serialización JSON.
        
        Returns:
            dict: Diccionario con todos los campos importantes del avatar
        
        Note:
            Las fechas se convierten a formato ISO para JSON
        """
        return {
            'id'                : self.id,
            'name'              : self.name,
            'description'       : self.description,
            'avatar_type'       : self.avatar_type,
            'language'          : self.language,
            'status'            : self.status.value,
            'is_public'         : self.is_public,
            'is_premium'        : self.is_premium,
            'creator_name'      : self.creator_name,
            'approver_name'     : self.approver_name,
            'usage_count'       : self.usage_count,
            'max_daily_usage'   : self.max_daily_usage,
            'price_per_use'     : self.price_per_use,
            'tags'              : self.tag_list,
            'heygen_avatar_url' : self.heygen_avatar_url,
            'preview_video_url' : self.preview_video_url,
            'thumbnail_url'     : self.thumbnail_url,
            'created_at'        : self.created_at.isoformat() if self.created_at else None,
            'approved_at'       : self.approved_at.isoformat() if self.approved_at else None,
            'last_used'         : self.last_used.isoformat() if self.last_used else None
        }