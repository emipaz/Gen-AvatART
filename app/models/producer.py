"""
Módulo de modelo Producer para la aplicación Gem-AvatART.

Este módulo define el modelo de datos para los productores de contenido digital.
Los productores son usuarios con capacidades avanzadas que pueden crear avatares,
gestionar equipos de subproductores y afiliados, y tienen acceso directo a la API de HeyGen.

El módulo incluye:
    - Clase Producer: Modelo principal para productores de contenido

Funcionalidades principales:
    - Gestión de API keys de HeyGen
    - Control de límites de subproductores y afiliados
    - Sistema de comisiones y ganancias
    - Monitoreo de uso de API y cuotas
    - Configuración de métodos de pago
    - Estadísticas de producción de contenido

Relaciones:
    - Relación uno-a-uno con User
    - Relación uno-a-muchos con Avatar
    - Gestión de equipos (subproductores y afiliados)
"""

from app import db
from datetime import datetime
from enum import Enum

class Producer(db.Model):
    """
    Modelo de datos para productores de contenido digital.
    
    Los productores son usuarios especializados que tienen acceso a funcionalidades
    avanzadas como la creación de avatares, gestión de equipos y acceso directo
    a la API de HeyGen para generar contenido multimedia.
    
    Attributes:
        id (int)                       : Identificador único del productor
        user_id (int)                  : ID del usuario asociado (relación uno-a-uno)
        heygen_api_key (str)           : Clave de API de HeyGen para integración
        heygen_api_key_encrypted (str) : Versión encriptada de la API key
        api_key_status (str)           : Estado de la API key (pending, active, invalid)
        company_name (str)             : Nombre de la empresa o negocio
        business_type (str)            : Tipo de negocio (marketing, education, entertainment, etc.)
        website (str)                  : Sitio web oficial del productor
        commission_rate (float)        : Tasa de comisión (porcentaje decimal)
        payment_method (str)           : Método de pago preferido
        payment_details (str)          : Detalles de pago en formato JSON
        max_subproducers (int)         : Límite máximo de subproductores
        max_affiliates (int)           : Límite máximo de afiliados
        monthly_api_limit (int)        : Límite mensual de llamadas a la API
        total_reels_created (int)      : Contador total de reels creados
        total_earnings (float)         : Ganancias totales acumuladas
        api_calls_this_month (int)     : Llamadas a la API en el mes actual
        created_at (datetime)          : Fecha de creación del perfil
        updated_at (datetime)          : Fecha de última actualización
        last_api_call (datetime)       : Fecha de la última llamada a la API
    """
    __tablename__ = 'producers'
    
    # Clave primaria
    id      = db.Column(db.Integer, primary_key=True)
    # Relación uno-a-uno con User
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    # Configuración de HeyGen
    heygen_api_key           = db.Column(db.String(255), nullable=False)
    heygen_api_key_encrypted = db.Column(db.Text)  # Versión encriptada
    api_key_status           = db.Column(db.String(20), default='pending')  # pending, active, invalid
    
    # Información comercial y empresarial
    company_name  = db.Column(db.String(100))  # Nombre de la empresa
    business_type = db.Column(db.String(50))   # Tipo de negocio
    website       = db.Column(db.String(200))  # Sitio web oficial
    
    # Configuración de comisiones
    commission_rate = db.Column(db.Float, default=0.15)  # 15% por defecto
    payment_method  = db.Column(db.String(50))           # paypal, bank_transfer, etc.
    payment_details = db.Column(db.Text)                 # JSON con detalles de pago
    
    # Límites y restricciones de la cuenta
    max_subproducers  = db.Column(db.Integer, default=10)   # Máximo 10 subproductores
    max_affiliates    = db.Column(db.Integer, default=100)  # Máximo 100 afiliados
    monthly_api_limit = db.Column(db.Integer, default=1000) # Límite mensual de API calls
    
    # Estadísticas y métricas de rendimiento
    total_reels_created   = db.Column(db.Integer, default=0)  # Contador total de reels
    total_earnings        = db.Column(db.Float, default=0.0)  # Ganancias acumuladas
    api_calls_this_month  = db.Column(db.Integer, default=0)  # Uso de API del mes actual
    
    # Campos de auditoría y timestamps
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)                        # Fecha de creación
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # Última actualización
    last_api_call = db.Column(db.DateTime)                                                 # Última llamada a API
    
    # Definición de relaciones con otros modelos
    avatars = db.relationship('Avatar', backref = 'producer', lazy = 'dynamic')  # Avatares creados
    
    # Relación con subproductores (usuarios invitados con rol subproducer)
    subproducers = db.relationship('User', 
                                 foreign_keys = 'User.invited_by_id',
                                 primaryjoin  = 'and_(Producer.user_id==User.invited_by_id, User.role=="subproducer")',
                                 lazy         = 'dynamic')
    
    # Relación con afiliados (usuarios invitados con rol affiliate)
    affiliates = db.relationship('User',
                               foreign_keys = 'User.invited_by_id', 
                               primaryjoin  = 'and_(Producer.user_id==User.invited_by_id, User.role=="affiliate")',
                               lazy         = 'dynamic')
    
    
    def __repr__(self):
        """
        Representación en string del objeto Producer.
        
        Returns:
            str: Representación legible del productor con su username
        """
        return f'<Producer {self.user.username}>'
    
    @property
    def current_subproducers_count(self):
        """
        Obtiene el número actual de subproductores activos.
        
        Returns:
            int: Cantidad de subproductores con estado 'active'
        """
        return self.subproducers.filter_by(status='active').count()
    
    @property
    def current_affiliates_count(self):
        """
        Obtiene el número actual de afiliados activos.
        
        Returns:
            int: Cantidad de afiliados con estado 'active'
        """
        return self.affiliates.filter_by(status='active').count()
    
    def can_add_subproducer(self):
        """
        Verifica si el productor puede agregar más subproductores.
        
        Compara el número actual de subproductores activos con el límite máximo
        configurado para este productor.
        
        Returns:
            bool: True si puede agregar más subproductores, False en caso contrario
        """
        return self.current_subproducers_count < self.max_subproducers
    
    def can_add_affiliate(self):
        """
        Verifica si el productor puede agregar más afiliados.
        
        Compara el número actual de afiliados activos con el límite máximo
        configurado para este productor.
        
        Returns:
            bool: True si puede agregar más afiliados, False en caso contrario
        """
        return self.current_affiliates_count < self.max_affiliates
    
    def has_api_quota(self):
        """
        Verifica si el productor tiene cuota de API disponible para el mes actual.
        
        Compara el número de llamadas realizadas este mes con el límite mensual
        configurado para determinar si puede realizar más llamadas a la API.
        
        Returns:
            bool: True si tiene cuota disponible, False si ya alcanzó el límite
        """
        return self.api_calls_this_month < self.monthly_api_limit
    
    def increment_api_usage(self):
        """
        Incrementa el contador de uso de API y actualiza la fecha de última llamada.
        
        Este método debe llamarse cada vez que se realiza una llamada a la API de HeyGen
        para mantener un control preciso del uso y aplicar los límites correspondientes.
        
        Note:
            Realiza commit automático a la base de datos
        """
        self.api_calls_this_month += 1
        self.last_api_call = datetime.utcnow()
        db.session.commit()
    
    def reset_monthly_usage(self):
        """
        Resetea el contador de uso mensual de API.
        
        Este método debe ejecutarse al inicio de cada mes mediante una tarea
        programada para reiniciar los límites de uso de API.
        
        Note:
            Realiza commit automático a la base de datos
        """
        self.api_calls_this_month = 0
        db.session.commit()
    
    def validate_api_key(self):
        """
        Valida la API key de HeyGen realizando una llamada de prueba.
        
        Utiliza el servicio de HeyGen para verificar que la API key es válida
        y tiene los permisos necesarios. Actualiza el estado de la API key
        según el resultado de la validación.
        
        Returns:
            bool: True si la API key es válida, False en caso contrario
        
        Note:
            Actualiza automáticamente el campo api_key_status y realiza commit
        """
        # TODO: Implementar validación real con HeyGen API
        
        from app.services.heygen_service import HeyGenService
        # Crear instancia del servicio con la API key del productor
        
        service = HeyGenService(self.heygen_api_key)
        is_valid = service.validate_api_key()
        
        self.api_key_status = 'active' if is_valid else 'invalid'
        db.session.commit()
        
        return is_valid
    
    def to_dict(self):
        """
        Convierte el objeto Producer a un diccionario para serialización JSON.
        
        Incluye todos los campos importantes del productor, estadísticas actuales
        y contadores dinámicos. Útil para APIs y respuestas JSON.
        
        Returns:
            dict: Diccionario con todos los campos relevantes del productor
        
        Note:
            Las fechas se convierten a formato ISO para compatibilidad JSON.
            No incluye información sensible como API keys.
        """
        return {
            'id'                    : self.id,
            'user_id'               : self.user_id,
            'company_name'          : self.company_name,
            'business_type'         : self.business_type,
            'website'               : self.website,
            'commission_rate'       : self.commission_rate,
            'api_key_status'        : self.api_key_status,
            'max_subproducers'      : self.max_subproducers,
            'max_affiliates'        : self.max_affiliates,
            'current_subproducers'  : self.current_subproducers_count,
            'current_affiliates'    : self.current_affiliates_count,
            'total_reels_created'   : self.total_reels_created,
            'total_earnings'        : self.total_earnings,
            'api_calls_this_month'  : self.api_calls_this_month,
            'monthly_api_limit'     : self.monthly_api_limit,
            'created_at'            : self.created_at.isoformat() if self.created_at else None
        }