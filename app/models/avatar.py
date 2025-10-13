"""
Módulo de modelo Avatar (CLONE) para la aplicación Gem-AvatART.

Este módulo define el modelo de datos para los avatares/clones digitales creados
mediante la integración con HeyGen. Los clones son avatares que pueden ser
utilizados por usuarios autorizados para generar videos mediante permisos granulares.

El módulo incluye:
    - Enum AvatarStatus: Estados posibles de un clone/avatar
    - Clase Avatar: Modelo principal (equivale a CLONE en el README)

Funcionalidades principales:
    - Gestión de permisos granulares por clone según README
    - Control de estados activo/inactivo (sin flujo de aprobación complejo)
    - Integración con HeyGen API usando avatar_ref
    - Sistema de permisos por subject_type (subproducer/user)
    - Metadata y configuración personalizable
    - Filtrado de avatares públicos de HeyGen
"""

from app import db
from datetime import datetime
from enum import Enum

class AvatarStatus(Enum):
    """
    Enumeración que define los estados posibles de un avatar.
    
   Estados disponibles:
        PENDING    : Pendiente de aprobación
        APPROVED   : Aprobado por el admin
        ACTIVE     : Clone activo y disponible para uso
        INACTIVE   : Clone deshabilitado por el productor
        PROCESSING : Clone en proceso de creación en HeyGen
        FAILED     : Falló la creación del clone en HeyGen
    """
    PENDING     = "pending"      # Pendiente de aprobación
    APPROVED    = "approved"     # Aprobado por el admin
    ACTIVE      = "active"       # Clone activo y disponible para uso   
    INACTIVE    = "inactive"     # Clone deshabilitado
    PROCESSING  = "processing"   # En proceso de creación
    FAILED      = "failed"       # Si falló la creación

