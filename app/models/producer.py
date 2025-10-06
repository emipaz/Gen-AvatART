from app import db
from datetime import datetime
from enum import Enum

class Producer(db.Model):
    """Modelo para perfil de productor"""
    __tablename__ = 'producers'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    
    # Configuración de HeyGen
    heygen_api_key = db.Column(db.String(255), nullable=False)
    heygen_api_key_encrypted = db.Column(db.Text)  # Versión encriptada
    api_key_status = db.Column(db.String(20), default='pending')  # pending, active, invalid
    
    # Información comercial
    company_name = db.Column(db.String(100))
    business_type = db.Column(db.String(50))
    website = db.Column(db.String(200))
    
    # Configuración de comisiones
    commission_rate = db.Column(db.Float, default=0.15)  # 15% por defecto
    payment_method = db.Column(db.String(50))  # paypal, bank_transfer, etc.
    payment_details = db.Column(db.Text)  # JSON con detalles de pago
    
    # Límites y configuración
    max_subproducers = db.Column(db.Integer, default=10)
    max_affiliates = db.Column(db.Integer, default=100)
    monthly_api_limit = db.Column(db.Integer, default=1000)
    
    # Estadísticas
    total_reels_created = db.Column(db.Integer, default=0)
    total_earnings = db.Column(db.Float, default=0.0)
    api_calls_this_month = db.Column(db.Integer, default=0)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_api_call = db.Column(db.DateTime)
    
    # Relaciones
    avatars = db.relationship('Avatar', backref='producer', lazy='dynamic')
    subproducers = db.relationship('User', 
                                 foreign_keys='User.invited_by_id',
                                 primaryjoin='and_(Producer.user_id==User.invited_by_id, User.role=="subproducer")',
                                 lazy='dynamic')
    affiliates = db.relationship('User',
                               foreign_keys='User.invited_by_id', 
                               primaryjoin='and_(Producer.user_id==User.invited_by_id, User.role=="affiliate")',
                               lazy='dynamic')
    
    def __repr__(self):
        return f'<Producer {self.user.username}>'
    
    @property
    def current_subproducers_count(self):
        return self.subproducers.filter_by(status='active').count()
    
    @property
    def current_affiliates_count(self):
        return self.affiliates.filter_by(status='active').count()
    
    def can_add_subproducer(self):
        """Verifica si puede agregar más subproductores"""
        return self.current_subproducers_count < self.max_subproducers
    
    def can_add_affiliate(self):
        """Verifica si puede agregar más afiliados"""
        return self.current_affiliates_count < self.max_affiliates
    
    def has_api_quota(self):
        """Verifica si tiene cuota de API disponible"""
        return self.api_calls_this_month < self.monthly_api_limit
    
    def increment_api_usage(self):
        """Incrementa el uso de API"""
        self.api_calls_this_month += 1
        self.last_api_call = datetime.utcnow()
        db.session.commit()
    
    def reset_monthly_usage(self):
        """Resetea el uso mensual de API"""
        self.api_calls_this_month = 0
        db.session.commit()
    
    def validate_api_key(self):
        """Valida la API key de HeyGen"""
        # TODO: Implementar validación real con HeyGen API
        from app.services.heygen_service import HeyGenService
        service = HeyGenService(self.heygen_api_key)
        is_valid = service.validate_api_key()
        
        self.api_key_status = 'active' if is_valid else 'invalid'
        db.session.commit()
        
        return is_valid
    
    def to_dict(self):
        """Convertir a diccionario para JSON"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'company_name': self.company_name,
            'business_type': self.business_type,
            'website': self.website,
            'commission_rate': self.commission_rate,
            'api_key_status': self.api_key_status,
            'max_subproducers': self.max_subproducers,
            'max_affiliates': self.max_affiliates,
            'current_subproducers': self.current_subproducers_count,
            'current_affiliates': self.current_affiliates_count,
            'total_reels_created': self.total_reels_created,
            'total_earnings': self.total_earnings,
            'api_calls_this_month': self.api_calls_this_month,
            'monthly_api_limit': self.monthly_api_limit,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }