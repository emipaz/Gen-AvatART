"""
Módulo de modelo Producer para la aplicación Gem-AvatART.

Este módulo define el modelo de datos para los productores, que son los usuarios
principales del sistema encargados de crear avatares y gestionar equipos de trabajo.
Los productores tienen acceso directo a HeyGen y manejan su propia facturación via Stripe Connect.

El módulo incluye:
    - Enum ProducerStatus : Estados posibles de un productor
    - Clase Producer      : Modelo principal para productores (ACTUALIZADO según README)

Funcionalidades principales (ACTUALIZADAS según README):
    - Integración con HeyGen API usando API key encriptada
    - Integración con Stripe Connect para cobros directos + application_fee
    - Gestión de equipos (subproductores y usuarios finales)
    - Configuraciones personalizables por productor
    - Sistema de comisiones y facturación
    - Control de límites y permisos por clone

Cambios según README:
    - ✅ NUEVO: stripe_account_id para Stripe Connect
    - ✅ NUEVO: settings JSON para configuraciones adicionales
    - ❌ SIMPLIFICADO: commission_rate, payment_method (ahora se maneja en Stripe)
"""


from app import db
from datetime import datetime
from enum import Enum
from cryptography.fernet import Fernet
import os

class ProducerStatus(Enum):
    """
    Enumeración que define los estados posibles de un productor.
    
    Estados disponibles:
        ACTIVE    : Productor activo con acceso completo
        SUSPENDED : Productor suspendido temporalmente
        PENDING   : Productor pendiente de configuración
        INACTIVE  : Productor inactivo (deshabilitado)
    """
    ACTIVE    = "active"    # Productor activo y operativo ✅ MANTENER
    SUSPENDED = "suspended" # Suspendido temporalmente ✅ MANTENER
    PENDING   = "pending"   # Pendiente de configuración ✅ MANTENER
    INACTIVE  = "inactive"  # Inactivo/deshabilitado ✅ MANTENER