class Avatar(db.Model):
    """
    Modelo de datos para avatares/clones digitales (CLONE según README).
    
    Este modelo gestiona toda la información relacionada con los avatares
    digitales, incluyendo su estado, configuración, permisos y metadatos.
    
    Attributes:
        id (int)                : Identificador único del avatar/clone
        producer_id (int)       : ID del productor propietario (REQUERIDO según README)
        created_by_id (int)     : ID del usuario que creó el avatar
        # approved_by_id (int)  : ❌ REMOVIDO - Sin flujo de aprobación
        name (str)              : Nombre descriptivo del avatar
        description (str)       : Descripción detallada del avatar
        avatar_type (str)       : Tipo de avatar (male, female, custom)
        language (str)          : Idioma principal del avatar
        avatar_ref (str)        : ✅ NUEVO - Referencia del avatar en HeyGen (era heygen_avatar_id)
        # heygen_avatar_id (str): ❌ RENOMBRADO a avatar_ref
        # heygen_avatar_url (str): ❌ REMOVIDO - Redundante
        preview_video_url (str) : URL del video de preview
        thumbnail_url (str)     : URL de la imagen miniatura
        status (AvatarStatus)   : Estado actual del avatar (ACTIVE/INACTIVE)
        # is_public (bool)      : ❌ REMOVIDO - Permisos granulares en tabla separada
        # is_premium (bool)     : ❌ REMOVIDO - Se maneja en Stripe
        # max_daily_usage (int) : ❌ REMOVIDO - Límites en clone_permissions
        # usage_count (int)     : ❌ REMOVIDO - Se maneja en jobs
        # price_per_use (float) : ❌ REMOVIDO - Se maneja en Stripe
        meta_data (dict)        : Información adicional en formato JSON
        tags (str)              : Etiquetas separadas por comas
        created_at (datetime)   : Fecha de creación
        updated_at (datetime)   : Fecha de última actualización
        # approved_at (datetime): ❌ REMOVIDO - Sin aprobación
        last_used (datetime)    : Fecha de último uso
    """
    __tablename__ = 'avatars'
    
    # Clave primaria
    id = db.Column(db.Integer, primary_key=True)
    
    # Relaciones con otras tablas
    producer_id    = db.Column(db.Integer, db.ForeignKey('producers.id'), nullable = False)
    created_by_id  = db.Column(db.Integer, db.ForeignKey('users.id'),     nullable = False)
    # approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Información básica del avatar
    name        = db.Column(db.String(100), nullable = False)
    description = db.Column(db.Text)
    avatar_type = db.Column(db.String(50))  # male, female, custom
    language    = db.Column(db.String(10), default = 'es')  # Idioma principal
    
    
    # Datos de integración con HeyGen
    # ✅ NUEVO campo según README (reemplaza heygen_avatar_id)
    avatar_ref = db.Column(db.String(100), nullable = False, index = True)  # Campo clave para HeyGen
    
    # Datos de integración con HeyGen
    # heygen_avatar_id  = db.Column(db.String(100), unique=True)
    # heygen_avatar_url = db.Column(db.String(500))
    
    preview_video_url = db.Column(db.String(500))
    thumbnail_url     = db.Column(db.String(500))
    
    # Estado y configuración de acceso
    status     = db.Column(db.Enum(AvatarStatus), nullable = False, default = AvatarStatus.PROCESSING)
    
    # is_public  = db.Column(db.Boolean, default=False)  # Si otros usuarios pueden usarlo
    # is_premium = db.Column(db.Boolean, default=False)  # Si requiere plan premium
    
    # Configuración de límites y uso
    # max_daily_usage = db.Column(db.Integer, default=10)
    # usage_count     = db.Column(db.Integer, default=0)
    # price_per_use   = db.Column(db.Float, default=0.0)  # Precio por uso si es premium
    
    # Metadatos y etiquetas
    # se usa meta_data por que metadata es palabra reservada en SQLAlchemy
    meta_data = db.Column(db.JSON)         # Información adicional del avatar
    tags      = db.Column(db.String(500))  # Tags separados por comas
    
    # Campos de auditoría y timestamps
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    # approved_at = db.Column(db.DateTime)
    last_used   = db.Column(db.DateTime)
    
    # Definición de relaciones con otros modelos
    created_by  = db.relationship('User', foreign_keys = [created_by_id] , backref = 'created_avatars')
    # approved_by = db.relationship('User', foreign_keys = [approved_by_id], backref = 'approved_avatars')
    reels       = db.relationship('Reel', backref = 'avatar', lazy = 'dynamic')
    
    def __repr__(self):
        """
        Representación en string del objeto Avatar.
        
        Returns:
            str: Representación legible del avatar
        """
        return f'<Avatar {self.name} ({self.status.value})>'
    
    @property
    def creator_name(self):
        """
        Obtiene el nombre completo del creador del avatar.
        
        Returns:
            str: Nombre completo del usuario creador o 'Desconocido'
        """
        return self.created_by.full_name if self.created_by else 'Desconocido'
    
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
        Note:
            Acepta tanto ['marketing', 'ventas'] como 'marketing, ventas'
        """
        if isinstance(tag_list, str):
            tag_list = [ t.strip() 
                         for t in tag_list.split(',') 
                            if t.strip()
                        ]
        elif not isinstance(tag_list, (list, tuple)):
            tag_list = []
        
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
        if self.status != AvatarStatus.ACTIVE:
            return False
        
        # El creador siempre puede usar su avatar
        if self.created_by_id == user.id:
            return True
        
        # ✅ El productor propietario siempre puede usar sus clones
        if user.is_producer() and user.producer_profile and user.producer_profile.id == self.producer_id:
            return True
        
        # ❌ LÓGICA COMENTADA del modelo original
        # if self.is_public:
        #     user_producer = user.get_producer()
        #     return user_producer and user_producer.id == self.producer_id
        
        # ✅ TODO - Implementar verificación en clone_permissions cuando esté listo
        # Para otros usuarios, verificar permisos específicos en clone_permissions
        
        return False
    
    # ✅ NUEVO método según README
    def can_be_managed_by(self, user):
        """
        Verifica si un usuario puede gestionar (activar/desactivar) este clone.
        
        Args:
            user (User): Usuario a verificar
        
        Returns:
            bool: True si puede gestionar el clone
        """
        if not user.is_producer():
            return False
        
        # Puede gestionar sus propios clones
        if self.producer_id == user.producer_profile.id:
            return True
        
        # Puede gestionar clones de sus subproductores
        if self.created_by and self.created_by.invited_by_id == user.id:
            return True
        
        return False
    
    def activate(self):
        """
        Activa el clone para uso.
    
        Note:
            Cambia el estado a ACTIVE permitiendo su uso
        """
        self.status = AvatarStatus.ACTIVE
        db.session.commit()

    def deactivate(self):
        """
        Desactiva el clone temporalmente.

        Note:
            Cambia el estado a INACTIVE impidiendo su uso
        """
        self.status = AvatarStatus.INACTIVE
        db.session.commit()

    def mark_failed(self, error_message=None):
        """
        Marca el clone como fallido en su creación.

        Args:
            error_message (str, opcional): Mensaje de error

        Note:
            Cambia el estado a FAILED y opcionalmente guarda el error
        """
        self.status = AvatarStatus.FAILED
        if error_message:
            if not self.meta_data:
                self.meta_data = {}
            self.meta_data['error'] = error_message
        db.session.commit()
    
    
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
            ✅ ACTUALIZADO - Campos según nueva estructura
        """
        return {
            'id'                : self.id,                    # ✅ MANTENER
            'producer_id'       : self.producer_id,           # ✅ NUEVO - Importante según README
            'name'              : self.name,                  # ✅ MANTENER
            'description'       : self.description,           # ✅ MANTENER
            'avatar_type'       : self.avatar_type,           # ✅ MANTENER
            'language'          : self.language,              # ✅ MANTENER
            'avatar_ref'        : self.avatar_ref,            # ✅ NUEVO - Campo clave
            'status'            : self.status.value,          # ✅ MANTENER
            'creator_name'      : self.creator_name,          # ✅ MANTENER
            'tags'              : self.tag_list,              # ✅ MANTENER
            'preview_video_url' : self.preview_video_url,     # ✅ MANTENER
            'thumbnail_url'     : self.thumbnail_url,         # ✅ MANTENER
            'created_at'        : self.created_at.isoformat() if self.created_at else None,  # ✅ MANTENER
            'updated_at'        : self.updated_at.isoformat() if self.updated_at else None,  # ✅ NUEVO
            'last_used'         : self.last_used.isoformat() if self.last_used else None,    # ✅ MANTENER
            
            # ❌ CAMPOS COMENTADOS del modelo original
            # 'is_public'         : self.is_public,           # Removido - permisos granulares
            # 'is_premium'        : self.is_premium,          # Removido - se maneja en Stripe
            # 'approver_name'     : self.approver_name,       # Removido - sin aprobación
            # 'usage_count'       : self.usage_count,         # Removido - se cuenta en jobs
            # 'max_daily_usage'   : self.max_daily_usage,     # Removido - límites en clone_permissions
            # 'price_per_use'     : self.price_per_use,       # Removido - precios en Stripe
            # 'heygen_avatar_url' : self.heygen_avatar_url,   # Removido - redundante
            # 'approved_at'       : self.approved_at.isoformat() if self.approved_at else None,  # Sin aprobación
        }