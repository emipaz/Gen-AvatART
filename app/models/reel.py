from app import db
from datetime import datetime
from enum import Enum

class ReelStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Reel(db.Model):
    """Modelo para reels generados"""
    __tablename__ = 'reels'
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Relaciones
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    avatar_id = db.Column(db.Integer, db.ForeignKey('avatars.id'), nullable=False)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Información del reel
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    script = db.Column(db.Text, nullable=False)  # Texto que dirá el avatar
    duration = db.Column(db.Float)  # Duración en segundos
    
    # HeyGen data
    heygen_video_id = db.Column(db.String(100), unique=True)
    video_url = db.Column(db.String(500))
    thumbnail_url = db.Column(db.String(500))
    
    # Estado y configuración
    status = db.Column(db.Enum(ReelStatus), nullable=False, default=ReelStatus.PENDING)
    is_public = db.Column(db.Boolean, default=False)
    
    # Configuración de video
    resolution = db.Column(db.String(20), default='1080p')  # 720p, 1080p, 4k
    background_type = db.Column(db.String(50), default='default')  # default, custom, green_screen
    background_url = db.Column(db.String(500))  # URL del background si es custom
    
    # Metadatos y configuración
    metadata = db.Column(db.JSON)  # Configuración adicional del video
    tags = db.Column(db.String(500))  # Tags separados por comas
    category = db.Column(db.String(50))  # Categoría del contenido
    
    # Información de procesamiento
    processing_started_at = db.Column(db.DateTime)
    processing_completed_at = db.Column(db.DateTime)
    error_message = db.Column(db.Text)  # Mensaje de error si falla
    
    # Estadísticas
    view_count = db.Column(db.Integer, default=0)
    download_count = db.Column(db.Integer, default=0)
    
    # Configuración de monetización
    cost = db.Column(db.Float, default=0.0)  # Costo de producción
    price = db.Column(db.Float, default=0.0)  # Precio de venta si aplica
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    approved_at = db.Column(db.DateTime)
    published_at = db.Column(db.DateTime)
    
    # Relaciones
    approved_by = db.relationship('User', foreign_keys=[approved_by_id], backref='approved_reels')
    commissions = db.relationship('Commission', backref='reel', lazy='dynamic')
    
    def __repr__(self):
        return f'<Reel {self.title}>'
    
    @property
    def creator_name(self):
        return self.creator.full_name if self.creator else 'Desconocido'
    
    @property
    def approver_name(self):
        return self.approved_by.full_name if self.approved_by else None
    
    @property
    def avatar_name(self):
        return self.avatar.name if self.avatar else 'Desconocido'
    
    @property
    def tag_list(self):
        """Devuelve las tags como lista"""
        return [tag.strip() for tag in (self.tags or '').split(',') if tag.strip()]
    
    @property
    def processing_time(self):
        """Calcula el tiempo de procesamiento"""
        if self.processing_started_at and self.processing_completed_at:
            return (self.processing_completed_at - self.processing_started_at).total_seconds()
        return None
    
    def set_tags(self, tag_list):
        """Establece las tags desde una lista"""
        self.tags = ', '.join([tag.strip() for tag in tag_list if tag.strip()])
    
    def start_processing(self):
        """Marca el inicio del procesamiento"""
        self.status = ReelStatus.PROCESSING
        self.processing_started_at = datetime.utcnow()
        db.session.commit()
    
    def complete_processing(self, video_url, thumbnail_url=None):
        """Marca el procesamiento como completado"""
        self.status = ReelStatus.COMPLETED
        self.processing_completed_at = datetime.utcnow()
        self.video_url = video_url
        if thumbnail_url:
            self.thumbnail_url = thumbnail_url
        db.session.commit()
    
    def fail_processing(self, error_message):
        """Marca el procesamiento como fallido"""
        self.status = ReelStatus.FAILED
        self.processing_completed_at = datetime.utcnow()
        self.error_message = error_message
        db.session.commit()
    
    def approve(self, approved_by_user):
        """Aprueba el reel"""
        self.status = ReelStatus.APPROVED
        self.approved_by_id = approved_by_user.id
        self.approved_at = datetime.utcnow()
        db.session.commit()
        
        # Generar comisiones cuando se aprueba
        self.generate_commissions()
    
    def reject(self):
        """Rechaza el reel"""
        self.status = ReelStatus.REJECTED
        db.session.commit()
    
    def publish(self):
        """Publica el reel"""
        self.is_public = True
        self.published_at = datetime.utcnow()
        db.session.commit()
    
    def increment_views(self):
        """Incrementa el contador de visualizaciones"""
        self.view_count += 1
        db.session.commit()
    
    def increment_downloads(self):
        """Incrementa el contador de descargas"""
        self.download_count += 1
        db.session.commit()
    
    def generate_commissions(self):
        """Genera comisiones para la cadena de usuarios"""
        from app.models.commission import Commission
        from app.models.user import UserRole
        
        if not self.cost or self.cost <= 0:
            return
        
        # Comisión para el productor
        producer = self.creator.get_producer()
        if producer:
            producer_commission = Commission(
                user_id=producer.user_id,
                reel_id=self.id,
                commission_type='producer',
                amount=self.cost * producer.commission_rate,
                percentage=producer.commission_rate * 100
            )
            db.session.add(producer_commission)
        
        # Comisión para el subproductor (si aplica)
        if self.creator.role == UserRole.SUBPRODUCER:
            subproducer_rate = 0.10  # 10% por defecto
            subproducer_commission = Commission(
                user_id=self.creator_id,
                reel_id=self.id,
                commission_type='subproducer',
                amount=self.cost * subproducer_rate,
                percentage=subproducer_rate * 100
            )
            db.session.add(subproducer_commission)
        
        # Comisión para el afiliado (si aplica)
        if self.creator.role == UserRole.AFFILIATE:
            affiliate_rate = 0.05  # 5% por defecto
            affiliate_commission = Commission(
                user_id=self.creator_id,
                reel_id=self.id,
                commission_type='affiliate',
                amount=self.cost * affiliate_rate,
                percentage=affiliate_rate * 100
            )
            db.session.add(affiliate_commission)
        
        db.session.commit()
    
    def to_dict(self):
        """Convertir a diccionario para JSON"""
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'script': self.script,
            'duration': self.duration,
            'status': self.status.value,
            'is_public': self.is_public,
            'resolution': self.resolution,
            'background_type': self.background_type,
            'creator_name': self.creator_name,
            'approver_name': self.approver_name,
            'avatar_name': self.avatar_name,
            'category': self.category,
            'tags': self.tag_list,
            'view_count': self.view_count,
            'download_count': self.download_count,
            'cost': self.cost,
            'price': self.price,
            'video_url': self.video_url,
            'thumbnail_url': self.thumbnail_url,
            'processing_time': self.processing_time,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'approved_at': self.approved_at.isoformat() if self.approved_at else None,
            'published_at': self.published_at.isoformat() if self.published_at else None,
            'processing_started_at': self.processing_started_at.isoformat() if self.processing_started_at else None,
            'processing_completed_at': self.processing_completed_at.isoformat() if self.processing_completed_at else None
        }