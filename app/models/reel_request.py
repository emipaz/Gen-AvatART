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
import logging
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
    speed         = db.Column(db.Float, default=1.0)  # Velocidad de la voz (0.5 a 1.5)
    pitch         = db.Column(db.Integer, default=0)  # Pitch de la voz (-50 a 50)
    
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
        from app.services.heygen_service import HeyGenService
        from flask import current_app
        import logging
        
        logger = logging.getLogger(__name__)
        
        # Actualizar estado de la solicitud
        self.status         = ReelRequestStatus.APPROVED
        self.reviewed_at    = datetime.utcnow()
        self.reviewed_by_id = reviewer.id
        self.producer_notes = producer_notes
        self.updated_at     = datetime.utcnow()
        
        # Crear el reel
        background_type = 'image' if self.background_url else 'default'
        new_reel = Reel(
            creator_id       = self.user_id,
            owner_id         = self.user_id,
            avatar_id        = self.avatar_id,
            title            = self.title,
            script           = self.script,
            background_url   = self.background_url,
            background_type  = background_type,
            resolution       = self.resolution,
            meta_data        = self.config_data,
            status           = ReelStatus.PENDING,
            created_at       = datetime.utcnow(),
            voice_id         = self.voice_id,
            speed            = self.speed if self.speed is not None else 1.0,
            pitch            = self.pitch if self.pitch is not None else 0
        )
        
        db.session.add(new_reel)
        db.session.flush()  # Para obtener el ID del reel
        
        # Vincular el reel creado con la solicitud
        self.created_reel_id = new_reel.id
        
        # 🆕 INTEGRACIÓN CON HEYGEN API
        try:
            # Obtener API key de configuración
            api_keys = []

            # Intentar primero con la API key del productor
            if self.producer and self.producer.heygen_api_key:
                api_keys.append(('producer', self.producer.heygen_api_key))

            # Fallback a la API master configurada en la app
            owner_api_key = current_app.config.get('HEYGEN_OWNER_API_KEY')
            if owner_api_key:
                api_keys.append(('owner', owner_api_key))

            if not api_keys:
                logger.warning("No hay API keys disponibles para enviar el reel a HeyGen. Permanecerá en estado PENDING.")
                return new_reel

            if not self.avatar.avatar_ref:
                logger.warning(f"Avatar {self.avatar.id} no tiene avatar_ref configurado")
                return new_reel

            last_error = None
            for source, api_key in api_keys:
                try:
                    heygen_service = HeyGenService(api_key=api_key)

                    logger.info(
                        "Enviando reel %s a HeyGen usando API key %s",
                        new_reel.id,
                        source
                    )

                    video_response = heygen_service.create_reel_video(
                        avatar_id=self.avatar.avatar_ref,
                        script=self.script,
                        title=self.title,
                        resolution=self.resolution or '1080x1920',
                        background_type='image' if self.background_url else 'color',
                        background_value=self.background_url or '#ffffff',
                        voice_id=self.voice_id,
                        voice_speed=self.speed if self.speed is not None else 1.0,
                        voice_pitch=self.pitch if self.pitch is not None else 0,
                        check_quota=False  # No verificar cuota por ahora
                    )

                    if video_response and video_response.get('data', {}).get('video_id'):
                        video_id = video_response['data']['video_id']
                        new_reel.start_processing(job_id=video_id)
                        logger.info(
                            "Reel %s enviado a HeyGen con ID %s usando API %s",
                            new_reel.id,
                            video_id,
                            source
                        )
                        break

                    logger.error(
                        "HeyGen no devolvió video_id para reel %s usando API %s",
                        new_reel.id,
                        source
                    )

                except Exception as e:
                    last_error = str(e)
                    logger.error(
                        "Error enviando reel %s a HeyGen con API %s: %s",
                        new_reel.id,
                        source,
                        last_error
                    )
            else:
                if last_error:
                    logger.error(
                        "No se pudo enviar el reel %s a HeyGen. Último error: %s",
                        new_reel.id,
                        last_error
                    )
                
        except Exception as e:
            logger.error(f"Error al enviar reel {new_reel.id} a HeyGen: {str(e)}")
            # No fallar la aprobación si HeyGen falla, solo log el error
        
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