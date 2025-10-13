"""
Módulo de modelo ProducerRequest para la aplicación Gem-AvatART.

Este módulo define el sistema de solicitudes para que usuarios regulares puedan
solicitar convertirse en productores. Maneja el flujo completo de solicitud,
revisión y aprobación/rechazo por parte de administradores.

El módulo incluye:
    - Enum ProducerRequestStatus : Estados de solicitud (pendiente, aprobada, rechazada)
    - Clase ProducerRequest      : Modelo principal para solicitudes de productor

Funcionalidades principales:
    - Sistema de solicitudes con motivación del usuario
    - Flujo de aprobación/rechazo administrativo
    - Auditoría completa (quién, cuándo, por qué)
    - Integración con sistema de roles de usuarios
    - Prevención de solicitudes duplicadas
    - Historial de cambios de estado

Flujo del sistema:
    1. Usuario final crea solicitud con motivación
    2. Administrador revisa y aprueba/rechaza
    3. Si aprueba: usuario cambia a rol PRODUCER
    4. Si rechaza: puede volver a solicitar después
"""

from datetime import datetime
from enum import Enum
from app import db


class ProducerRequestStatus(Enum):
    """
    Enumeración que define los estados posibles de una solicitud de productor.
    
    Estados disponibles:
        PENDING  : Solicitud creada, pendiente de revisión administrativa
        APPROVED : Solicitud aprobada, usuario puede acceder a funciones de productor
        REJECTED : Solicitud rechazada, usuario mantiene rol actual
    """
    PENDING  = "pending"   # Solicitud pendiente de revisión
    APPROVED = "approved"  # Solicitud aprobada por administrador
    REJECTED = "rejected"  # Solicitud rechazada por administrador


