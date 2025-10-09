"""
Módulo de modelo ClonePermission para la aplicación Gem-AvatART.

Este módulo define el modelo de datos para el sistema de permisos granulares de clones/avatares.
Implementa el ACL (Access Control List) que permite a los productores controlar exactamente
quién puede usar sus clones y bajo qué limitaciones.

SEGÚN README - "ACL por avatar" es política imprescindible:
    clone_permissions = { 
        clone_id, 
        productor_id, 
        allowed_users[], 
        allowed_subproductores[], 
        limits{daily, monthly, per_render}, 
        status{active|paused} 
    }

El módulo incluye:
    - Enum PermissionSubjectType : Tipos de usuarios que pueden recibir permisos
    - Enum PermissionStatus      : Estados posibles de un permiso
    - Clase ClonePermission      : Modelo principal para permisos granulares de clones

Funcionalidades principales:
    - Control granular de acceso por clone/avatar
    - Límites configurables (diario, mensual, por render)
    - Gestión de permisos para subproductores y usuarios finales
    - Sistema de activación/pausado de permisos
    - Tracking de uso y consumo de límites
    - Auditoría completa de accesos y modificaciones

Flujo de trabajo típico:
    1. Productor crea un clone/avatar
    2. Productor otorga permisos específicos a usuarios
    3. Usuarios pueden usar el clone dentro de los límites
    4. Sistema trackea el uso y aplica restricciones
    5. Productor puede modificar/pausar permisos en tiempo real
"""

from app import db
from datetime import datetime, date
from enum import Enum
from sqlalchemy import and_, or_

class PermissionSubjectType(Enum):
    """
    Enumeración que define los tipos de usuarios que pueden recibir permisos.
    
    Tipos disponibles:
        SUBPRODUCER : Subproductor del equipo del productor
        FINAL_USER  : Usuario final que paga por usar el clone
    
    Note:
        Los PRODUCTORES tienen acceso automático a sus propios clones,
        no necesitan permisos explícitos
    """
    SUBPRODUCER = "subproducer"  # Subproductor del equipo
    FINAL_USER  = "final_user"   # Usuario final que paga por uso

class PermissionStatus(Enum):
    """
    Enumeración que define los estados posibles de un permiso.
    
    Estados disponibles:
        ACTIVE    : Permiso activo, usuario puede usar el clone
        PAUSED    : Permiso pausado temporalmente
        EXPIRED   : Permiso expirado por límites o tiempo
        REVOKED   : Permiso revocado por el productor
    """
    ACTIVE  = "active"   # Permiso activo y operativo
    PAUSED  = "paused"   # Pausado temporalmente por el productor
    EXPIRED = "expired"  # Expirado por límites o tiempo
    REVOKED = "revoked"  # Revocado permanentemente

