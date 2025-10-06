"""
Módulo de modelo Reel para la aplicación Gem-AvatART.

Este módulo define el modelo de datos para los reels/videos generados mediante
la integración con HeyGen. Los reels son videos creados usando avatares digitales
que pronuncian un script específico y pueden incluir fondos personalizados.

El módulo incluye:
    - Enum ReelStatus: Estados posibles de un reel durante su ciclo de vida
    - Clase Reel: Modelo principal para gestión de videos generados

Funcionalidades principales:
    - Gestión del ciclo de vida de videos (creación, procesamiento, aprobación)
    - Integración con HeyGen para generación de videos
    - Sistema de comisiones automático al aprobar reels
    - Control de configuraciones de video (resolución, fondos, etc.)
    - Estadísticas de visualización y descarga
    - Sistema de etiquetas y categorización
    - Gestión de monetización y costos

Flujo de trabajo típico:
    1. PENDING: Reel creado, pendiente de revisión
    2. PROCESSING: Enviado a HeyGen para generación
    3. COMPLETED: Video generado exitosamente
    4. APPROVED: Aprobado por administrador (genera comisiones)
    5. Publicado para visualización pública
"""


from app import db
from datetime import datetime
from enum import Enum

class ReelStatus(Enum):
    """
    Enumeración que define los estados posibles de un reel durante su ciclo de vida.
    
    Estados disponibles:
        PENDING    : Reel creado, pendiente de revisión administrativa
        APPROVED   : Reel aprobado por administrador, listo para procesamiento
        REJECTED   : Reel rechazado por administrador
        PROCESSING : Reel en proceso de generación en HeyGen
        COMPLETED  : Video generado exitosamente por HeyGen
        FAILED     : Falló la generación del video en HeyGen
    """
    PENDING    = "pending"     # Pendiente de revisión
    APPROVED   = "approved"    # Aprobado para procesamiento
    REJECTED   = "rejected"    # Rechazado por administrador
    PROCESSING = "processing"  # En proceso de generación
    COMPLETED  = "completed"   # Video generado exitosamente
    FAILED     = "failed"      # Falló la generación

