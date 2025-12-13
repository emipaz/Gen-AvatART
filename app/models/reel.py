"""
Módulo de modelo Reel para la aplicación Gem-AvatART.

Este módulo define el modelo de datos para los reels/videos generados mediante
la integración con HeyGen. Los reels son videos creados usando avatares digitales
que pronuncian un script específico y pueden incluir fondos personalizados.

El módulo incluye:
    - Enum ReelStatus: Estados posibles de un reel durante su ciclo de vida (ACTUALIZADO)
    - Clase Reel: Modelo principal para gestión de videos generados (ACTUALIZADO según README)

Funcionalidades principales:
    - Gestión del ciclo de vida de videos (creación, procesamiento, completado)
    - Integración con HeyGen para generación de videos via jobs
    - Sistema de comisiones automático con Stripe Connect (ACTUALIZADO)
    - Control de configuraciones de video (resolución, fondos, etc.)
    - Estadísticas de visualización y descarga
    - Sistema de etiquetas y categorización
    - Gestión de monetización y costos via Stripe

Flujo de trabajo típico (ACTUALIZADO según README):
    1. PENDING: Reel creado, listo para enviar a HeyGen
    2. PROCESSING: Enviado a HeyGen como job
    3. COMPLETED: Video generado exitosamente via webhook
    4. FAILED: Falló la generación (webhook error)
    5. Publicado para visualización
"""


from app import db
from datetime import datetime
from enum import Enum

class ReelStatus(Enum):
    """
    Enumeración que define los estados posibles de un reel durante su ciclo de vida.
    
    Estados disponibles (ACTUALIZADO según README):
        PENDING    : Reel creado, listo para enviar a HeyGen
        PROCESSING : Reel enviado a HeyGen como job, esperando resultado
        COMPLETED  : Video generado exitosamente por HeyGen
        FAILED     : Falló la generación del video en HeyGen
        PUBLISHED  : ✅ NUEVO - Reel publicado y disponible públicamente
    """
    
    PENDING    = "pending"     # Listo para enviar a HeyGen
    PROCESSING = "processing"  # En proceso de generación
    COMPLETED  = "completed"   # Video generado exitosamente
    FAILED     = "failed"      # Falló la generación
    PUBLISHED  = "published"   # Publicado y disponible
    
class Reel(db.Model):
    """
    Modelo de datos para reels/videos generados con avatares digitales.
    
    Este modelo gestiona todo el ciclo de vida de los videos creados con HeyGen,
    desde su creación inicial hasta su publicación final, incluyendo el sistema
    de comisiones via Stripe Connect, estadísticas y configuraciones técnicas.
    
    ACTUALIZADO según README para integración con Stripe Connect y simplificación
    del flujo de trabajo.
    
    Attributes:
        id (int)                           : Identificador único del reel
        creator_id (int)                   : ID del usuario que creó el reel
        avatar_id (int)                    : ID del avatar/clone utilizado para el video
        voice_id (str)                     : ID de la voz seleccionada en HeyGen
        title (str)                        : Título del reel
        description (str)                  : Descripción detallada del contenido
        script (str)                       : Texto que pronunciará el avatar
        duration (float)                   : Duración del video en segundos
        heygen_video_id (str)              : ID único del video en HeyGen
        heygen_job_id (str)                : ID del job en HeyGen para tracking
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
        stripe_payment_intent_id (str)     : ID del Payment Intent de Stripe
        created_at (datetime)              : Fecha de creación
        updated_at (datetime)              : Fecha de última actualización
        published_at (datetime)            : Fecha de publicación
        stripe_payment_intent_id (str)     : ID del Payment Intent de Stripe para tracking de pagos
    """
    __tablename__ = 'reels'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    
    # FK
    creator_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    owner_id   = db.Column(db.Integer, db.ForeignKey('users.id'))  # <-- NUEVO (propietario/cliente)
    avatar_id  = db.Column(db.Integer, db.ForeignKey('avatars.id'), nullable=True)  # <-- antes era False
    voice_id   = db.Column(db.String(100))  # ID de voz seleccionada en HeyGen

    # relaciones (las usa tu template y propiedades)
    # overlaps: necesario para evitar warnings de SQLAlchemy por relaciones superpuestas sobre creator_id
    # creator_user y reels también usan creator_id, por eso se indica el parámetro
    creator = db.relationship('User', foreign_keys=[creator_id], backref=db.backref('reels_creados', overlaps="creator_user,reels"), overlaps="creator_user,reels")
    owner   = db.relationship('User', foreign_keys=[owner_id],   backref='reels_propios')
    avatar  = db.relationship('Avatar', back_populates='reels')
    
    # Información básica del reel
    title       = db.Column(db.String(200), nullable = False)  # Título del video
    description = db.Column(db.Text)                         # Descripción detallada
    script      = db.Column(db.Text, nullable = False)         # Texto que dirá el avatar
    duration    = db.Column(db.Float)                        # Duración en segundos
    
    # Datos de integración con HeyGen
    heygen_video_id = db.Column(db.String(100), unique = True)  # ID único en HeyGen
    heygen_job_id   = db.Column(db.String(100), index=True)     # ID del job en HeyGen
    video_url       = db.Column(db.String(500))                 # URL del video generado
    thumbnail_url   = db.Column(db.String(500))                 # URL de la miniatura
    
    # Estado y configuración de acceso
    status    = db.Column(db.Enum(ReelStatus), nullable = False, default = ReelStatus.PENDING)
    is_public = db.Column(db.Boolean, default = False)  # Visibilidad pública
    
    # Configuración técnica del video
    resolution      = db.Column(db.String(20), default = '1080p')    # Resolución: 720p, 1080p, 4k
    background_type = db.Column(db.String(50), default = 'default')  # Tipo de fondo
    background_url  = db.Column(db.String(500))                    # URL del fondo personalizado

    # Configuración de voz
    speed = db.Column(db.Float, default=1.0)  # Velocidad de la voz (0.5 a 1.5)
    pitch = db.Column(db.Integer, default=0)  # Pitch de la voz (-50 a 50)
    
    # Metadatos y categorización
    meta_data = db.Column(db.JSON)         # Configuración adicional del video
    tags      = db.Column(db.String(500))  # Etiquetas separadas por comas
    category  = db.Column(db.String(50))   # Categoría del contenido
    
    # Información de procesamiento y errores
    processing_started_at   = db.Column(db.DateTime)  # Inicio del procesamiento
    processing_completed_at = db.Column(db.DateTime)  # Fin del procesamiento
    error_message           = db.Column(db.Text)      # Mensaje de error si falla
    
    # Estadísticas de uso
    view_count     = db.Column(db.Integer, default = 0)  # Contador de visualizaciones
    download_count = db.Column(db.Integer, default = 0)  # Contador de descargas

    # Configuración de monetización
    cost  = db.Column(db.Float, default = 0.0)  # Costo de producción
    price = db.Column(db.Float, default = 0.0)  # Precio de venta si aplica
    
    stripe_payment_intent_id = db.Column(db.String(100), index=True)  # Para tracking de pagos
    
    # Campos de auditoría y timestamps
    created_at   = db.Column(db.DateTime, default = datetime.utcnow)                              # Fecha de creación
    updated_at   = db.Column(db.DateTime, default = datetime.utcnow, onupdate = datetime.utcnow)  # Última actualización                                                    # Fecha de aprobación
    published_at = db.Column(db.DateTime)                                                         # Fecha de publicación
    
    # Definición de relaciones con otros modelos
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
        self.tags = ', '.join([tag.strip() 
                                for tag in tag_list 
                                    if tag.strip()
                                ])

    def start_processing(self, job_id=None):
        """
        Marca el inicio del procesamiento del reel en HeyGen.
        
        Cambia el estado a PROCESSING y registra el timestamp de inicio.
        Este método se llama cuando se envía el reel a HeyGen para generación.
        
        Note:
            Realiza commit automático a la base de datos
        """
        self.status                = ReelStatus.PROCESSING
        self.processing_started_at = datetime.utcnow()
        if job_id:
            self.heygen_job_id = job_id
            # HeyGen usa el mismo identificador para job/video; guardamos ambos para evitar polling fallido
            if not self.heygen_video_id:
                self.heygen_video_id = job_id
        db.session.commit()
    
    def complete_processing(self, video_url, thumbnail_url=None, video_id=None):
        """
        Marca el procesamiento como completado exitosamente.
        
        Args:
            video_url (str): URL del video generado por HeyGen
            thumbnail_url (str, opcional): URL de la imagen miniatura
            video_id (str, opcional): ID del video en HeyGen
        
        Note:
            ✅ ACTUALIZADO - Ahora acepta video_id según README
            Cambia el estado a COMPLETED y registra las URLs del contenido generado.
            Realiza commit automático a la base de datos
        """
        self.status                  = ReelStatus.COMPLETED
        self.processing_completed_at = datetime.utcnow()
        self.video_url               = video_url

        if thumbnail_url:
            self.thumbnail_url = thumbnail_url
            
        # ✅ NUEVO - Guardar video_id si se proporciona
        if video_id:
            self.heygen_video_id = video_id
            
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

    def publish(self):
        """
        Publica el reel para acceso público.
        
        Note:
            Marca el reel como público y registra la fecha de publicación.
            Realiza commit automático a la base de datos
        """
        self.status       = ReelStatus.PUBLISHED
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
        
    def set_stripe_payment(self, payment_intent_id):
        """
        Establece el Payment Intent de Stripe para este reel.
        
        Args:
            payment_intent_id (str): ID del Payment Intent de Stripe
            
        Note:
            ✅ NUEVO - Para tracking de pagos via Stripe Connect
        """
        self.stripe_payment_intent_id = payment_intent_id
        db.session.commit()
    
    def generate_commissions(self):
        """
        Genera comisiones automáticamente para la cadena de usuarios.

        LÓGICA CORREGIDA según README:
        - FINAL_USER: PAGA (no recibe comisión) - es quien genera el reel y paga por él
        - PRODUCTOR: RECIBE el pago principal (100% menos lo que comparte)
        - SUBPRODUCER: RECIBE parte del pago del productor (solo si él creó el reel)
        - PLATAFORMA: RECIBE application_fee via Stripe Connect automáticamente

        TASAS PARAMETRIZADAS (fáciles de cambiar):
            SUBPRODUCER_COMMISSION_RATE = 10%  # Del total, va al subproducer
            PRODUCER_KEEPS_RATE = 90%          # Del total, se queda el productor

        Tipos de comisiones generadas:
            - 'producer': Comisión que se queda el productor
            - 'subproducer': Comisión para el subproducer (solo si él creó el reel)

        Note:
            Solo genera comisiones si el reel tiene un costo definido mayor a 0.
            El FINAL_USER nunca recibe comisión porque él es quien PAGA.
            Realiza commit automático a la base de datos
        """
        from app.models.commission import Commission
        from app.models.user import UserRole

        # ✅ TASAS PARAMETRIZADAS - Fáciles de cambiar
        SUBPRODUCER_COMMISSION_RATE = 0.10  # 10% del total va al subproducer
        PRODUCER_KEEPS_RATE = 0.90          # 90% del total se queda el productor

        # Solo generar comisiones si hay un costo definido
        if not self.cost or self.cost <= 0:
            return

        # Obtener el productor asociado
        producer = self.creator.get_producer()
        if not producer:
            return

        # ✅ LÓGICA CORREGIDA según tipo de creador:

        if self.creator.role == UserRole.SUBPRODUCER:
            # CASO 1: SUBPRODUCER creó el reel
            # - Subproducer recibe su comisión (10%)
            # - Productor se queda con el resto (90%)

            subproducer_commission = Commission(
                user_id                  = self.creator_id,
                producer_id              = producer.id,
                reel_id                  = self.id,
                commission_type          = 'subproducer',
                amount                   = self.cost * SUBPRODUCER_COMMISSION_RATE,
                percentage               = SUBPRODUCER_COMMISSION_RATE * 100,
                stripe_payment_intent_id = self.stripe_payment_intent_id
            )
            db.session.add(subproducer_commission)

            producer_commission = Commission(
                user_id                   = producer.user_id,
                producer_id               = producer.id,
                reel_id                   = self.id,
                commission_type           = 'producer',
                amount                    = self.cost * PRODUCER_KEEPS_RATE,
                percentage                = PRODUCER_KEEPS_RATE * 100,
                stripe_payment_intent_id  = self.stripe_payment_intent_id
            )
            db.session.add(producer_commission)

        elif self.creator.role == UserRole.FINAL_USER:
            # CASO 2: FINAL_USER creó el reel
            # - Final_user PAGA (no recibe nada)
            # - Productor recibe TODO (100%)

            producer_commission = Commission(
                user_id                   = producer.user_id,
                producer_id               = producer.id,
                reel_id                   = self.id,
                commission_type           = 'producer',
                amount                    = self.cost,  # 100% del costo
                percentage                = 100.0,
                stripe_payment_intent_id  = self.stripe_payment_intent_id
            )
            db.session.add(producer_commission)

        elif self.creator.role == UserRole.PRODUCER:
            # CASO 3: PRODUCTOR creó su propio reel
            # - Productor recibe TODO (100%)

            producer_commission = Commission(
                user_id                   = producer.user_id,
                producer_id               = producer.id,
                reel_id                   = self.id,
                commission_type           = 'producer',
                amount                    = self.cost,  # 100% del costo
                percentage                = 100.0,
                stripe_payment_intent_id  = self.stripe_payment_intent_id
            )
            db.session.add(producer_commission)
        db.session.commit()
    
    # NUEVO método - Auto-generar comisiones al completar
    def complete_and_generate_commissions(self, video_url, thumbnail_url=None, video_id=None):
        """
        Completa el procesamiento y genera comisiones automáticamente.
        
        Args:
            video_url (str): URL del video generado
            thumbnail_url (str, opcional): URL de la miniatura
            video_id (str, opcional): ID del video en HeyGen
            
        Note:
            ✅ NUEVO - Combina complete_processing() y generate_commissions()
            según el flujo simplificado del README
        """
        # Completar procesamiento
        self.complete_processing(video_url, thumbnail_url, video_id)
        
        # Generar comisiones automáticamente
        self.generate_commissions()

    def to_dict(self):
        """
        Convierte el objeto Reel a un diccionario para serialización JSON.

        Returns:
            dict: Diccionario con todos los campos importantes del reel

        Note:
            ✅ ACTUALIZADO - Removidos campos de aprobación según README
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
            'avatar_name'               : self.avatar_name,
            'voice_id'                  : self.voice_id,
            'voice_speed'               : self.speed,
            'voice_pitch'               : self.pitch,
            'category'                  : self.category,
            'tags'                      : self.tag_list,
            'view_count'                : self.view_count,
            'download_count'            : self.download_count,
            'cost'                      : self.cost,
            'price'                     : self.price,
            'video_url'                 : self.video_url,
            'thumbnail_url'             : self.thumbnail_url,
            'heygen_job_id'             : self.heygen_job_id,                  # ✅ NUEVO
            'stripe_payment_intent_id'  : self.stripe_payment_intent_id,      # ✅ NUEVO
            'processing_time'           : self.processing_time,
            'created_at'                : self.created_at.isoformat() if self.created_at else None,
            'published_at'              : self.published_at.isoformat() if self.published_at else None,
            'processing_started_at'     : self.processing_started_at.isoformat() if self.processing_started_at else None,
            'processing_completed_at'   : self.processing_completed_at.isoformat() if self.processing_completed_at else None

            # ❌ CAMPOS REMOVIDOS - Ya no existen según README
            # 'approver_name'             : self.approver_name,     # approved_by removido
            # 'approved_at'               : self.approved_at.isoformat() if self.approved_at else None,  # approved_at removido
        }
    
    