class ClonePermission(db.Model):
    """
    Modelo de datos para permisos granulares de clones/avatares.
    
    Este modelo implementa el sistema ACL (Access Control List) que permite
    a los productores controlar exactamente quién puede usar sus clones,
    con qué limitaciones y bajo qué condiciones.
    
    Según README: "ACL por avatar" es una política imprescindible para
    el control granular de acceso a los clones.
    
    Attributes:
        id (int)                        : Identificador único del permiso
        clone_id (int)                  : ID del clone/avatar al que aplica el permiso
        producer_id (int)               : ID del productor propietario del clone
        subject_type (PermissionSubjectType) : Tipo de usuario (subproducer/final_user)
        subject_id (int)                : ID del usuario que recibe el permiso
        status (PermissionStatus)       : Estado actual del permiso
        daily_limit (int)               : Límite de generaciones por día (0 = ilimitado)
        monthly_limit (int)             : Límite de generaciones por mes (0 = ilimitado)
        per_render_cost (float)         : Costo por generación para el usuario
        daily_used (int)                : Generaciones usadas hoy
        monthly_used (int)              : Generaciones usadas este mes
        total_used (int)                : Total de generaciones realizadas
        expires_at (datetime)           : Fecha de expiración del permiso (opcional)
        notes (str)                     : Notas adicionales del productor
        meta_data (dict)                : Configuraciones adicionales en JSON
        created_at (datetime)           : Fecha de creación del permiso
        updated_at (datetime)           : Fecha de última actualización
        last_used_at (datetime)         : Fecha del último uso del permiso
        granted_by_id (int)             : ID del usuario que otorgó el permiso
    """
    __tablename__ = 'clone_permissions'
    
    # Clave primaria
    id = db.Column(db.Integer, primary_key=True)
    
    # Relaciones con otras entidades
    clone_id      = db.Column(db.Integer, db.ForeignKey('avatars.id'),   nullable = False)    # Clone/avatar
    producer_id   = db.Column(db.Integer, db.ForeignKey('producers.id'), nullable = False)  # Productor propietario
    subject_id    = db.Column(db.Integer, db.ForeignKey('users.id'),     nullable = False)      # Usuario beneficiario
    granted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'),     nullable = False)    # Quien otorgó el permiso
    
    # Tipo y estado del permiso
    subject_type = db.Column(db.Enum(PermissionSubjectType), nullable = False)  # Tipo de usuario
    status       = db.Column(db.Enum(PermissionStatus),      nullable = False, default=PermissionStatus.ACTIVE)
    
    # Límites configurables (0 = ilimitado)
    daily_limit     = db.Column(db.Integer, default = 0)    # Límite diario de generaciones
    monthly_limit   = db.Column(db.Integer, default = 0)    # Límite mensual de generaciones
    per_render_cost = db.Column(db.Float,   default = 0.0)  # Costo por generación

    # Contadores de uso
    daily_used   = db.Column(db.Integer, default = 0)  # Uso diario actual
    monthly_used = db.Column(db.Integer, default = 0)  # Uso mensual actual
    total_used   = db.Column(db.Integer, default = 0)  # Uso total histórico

    # Configuración adicional
    expires_at  = db.Column(db.DateTime)  # Fecha de expiración opcional
    notes       = db.Column(db.Text)      # Notas del productor
    meta_data   = db.Column(db.JSON)      # Configuraciones adicionales
    
    # Campos de auditoría y timestamps
    created_at   = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at   = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_used_at = db.Column(db.DateTime)
    
    # Relaciones con otros modelos
    clone        = db.relationship('Avatar', backref = 'permissions')
    subject_user = db.relationship('User', foreign_keys = [subject_id],    backref = 'clone_permissions_received')
    granted_by   = db.relationship('User', foreign_keys = [granted_by_id], backref = 'clone_permissions_granted')
    
    # Índices únicos para evitar permisos duplicados
    
    __table_args__ = (
        db.UniqueConstraint('clone_id', 'subject_id', name = 'unique_clone_subject_permission'),
        db.Index('idx_clone_permissions_lookup', 'clone_id', 'subject_type', 'status'),
        db.Index('idx_permissions_by_user', 'subject_id', 'status'),
    )
    
    def __repr__(self):
        """
        Representación en string del objeto ClonePermission.
        
        Returns:
            str: Representación legible del permiso
        """
        return f'<ClonePermission {self.subject_type.value}:{self.subject_id} -> Clone:{self.clone_id}>'
    
    @property
    def clone_name(self):
        """
        Obtiene el nombre del clone/avatar asociado.
        
        Returns:
            str: Nombre del clone o 'Desconocido' si no existe
        """
        return self.clone.name if self.clone else 'Desconocido'
    
    @property
    def subject_name(self):
        """
        Obtiene el nombre completo del usuario beneficiario.
        
        Returns:
            str: Nombre completo del usuario o 'Desconocido'
        """
        return self.subject_user.full_name if self.subject_user else 'Desconocido'
    
    @property
    def granted_by_name(self):
        """
        Obtiene el nombre de quien otorgó el permiso.
        
        Returns:
            str: Nombre completo del otorgante o 'Sistema'
        """
        return self.granted_by.full_name if self.granted_by else 'Sistema'
    
    @property
    def is_active(self):
        """
        Verifica si el permiso está activo y puede usarse.
        
        Returns:
            bool: True si está activo, False en caso contrario
        """
        return self.status == PermissionStatus.ACTIVE
    
    @property
    def is_expired(self):
        """
        Verifica si el permiso ha expirado por fecha.
        
        Returns:
            bool: True si ha expirado, False en caso contrario
        """
        if self.expires_at:
            return datetime.utcnow() > self.expires_at
        return False
    
    @property
    def daily_remaining(self):
        """
        Calcula las generaciones restantes para hoy.
        
        Returns:
            int or None: Generaciones restantes (None = ilimitado)
        """
        if self.daily_limit == 0:
            return None  # Ilimitado
        return max(0, self.daily_limit - self.daily_used)
    
    @property
    def monthly_remaining(self):
        """
        Calcula las generaciones restantes para este mes.
        
        Returns:
            int or None: Generaciones restantes (None = ilimitado)
        """
        if self.monthly_limit == 0:
            return None  # Ilimitado
        return max(0, self.monthly_limit - self.monthly_used)
    
    def can_use_clone(self):
        """
        Verifica si el usuario puede usar el clone actualmente.
        
        Considera estado, expiración y límites diarios/mensuales.
        
        Returns:
            tuple: (bool, str) - (puede_usar, razon_si_no_puede)
        """
        # Verificar estado activo
        if not self.is_active:
            return False, f"Permiso {self.status.value}"
        
        # Verificar expiración por fecha
        if self.is_expired:
            return False, "Permiso expirado por fecha"
        
        # Verificar límite diario
        if self.daily_limit > 0 and self.daily_used >= self.daily_limit:
            return False, f"Límite diario alcanzado ({self.daily_limit})"
        
        # Verificar límite mensual
        if self.monthly_limit > 0 and self.monthly_used >= self.monthly_limit:
            return False, f"Límite mensual alcanzado ({self.monthly_limit})"
        
        return True, "Permiso válido"
    
    def use_clone(self):
        """
        Registra el uso del clone, incrementando contadores.
        
        Debe llamarse cada vez que el usuario genere un video
        con este clone.
        
        Returns:
            bool: True si se registró el uso, False si no se pudo usar
        
        Note:
            Realiza commit automático a la base de datos
        """
        can_use, reason = self.can_use_clone()
        if not can_use:
            return False
        
        # Incrementar contadores
        self.daily_used += 1
        self.monthly_used += 1
        self.total_used += 1
        self.last_used_at = datetime.utcnow()
        
        # Auto-expirar si alcanzó límites
        if self.daily_limit > 0 and self.daily_used >= self.daily_limit:
            if self.monthly_limit > 0 and self.monthly_used >= self.monthly_limit:
                self.status = PermissionStatus.EXPIRED
        
        db.session.commit()
        return True
    
    def reset_daily_usage(self):
        """
        Resetea el contador diario de uso.
        
        Debe llamarse automáticamente cada día mediante un job/scheduler.
        
        Note:
            Realiza commit automático a la base de datos
        """
        self.daily_used = 0
        
        # Reactivar si estaba pausado solo por límite diario
        if self.status == PermissionStatus.EXPIRED and self.monthly_remaining is not None and self.monthly_remaining > 0:
            self.status = PermissionStatus.ACTIVE
        
        db.session.commit()
    
    def reset_monthly_usage(self):
        """
        Resetea el contador mensual de uso.
        
        Debe llamarse automáticamente cada mes mediante un job/scheduler.
        
        Note:
            Realiza commit automático a la base de datos
        """
        self.monthly_used = 0
        
        # Reactivar si estaba pausado solo por límite mensual
        if self.status == PermissionStatus.EXPIRED:
            self.status = PermissionStatus.ACTIVE
        
        db.session.commit()
    
    def pause(self, reason=None):
        """
        Pausa el permiso temporalmente.
        
        Args:
            reason (str, opcional): Motivo de la pausa
        
        Note:
            Realiza commit automático a la base de datos
        """
        self.status = PermissionStatus.PAUSED
        if reason:
            self.notes = f"Pausado: {reason}"
        db.session.commit()
    
    def activate(self):
        """
        Activa el permiso si no está revocado o expirado.
        
        Note:
            Realiza commit automático a la base de datos
        """
        if self.status not in [PermissionStatus.REVOKED, PermissionStatus.EXPIRED]:
            self.status = PermissionStatus.ACTIVE
            db.session.commit()
    
    def revoke(self, reason=None):
        """
        Revoca permanentemente el permiso.
        
        Args:
            reason (str, opcional): Motivo de la revocación
        
        Note:
            Una vez revocado, el permiso no puede reactivarse.
            Realiza commit automático a la base de datos
        """
        self.status = PermissionStatus.REVOKED
        if reason:
            self.notes = f"Revocado: {reason}"
        db.session.commit()
    
    def update_limits(self, daily_limit=None, monthly_limit=None, per_render_cost=None):
        """
        Actualiza los límites del permiso.
        
        Args:
            daily_limit (int, opcional): Nuevo límite diario
            monthly_limit (int, opcional): Nuevo límite mensual
            per_render_cost (float, opcional): Nuevo costo por render
        
        Note:
            Realiza commit automático a la base de datos
        """
        if daily_limit is not None:
            self.daily_limit = daily_limit
        if monthly_limit is not None:
            self.monthly_limit = monthly_limit
        if per_render_cost is not None:
            self.per_render_cost = per_render_cost
        
        self.updated_at = datetime.utcnow()
        db.session.commit()
    
    @staticmethod
    def grant_permission(clone_id, producer_id, subject_id, subject_type, granted_by_id, 
                        daily_limit=0, monthly_limit=0, per_render_cost=0.0, expires_at=None, notes=None):
        """
        Otorga un nuevo permiso para usar un clone.
        
        Args:
            clone_id (int)                       : ID del clone/avatar
            producer_id (int)                    : ID del productor propietario
            subject_id (int)                     : ID del usuario beneficiario
            subject_type (PermissionSubjectType) : Tipo de usuario
            granted_by_id (int)                  : ID de quien otorga el permiso
            daily_limit (int)                    : Límite diario (0 = ilimitado)
            monthly_limit (int)                  : Límite mensual (0 = ilimitado)
            per_render_cost (float)              : Costo por render
            expires_at (datetime)                : Fecha de expiración opcional
            notes (str): Notas adicionales
        
        Returns:
            ClonePermission: Nueva instancia de permiso creada
        
        Raises:
            ValueError: Si ya existe un permiso para este usuario y clone
        
        Note:
            Realiza commit automático a la base de datos
        """
        # Verificar si ya existe un permiso
        existing = ClonePermission.query.filter_by(
            clone_id=clone_id,
            subject_id=subject_id
        ).first()
        
        if existing:
            raise ValueError(f"Ya existe un permiso para este usuario en este clone")
        
        # Crear nuevo permiso
        permission = ClonePermission(
            clone_id        = clone_id,
            producer_id     = producer_id,
            subject_id      = subject_id,
            subject_type    = subject_type,
            granted_by_id   = granted_by_id,
            daily_limit     = daily_limit,
            monthly_limit   = monthly_limit,
            per_render_cost = per_render_cost,
            expires_at      = expires_at,
            notes           = notes,
            status          = PermissionStatus.ACTIVE
        )
        
        db.session.add(permission)
        db.session.commit()
        return permission
    
    @staticmethod
    def get_user_permissions(user_id, status=None):
        """
        Obtiene todos los permisos de un usuario específico.
        
        Args:
            user_id (int): ID del usuario
            status (PermissionStatus, opcional): Filtrar por estado
        
        Returns:
            Query: Query de permisos del usuario
        """
        query = ClonePermission.query.filter_by(subject_id=user_id)
        if status:
            query = query.filter_by(status=status)
        return query
    
    @staticmethod
    def get_clone_permissions(clone_id, status=None):
        """
        Obtiene todos los permisos de un clone específico.
        
        Args:
            clone_id (int): ID del clone/avatar
            status (PermissionStatus, opcional): Filtrar por estado
        
        Returns:
            Query: Query de permisos del clone
        """
        query = ClonePermission.query.filter_by(clone_id=clone_id)
        if status:
            query = query.filter_by(status=status)
        return query
    
    @staticmethod
    def get_producer_permissions(producer_id, status=None):
        """
        Obtiene todos los permisos otorgados por un productor.
        
        Args:
            producer_id (int): ID del productor
            status (PermissionStatus, opcional): Filtrar por estado
        
        Returns:
            Query: Query de permisos del productor
        """
        query = ClonePermission.query.filter_by(producer_id=producer_id)
        if status:
            query = query.filter_by(status=status)
        return query
    
    @staticmethod
    def can_user_use_clone(user_id, clone_id):
        """
        Verifica si un usuario puede usar un clone específico.
        
        Args:
            user_id (int): ID del usuario
            clone_id (int): ID del clone/avatar
        
        Returns:
            tuple: (bool, str, ClonePermission or None) - (puede_usar, razón, permiso)
        """
        permission = ClonePermission.query.filter_by(
            subject_id = user_id,
            clone_id   = clone_id
        ).first()
        
        if not permission:
            return False, "No tiene permiso para usar este clone", None
        
        can_use, reason = permission.can_use_clone()
        return can_use, reason, permission
    
    def to_dict(self):
        """
        Convierte el objeto ClonePermission a un diccionario para serialización JSON.
        
        Returns:
            dict: Diccionario con todos los campos importantes del permiso
        
        Note:
            Las fechas se convierten a formato ISO para compatibilidad JSON
        """
        can_use, reason = self.can_use_clone()
        
        return {
            'id'                : self.id,
            'clone_id'          : self.clone_id,
            'clone_name'        : self.clone_name,
            'producer_id'       : self.producer_id,
            'subject_id'        : self.subject_id,
            'subject_name'      : self.subject_name,
            'subject_type'      : self.subject_type.value,
            'granted_by_id'     : self.granted_by_id,
            'granted_by_name'   : self.granted_by_name,
            'status'            : self.status.value,
            'daily_limit'       : self.daily_limit,
            'monthly_limit'     : self.monthly_limit,
            'per_render_cost'   : self.per_render_cost,
            'daily_used'        : self.daily_used,
            'monthly_used'      : self.monthly_used,
            'total_used'        : self.total_used,
            'daily_remaining'   : self.daily_remaining,
            'monthly_remaining' : self.monthly_remaining,
            'is_active'         : self.is_active,
            'is_expired'        : self.is_expired,
            'can_use'           : can_use,
            'can_use_reason'    : reason,
            'notes'             : self.notes,
            'metadata'          : self.meta_data or {},
            'expires_at'        : self.expires_at.isoformat() if self.expires_at else None,
            'created_at'        : self.created_at.isoformat() if self.created_at else None,
            'updated_at'        : self.updated_at.isoformat() if self.updated_at else None,
            'last_used_at'      : self.last_used_at.isoformat() if self.last_used_at else None
        }