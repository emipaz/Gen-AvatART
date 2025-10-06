from app import db
from datetime import datetime
from enum import Enum

class CommissionStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    PAID = "paid"
    CANCELLED = "cancelled"

class Commission(db.Model):
    """Modelo para comisiones generadas"""
    __tablename__ = 'commissions'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relaciones
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reel_id = db.Column(db.Integer, db.ForeignKey('reels.id'), nullable=False)
    
    # Información de la comisión
    commission_type = db.Column(db.String(50), nullable=False)  # producer, subproducer, affiliate
    amount = db.Column(db.Float, nullable=False)
    percentage = db.Column(db.Float, nullable=False)  # Porcentaje aplicado
    
    # Estado y procesamiento
    status = db.Column(db.Enum(CommissionStatus), nullable=False, default=CommissionStatus.PENDING)
    currency = db.Column(db.String(3), default='USD')
    
    # Información de pago
    payment_method = db.Column(db.String(50))  # paypal, bank_transfer, etc.
    payment_reference = db.Column(db.String(100))  # ID de transacción
    payment_details = db.Column(db.JSON)  # Detalles adicionales del pago
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    approved_at = db.Column(db.DateTime)
    paid_at = db.Column(db.DateTime)
    
    # Metadatos
    notes = db.Column(db.Text)  # Notas adicionales
    
    def __repr__(self):
        return f'<Commission {self.commission_type}: ${self.amount}>'
    
    @property
    def user_name(self):
        return self.user.full_name if self.user else 'Desconocido'
    
    @property
    def reel_title(self):
        return self.reel.title if self.reel else 'Desconocido'
    
    def approve(self):
        """Aprueba la comisión"""
        self.status = CommissionStatus.APPROVED
        self.approved_at = datetime.utcnow()
        db.session.commit()
    
    def mark_as_paid(self, payment_reference=None, payment_method=None):
        """Marca la comisión como pagada"""
        self.status = CommissionStatus.PAID
        self.paid_at = datetime.utcnow()
        if payment_reference:
            self.payment_reference = payment_reference
        if payment_method:
            self.payment_method = payment_method
        db.session.commit()
    
    def cancel(self, reason=None):
        """Cancela la comisión"""
        self.status = CommissionStatus.CANCELLED
        if reason:
            self.notes = f"Cancelada: {reason}"
        db.session.commit()
    
    @staticmethod
    def get_user_total_earnings(user_id, status=None):
        """Obtiene el total de ganancias de un usuario"""
        query = Commission.query.filter_by(user_id=user_id)
        if status:
            query = query.filter_by(status=status)
        return sum([c.amount for c in query.all()])
    
    @staticmethod
    def get_monthly_earnings(user_id, year, month):
        """Obtiene las ganancias de un mes específico"""
        from calendar import monthrange
        
        start_date = datetime(year, month, 1)
        last_day = monthrange(year, month)[1]
        end_date = datetime(year, month, last_day, 23, 59, 59)
        
        query = Commission.query.filter_by(user_id=user_id).filter(
            Commission.created_at >= start_date,
            Commission.created_at <= end_date
        )
        
        return sum([c.amount for c in query.all()])
    
    def to_dict(self):
        """Convertir a diccionario para JSON"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'user_name': self.user_name,
            'reel_id': self.reel_id,
            'reel_title': self.reel_title,
            'commission_type': self.commission_type,
            'amount': self.amount,
            'percentage': self.percentage,
            'status': self.status.value,
            'currency': self.currency,
            'payment_method': self.payment_method,
            'payment_reference': self.payment_reference,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'paid_at': self.paid_at.isoformat() if self.paid_at else None
        }