class Reel(db.Model):
    """
    Modelo de datos para reels/videos generados con avatares digitales.
    
    Este modelo gestiona todo el ciclo de vida de los videos creados con HeyGen,
    desde su creación inicial hasta su publicación final, incluyendo el sistema
    de comisiones, estadísticas y configuraciones técnicas.
    
    Attributes:
        id (int)                           : Identificador único del reel
        creator_id (int)                   : ID del usuario que creó el reel
        avatar_id (int)                    : ID del avatar utilizado para el video
        approved_by_id (int)               : ID del usuario que aprobó el reel
        title (str)                        : Título del reel
        description (str)                  : Descripción detallada del contenido
        script (str)                       : Texto que pronunciará el avatar
        duration (float)                   : Duración del video en segundos
        heygen_video_id (str)              : ID único del video en HeyGen
        video_url (str)                    : URL del video generado
        thumbnail_url (str)                : URL de la imagen miniatura
        status (ReelStatus)                : Estado actual del reel
        is_public (bool)                   : Si el reel es visible públicamente
        resolution (str)                   : Resolución del video (720p, 1080p, 4k)
        background_type (str)              : Tipo de fondo (default, custom, green_screen)
        background_url (str)               : URL del fondo personalizado
        meta_data (dict)                   : Configuración adicional en formato JSON
        tags (str)                         : Etiquetas separadas por comas
        category (str)                     : Categoría del contenido
        processing_started_at (datetime)   : Inicio del procesamiento
        processing_completed_at (datetime) : Fin del procesamiento
        error_message (str)                : Mensaje de error si falla
        view_count (int)                   : Contador de visualizaciones
        download_count (int)               : Contador de descargas
        cost (float)                       : Costo de producción del reel
        price (float)                      : Precio de venta si aplica
        created_at (datetime)              : Fecha de creación
        updated_at (datetime)              : Fecha de última actualización
        approved_at (datetime)             : Fecha de aprobación
        published_at (datetime)            : Fecha de publicación
    """
    __tablename__ = 'reels'
    
    # Clave primaria
    id = db.Column(db.Integer, primary_key=True)
    
    # Relaciones con otras tablas
    creator_id     = db.Column(db.Integer, db.ForeignKey('users.id'),   nullable = False)
    avatar_id      = db.Column(db.Integer, db.ForeignKey('avatars.id'), nullable = False)
    approved_by_id = db.Column(db.Integer, db.ForeignKey('users.id'),   nullable = True)
    
    # Información básica del reel
    title       = db.Column(db.String(200), nullable = False)  # Título del video
    description = db.Column(db.Text)                         # Descripción detallada
    script      = db.Column(db.Text, nullable = False)         # Texto que dirá el avatar
    duration    = db.Column(db.Float)                        # Duración en segundos
    
    # Datos de integración con HeyGen
    heygen_video_id = db.Column(db.String(100), unique = True)  # ID único en HeyGen
    video_url       = db.Column(db.String(500))               # URL del video generado
    thumbnail_url   = db.Column(db.String(500))               # URL de la miniatura
    
    # Estado y configuración de acceso
    status    = db.Column(db.Enum(ReelStatus), nullable = False, default = ReelStatus.PENDING)
    is_public = db.Column(db.Boolean, default = False)  # Visibilidad pública
    
    # Configuración técnica del video
    resolution      = db.Column(db.String(20), default = '1080p')    # Resolución: 720p, 1080p, 4k
    background_type = db.Column(db.String(50), default = 'default')  # Tipo de fondo
    background_url  = db.Column(db.String(500))                    # URL del fondo personalizado
    
    # Metadatos y categorización
    meta_data = db.Column(db.JSON)         # Configuración adicional del video
    tags      = db.Column(db.String(500))  # Etiquetas separadas por comas
    category  = db.Column(db.String(50))   # Categoría del contenido
    
    # Información de procesamiento y errores
    processing_started_at   = db.Column(db.DateTime)  # Inicio del procesamiento
    processing_completed_at = db.Column(db.DateTime)  # Fin del procesamiento
    error_message          = db.Column(db.Text)       # Mensaje de error si falla
    
    # Estadísticas de uso
    view_count     = db.Column(db.Integer, default = 0)  # Contador de visualizaciones
    download_count = db.Column(db.Integer, default = 0)  # Contador de descargas

    # Configuración de monetización
    cost  = db.Column(db.Float, default = 0.0)  # Costo de producción
    price = db.Column(db.Float, default = 0.0)  # Precio de venta si aplica

    # Campos de auditoría y timestamps
    created_at   = db.Column(db.DateTime, default = datetime.utcnow)                           # Fecha de creación
    updated_at   = db.Column(db.DateTime, default = datetime.utcnow, onupdate = datetime.utcnow) # Última actualización
    approved_at  = db.Column(db.DateTime)                                                    # Fecha de aprobación
    published_at = db.Column(db.DateTime)                                                    # Fecha de publicación
    
    # Definición de relaciones con otros modelos
    approved_by = db.relationship('User',       foreign_keys = [approved_by_id], backref = 'approved_reels')
    commissions = db.relationship('Commission', backref = 'reel', lazy = 'dynamic')
    
    def __repr__(self):
        """
        Representación en string del objeto Reel.
        
        Returns:
            str: Representación legible del reel con su título
        """
        return f'<Reel {self.title}>'
    
    @property
    def creator_name(self):
        """
        Obtiene el nombre completo del creador del reel.
        
        Returns:
            str: Nombre completo del usuario creador o 'Desconocido'
        """
        return self.creator.full_name if self.creator else 'Desconocido'
    
    @property
    def approver_name(self):
        """
        Obtiene el nombre completo del usuario que aprobó el reel.
        
        Returns:
            str or None: Nombre completo del aprobador o None si no está aprobado
        """
        return self.approved_by.full_name if self.approved_by else None
    
    @property
    def avatar_name(self):
        """
        Obtiene el nombre del avatar utilizado en el reel.
        
        Returns:
            str: Nombre del avatar o 'Desconocido' si no existe
        """
        return self.avatar.name if self.avatar else 'Desconocido'
    
    @property
    def tag_list(self):
        """
        Convierte el string de tags en una lista.
        
        Returns:
            list: Lista de etiquetas limpias (sin espacios extra)
        """
        return [tag.strip() 
                for tag in (self.tags or '').split(',') 
                    if tag.strip()
                ]
    
    @property
    def processing_time(self):
        """
        Calcula el tiempo total de procesamiento del reel.
        
        Returns:
            float or None: Tiempo de procesamiento en segundos, None si no completado
        """
        if self.processing_started_at and self.processing_completed_at:
            return (self.processing_completed_at - self.processing_started_at).total_seconds()
        return None
    
    def set_tags(self, tag_list):
        """
        Establece las etiquetas desde una lista.
        
        Args:
            tag_list (list): Lista de strings con las etiquetas
        """
        self.tags = ', '.join([tag.strip() for tag in tag_list if tag.strip()])
    
    def start_processing(self):
        """
        Marca el inicio del procesamiento del reel en HeyGen.
        
        Cambia el estado a PROCESSING y registra el timestamp de inicio.
        Este método se llama cuando se envía el reel a HeyGen para generación.
        
        Note:
            Realiza commit automático a la base de datos
        """
        self.status = ReelStatus.PROCESSING
        self.processing_started_at = datetime.utcnow()
        db.session.commit()
    
    def complete_processing(self, video_url, thumbnail_url=None):
        """
        Marca el procesamiento como completado exitosamente.
        
        Args:
            video_url (str): URL del video generado por HeyGen
            thumbnail_url (str, opcional): URL de la imagen miniatura
        
        Note:
            Cambia el estado a COMPLETED y registra las URLs del contenido generado.
            Realiza commit automático a la base de datos
        """
        self.status                  = ReelStatus.COMPLETED
        self.processing_completed_at = datetime.utcnow()
        self.video_url               = video_url
        if thumbnail_url:
            self.thumbnail_url = thumbnail_url
        db.session.commit()
    
    def fail_processing(self, error_message):
        """
        Marca el procesamiento como fallido.
        
        Args:
            error_message (str): Descripción del error ocurrido durante el procesamiento
        
        Note:
            Cambia el estado a FAILED y registra el mensaje de error.
            Realiza commit automático a la base de datos
        """
        self.status                   = ReelStatus.FAILED
        self.processing_completed_at  = datetime.utcnow()
        self.error_message            = error_message
        db.session.commit()
    
    def approve(self, approved_by_user):
        """
        Aprueba el reel para su uso y genera las comisiones correspondientes.
        
        Args:
            approved_by_user (User): Usuario que aprueba el reel
        
        Note:
            Cambia el estado a APPROVED, registra quién y cuándo lo aprobó,
            y automáticamente genera las comisiones para la cadena de usuarios.
            Realiza commit automático a la base de datos
        """
        self.status          = ReelStatus.APPROVED
        self.approved_by_id  = approved_by_user.id
        self.approved_at     = datetime.utcnow()
        db.session.commit()
        
        # Generar comisiones cuando se aprueba
        self.generate_commissions()
    
    def reject(self):
        """
        Rechaza el reel.
        
        Note:
            Cambia el estado a REJECTED. El reel no podrá ser procesado ni usado.
            Realiza commit automático a la base de datos
        """
        self.status = ReelStatus.REJECTED
        db.session.commit()
    
    def publish(self):
        """
        Publica el reel para acceso público.
        
        Note:
            Marca el reel como público y registra la fecha de publicación.
            Realiza commit automático a la base de datos
        """
        self.is_public    = True
        self.published_at = datetime.utcnow()
        db.session.commit()
    
    def increment_views(self):
        """
        Incrementa el contador de visualizaciones del reel.
        
        Note:
            Se debe llamar cada vez que un usuario visualiza el reel.
            Realiza commit automático a la base de datos
        """
        self.view_count += 1
        db.session.commit()
    
    def increment_downloads(self):
        """
        Incrementa el contador de descargas del reel.
        
        Note:
            Se debe llamar cada vez que un usuario descarga el reel.
            Realiza commit automático a la base de datos
        """
        self.download_count += 1
        db.session.commit()
    
    def generate_commissions(self):
        """
        Genera comisiones automáticamente para la cadena de usuarios.
        
        Crea comisiones para el productor, subproductor y/o afiliado según
        corresponda, basándose en el rol del creador y las tasas configuradas.
        
        Tipos de comisiones generadas:
            - Producer: Comisión base para el productor principal
            - Subproducer: 10% si el creador es subproductor
            - Affiliate: 5% si el creador es afiliado
        
        Note:
            Solo genera comisiones si el reel tiene un costo definido mayor a 0.
            Realiza commit automático a la base de datos
        """
        from app.models.commission import Commission
        from app.models.user import UserRole
        # Solo generar comisiones si hay un costo definido
        if not self.cost or self.cost <= 0:
            return
        
        # Comisión para el productor
        producer = self.creator.get_producer()
        if producer:
            producer_commission = Commission(
                user_id         = producer.user_id,
                reel_id         = self.id,
                commission_type = 'producer',
                amount          = self.cost * producer.commission_rate,
                percentage      = producer.commission_rate * 100
            )
            db.session.add(producer_commission)
        
        # Comisión para el subproductor (si aplica)
        if self.creator.role == UserRole.SUBPRODUCER:
            subproducer_rate       = 0.10  # 10% por defecto
            subproducer_commission = Commission(
                user_id            = self.creator_id,
                reel_id            = self.id,
                commission_type    = 'subproducer',
                amount             = self.cost * subproducer_rate,
                percentage         = subproducer_rate * 100
            )
            db.session.add(subproducer_commission)
        
        # Comisión para el afiliado (si aplica)
        if self.creator.role == UserRole.AFFILIATE:
            affiliate_rate         = 0.05  # 5% por defecto
            affiliate_commission   = Commission(
                user_id            = self.creator_id,
                reel_id            = self.id,
                commission_type    = 'affiliate',
                amount             = self.cost * affiliate_rate,
                percentage         = affiliate_rate * 100
            )
            db.session.add(affiliate_commission)
        
        db.session.commit()
    
    def to_dict(self):
        """
        Convierte el objeto Reel a un diccionario para serialización JSON.
        
        Returns:
            dict: Diccionario con todos los campos importantes del reel
        
        Note:
            Las fechas se convierten a formato ISO para compatibilidad JSON.
            Incluye propiedades calculadas como processing_time y contadores.
        """
        return {
            'id'                        : self.id,
            'title'                     : self.title,
            'description'               : self.description,
            'script'                    : self.script,
            'duration'                  : self.duration,
            'status'                    : self.status.value,
            'is_public'                 : self.is_public,
            'resolution'                : self.resolution,
            'background_type'           : self.background_type,
            'creator_name'              : self.creator_name,
            'approver_name'             : self.approver_name,
            'avatar_name'               : self.avatar_name,
            'category'                  : self.category,
            'tags'                      : self.tag_list,
            'view_count'                : self.view_count,
            'download_count'            : self.download_count,
            'cost'                      : self.cost,
            'price'                     : self.price,
            'video_url'                 : self.video_url,
            'thumbnail_url'             : self.thumbnail_url,
            'processing_time'           : self.processing_time,
            'created_at'                : self.created_at.isoformat() if self.created_at else None,
            'approved_at'               : self.approved_at.isoformat() if self.approved_at else None,
            'published_at'              : self.published_at.isoformat() if self.published_at else None,
            'processing_started_at'     : self.processing_started_at.isoformat() if self.processing_started_at else None,
            'processing_completed_at'   : self.processing_completed_at.isoformat() if self.processing_completed_at else None
        }