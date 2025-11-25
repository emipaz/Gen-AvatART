"""
Módulo de modelo ReelRequest para la aplicación Gem-AvatART.

Este módulo define el sistema de solicitudes para que usuarios finales puedan
solicitar la creación de reels usando avatares. Requiere aprobación del productor
propietario del avatar antes de proceder con la creación.

El módulo incluye:
    - Enum ReelRequestStatus : Estados de solicitud (pendiente, aprobada, rechazada)
    - Clase ReelRequest      : Modelo principal para solicitudes de reel

Funcionalidades principales:
    - Sistema de solicitudes con script y configuración
    - Flujo de aprobación/rechazo por productor del avatar
    - Auditoría completa (quién, cuándo, por qué)
    - Integración con sistema de avatares y usuarios
    - Prevención de solicitudes duplicadas
    - Conversión automática a Reel tras aprobación

Flujo del sistema:
    1. Usuario final crea solicitud de reel con avatar específico
    2. Productor propietario del avatar revisa y aprueba/rechaza
    3. Si aprueba: se crea automáticamente el Reel
    4. Si rechaza: usuario puede crear nueva solicitud
"""

from datetime import datetime
from enum import Enum
from app import db


class ReelRequestStatus(Enum):
    """
    Enumeración que define los estados posibles de una solicitud de reel.
    
    Estados disponibles:
        DRAFT    : Borrador creado por usuario, aún no enviado
        PENDING  : Solicitud creada, pendiente de revisión del productor
        APPROVED : Solicitud aprobada, reel será/fue creado
        REJECTED : Solicitud rechazada por el productor
        EXPIRED  : Solicitud expirada sin respuesta
    """
    DRAFT    = "draft"     # Borrador no enviado aún
    PENDING  = "pending"   # Solicitud pendiente de revisión
    APPROVED = "approved"  # Solicitud aprobada por productor
    REJECTED = "rejected"  # Solicitud rechazada por productor
    EXPIRED  = "expired"   # Solicitud expirada