class ProducerRequest(db.Model):
    """
    Modelo de datos para solicitudes de upgrade a productor.
    
    Representa la solicitud formal de un usuario para convertirse en productor
    de la plataforma. Incluye información sobre motivación, estado de revisión
    y auditoría completa del proceso de aprobación/rechazo.
    
    Attributes:
        id (int)                        : Identificador único de la solicitud
        user_id (int)                   : ID del usuario solicitante
        motivation (str)                : Motivación del usuario para ser productor
        company_name (str)              : Nombre de empresa propuesta (opcional)
        business_type (str)             : Tipo de negocio (opcional)
        website (str)                   : Sitio web corporativo (opcional)
        expected_volume (int)           : Volumen esperado de reels/mes (opcional)
        status (ProducerRequestStatus)  : Estado actual de la solicitud
        created_at (datetime)           : Fecha de creación de la solicitud
        reviewed_at (datetime)          : Fecha de revisión por administrador
        reviewed_by_id (int)            : ID del administrador que revisó
        rejection_reason (str)          : Motivo del rechazo (si aplica)
        notes (str)                     : Notas internas del administrador
    """
    __tablename__ = "producer_requests"
    
    # Clave primaria
    id = db.Column(db.Integer, primary_key=True)
    
    # Relación con el usuario solicitante (obligatorio)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    
    # Información proporcionada por el usuario en la solicitud
    motivation      = db.Column(db.Text,        nullable = True)  # Motivación para ser productor
    company_name    = db.Column(db.String(100), nullable = True)  # Empresa propuesta
    business_type   = db.Column(db.String(50),  nullable = True)  # Tipo de negocio
    website         = db.Column(db.String(200), nullable = True)  # Sitio web corporativo
    expected_volume = db.Column(db.Integer,     nullable = True)  # Reels esperados por mes
    
    # Estado y control de flujo
    status = db.Column(
        db.Enum(ProducerRequestStatus),
        default  = ProducerRequestStatus.PENDING,
        nullable = False,
        index    = True  # Índice para consultas frecuentes por estado
    )
    
    # Campos de auditoría y timestamps
    created_at     = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    reviewed_at    = db.Column(db.DateTime, nullable=True)  # Cuándo fue revisada
    reviewed_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)  # Quién la revisó
    
    # Información de rechazo y notas administrativas
    rejection_reason = db.Column(db.Text, nullable=True)  # Motivo del rechazo
    notes            = db.Column(db.Text, nullable=True)  # Notas internas del admin
    
    # Definición de relaciones con otros modelos
    user        = db.relationship('User', foreign_keys=[user_id], backref='producer_requests', lazy='select')
    reviewed_by = db.relationship('User', foreign_keys=[reviewed_by_id], lazy='select')
    
    def __repr__(self):
        """
        Representación en string del objeto ProducerRequest.
        
        Returns:
            str: Representación legible de la solicitud con user_id y estado
        """
        return f"<ProducerRequest user_id={self.user_id} status={self.status.value}>"
    
    def approve(self, admin_user, notes=None):
        """
        Aprobar la solicitud y cambiar el rol del usuario a PRODUCER.
        
        Marca la solicitud como aprobada, registra auditoría y cambia
        el rol del usuario solicitante. Acción crítica que otorga
        nuevos permisos en la plataforma.
        
        Args:
            admin_user (User): Usuario administrador que aprueba
            notes (str, opcional): Notas adicionales del administrador
        
        Raises:
            ValueError: Si la solicitud no está en estado PENDING
            AttributeError: Si el usuario asociado no existe
        
        Note:
            - Cambia automáticamente el rol del usuario a PRODUCER
            - Registra quién y cuándo aprobó para auditoría
            - Una vez aprobada, no se puede revertir directamente
            - Debería disparar notificación al usuario (futuro)
        """
        # Validar que la solicitud esté pendiente
        if self.status != ProducerRequestStatus.PENDING:
            raise ValueError(f"No se puede aprobar solicitud con estado {self.status.value}")
        
        # Validar que el usuario exista
        if not self.user:
            raise AttributeError("Usuario asociado a la solicitud no encontrado")
        
        # Actualizar estado de la solicitud
        self.status         = ProducerRequestStatus.APPROVED
        self.reviewed_at    = datetime.utcnow()
        self.reviewed_by_id = admin_user.id
        if notes:
            self.notes = notes
        
        # Cambiar rol del usuario a PRODUCER (importación local para evitar ciclos)
        from app.models.user import UserRole
        self.user.role = UserRole.PRODUCER
        
        # Confirmar cambios en base de datos
        db.session.commit()
    
    def reject(self, admin_user, reason=None, notes=None):
        """
        Rechazar la solicitud manteniendo el rol actual del usuario.
        
        Marca la solicitud como rechazada con motivo opcional.
        El usuario mantiene su rol actual y puede volver a
        solicitar en el futuro.
        
        Args:
            admin_user (User): Usuario administrador que rechaza
            reason (str, opcional): Motivo del rechazo para el usuario
            notes (str, opcional): Notas internas del administrador
        
        Raises:
            ValueError: Si la solicitud no está en estado PENDING
        
        Note:
            - Usuario mantiene rol actual (no hay cambio de permisos)
            - Puede crear nueva solicitud después del rechazo
            - Motivo del rechazo ayuda al usuario a mejorar futura solicitud
            - Registra auditoría completa del proceso
        """
        # Validar que la solicitud esté pendiente
        if self.status != ProducerRequestStatus.PENDING:
            raise ValueError(f"No se puede rechazar solicitud con estado {self.status.value}")
        
        # Actualizar estado de la solicitud
        self.status = ProducerRequestStatus.REJECTED
        self.reviewed_at = datetime.utcnow()
        self.reviewed_by_id = admin_user.id
        if reason:
            self.rejection_reason = reason
        if notes:
            self.notes = notes
        
        # Confirmar cambios en base de datos
        db.session.commit()
    
    def can_be_modified(self):
        """
        Verificar si la solicitud puede ser modificada por el usuario.
        
        Una solicitud puede ser modificada solo si está en estado
        PENDING. Una vez aprobada o rechazada, no se puede cambiar.
        
        Returns:
            bool: True si puede modificarse, False en caso contrario
        
        Note:
            - Solo solicitudes PENDING pueden modificarse
            - Útil para validaciones en formularios de edición
            - Previene modificación de solicitudes ya procesadas
        """
        return self.status == ProducerRequestStatus.PENDING
    
    @property
    def is_pending(self):
        """
        Verificar si la solicitud está pendiente de revisión.
        
        Returns:
            bool: True si está pendiente, False en caso contrario
        """
        return self.status == ProducerRequestStatus.PENDING
    
    @property
    def is_approved(self):
        """
        Verificar si la solicitud fue aprobada.
        
        Returns:
            bool: True si está aprobada, False en caso contrario
        """
        return self.status == ProducerRequestStatus.APPROVED
    
    @property
    def is_rejected(self):
        """
        Verificar si la solicitud fue rechazada.
        
        Returns:
            bool: True si está rechazada, False en caso contrario
        """
        return self.status == ProducerRequestStatus.REJECTED
    
    @classmethod
    def get_pending_requests(cls):
        """
        Obtener todas las solicitudes pendientes de revisión.
        
        Método de clase para obtener solicitudes que requieren
        atención administrativa. Útil para dashboards y notificaciones.
        
        Returns:
            Query: Consulta con solicitudes pendientes ordenadas por fecha
        
        Note:
            - Ordenadas por fecha de creación (más antiguas primero)
            - Include join con usuario para información completa
            - Útil para alertas y dashboards administrativos
        """
        return cls.query.filter_by(status = ProducerRequestStatus.PENDING)\
                      .order_by(cls.created_at.asc())
    
    @classmethod
    def user_has_pending_request(cls, user_id):
        """
        Verificar si un usuario tiene una solicitud pendiente.
        
        Previene que usuarios creen múltiples solicitudes simultáneas.
        Un usuario solo puede tener una solicitud pendiente a la vez.
        
        Args:
            user_id (int): ID del usuario a verificar
        
        Returns:
            bool: True si tiene solicitud pendiente, False en caso contrario
        
        Note:
            - Previene spam de solicitudes del mismo usuario
            - Útil para validación antes de crear nueva solicitud
            - No considera solicitudes ya procesadas (aprobadas/rechazadas)
        """
        return cls.query.filter_by(
            user_id = user_id,
            status  = ProducerRequestStatus.PENDING
        ).first() is not None
    
    def to_dict(self):
        """
        Convertir la solicitud a diccionario para APIs JSON.
        
        Serializa el objeto para respuestas de API, incluyendo
        información de relaciones y timestamps formateados.
        
        Returns:
            dict: Diccionario con toda la información de la solicitud
        
        Note:
            - Incluye información del usuario solicitante
            - Timestamps en formato ISO para compatibilidad
            - Información del revisor si está disponible
            - Excluye información sensible como notas internas
        """
        return {
            'id'     : self.id,
            'user_id'   : self.user_id,
            'user'      : {
                            'id'        : self.user.id,
                            'username'  : self.user.username,
                            'full_name' : self.user.full_name,
                            'email'     : self.user.email
                            } if self.user else None,
            'motivation'     : self.motivation,
            'company_name'   : self.company_name,
            'business_type'  : self.business_type,
            'website'        : self.website,
            'expected_volume' : self.expected_volume,
            'status'         : self.status.value,
            'created_at'     : self.created_at.isoformat() if self.created_at else None,
            'reviewed_at'    : self.reviewed_at.isoformat() if self.reviewed_at else None,
            'reviewed_by': {
                            'id'        : self.reviewed_by.id,
                            'username'  : self.reviewed_by.username,
                            'full_name' : self.reviewed_by.full_name
                            } if self.reviewed_by else None,
            'rejection_reason': self.rejection_reason
        }
