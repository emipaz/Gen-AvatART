"""
Módulo de modelo Commission para la aplicación Gem-AvatART.

Este módulo define el modelo de datos para el sistema de comisiones de la aplicación.
Gestiona las comisiones generadas por la creación de reels/videos, incluyendo
diferentes tipos de comisiones (productor, subproductor, afiliado) y su procesamiento
de pagos correspondiente.

El módulo incluye:
    - Enum CommissionStatus: Estados posibles de una comisión
    - Clase Commission: Modelo principal del sistema de comisiones

Funcionalidades principales:
    - Gestión de diferentes tipos de comisiones
    - Control de estados de aprobación y pago
    - Cálculo de ganancias por usuario y período
    - Integración con sistemas de pago
    - Auditoría completa de transacciones
"""

from app import db
from datetime import datetime
from enum import Enum

class CommissionStatus(Enum):
    """
    Enumeración que define los estados posibles de una comisión.
    
    Estados disponibles:
        PENDING: Comisión creada, pendiente de aprobación
        APPROVED: Comisión aprobada, lista para pagar
        PAID: Comisión pagada al usuario
        CANCELLED: Comisión cancelada por algún motivo
    """
    PENDING   = "pending"    # Pendiente de aprobación
    APPROVED  = "approved"   # Aprobada para pago
    PAID      = "paid"       # Pagada al usuario
    CANCELLED = "cancelled"  # Cancelada