class Producer(db.Model):
    """
    Modelo de datos para productores de contenido.
    
    Los productores son usuarios especializados que:
    - Gestionan su propia API key de HeyGen
    - Manejan facturación via Stripe Connect (NUEVO según README)
    - Supervisan equipos de subproductores y usuarios finales
    - Configuran permisos granulares por clone
    - Definen límites de uso para su equipo
    
    Attributes:
        id (int)                        : Identificador único del productor
        user_id (int)                   : ID del usuario asociado (relación uno-a-uno)
        company_name (str)              : Nombre de la empresa/marca
        business_type (str)             : Tipo de negocio
        phone (str)                     : Teléfono de contacto comercial
        address (str)                   : Dirección física
        city (str)                      : Ciudad
        country (str)                   : País
        website (str)                   : Sitio web corporativo
        heygen_api_key_encrypted (str)  : API key de HeyGen encriptada
        stripe_account_id (str)         : ✅ NUEVO - ID de cuenta Stripe Connect
        settings (dict)                 : ✅ NUEVO - Configuraciones adicionales JSON
        status (ProducerStatus)         : Estado actual del productor
        is_verified (bool)              : Si está verificado para operar
        created_at (datetime)           : Fecha de registro
        updated_at (datetime)           : Fecha de última actualización
        verified_at (datetime)          : Fecha de verificación
        
    Campos REMOVIDOS/SIMPLIFICADOS según README:
        # commission_rate (float)       : ❌ Se maneja en Stripe Connect
        # payment_method (str)          : ❌ Se maneja en Stripe Connect  
        # payment_details (dict)        : ❌ Se maneja en Stripe Connect
    """
    __tablename__ = 'producers'
    
    # Clave primaria
    id      = db.Column(db.Integer, primary_key=True)
    # Relación uno-a-uno con User
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    # Información comercial del productor
    company_name  = db.Column(db.String(100), nullable = False)  # ✅ MANTENER
    business_type = db.Column(db.String(50))                     # ✅ MANTENER
    phone         = db.Column(db.String(20))                     # ✅ MANTENER
    address       = db.Column(db.String(200))                    # ✅ MANTENER
    city          = db.Column(db.String(50))                     # ✅ MANTENER
    country       = db.Column(db.String(50))                     # ✅ MANTENER
    website       = db.Column(db.String(100))       
    
    # Límites/metrics de gestión
    max_subproducers   = db.Column(db.Integer, default=10)
    max_affiliates     = db.Column(db.Integer, default=100)
    monthly_api_limit  = db.Column(db.Integer, default=1000)
    
    # Integración con servicios externos
    heygen_api_key_encrypted = db.Column(db.Text)  # ✅ MANTENER - API key de HeyGen encriptada
    
    # ✅ NUEVO según README - Integración con Stripe Connect
    stripe_account_id = db.Column(db.String(100), index=True)  # Para Direct Charges + application_fee
    
    # ✅ NUEVO según README - Configuraciones adicionales
    settings = db.Column(db.JSON)  # Configuraciones personalizables del productor
    
    status      = db.Column(db.Enum(ProducerStatus), nullable=False, default=ProducerStatus.PENDING)
    is_verified = db.Column(db.Boolean, default=False)
    
    # Campos de auditoría y timestamps
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)                            # Fecha de creación
    updated_at    = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)  # Última actualización
    verified_at   = db.Column(db.DateTime)                                                        # Fecha de verificación  
    
    # Definición de relaciones con otros modelos
    avatars = db.relationship('Avatar', backref = 'producer', lazy = 'dynamic')  # Avatares creados
    
    commissions = db.relationship('Commission', backref = 'producer', lazy = 'dynamic')  # Comisiones ganadas

    
    def __repr__(self):
        """
        Representación en string del objeto Producer.
        
        Returns:
            str: Representación legible del productor con su company_name
        """
        return f'<Producer {self.company_name}>'
    
    def set_heygen_api_key(self, api_key):
        """
        Establece y encripta la API key de HeyGen.
        
        Utiliza Fernet para encriptar la API key antes de almacenarla
        en la base de datos. La clave de encriptación debe estar en
        las variables de entorno.
        
        Args:
            api_key (str): API key de HeyGen en texto plano
        
        Raises:
            ValueError: Si no se encuentra la clave de encriptación
        
        Note:
            No realiza commit automático, debe hacerse manualmente
        """
        encryption_key = os.environ.get('ENCRYPTION_KEY')
        if not encryption_key:
            raise ValueError("Clave de encriptación no encontrada en variables de entorno")
        
        fernet = Fernet(encryption_key.encode())
        self.heygen_api_key_encrypted = fernet.encrypt(api_key.encode()).decode()  # ✅ MANTENER
    
    def get_heygen_api_key(self):
        """
        Desencripta y retorna la API key de HeyGen.
        
        Utiliza Fernet para desencriptar la API key almacenada
        en la base de datos.
        
        Returns:
            str or None: API key en texto plano si existe y se puede desencriptar, None en caso contrario
        
        Raises:
            ValueError: Si no se encuentra la clave de encriptación
        """
        if not self.heygen_api_key_encrypted:
            return None
        
        encryption_key = os.environ.get('ENCRYPTION_KEY')
        if not encryption_key:
            raise ValueError("Clave de encriptación no encontrada en variables de entorno")
        
        try:
            fernet = Fernet(encryption_key.encode())
            return fernet.decrypt(self.heygen_api_key_encrypted.encode()).decode()  # ✅ MANTENER
        except Exception:
            return None
           
    # Stripe Connect
    def set_stripe_account(self, account_id):
        """
        Establece la cuenta de Stripe Connect del productor.
        
        Args:
            account_id (str): ID de la cuenta de Stripe Connect
            
        Note:
            Para integración con Stripe Connect
        """
        self.stripe_account_id = account_id
        db.session.commit()
    
    def has_stripe_connected(self):
        """
        Verifica si el productor tiene Stripe Connect configurado.
        
        Returns:
            bool: True si tiene cuenta Stripe conectada
            
        Note:
            ✅ NUEVO - Para verificar configuración de Stripe Connect
        """
        return bool(self.stripe_account_id)
    
    def get_setting(self, key, default=None):
        """
        Obtiene un valor de configuración específico.
        
        Args:
            key (str): Clave de la configuración
            default: Valor por defecto si no existe
            
        Returns:
            Valor de la configuración o default
            
        Note:
            ✅ NUEVO - Para acceso a configuraciones JSON
        """
        if not self.settings:
            return default
        return self.settings.get(key, default)
    
    def set_setting(self, key, value):
        """
        Establece un valor de configuración específico.
        
        Args:
            key (str): Clave de la configuración
            value: Valor a establecer
            
        Note:
            ✅ NUEVO - Para modificar configuraciones JSON
        """
        if not self.settings:
            self.settings = {}
        self.settings[key] = value
        db.session.commit()
    
    def update_settings(self, settings_dict):
        """
        Actualiza múltiples configuraciones de una vez.
        
        Args:
            settings_dict (dict): Diccionario con configuraciones
            
        Note:
            ✅ NUEVO - Para actualización masiva de configuraciones
        """
        if not self.settings:
            self.settings = {}
        self.settings.update(settings_dict)
        db.session.commit()
    
    def has_heygen_access(self):
        """
        Verifica si el productor tiene acceso configurado a HeyGen.
        
        Returns:
            bool: True si tiene API key de HeyGen configurada, False en caso contrario
        """
        return bool(self.heygen_api_key_encrypted) 
    
    def can_operate(self):
        """
        Verifica si el productor puede operar completamente.
        
        Para operar necesita:
        - Estado ACTIVE
        - API key de HeyGen configurada
        - Cuenta Stripe Connect configurada (NUEVO según README)
        
        Returns:
            bool: True si puede operar, False en caso contrario
            
        Note:
            ✅ ACTUALIZADO - Incluye verificación de Stripe Connect
        """
        return (self.status == ProducerStatus.ACTIVE and 
                self.has_heygen_access() and 
                self.has_stripe_connected())  # ✅ NUEVO requisito
    
    def get_team_members(self):
        """
        Obtiene todos los miembros del equipo del productor.
        
        Incluye subproductores y usuarios finales invitados por este productor.
        
        Returns:
            Query: Query de usuarios que forman parte del equipo
            
        Note:
            ✅ ACTUALIZADO - Comentario menciona "usuarios finales" en lugar de "afiliados"
        """
        from app.models.user import User, UserRole
        return User.query.filter(
            User.invited_by_id == self.user_id,
            User.role.in_([UserRole.SUBPRODUCER, UserRole.FINAL_USER])  # ✅ CAMBIO - era AFFILIATE
        )
    
    def get_total_avatars(self):
        """
        Obtiene el total de avatares/clones del productor.
        
        Incluye avatares propios y de sus subproductores.
        
        Returns:
            int: Número total de avatares
        """
        own_avatars = self.avatars.count()  # ✅ MANTENER
        
        # Avatares de subproductores
        team_members = self.get_team_members()
        subproducer_avatars = sum([
            member.created_avatars.count() 
            for member in team_members 
            if member.can_create_avatars()
        ])
        
        return own_avatars + subproducer_avatars  # ✅ MANTENER lógica
    
    def activate(self):
        """
        Activa el productor para operación completa.
        
        Cambia el estado a ACTIVE y registra la fecha de verificación
        si es la primera vez que se activa.
        
        Note:
            Realiza commit automático a la base de datos
        """
        self.status = ProducerStatus.ACTIVE
        if not self.verified_at:
            self.verified_at = datetime.utcnow()
            self.is_verified = True
        db.session.commit()  # ✅ MANTENER
    
    def suspend(self):
        """
        Suspende temporalmente al productor.
        
        Cambia el estado a SUSPENDED impidiendo la operación
        pero manteniendo los datos para reactivación.
        
        Note:
            Realiza commit automático a la base de datos
        """
        self.status = ProducerStatus.SUSPENDED
        db.session.commit()  # ✅ MANTENER
    
    def deactivate(self):
        """
        Desactiva permanentemente al productor.
        
        Cambia el estado a INACTIVE impidiendo la operación.
        
        Note:
            Realiza commit automático a la base de datos
        """
        self.status = ProducerStatus.INACTIVE
        db.session.commit()  # ✅ MANTENER

    def to_dict(self):
        """
        Convierte el objeto Producer a un diccionario para serialización JSON.
        
        Incluye información del productor sin datos sensibles como API keys.
        
        Returns:
            dict: Diccionario con los campos públicos del productor
            
        Note:
            ✅ ACTUALIZADO - Incluye nuevos campos según README
        """
        return {
            'id'                  : self.id,                                                      # ✅ MANTENER
            'user_id'             : self.user_id,                                                 # ✅ MANTENER
            'company_name'        : self.company_name,                                            # ✅ MANTENER
            'business_type'       : self.business_type,                                           # ✅ MANTENER
            'phone'               : self.phone,                                                   # ✅ MANTENER
            'address'             : self.address,                                                 # ✅ MANTENER
            'city'                : self.city,                                                    # ✅ MANTENER
            'country'             : self.country,                                                 # ✅ MANTENER
            'website'             : self.website,                                                 # ✅ MANTENER
            'status'              : self.status.value,                                            # ✅ MANTENER
            'is_verified'         : self.is_verified,                                             # ✅ MANTENER
            'has_heygen_access'   : self.has_heygen_access(),                                     # ✅ MANTENER
            'has_stripe_connected': self.has_stripe_connected(),                                  # ✅ NUEVO
            'can_operate'         : self.can_operate(),                                           # ✅ MANTENER (lógica actualizada)
            'total_avatars'       : self.get_total_avatars(),                                     # ✅ MANTENER
            'settings'            : self.settings or {},                                          # ✅ NUEVO
            'created_at'          : self.created_at.isoformat() if self.created_at else None,    # ✅ MANTENER
            'verified_at'         : self.verified_at.isoformat() if self.verified_at else None   # ✅ MANTENER
            
            # ❌ CAMPOS COMENTADOS - Removidos según README
            # 'commission_rate'     : self.commission_rate,    # Se maneja en Stripe Connect
            # 'payment_method'      : self.payment_method,     # Se maneja en Stripe Connect
            # 'payment_details'     : self.payment_details,    # Se maneja en Stripe Connect
        }