class ReelRequest(db.Model):
    """
    Modelo de datos para solicitudes de creación de reels.
    
    Representa la solicitud formal de un usuario para crear un reel
    usando un avatar específico. Requiere aprobación del productor
    propietario del avatar.
    
    Attributes:
        id (int)                   : ID único de la solicitud
        user_id (int)              : ID del usuario que solicita (FK)
        avatar_id (int)            : ID del avatar a usar (FK)
        producer_id (int)          : ID del productor que debe aprobar (FK)
        
        # Contenido del reel solicitado
        title (str)                : Título del reel solicitado
        script (str)               : Texto/script que dirá el avatar
        background_url (str)       : URL del fondo personalizado (opcional)
        resolution (str)           : Resolución deseada
        
        # Configuración y metadata
        config_data (JSON)         : Configuraciones adicionales
        user_notes (str)           : Notas del usuario para el productor
        
        # Estado y gestión
        status (ReelRequestStatus) : Estado actual de la solicitud
        created_at (datetime)      : Fecha de creación
        updated_at (datetime)      : Última actualización
        
        # Aprobación/Rechazo
        reviewed_at (datetime)     : Fecha de revisión
        reviewed_by_id (int)       : ID del usuario que revisó (FK)
        producer_notes (str)       : Notas del productor
        
        # Resultado
        created_reel_id (int)      : ID del reel creado tras aprobación (FK)
        
    Relationships:
        user (User)         : Usuario solicitante
        avatar (Avatar)     : Avatar para usar en el reel
        producer (Producer) : Productor que debe revisar
        reviewed_by (User)  : Usuario que hizo la revisión
        created_reel (Reel) : Reel creado tras aprobación
        
    Methods:
        approve()        : Marca como aprobada y crea el reel
        reject()         : Marca como rechazada con razón
        can_be_approved(): Verifica si puede ser aprobada
        is_expired()     : Verifica si ha expirado
    """
    
    __tablename__ = 'reel_requests'
    
    # Identificación
    id         = db.Column(db.Integer, primary_key=True)
    user_id    = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    avatar_id  = db.Column(db.Integer, db.ForeignKey('avatars.id'), nullable=False)
    producer_id = db.Column(db.Integer, db.ForeignKey('producers.id'), nullable=False)
    
    # Contenido del reel solicitado
    title         = db.Column(db.String(200), nullable=False)
    script        = db.Column(db.Text, nullable=False)
    background_url = db.Column(db.String(500))
    resolution    = db.Column(db.String(20), default='1080p')
    voice_id      = db.Column(db.String(100))  # ID de la voz seleccionada de HeyGen
    
    # Configuración y metadata
    config_data = db.Column(db.JSON)
    user_notes  = db.Column(db.Text)
    
    # Estado y gestión
    status      = db.Column(db.Enum(ReelRequestStatus), default=ReelRequestStatus.DRAFT, nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Aprobación/Rechazo
    reviewed_at     = db.Column(db.DateTime)
    reviewed_by_id  = db.Column(db.Integer, db.ForeignKey('users.id'))
    producer_notes  = db.Column(db.Text)
    
    # Resultado
    created_reel_id = db.Column(db.Integer, db.ForeignKey('reels.id'))
    
    # Relationships
    user         = db.relationship('User', foreign_keys=[user_id], backref='reel_requests')
    avatar       = db.relationship('Avatar', backref='reel_requests')
    producer     = db.relationship('Producer', backref='reel_requests')
    reviewed_by  = db.relationship('User', foreign_keys=[reviewed_by_id], backref='reviewed_reel_requests')
    created_reel = db.relationship('Reel', backref='request_origin')
    
    def approve(self, reviewer, producer_notes=None):
        """
        Aprueba la solicitud de reel y crea el reel correspondiente.
        
        Args:
            reviewer (User): Usuario que aprueba (debe ser productor)
            producer_notes (str): Notas opcionales del productor
            
        Returns:
            Reel: El reel creado tras la aprobación
        """
        from app.models.reel import Reel, ReelStatus
        
        # Actualizar estado de la solicitud
        self.status         = ReelRequestStatus.APPROVED
        self.reviewed_at    = datetime.utcnow()
        self.reviewed_by_id = reviewer.id
        self.producer_notes = producer_notes
        self.updated_at     = datetime.utcnow()
        
        # Crear el reel
        new_reel = Reel(
            creator_id       = self.user_id,
            avatar_id        = self.avatar_id,
            title            = self.title,
            script           = self.script,
            background_url   = self.background_url,
            resolution       = self.resolution,
            meta_data        = self.config_data,
            status           = ReelStatus.PENDING,
            created_at       = datetime.utcnow()
        )
        
        db.session.add(new_reel)
        db.session.flush()  # Para obtener el ID del reel
        
        # Vincular el reel creado con la solicitud
        self.created_reel_id = new_reel.id
        
        return new_reel
    
    def reject(self, reviewer, producer_notes):
        """
        Rechaza la solicitud de reel.
        
        Args:
            reviewer (User): Usuario que rechaza (debe ser productor)
            producer_notes (str): Razón del rechazo
        """
        self.status         = ReelRequestStatus.REJECTED
        self.reviewed_at    = datetime.utcnow()
        self.reviewed_by_id = reviewer.id
        self.producer_notes = producer_notes
        self.updated_at     = datetime.utcnow()
    
    def can_be_approved(self):
        """
        Verifica si la solicitud puede ser aprobada.
        
        Returns:
            bool: True si puede ser aprobada, False en caso contrario
        """
        return (self.status == ReelRequestStatus.PENDING and 
                self.avatar.is_available() and 
                not self.is_expired())
    
    def is_expired(self, days=30):
        """
        Verifica si la solicitud ha expirado.
        
        Args:
            days (int): Días para considerar expirada (default: 30)
            
        Returns:
            bool: True si ha expirado, False en caso contrario
        """
        if not self.created_at:
            return False
        
        from datetime import timedelta
        expiry_date = self.created_at + timedelta(days=days)
        return datetime.utcnow() > expiry_date
    
    @property
    def days_since_created(self):
        """Días transcurridos desde la creación."""
        if not self.created_at:
            return 0
        return (datetime.utcnow() - self.created_at).days
    
    @property
    def requestor_name(self):
        """Nombre completo del usuario solicitante."""
        return self.user.full_name if self.user else 'Usuario desconocido'
    
    @property
    def avatar_name(self):
        """Nombre del avatar solicitado."""
        return self.avatar.name if self.avatar else 'Avatar desconocido'
    
    @property
    def producer_name(self):
        """Nombre del productor que debe revisar."""
        return self.producer.display_name if self.producer else 'Productor desconocido'
    
    @property
    def status_badge_class(self):
        """Clase CSS para el badge de estado."""
        return {
            ReelRequestStatus.DRAFT: 'secondary',
            ReelRequestStatus.PENDING: 'warning',
            ReelRequestStatus.APPROVED: 'success',
            ReelRequestStatus.REJECTED: 'danger',
            ReelRequestStatus.EXPIRED: 'secondary'
        }.get(self.status, 'secondary')
    
    def send_to_producer(self, user):
        """
        Envía el borrador al productor para su revisión.
        
        Args:
            user (User): Usuario que envía la solicitud
        """
        if self.status != ReelRequestStatus.DRAFT:
            raise ValueError("Solo se pueden enviar borradores")
        
        self.status = ReelRequestStatus.PENDING
        self.sent_at = datetime.utcnow()
        
        # La notificación por email se manejará en la ruta
    
    def can_be_edited(self):
        """
        Determina si la solicitud puede ser editada.
        Se pueden editar borradores y reels rechazados.
        """
        return self.status in [ReelRequestStatus.DRAFT, ReelRequestStatus.REJECTED]
    
    def can_be_deleted(self):
        """
        Determina si la solicitud puede ser eliminada.
        Solo se pueden eliminar borradores.
        """
        return self.status == ReelRequestStatus.DRAFT
    
    def __repr__(self):
        return f'<ReelRequest {self.id}: {self.title} by {self.requestor_name} ({self.status.value})>'