class Commission(db.Model):
    """"
    Modelo de datos para el sistema de comisiones de la aplicación.
    
    Este modelo gestiona las comisiones generadas por la creación de contenido,
    incluyendo su procesamiento, aprobación y pago a los diferentes tipos de usuarios
    (productores, subproductores, afiliados).
    
    Attributes:
        id (int)                  : Identificador único de la comisión
        user_id (int)             : ID del usuario que recibe la comisión
        reel_id (int)             : ID del reel que generó la comisión
        commission_type (str)     : Tipo de comisión (producer, subproducer, affiliate)
        amount (float)            : Monto de la comisión en la moneda especificada
        percentage (float)        : Porcentaje aplicado para calcular la comisión
        status (CommissionStatus) : Estado actual de la comisión
        currency (str)            : Código de moneda (USD, EUR, etc.)
        payment_method (str)      : Método de pago utilizado
        payment_reference (str)   : Referencia o ID de la transacción de pago
        payment_details (dict)    : Detalles adicionales del pago en formato JSON
        created_at (datetime)     : Fecha de creación de la comisión
        approved_at (datetime)    : Fecha de aprobación
        paid_at (datetime)        : Fecha de pago
        notes (str)               : Notas adicionales sobre la comisión
    """
    __tablename__ = 'commissions'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relaciones
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reel_id = db.Column(db.Integer, db.ForeignKey('reels.id'), nullable=False)
    
    # Información de la comisión
    commission_type = db.Column(db.String(50), nullable=False)  # producer, subproducer, affiliate
    amount          = db.Column(db.Float, nullable=False)
    percentage      = db.Column(db.Float, nullable=False)  # Porcentaje aplicado
    
    # Estado y procesamiento
    status   = db.Column(db.Enum(CommissionStatus), nullable=False, default=CommissionStatus.PENDING)
    currency = db.Column(db.String(3), default='USD')
    
    # Información de pago
    payment_method    = db.Column(db.String(50))  # paypal, bank_transfer, etc.
    payment_reference = db.Column(db.String(100)) # ID de transacción
    payment_details   = db.Column(db.JSON)        # Detalles adicionales del pago
    
    # Timestamps
    created_at  = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime)
    paid_at     = db.Column(db.DateTime)
    
    # Metadatos
    notes = db.Column(db.Text)  # Notas adicionales
    
    def __repr__(self):
        """
        Representación en string del objeto Commission.
        
        Returns:
            str: Representación legible de la comisión con tipo y monto
        """
        return f'<Commission {self.commission_type}: ${self.amount}>'
    
    @property
    def user_name(self):
        """
        Obtiene el nombre completo del usuario beneficiario de la comisión.
        
        Returns:
            str: Nombre completo del usuario o 'Desconocido' si no existe
        """
        return self.user.full_name if self.user else 'Desconocido'
    
    @property
    def reel_title(self):
        """
        Obtiene el título del reel que generó esta comisión.
        
        Returns:
            str: Título del reel o 'Desconocido' si no existe
        """
        return self.reel.title if self.reel else 'Desconocido'
    
    def approve(self):
        """
        Aprueba la comisión para su posterior pago.
        
        Cambia el estado a APPROVED y registra la fecha de aprobación.
        Una vez aprobada, la comisión puede ser procesada para pago.
        
        Note:
            Realiza commit automático a la base de datos
        """
        self.status      = CommissionStatus.APPROVED
        self.approved_at = datetime.utcnow()
        db.session.commit()
    
    def mark_as_paid(self, payment_reference=None, payment_method=None):
        """
        Marca la comisión como pagada y registra los detalles del pago.
        
        Args:
            payment_reference (str, opcional): Referencia o ID de la transacción
            payment_method (str, opcional): Método de pago utilizado
        
        Note:
            Realiza commit automático a la base de datos
        """
        self.status  = CommissionStatus.PAID
        self.paid_at = datetime.now()
        
        # Actualizar información de pago si se proporciona
        if payment_reference:
            self.payment_reference = payment_reference
        if payment_method:
            self.payment_method = payment_method
        db.session.commit()
    
    def cancel(self, reason=None):
        """
        Cancela la comisión con una razón opcional.
        
        Args:
            reason (str, opcional): Motivo de la cancelación
        
        Note:
            Una vez cancelada, la comisión no puede ser reactivada.
            Realiza commit automático a la base de datos
        """
        self.status = CommissionStatus.CANCELLED
        # Agregar razón de cancelación a las notas
        if reason:
            self.notes = f"Cancelada: {reason}"
        db.session.commit()
    
    @staticmethod
    def get_user_total_earnings(user_id, status=None):
        """
        Calcula el total de ganancias de un usuario específico.
        
        Args:
            user_id (int): ID del usuario para calcular ganancias
            status (CommissionStatus, opcional): Filtrar por estado específico
        
        Returns:
            float: Suma total de todas las comisiones del usuario
        
        Example:
            >>> total_pagado = Commission.get_user_total_earnings(123, CommissionStatus.PAID)
            >>> total_general = Commission.get_user_total_earnings(123)
        """
        # Construir query base filtrada por usuario
        query = Commission.query.filter_by(user_id=user_id)
        # Aplicar filtro de estado si se especifica
        if status:
            query = query.filter_by(status = status)
        return sum([c.amount for c in query.all()])
    
    @staticmethod
    def get_monthly_earnings(user_id, year, month):
        """
        Obtiene las ganancias de un usuario para un mes específico.
        
        Args:
            user_id (int): ID del usuario
            year (int): Año a consultar
            month (int): Mes a consultar (1-12)
        
        Returns:
            float: Suma de comisiones creadas en el mes especificado
        
        Example:
            >>> ganancias_enero = Commission.get_monthly_earnings(123, 2024, 1)
        """
        # Calcular rango de fechas para el mes
        from calendar import monthrange
        
        start_date = datetime(year, month, 1)
        last_day   = monthrange(year, month)[1]
        end_date   = datetime(year, month, last_day, 23, 59, 59)
        
        # Filtrar comisiones por usuario y rango de fechas
        query = Commission.query.filter_by(user_id=user_id).filter(
            Commission.created_at >= start_date,
            Commission.created_at <= end_date
        )
        
        return sum([c.amount for c in query.all()])
    
    def to_dict(self):
        """
        Convierte el objeto Commission a un diccionario para serialización JSON.
        
        Returns:
            dict: Diccionario con todos los campos importantes de la comisión
        
        Note:
            Las fechas se convierten a formato ISO para compatibilidad JSON
        """
        return {
            'id'                : self.id,
            'user_id'           : self.user_id,
            'user_name'         : self.user_name,
            'reel_id'           : self.reel_id,
            'reel_title'        : self.reel_title,
            'commission_type'   : self.commission_type,
            'amount'            : self.amount,
            'percentage'        : self.percentage,
            'status'            : self.status.value,
            'currency'          : self.currency,
            'payment_method'    : self.payment_method,
            'payment_reference' : self.payment_reference,
            'notes'             : self.notes,
            'created_at'        : self.created_at.isoformat() if self.created_at else None,
            'approved_at'       : self.approved_at.isoformat() if self.approved_at else None,
            'paid_at'           : self.paid_at.isoformat() if self.paid_at else None
        }