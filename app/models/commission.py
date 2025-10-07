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
    
    Estados disponibles (ACTUALIZADO según README):
        PENDING   : Comisión creada, pendiente de aprobación
        APPROVED  : Comisión aprobada, lista para pagar
        PAID      : Comisión pagada al usuario
        CANCELLED : Comisión cancelada por algún motivo
        REFUNDED  : Comisión reembolsada (para Stripe)
    """
    PENDING   = "pending"    # Pendiente de aprobación 
    APPROVED  = "approved"   # Aprobada para pago 
    PAID      = "paid"       # Pagada al usuario 
    CANCELLED = "cancelled"  # Cancelada 
    REFUNDED  = "refunded"   # Para reembolsos de Stripe

class Commission(db.Model):
    """"
    Modelo de datos para el sistema de comisiones de la aplicación.
    
    Este modelo gestiona las comisiones generadas por la creación de contenido,
    incluyendo su procesamiento, aprobación y pago a los diferentes tipos de usuarios
    (productores, subproductores, afiliados).
    
    Attributes:
        id (int)                      : Identificador único de la comisión
        user_id (int)                 : ID del usuario que recibe la comisión
        producer_id (int)             : ID del productor que genera la transacción
        reel_id (int)                 : ID del reel que generó la comisión
        commission_type (str)         : Tipo de comisión (producer, subproducer, affiliate)
        amount (float)                : Monto de la comisión en la moneda especificada
        percentage (float)            : Porcentaje aplicado para calcular la comisión
        application_fee_amount (float): Monto exacto del application_fee
        stripe_payment_intent_id (str): ID del Payment Intent de Stripe
        status (CommissionStatus)     : Estado actual de la comisión
        currency (str)                : Código de moneda (USD, EUR, etc.)
        payment_method (str)          : Método de pago utilizado
        payment_reference (str)       : Referencia o ID de la transacción de pago
        payment_details (dict)        : Detalles adicionales del pago en formato JSON
        created_at (datetime)         : Fecha de creación de la comisión
        approved_at (datetime)        : Fecha de aprobación
        paid_at (datetime)            : Fecha de pago
        notes (str)                   : Notas adicionales sobre la comisión
    """
    __tablename__ = 'commissions'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relaciones
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable = False)
    reel_id = db.Column(db.Integer, db.ForeignKey('reels.id'), nullable = False)
    # Relación con productor
    producer_id = db.Column(db.Integer, db.ForeignKey('producers.id'), nullable = True)  # Para Stripe Connect
    
    # Información de la comisión
    commission_type = db.Column(db.String(50), nullable = False)  # producer, subproducer, affiliate
    amount          = db.Column(db.Float, nullable = False)
    percentage      = db.Column(db.Float, nullable = False)  # Porcentaje aplicado
    
    
    # Integración con Stripe Connect
    application_fee_amount   = db.Column(db.Float, nullable = True)    # Monto exacto del application_fee
    stripe_payment_intent_id = db.Column(db.String(100), index = True) # ID del Payment Intent de Stripe
    
    
    # Estado y procesamiento
    status   = db.Column(db.Enum(CommissionStatus), nullable = False, default = CommissionStatus.PENDING)
    currency = db.Column(db.String(3), default = 'USD')
    
    # Información de pago
    payment_method    = db.Column(db.String(50))  # paypal, bank_transfer, etc.
    payment_reference = db.Column(db.String(100)) # ID de transacción
    payment_details   = db.Column(db.JSON)        # Detalles adicionales del pago
    
    # Metadatos adicionales
    meta_data = db.Column(db.JSON)  # Para información adicional de Stripe y contexto
    
    
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
        # ✅ ACTUALIZADO - Mostrar application_fee si existe
        if self.application_fee_amount:
            return f'<Commission {self.commission_type}: ${self.application_fee_amount} (fee)>'
        return f'<Commission {self.commission_type}: ${self.amount}>'  # ✅ MANTENER fallback
    
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
    
    @property
    def producer_name(self):
        """
        Obtiene el nombre de la empresa del productor asociado.
        
        Returns:
            str: Nombre de la empresa o 'N/A' si no existe
        """
        return self.producer.company_name if self.producer else 'N/A'
    
    
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
    
    def mark_paid_by_stripe(self, stripe_data=None):
        """
        Marca la comisión como pagada por Stripe.
        
        Args:
            stripe_data (dict, opcional): Datos adicionales del webhook de Stripe
            
        Note:
            ✅ NUEVO - Para procesar webhooks de Stripe
        """
        self.status = CommissionStatus.PAID
        self.paid_at = datetime.utcnow()
        self.payment_method = 'stripe'
        
        if stripe_data:
            if not self.metadata:
                self.metadata = {}
            self.metadata['stripe_webhook'] = stripe_data
        db.session.commit()
    
    def mark_failed_by_stripe(self, error_message=None):
        """
        Marca la comisión como fallida por Stripe.
        
        Args:
            error_message (str, opcional): Mensaje de error
            
        Note:
            ✅ NUEVO - Para manejar fallos de Stripe
        """
        self.status = CommissionStatus.CANCELLED  # Usamos CANCELLED para fallos
        if error_message:
            if not self.metadata:
                self.metadata = {}
            self.metadata['error'] = error_message
            self.notes = f"Error de Stripe: {error_message}"
        db.session.commit()
    
    def refund_by_stripe(self, refund_data=None):
        """
        Marca la comisión como reembolsada por Stripe.
        
        Args:
            refund_data (dict, opcional): Datos del reembolso
            
        Note:
            ✅ NUEVO - Para manejar reembolsos
        """
        self.status = CommissionStatus.REFUNDED
        if refund_data:
            if not self.metadata:
                self.metadata = {}
            self.metadata['refund'] = refund_data
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
    def create_from_stripe_charge(user_id, producer_id, payment_intent_id, amount, fee_amount, 
                                  commission_type='platform_fee', **kwargs):
        """
        Crea una comisión desde un cargo de Stripe Connect.
        
        Args:
            user_id (int): ID del usuario
            producer_id (int): ID del productor
            payment_intent_id (str): ID del Payment Intent
            amount (float): Monto total
            fee_amount (float): Monto del application fee
            commission_type (str): Tipo de comisión
            **kwargs: Campos adicionales (reel_id, etc.)
            
        Returns:
            Commission: Nueva instancia de comisión
            
        Note:
            ✅ NUEVO - Factory method para crear desde Stripe
        """
        # Calcular porcentaje si es posible
        percentage = (fee_amount / amount * 100) if amount > 0 else 0
        
        commission = Commission(
            user_id                  = user_id,
            producer_id              = producer_id,
            stripe_payment_intent_id = payment_intent_id,
            amount                   = amount,
            application_fee_amount   = fee_amount,
            percentage               = percentage,
            commission_type          = commission_type,
            status                   = CommissionStatus.PENDING,
            payment_method           = 'stripe',
            **kwargs
        )
        
        db.session.add(commission)
        db.session.commit()
        return commission
    
    
    
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
            ✅ ACTUALIZADO - Incluye nuevos campos según README
        """
        return {
            'id'                       : self.id,                                                    # ✅ MANTENER
            'user_id'                  : self.user_id,                                               # ✅ MANTENER
            'user_name'                : self.user_name,                                             # ✅ MANTENER
            'producer_id'              : self.producer_id,                                           # ✅ NUEVO
            'producer_name'            : self.producer_name,                                         # ✅ NUEVO
            'reel_id'                  : self.reel_id,                                               # ✅ MANTENER
            'reel_title'               : self.reel_title,                                            # ✅ MANTENER
            'commission_type'          : self.commission_type,                                       # ✅ MANTENER
            'amount'                   : self.amount,                                                # ✅ MANTENER
            'percentage'               : self.percentage,                                            # ✅ MANTENER
            'application_fee_amount'   : self.application_fee_amount,                                # ✅ NUEVO
            'stripe_payment_intent_id' : self.stripe_payment_intent_id,                             # ✅ NUEVO
            'status'                   : self.status.value,                                          # ✅ MANTENER
            'currency'                 : self.currency,                                              # ✅ MANTENER
            'payment_method'           : self.payment_method,                                        # ✅ MANTENER
            'payment_reference'        : self.payment_reference,                                     # ✅ MANTENER
            'metadata'                 : self.metadata or {},                                        # ✅ NUEVO
            'is_stripe_processed'      : self.is_stripe_processed(),                                 # ✅ NUEVO
            'notes'                    : self.notes,                                                 # ✅ MANTENER
            'created_at'               : self.created_at.isoformat() if self.created_at else None,  # ✅ MANTENER
            'approved_at'              : self.approved_at.isoformat() if self.approved_at else None,# ✅ MANTENER
            'paid_at'                  : self.paid_at.isoformat() if self.paid_at else None         # ✅ MANTENER
        }