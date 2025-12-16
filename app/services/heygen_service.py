"""
Módulo de servicio de HeyGen para la aplicación Gem-AvatART.

Este módulo proporciona funcionalidades completas para la integración con la API de HeyGen,
incluyendo gestión de avatares digitales, creación de videos, procesamiento de reels y
manejo del ciclo de vida completo de los contenidos multimedia generados por IA.

FUNCIONALIDADES SEGÚN README:
    - Gestión de avatares digitales y clones personalizados
    - Creación de videos usando avatares con scripts de texto
    - Procesamiento de reels en formato vertical (9:16)
    - Control de estados de procesamiento y webhooks
    - Gestión de cuotas y límites de API por productor
    - Sincronización de avatares entre HeyGen y la plataforma
    - Validación y configuración de API keys encriptadas

MODOS DE PROCESAMIENTO SOPORTADOS:
    📋 WEBHOOK  - Notificaciones automáticas en tiempo real (producción)
    🔍 POLLING  - Verificación manual periódica (desarrollo local)
    🔀 HYBRID   - Webhooks + fallback a polling (flexible)

    Configuración por entorno:
    - Desarrollo: 'polling' (simple, no requiere URL pública)
    - Staging:    'hybrid'  (permite probar ambos modos)
    - Producción: 'webhook' (máximo rendimiento)

    Variables de entorno:
    - HEYGEN_PROCESSING_MODE: 'webhook' | 'polling' | 'hybrid'
    - HEYGEN_WEBHOOK_BASE_URL: URL pública para webhooks (ej: https://gem-avatart.com)

    Uso en código:
        processor = HeyGenVideoProcessor(
            api_key="api-key",
            processing_mode='hybrid',
            webhook_base_url='https://gem-avatart.com'
        )
        
        # El mismo código funciona para todos los modos
        success = processor.process_reel(reel_model)
        
        # Verificar modo para acciones post-procesamiento
        if processor.should_use_polling():
            # Programar verificación periódica
            schedule_status_check(reel_id)

El módulo incluye:
    - Enum ProcessingMode        : Tipos de procesamiento (webhook/polling/hybrid)
    - Clase HeyGenService        : Interfaz principal con la API de HeyGen
    - Clase HeyGenVideoProcessor : Procesador especializado para reels con soporte multi-modo
    - Clase HeyGenError          : Excepciones personalizadas para manejo de errores
    - Funciones de utilidad      : Validación, formateo y conversión de datos

Funcionalidades principales:
    - Autenticación segura con API keys de productores
    - CRUD completo de avatares digitales
    - Generación de videos con múltiples configuraciones
    - Manejo de estados de procesamiento (pending, processing, completed, failed)
    - Sistema híbrido de webhooks + polling para máxima flexibilidad
    - Gestión de cuotas y límites por productor
    - Soporte para múltiples formatos y resoluciones
    - Cache inteligente para optimización de requests
    - Auto-detección de entorno para configuración óptima

Dependencias:
    - requests  : Para comunicación HTTP con API de HeyGen
    - typing    : Para type hints y mejor documentación
    - datetime  : Para manejo de timestamps y fechas
    - json      : Para serialización de datos complejos
    - enum      : Para definición de modos de procesamiento
"""

from flask import current_app
import requests
import json
import logging
from typing import Dict, Optional, List, Union, Any
from datetime import datetime, timedelta
from enum import Enum
from functools import lru_cache

# Configurar logging para el servicio de HeyGen
logger = logging.getLogger(__name__)


# ============================================================================
# CACHE PARA VOCES (5 minutos de TTL)
# ============================================================================

@lru_cache(maxsize=50)
def _fetch_all_voices_cached(api_key: str, base_url: str) -> tuple:
    """
    Función cacheada para obtener todas las voces de HeyGen.
    Usa LRU cache para evitar llamadas repetidas a la API.
    Cache individual por API key ya que cada productor puede tener voces personalizadas.
    El cache se invalida automáticamente después de un tiempo.
    
    Args:
        api_key: API key de HeyGen (único por productor)
        base_url: URL base de la API
    
    Returns:
        tuple: (lista_de_voces, timestamp)
    
    Note:
        maxsize=50 permite cachear voces de hasta 50 productores diferentes.
        Aumenta este valor si tienes más productores activos.
    """
    try:
        session = requests.Session()
        session.headers.update({
            'X-Api-Key'     : api_key,
            'Content-Type'  : 'application/json',
            'Accept'        : 'application/json'
        })
        
        response = session.get(
            f"{base_url}/v2/voices",
            timeout=30
        )
        
        if response.status_code == 200:
            data   = response.json()
            voices = data.get('data', {}).get('voices', [])
            logger.info(f"Cache: Obtenidas {len(voices)} voces de HeyGen")
            return (voices, datetime.now())
        else:
            logger.warning(f"Cache: Error obteniendo voces - Status: {response.status_code}")
            return ([], datetime.now())
    except Exception as e:
        logger.error(f"Cache: Error obteniendo voces: {e}")
        return ([], datetime.now())


# ============================================================================
# ENUMERACIONES Y CONSTANTES
# ============================================================================


class VideoStatus(Enum):
    """
    Enumeración que define los estados posibles de un video en HeyGen.
    
    Estados disponibles:
        PENDING    : Video en cola, esperando procesamiento
        PROCESSING : Video siendo generados por HeyGen
        COMPLETED  : Video generado exitosamente
        FAILED     : Error en la generación del video
        CANCELLED  : Video cancelado por el usuario
    """
    PENDING    = "pending"     # En cola de procesamiento
    PROCESSING = "processing"  # Siendo generado
    COMPLETED  = "completed"   # Generado exitosamente
    FAILED     = "failed"      # Error en la generación
    CANCELLED  = "cancelled"   # Cancelado por usuario


class AvatarType(Enum):
    """
    Enumeración que define los tipos de avatares disponibles en HeyGen.
    
    Tipos disponibles:
        PUBLIC     : Avatares públicos de HeyGen
        CUSTOM     : Avatares personalizados del productor
        PREMIUM    : Avatares premium de HeyGen
        INSTANT    : Avatares de creación instantánea
    """
    PUBLIC  = "public"   # Avatares públicos de HeyGen
    CUSTOM  = "custom"   # Avatares personalizados
    PREMIUM = "premium"  # Avatares premium
    # INSTANT = "instant"  # Avatares instantáneos


class ProcessingMode(Enum):
    """
    Enumeración que define los modos de procesamiento de videos.
    
    Modos disponibles:
        WEBHOOK  : Usa webhooks para notificaciones automáticas
        POLLING  : Usa polling manual para verificar estado
        HYBRID   : Intenta webhooks, fallback a polling
    """
    WEBHOOK = "webhook"   # Notificaciones automáticas
    POLLING = "polling"   # Verificación manual
    HYBRID  = "hybrid"    # Webhooks + fallback polling


class VideoResolution(Enum):
    """
    Enumeración que define las resoluciones soportadas.
    
    Resoluciones disponibles:
        HD_720P  : 1280x720 (HD)
        FULL_HD  : 1920x1080 (Full HD)
        UHD_4K   : 3840x2160 (4K Ultra HD)
        VERTICAL_HD : 720x1280 (Vertical HD para reels)
        VERTICAL_FHD: 1080x1920 (Vertical Full HD para reels)
    """
    HD_720P      = "720p"      # 1280x720
    FULL_HD      = "1080p"     # 1920x1080
    UHD_4K       = "4k"        # 3840x2160
    VERTICAL_HD  = "720x1280"  # Vertical para reels
    VERTICAL_FHD = "1080x1920" # Vertical Full HD


# ============================================================================
# CLASE PRINCIPAL DEL SERVICIO
# ============================================================================

class HeyGenService:
    """
    Servicio principal para interacinar con la API de HeyGen.
    
    Esta clase encapsula toda la funcionalidad necesaria para comunicarse
    con la API de HeyGen, incluyendo autenticación, gestión de avatares,
    creación de videos y manejo de estados de procesamiento.
    
    Attributes:
        api_key (str)      : Clave de API para autenticación con HeyGen
        base_url (str)     : URL base de la API de HeyGen
        session (Session)  : Sesión HTTP configurada con headers de autenticación
        timeout (int)      : Timeout para requests HTTP (segundos)
        max_retries (int)  : Número máximo de reintentos para requests fallidos
    
    Example:
        >>> service = HeyGenService("your-api-key")
        >>> user_info = service.get_user_info()
        >>> avatars = service.list_avatars()
        >>> video = service.create_reel_video("avatar_id", "Hola mundo")
    """
    
    def __init__(self, 
                 api_key     : str, 
                 base_url    : str = "https://api.heygen.com",
                 timeout     : int = 30,
                 max_retries : int = 3):
        """
        Inicializa el servicio de HeyGen con configuración personalizada.
        
        Args:
            api_key (str)       : Clave de API válida de HeyGen
            base_url (str)      : URL base de la API (por defecto producción)
            timeout (int)       : Timeout para requests en segundos
            max_retries (int)   : Número máximo de reintentos automáticos
        
        Raises:
            ValueError: Si la API key está vacía o es inválida
        """
        if not api_key or not isinstance(api_key, str):
            raise ValueError("API key debe ser una string no vacía")
        
        self.api_key     = api_key
        self.base_url    = base_url.rstrip('/')
        self.timeout     = timeout
        self.max_retries = max_retries
        
        # Configurar sesión HTTP con headers predeterminados
        self.session = requests.Session()
        self.session.headers.update({
            'x-api-key'     : api_key,
            'accept'        : 'application/json'
        })
        
        logger.info(f"HeyGenService inicializado con base_url: {base_url}")


    # ============================================================================
    # MÉTODOS DE AUTENTICACIÓN Y VALIDACIÓN
    # ============================================================================


    def validate_api_key(self) -> bool:
        """
        Valida si la API key configurada es válida y funcional.
        
        Usa el endpoint de voces para verificar que la autenticación
        sea correcta y que la API key tenga los permisos necesarios.
        
        Returns:
            bool: True si la API key es válida, False en caso contrario
        
        Example:
            >>> service = HeyGenService("api_key")
            >>> if service.validate_api_key():
            ...     print("API key válida")
            ... else:
            ...     print("API key inválida")
        """
        try:
            # Usar el endpoint de voces para validar la API key
            response = self.session.get(
                f"{self.base_url}/v2/voices",
                timeout=self.timeout
            )
            
            is_valid = response.status_code == 200
            
            if is_valid:
                logger.info("API key validada exitosamente")
            else:
                logger.warning(f"API key inválida - Status: {response.status_code}")
                if response.status_code == 401:
                    logger.error("API key no autorizada - verificar credenciales")
                elif response.status_code == 403:
                    logger.error("API key sin permisos suficientes")
                
            return is_valid
            
        except requests.RequestException as e:
            logger.error(f"Error validando API key: {str(e)}")
            return False


    def get_user_info(self) -> Optional[Dict[str, Any]]:
        """
        Obtiene información del perfil del usuario autenticado actualmente.
        
        Recupera datos del perfil del usuario en HeyGen asociado a la API key,
        incluyendo nombre de usuario, email y nombres.
        
        Returns:
            Optional[Dict]: Información del usuario o None si hay error:
                - username (str)   : Nombre de usuario único
                - email (str)      : Email registrado en la cuenta
                - first_name (str) : Primer nombre del usuario
                - last_name (str)  : Apellido del usuario
        
        Example:
            >>> user = service.get_user_info()
            >>> if user:
            ...     data = user['data']
            ...     print(f"Usuario: {data['first_name']} {data['last_name']}")
            ...     print(f"Email: {data['email']}")
        """
        try:
            response = self.session.get(
                f"{self.base_url}/v1/user/me",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                user_data = response.json()
                data = user_data.get('data', {})
                logger.info(f"Información de usuario obtenida: {data.get('email', 'N/A')}")
                return user_data
                
            else:
                logger.warning(f"Error obteniendo información del usuario - Status: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error obteniendo información del usuario: {str(e)}")
            return None


    # ============================================================================
    # MÉTODOS DE GESTIÓN DE AVATARES
    # ============================================================================


    def list_avatars(self, 
                    avatar_type: Optional[str] = None,
                    page: int = 1,
                    limit: int = 50) -> List[Dict[str, Any]]:
        """
        Lista todos los avatares disponibles para la API key.
        
        Obtiene la lista completa de avatares accesibles, incluyendo
        avatares públicos de HeyGen y avatares personalizados del usuario.
        Soporta paginación y filtrado por tipo.
        
        Args:
            avatar_type (str, opcional): Filtro por tipo ('public', 'custom', 'premium')
            page (int): Número de página (por defecto 1)
            limit (int): Elementos por página (máximo 100)
        
        Returns:        
            List[Dict] : Lista de avatares con la siguiente estructura:
                - id (str)                  : ID único del avatar
                - name (str)                : Nombre descriptivo
                - avatar_type (str)         : Tipo de avatar
                - preview_image_url (str)   : URL de imagen de preview
                - gender (str)              : Género del avatar
                - language (List[str])      : Idioms soportados
                - is_public (bool)          : Si es público o personalizado
                - created_at (str)          : Fecha de creación
        
        Example:
            >>> avatars = service.list_avatars(avatar_type="public", limit=10)
            >>> for avatar in avatars:
            ...     print(f"{avatar['name']} - {avatar['avatar_type']}")
        """
        try:
            params = {
                'page': page,
                'limit': min(limit, 100)  # Máximo 100 por página
            }
            
            if avatar_type:
                params['type'] = avatar_type
            
            response = self.session.get(
                f"{self.base_url}/v2/avatars",
                params  = params,
                timeout = self.timeout
            )
            
            if response.status_code == 200:
                data    = response.json()
                avatars = data.get("data", {}).get("avatars", [])
                
                logger.info(f"Obtenidos {len(avatars)} avatares (página {page})")
                return avatars
            else:
                logger.warning(f"Error listando avatares - Status: {response.status_code}")
                return []
                
        except requests.RequestException as e:
            logger.error(f"Error listando avatares: {str(e)}")
            return []
    

    def create_avatar(self, avatar_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Crea un nuevo avatar personalizado en HeyGen.
        
        Permite crear avatares personalizados subiendo imágenes o videos
        del usuario. El proceso incluye validación de contenido, 
        procesamiento de IA y aprobación automática.
        
        Args:
            avatar_data (Dict)                : Datos del avatar a crear con estructura:
                - name (str)                  : Nombre descriptivo del avatar
                - gender (str)                : Género ('male', 'female')
                - image_url (str)             : URL de imagen para el avatar
                - voice_id (str, opcional)    : ID de voz a usar por defecto
                - description (str, opcional) : Descripción del avatar
                - tags (List[str], opcional)  : Etiquetas para categorización
        
        Returns:
            Optional[Dict]            : Respuesta de creación o None si hay error:
                - id (str)            : ID único del avatar creado
                - status (str)        : Estado del procesamiento
                - preview_url (str)   : URL de preview del avatar
                - estimated_time (int): Tiempo estimado de procesamiento
        
        Example:
            >>> avatar_data = {
            ...     "name": "Mi Avatar Personal",
            ...     "gender": "male",
            ...     "image_url": "https://example.com/photo.jpg"
            ... }
            >>> result = service.create_avatar(avatar_data)
        """
        try:
            response = self.session.post(
                f"{self.base_url}/v2/avatars",
                json    = avatar_data,
                timeout = self.timeout
            )
            
            if response.status_code in [200, 201]:
                result = response.json()
                logger.info(f"Avatar '{avatar_data.get('name')}' creado exitosamente")
                return result
            else:
                logger.warning(f"Error creando avatar - Status: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error creando avatar: {str(e)}")
            return None


    def get_avatar(self, avatar_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene información detallada de un avatar específico.
        
        Recupera todos los datos disponibles de un avatar, incluyendo
        estado de procesamiento, configuraciones, estadísticas de uso
        y URLs de recursos multimedia.
        
        Args:
            avatar_id (str): ID único del avatar en HeyGen
        
        Returns:
            Optional[Dict] : Información completa del avatar o None:
                - id (str)                : ID único del avatar
                - name (str)              : Nombre del avatar
                - type (str)              : Tipo de avatar ("avatar")
                - gender (str)            : Género del avatar
                - preview_image_url (str) : URL de imagen de preview
                - preview_video_url (str) : URL de video de preview
                - premium (bool)          : Si es avatar premium
                - is_public (bool)        : Si es avatar público
                - default_voice_id (str)  : ID de voz predeterminada (puede ser None)
                - tags (List[str])        : Etiquetas del avatar
        
        Example:
            >>> avatar = service.get_avatar("avatar_123")
            >>> if avatar:
            ...     print(f"Avatar: {avatar['name']} - Estado: {avatar['status']}")
        """
        try:
            response = self.session.get(
                f"{self.base_url}/v2/avatar/{avatar_id}/details",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                avatar_data = response.json()
                logger.info(f"Avatar {avatar_id} obtenido exitosamente")
                return avatar_data
            else:
                logger.warning(f"Avatar {avatar_id} no encontrado - Status: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error obteniendo avatar {avatar_id}: {str(e)}")
            return None


    # ============================================================================
    # MÉTODOS DE GESTIÓN DE VIDEOS (REELS)
    # ============================================================================


    def create_video(self, video_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Crea un nuevo video usando un avatar y configuraciones específicas.
        
        Inicia el procesamiento de un video con el avatar seleccionado,
        aplicando el script de texto, configuraciones de voz, fondo y
        otros parámetros multimedia especificados.
        
        Args:
            video_data (Dict)                 : Configuración del video con estructura:
                - avatar_id (str)             : ID del avatar a usar
                - script (str)                : Texto que dirá el avatar
                - voice (Dict, opcional)      : Configuración de voz
                - background (Dict, opcional) : Configuración de fondo
                - dimension (str, opcional)   : Dimensiones del video
                - title (str, opcional)       : Título descriptivo
        
        Returns:
            Optional[Dict] : Respuesta de creación o None si hay error:
                - video_id (str)                   : ID único del video en procesamiento
                - status (str)                     : Estado inicial (pending/processing)
                - estimated_duration (int)         : Duración estimada en segundos
                - estimated_processing_time (int)  : Tiempo estimado de procesamiento
                - webhook_url (str, opcional)      : URL para notificaciones
        
        Example:
            >>> video_config = {
            ...     "avatar_id": "avatar_123",
            ...     "script": "Hola, este es mi mensaje personalizado",
            ...     "dimension": "1080x1920"
            ... }
            >>> result = service.create_video(video_config)
        """
        try:
            response = self.session.post(
                f"{self.base_url}/v2/video/generate",
                json    = video_data,
                timeout = self.timeout * 2  # Timeout extendido para creación
            )
            
            if response.status_code in [200, 201]:
                result   = response.json()
                video_id = result.get('data', {}).get('video_id')
                logger.info(f"Video {video_id} creado exitosamente - Estado: pending")
                return result
            else:
                error_detail = "Sin detalles"
                try:
                    error_response = response.json()
                    error_detail = error_response.get('message') or error_response.get('error') or str(error_response)
                except:
                    error_detail = response.text[:200] if response.text else "Sin contenido"
                
                logger.warning(f"Error creando video - Status: {response.status_code} - Detalle: {error_detail}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error creando video: {str(e)}")
            return None


    def get_video_status(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene el estado actual y detalles de procesamiento de un video.
        
        Consulta el estado de procesamiento de un video específico,
        incluyendo progreso, tiempo restante, errores si los hay,
        y URLs de descarga una vez completado.
        
        Args:
            video_id (str): ID único del video en HeyGen
        
        Returns:
            Optional[Dict] : Estado y detalles del video o None:
                - video_id (str)      : ID del video
                - status (str)        : Estado (pending, processing, completed, failed)
                - progress (int)      : Porcentaje de progreso (0-100)
                - duration (float)    : Duración del video en segundos
                - video_url (str)     : URL de descarga (solo si completed)
                - thumbnail_url (str) : URL de miniatura (solo si completed)
                - error_message (str) : Mensaje de error (solo si failed)
                - created_at (str)    : Fecha de creación
                - completed_at (str)  : Fecha de completado (solo si completed)
        
        Example:
            >>> status = service.get_video_status("video_456")
            >>> if status['status'] == 'completed':
            ...     video_url = status['video_url']
            ...     print(f"Video listo: {video_url}")
        """
        try:
            response = self.session.get(
                f"{self.base_url}/v1/video_status.get",
                params={'video_id': video_id},
                timeout=self.timeout
            )

            if response.status_code == 200:
                status_data    = response.json()
                current_status = status_data.get('data', {}).get('status', 'unknown')
                logger.info(f"Video {video_id} - Estado: {current_status}")
                return status_data
            else:
                logger.warning(
                    "Video %s no encontrado - Status: %s - Payload: %s",
                    video_id,
                    response.status_code,
                    response.text[:200]
                )
                return None

        except requests.RequestException as e:
            logger.error(f"Error obteniendo estado del video {video_id}: {str(e)}")
            return None


    def get_avatar_default_voice(self, avatar_id: str) -> Optional[str]:
        """
        Obtiene el ID de la voz predeterminada de un avatar específico.
        
        Algunos avatares tienen una voz predeterminada asociada que es la voz
        del video/avatar original. Este método verifica si el avatar tiene
        una voz por defecto configurada.
        
        Args:
            avatar_id (str): ID único del avatar en HeyGen
        
        Returns:
            Optional[str]: ID de la voz predeterminada o None si no tiene
        
        Example:
            >>> default_voice_id = service.get_avatar_default_voice("avatar_123")
            >>> if default_voice_id:
            ...     print(f"Voz predeterminada: {default_voice_id}")
            ... else:
            ...     print("El avatar no tiene voz predeterminada - usuario debe elegir")
        """
        avatar_details = self.get_avatar(avatar_id)
        
        if avatar_details:
            data          = avatar_details.get('data', {})
            default_voice = data.get('default_voice_id')
            
            if default_voice:
                logger.info(f"Avatar {avatar_id} tiene voz predeterminada: {default_voice}")
                return default_voice
            else:
                logger.info(f"Avatar {avatar_id} no tiene voz predeterminada")
                return None
        else:
            logger.warning(f"No se pudo obtener información del avatar {avatar_id}")
            return None


    def get_voice_details(self, voice_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene información detallada de una voz específica.
        
        Como HeyGen no tiene endpoint individual para voces, busca la voz
        en la lista de voces disponibles para obtener su información.
        Usa cache para mejorar el rendimiento.
        
        Args:
            voice_id (str): ID único de la voz en HeyGen
        
        Returns:
            Optional[Dict]: Información de la voz o None:
                - voice_id (str)                    : ID único de la voz
                - name (str)                        : Nombre descriptivo
                - gender (str)                      : Género de la voz
                - language (str)                    : Idioma de la voz
                - preview_audio (str)               : URL de preview de audio
                - emotion_support (bool)            : Si soporta emociones
                - support_interactive_avatar (bool) : Si soporta avatares interactivos
        
        Example:
            >>> voice_info = service.get_voice_details("voice_123")
            >>> if voice_info:
            ...     print(f"Voz: {voice_info['name']} - {voice_info['gender']}")
        """
        try:
            # Obtener todas las voces desde cache (sin filtro)
            voices, _ = _fetch_all_voices_cached(self.api_key, self.base_url)
            
            # Buscar la voz específica por ID
            for voice in voices:
                if voice.get('voice_id') == voice_id:
                    logger.info(f"Voz {voice_id} encontrada en cache: {voice.get('name')}")
                    return voice
            
            logger.warning(f"Voz {voice_id} no encontrada en cache")
            return None
                
        except Exception as e:
            logger.error(f"Error buscando voz {voice_id}: {str(e)}")
            return None


    def get_voice_config_for_avatar(self, avatar_id: str, user_voice_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Obtiene la configuración de voz para usar con un avatar específico.
        
        Implementa la lógica de selección de voz:
        1. Si el usuario especifica una voz, usar esa
        2. Si no, usar la voz predeterminada del avatar
        3. Si el avatar no tiene voz predeterminada, requerir selección del usuario
        
        Args:
            avatar_id (str): ID del avatar
            user_voice_id (str, opcional): ID de voz elegida por el usuario
        
        Returns:
            Dict[str, Any]: Configuración de voz para el video:
                - voice_id (str): ID de la voz a usar
                - source (str): Origen de la voz ('user', 'avatar_default', 'required')
                - voice_info (Dict): Información detallada de la voz
        
        Raises:
            ValueError: Si el avatar no tiene voz predeterminada y el usuario no eligió ninguna
        
        Example:
            >>> voice_config = service.get_voice_config_for_avatar("avatar_123", "voice_456")
            >>> video_data = {
            ...     "avatar_id": "avatar_123",
            ...     "script": "Hola mundo",
            ...     "voice": {"voice_id": voice_config['voice_id']}
            ... }
        """
        # Si el usuario especificó una voz, usarla
        if user_voice_id:
            voice_info = self.get_voice_details(user_voice_id)
            if voice_info:
                return {
                    'voice_id'  : user_voice_id,
                    'source'    : 'user',
                    'voice_info': voice_info
                }
            else:
                raise ValueError(f"Voz especificada por usuario no válida: {user_voice_id}")
        
        # Si no hay voz del usuario, intentar usar la predeterminada del avatar
        default_voice_id = self.get_avatar_default_voice(avatar_id)
        
        if default_voice_id:
            voice_info = None
            try:
                voice_info = self.get_voice_details(default_voice_id)
            except Exception as e:
                logger.warning(
                    "No se pudo obtener información detallada para la voz predeterminada %s: %s",
                    default_voice_id,
                    e
                )

            if not voice_info:
                logger.info(
                    "Usando voz predeterminada %s del avatar aunque no se obtuvo metadata adicional",
                    default_voice_id
                )

            return {
                'voice_id'   : default_voice_id,
                'source'     : 'avatar_default', 
                'voice_info' : voice_info
            }
        
        # FALLBACK: Si el avatar no tiene voz predeterminada, usar una voz por defecto en español
        logger.warning(f"Avatar {avatar_id} no tiene voz predeterminada. Usando voz por defecto.")
        
        try:
            # Intentar obtener la primera voz en español disponible
            spanish_voices = self.list_voices(language='es')
            if spanish_voices:
                fallback_voice_id = spanish_voices[0]['voice_id']
                logger.info(f"Usando voz fallback: {fallback_voice_id} ({spanish_voices[0].get('name', 'Sin nombre')})")
                return {
                    'voice_id'   : fallback_voice_id,
                    'source'     : 'fallback', 
                    'voice_info' : spanish_voices[0]
                }
        except Exception as e:
            logger.error(f"Error obteniendo voz fallback: {str(e)}")
        
        # Si todo falla, lanzar excepción
        raise ValueError(
            f"Avatar {avatar_id} no tiene voz predeterminada válida y no se pudo obtener voz fallback. "
            "El usuario debe seleccionar una voz de la lista disponible."
        )


    # ============================================================================
    # MÉTODOS DE GESTIÓN DE VOCES
    # ============================================================================


    def list_voices(self, 
                   language   : Optional[str] = 'es',
                   gender     : Optional[str] = None,
                   voice_type : Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Lista las voces disponibles filtradas por idioma y características.
        
        Obtiene todas las voces disponibles en HeyGen para el idioma especificado,
        con opciones de filtrado por género, tipo de voz y otras características.
        Usa cache LRU para evitar llamadas repetidas a la API.
        
        Args:
            language (str, opcional): Código o nombre de idioma (ej: 'es', 'Spanish'). 
                                     Si es None, retorna todas las voces sin filtro.
            gender (str, opcional): Filtro por género ('male', 'female')
            voice_type (str, opcional): Tipo de voz ('standard', 'premium', 'neural')
        
        Returns:
            List[Dict] : Lista de voces disponibles:
                - voice_id (str)                    : ID único de la voz
                - name (str)                        : Nombre descriptivo
                - language (str)                    : Idioma de la voz
                - gender (str)                      : Género de la voz
                - preview_audio (str)               : URL de preview de audio
                - emotion_support (bool)            : Si soporta emociones
                - support_interactive_avatar (bool) : Si soporta avatares interactivos
                - support_pause (bool)              : Si soporta pausas
                - support_locale (bool)             : Si soporta localización
        
        Example:
            >>> voices = service.list_voices(language='Spanish', gender='female')
            >>> for voice in voices:
            ...     print(f"{voice['name']} - {voice['gender']} - Emociones: {voice['emotion_support']}")
            
            >>> all_voices = service.list_voices(language=None)  # Sin filtro de idioma
        """
        try:
            # Obtener voces desde cache
            voices, cache_time = _fetch_all_voices_cached(self.api_key, self.base_url)
            
            # Verificar si el cache tiene más de 30 minutos
            cache_age = (datetime.now() - cache_time).total_seconds()
            if cache_age > 1800:  # 30 minutos
                logger.info("Cache de voces expirado, invalidando...")
                _fetch_all_voices_cached.cache_clear()
                voices, cache_time = _fetch_all_voices_cached(self.api_key, self.base_url)
            
            # Si no hay voces en cache, retornar vacío
            if not voices:
                logger.warning("No se pudieron obtener voces desde cache")
                return []
            
            # Aplicar filtros
            filtered_voices = voices.copy()
            
            # Filtrar por idioma si se especifica
            if language:
                filtered_voices = [
                    voice for voice in filtered_voices 
                    if language.lower() in voice.get('language', '').lower()
                    or language.upper() in voice.get('language', '').upper()
                ]
            
            # Filtrar por género si se especifica
            if gender:
                filtered_voices = [
                    voice for voice in filtered_voices
                    if gender.lower() in voice.get('gender', '').lower()
                ]
            
            # Filtrar por tipo de voz si se especifica (basado en características)
            if voice_type:
                if voice_type == 'premium':
                    # Considerar premium las que soporten emociones
                    filtered_voices = [
                        voice for voice in filtered_voices
                        if voice.get('emotion_support', False)
                    ]
                elif voice_type == 'interactive':
                    # Voces que soporten avatares interactivos
                    filtered_voices = [
                        voice for voice in filtered_voices
                        if voice.get('support_interactive_avatar', False)
                    ]
            
            logger.info(f"Obtenidas {len(filtered_voices)} voces filtradas (de {len(voices)} en cache)")
            return filtered_voices
                
        except Exception as e:
            logger.error(f"Error listando voces: {str(e)}")
            return []


    def get_voice_locales(self) -> List[Dict[str, Any]]:
        """
        Obtiene la lista de locales/idiomas soportados para voces.
        
        Recupera todos los idiomas y locales disponibles en HeyGen
        para filtrar voces por región específica.
        
        Returns:
            List[Dict]: Lista de locales disponibles:
                - value (str)         : Descripción completa del locale
                - label (str)         : Etiqueta corta del idioma
                - language (str)      : Nombre del idioma
                - locale (str)        : Código de locale (ej: 'es-ES')
                - language_code (str) : Código de idioma
                - tag (str)           : Etiqueta de versión (puede ser None)
        
        Example:
            >>> locales = service.get_voice_locales()
            >>> spanish_locales = [l for l in locales if 'Spanish' in l['language']]
        """
        try:
            response = self.session.get(
                f"{self.base_url}/v2/voices/locales",
                timeout = self.timeout
            )
            
            if response.status_code == 200:
                data    = response.json()
                locales = data.get('data', {}).get('locales', [])
                logger.info(f"Obtenidos {len(locales)} locales de voz disponibles")
                return locales
            else:
                logger.warning(f"Error obteniendo locales - Status: {response.status_code}")
                return []
                
        except requests.RequestException as e:
            logger.error(f"Error obteniendo locales de voces: {str(e)}")
            return []


    # ============================================================================
    # MÉTODOS DE GESTIÓN DE WEBHOOKS
    # ============================================================================


    def list_webhook_endpoints(self) -> List[Dict[str, Any]]:
        """
        Obtiene la lista de todos los endpoints de webhook registrados en la cuenta.
        
        Recupera información detallada sobre todos los webhooks configurados,
        incluyendo URLs, eventos suscritos, estado y configuración de seguridad.
        
        Returns:
            List[Dict]: Lista de endpoints de webhook:
                - endpoint_id (str)   : ID único del endpoint
                - url (str)           : URL del webhook
                - username (str)      : Usuario asociado
                - events (List[str])  : Eventos suscritos (null = todos)
                - status (str)        : Estado (enabled/disabled)
                - secret (str)        : Clave secreta para verificación
                - space_id (str)      : ID del espacio
                - entity_id (str)     : ID de entidad específica (opcional)
                - created_at (str)    : Fecha de creación
        
        Example:
            >>> endpoints = service.list_webhook_endpoints()
            >>> for endpoint in endpoints:
            ...     print(f"Webhook {endpoint['endpoint_id']}: {endpoint['url']}")
        """
        try:
            response = self.session.get(
                f"{self.base_url}/v1/webhook/endpoint.list",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                endpoints = data.get('data', [])
                logger.info(f"Obtenidos {len(endpoints)} endpoints de webhook")
                return endpoints
            else:
                logger.warning(f"Error listando webhooks - Status: {response.status_code}")
                return []
                
        except requests.RequestException as e:
            logger.error(f"Error listando endpoints de webhook: {str(e)}")
            return []


    def add_webhook_endpoint(self, 
                           url: str, 
                           events: Optional[List[str]] = None,
                           entity_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Registra un nuevo endpoint de webhook para recibir notificaciones de eventos.
        
        Configura un webhook que recibirá notificaciones en tiempo real cuando
        ocurran eventos específicos en HeyGen (completado de videos, errores, etc.).
        
        Args:
            url (str): URL donde HeyGen enviará las notificaciones
                      (debe soportar HTTPS con SSL nivel 2 o superior)
            events (List[str], opcional): Tipos de eventos a escuchar
                                        (None = todos los eventos)
            entity_id (str, opcional): ID específico de entidad asociada
        
        Returns:
            Optional[Dict]: Información del webhook creado o None:
                - endpoint_id (str)    : ID único del endpoint creado
                - url (str)            : URL del webhook
                - events (List[str])   : Eventos configurados
                - secret (str)         : Clave secreta para verificación
                - status (str)         : Estado (enabled)
                - created_at (str)     : Fecha de creación
        
        Raises:
            HeyGenError: Si la URL es inválida o no cumple requisitos SSL
        
        Example:
            >>> webhook = service.add_webhook_endpoint(
            ...     url="https://mi-app.com/webhooks/heygen",
            ...     events=["avatar_video.success", "avatar_video.fail"]
            ... )
            >>> if webhook:
            ...     endpoint_id = webhook['data']['endpoint_id']
            ...     secret = webhook['data']['secret']
        """
        try:
            payload = {
                "url": url
            }
            
            if events is not None:
                payload["events"] = events
            
            if entity_id is not None:
                payload["entity_id"] = entity_id
            
            response = self.session.post(
                f"{self.base_url}/v1/webhook/endpoint.add",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                webhook_data = response.json()
                logger.info(f"Webhook creado exitosamente: {url}")
                return webhook_data
            else:
                error_data = response.json() if response.content else {}
                error_msg = error_data.get('message', f'HTTP {response.status_code}')
                
                if response.status_code == 400 and '400542' in str(error_data.get('code')):
                    raise HeyGenError(f"URL de webhook inválida: {url}", "INVALID_WEBHOOK_URL")
                
                logger.warning(f"Error creando webhook - {error_msg}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error creando endpoint de webhook: {str(e)}")
            return None


    def update_webhook_endpoint(self, 
                              endpoint_id: str,
                              url: Optional[str] = None,
                              events: Optional[List[str]] = None) -> Optional[Dict[str, Any]]:
        """
        Actualiza un endpoint de webhook existente.
        
        Modifica la configuración de un webhook ya registrado, permitiendo
        cambiar la URL, los eventos suscritos y otras configuraciones.
        
        Args:
            endpoint_id (str)               : ID único del endpoint a actualizar
            url (str, opcional)             : Nueva URL del webhook
            events (List[str], opcional) : Nueva lista de eventos (None = todos)
        
        Returns:
            Optional[Dict]: Información del webhook actualizado o None
        
        Raises:
            HeyGenError: Si el endpoint no existe o la URL es inválida
        
        Example:
            >>> updated = service.update_webhook_endpoint(
            ...     endpoint_id="abc123...",
            ...     url="https://nueva-url.com/webhook",
            ...     events=["avatar_video.success"]
            ... )
        """
        try:
            payload = {
                "endpoint_id": endpoint_id
            }
            
            if url is not None:
                payload["url"] = url
            
            if events is not None:
                payload["events"] = events
            
            response = self.session.patch(
                f"{self.base_url}/v1/webhook/endpoint.update",
                json=payload,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                webhook_data = response.json()
                logger.info(f"Webhook {endpoint_id} actualizado exitosamente")
                return webhook_data
            else:
                error_data = response.json() if response.content else {}
                error_code = error_data.get('code')
                error_msg = error_data.get('message', f'HTTP {response.status_code}')
                
                if error_code == 400542:
                    raise HeyGenError(f"URL de webhook inválida: {url}", "INVALID_WEBHOOK_URL")
                elif error_code == 400131:
                    raise HeyGenError(f"Endpoint de webhook no encontrado: {endpoint_id}", "WEBHOOK_NOT_FOUND")
                
                logger.warning(f"Error actualizando webhook - {error_msg}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error actualizando endpoint de webhook: {str(e)}")
            return None


    def delete_webhook_endpoint(self, endpoint_id: str) -> bool:
        """
        Elimina un endpoint de webhook existente.
        
        Desregistra completamente un webhook, deteniendo todas las
        notificaciones a esa URL específica.
        
        Args:
            endpoint_id (str): ID único del endpoint a eliminar
        
        Returns:
            bool: True si se eliminó exitosamente, False en caso contrario
        
        Example:
            >>> if service.delete_webhook_endpoint("abc123..."):
            ...     print("Webhook eliminado exitosamente")
        """
        try:
            params = {
                "endpoint_id": endpoint_id
            }
            
            response = self.session.delete(
                f"{self.base_url}/v1/webhook/endpoint.delete",
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                logger.info(f"Webhook {endpoint_id} eliminado exitosamente")
                return True
            else:
                logger.warning(f"Error eliminando webhook {endpoint_id} - Status: {response.status_code}")
                return False
                
        except requests.RequestException as e:
            logger.error(f"Error eliminando endpoint de webhook: {str(e)}")
            return False


    def list_available_webhook_events(self) -> List[str]:
        """
        Obtiene la lista de todos los tipos de eventos de webhook soportados.
        
        Recupera todos los eventos disponibles que pueden ser configurados
        en los webhooks para recibir notificaciones específicas.
        
        Returns:
            List[str]: Lista de tipos de eventos disponibles:
                - avatar_video.success/fail            : Generación de videos con avatares
                - avatar_video_gif.success/fail        : Generación de GIFs con avatares
                - photo_avatar_generation.success/fail : Creación de avatares desde foto
                - photo_avatar_train.success/fail      : Entrenamiento de avatares
                - instant_avatar.success/fail          : Avatares instantáneos
                - video_translate.success/fail         : Traducción de videos
                - Y más eventos según disponibilidad
        
        Example:
            >>> events = service.list_available_webhook_events()
            >>> print(f"Eventos disponibles: {len(events)}")
            >>> for event in events:
            ...     print(f"- {event}")
        """
        try:
            response = self.session.get(
                f"{self.base_url}/v1/webhook/webhook.list",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                data = response.json()
                events = data.get('data', [])
                logger.info(f"Obtenidos {len(events)} tipos de eventos de webhook")
                return events
            else:
                logger.warning(f"Error listando eventos de webhook - Status: {response.status_code}")
                return []
                
        except requests.RequestException as e:
            logger.error(f"Error listando eventos de webhook: {str(e)}")
            return []


    def setup_video_webhook(self, webhook_url: str) -> Optional[str]:
        """
        Configura un webhook específicamente para eventos de videos (éxito y falla).
        
        Método de conveniencia que configura automáticamente un webhook
        para recibir notificaciones cuando los videos se completen o fallen.
        
        Args:
            webhook_url (str): URL donde recibir las notificaciones
        
        Returns:
            Optional[str]: ID del endpoint creado o None si falló
        
        Example:
            >>> endpoint_id = service.setup_video_webhook("https://mi-app.com/webhook")
            >>> if endpoint_id:
            ...     print(f"Webhook configurado: {endpoint_id}")
        """
        video_events = [
            "avatar_video.success",
            "avatar_video.fail",
            "avatar_video_gif.success",
            "avatar_video_gif.fail"
        ]
        
        result = self.add_webhook_endpoint(webhook_url, video_events)
        
        if result and result.get('code') == 100:
            endpoint_id = result.get('data', {}).get('endpoint_id')
            logger.info(f"Webhook de video configurado exitosamente: {endpoint_id}")
            return endpoint_id
        
        return None


    # ============================================================================
    # MÉTODOS DE GESTIÓN DE CUOTAS Y LÍMITES
    # ============================================================================


    def get_remaining_quota(self) -> Optional[Dict[str, Any]]:
        """
        Obtiene la cuota restante de API para el usuario autenticado.
        
        Recupera información detallada sobre la cuota restante disponible
        y los créditos por categoría para el usuario actual.
        
        Returns:
            Optional[Dict]: Información de cuota restante o None si hay error:
                - remaining_quota (int) : Cuota total restante
                - details (Dict)        : Desglose por tipo de crédito:
                    
                    - api (int)                                  : Créditos de API general
                    - avatar_iv_free_credit (int)                : Créditos gratuitos de avatar
                    - generative_element_free_image_credit (int) : Créditos de imagen generativa
                    - generative_element_free_video_credit (int) : Créditos de video generativo
                    - video_agent_quality_mode_credit (int)      : Créditos de modo calidad
                    - plan_credit (int)                          : Créditos del plan
        
        Note:
            Para convertir cuota a créditos, divide la cantidad entre 60.
            Ejemplo: remaining_quota=3600 = 60 créditos (3600/60=60)
        
        Example:
            >>> quota = service.get_remaining_quota()
            >>> if quota:
            ...     remaining = quota['data']['remaining_quota']
            ...     credits = remaining // 60  # Convertir a créditos
            ...     print(f"Cuota restante: {remaining} ({credits} créditos)")
        """
        try:
            response = self.session.get(
                f"{self.base_url}/v2/user/remaining_quota",
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                quota_data = response.json()
                data       = quota_data.get('data', {})
                remaining  = data.get('remaining_quota', 0)
                credits    = remaining // 60 if remaining > 0 else 0
                
                logger.info(f"Cuota restante: {remaining} ({credits} créditos)")
                return quota_data
            else:
                logger.warning(f"Error obteniendo cuota restante - Status: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error obteniendo cuota restante: {str(e)}")
            return None


    def get_quota_info(self) -> Optional[Dict[str, Any]]:
        """
        Alias para get_remaining_quota() para mantener compatibilidad.
        
        Returns:
            Optional[Dict]: Información de cuota restante
        """
        return self.get_remaining_quota()


    def check_sufficient_quota(self, required_quota: int = 60) -> bool:
        """
        Verifica si hay cuota suficiente para crear un video.
        
        Args:
            required_quota (int): Cuota mínima requerida (por defecto 60 = 1 crédito)
        
        Returns:
            bool: True si hay cuota suficiente, False en caso contrario
        
        Raises:
            HeyGenQuotaExceededError: Si no hay cuota suficiente
        
        Example:
            >>> if service.check_sufficient_quota():
            ...     video = service.create_video(video_data)
        """
        quota_info = self.get_remaining_quota()
        
        if not quota_info:
            logger.warning("No se pudo verificar cuota - asumiendo suficiente")
            return True
        
        remaining = quota_info.get('data', {}).get('remaining_quota', 0)
        
        if remaining < required_quota:
            raise HeyGenQuotaExceededError(remaining, required_quota)
        
        return True


    # ============================================================================
    # MÉTODOS ESPECÍFICOS PARA REELS
    # ============================================================================


    def create_reel_video(self, 
                         avatar_id: str, 
                         script: str, 
                         **kwargs) -> Optional[Dict[str, Any]]:
        """
        Crea un video reel optimizado para redes sociales con configuración específica.
        
        Genera un video en formato vertical (9:16) optimizado para plataformas
        como Instagram Reels, TikTok y YouTube Shorts, usando configuraciones
        predeterminadas específicas para este tipo de contenido.
        
        Args:
            avatar_id (str): ID del avatar a usar en el reel
            script (str): Texto que dirá el avatar (máximo 500 caracteres)
            **kwargs: Configuraciones adicionales opcionales:
                - voice_id (str)         : ID de voz específica a usar
                - voice_speed (float)    : Velocidad de la voz (0.5-2.0)
                - voice_emotion (str)    : Emoción de la voz
                - background_type (str)  : Tipo de fondo ('color', 'image', 'video')
                - background_value (str) : Valor del fondo (color hex, URL)
                - resolution (str)       : Resolución específica ('1080x1920', '720x1280')
                - title (str)            : Título del reel para identificación
                - webhook_url (str)      : URL para notificaciones de estado
                - check_quota (bool)     : Verificar cuota antes de crear (por defecto True)
        
        Returns:
            Optional[Dict]: Respuesta de creación del reel o None:
                - video_id (str)           : ID único del video reel
                - status (str)             : Estado inicial (pending)
                - estimated_duration (int) : Duración estimada en segundos
                - reel_optimized (bool)    : Confirmación de optimización para reel
                - preview_url (str)        : URL de preview una vez procesado
        
        Example:
            >>> reel = service.create_reel_video(
            ...     avatar_id="avatar_123",
            ...     script="¡Hola! Este es mi primer reel con IA",
            ...     voice_emotion="excited",
            ...     background_type="color",
            ...     background_value="#FF6B6B"
            ... )
        """
        # Verificar cuota si está habilitado
        if kwargs.get('check_quota', True):
            try:
                self.check_sufficient_quota()
            except HeyGenQuotaExceededError as e:
                logger.error(f"Cuota insuficiente para crear reel: {str(e)}")
                raise
        
        # Configuración específica para reels
        # Convertir resolución string a formato de diccionario que HeyGen espera
        resolution_str = kwargs.get('resolution', '720x1280')
        
        # Convertir formatos de frontend a formatos de backend
        resolution_mapping = {
            '720p': '720x1280',    # HD vertical
            '1080p': '1080x1920',  # Full HD vertical  
            '4K': '2160x3840',     # 4K vertical
            '720x1280': '720x1280',   # Ya está en formato correcto
            '1080x1920': '1080x1920', # Ya está en formato correcto
            '2160x3840': '2160x3840'  # Ya está en formato correcto
        }
        
        # Mapear resolución
        resolution_str = resolution_mapping.get(resolution_str, '720x1280')  # Default a 720x1280 para cuentas básicas
        
        if 'x' in resolution_str:
            width, height = resolution_str.split('x')
            dimension_dict = {"width": int(width), "height": int(height)}
        else:
            dimension_dict = {"width": 720, "height": 1280}  # Default a resolución básica
        
        # Configuración de voz usando la nueva lógica
        try:
            voice_config_result = self.get_voice_config_for_avatar(
                avatar_id, 
                kwargs.get('voice_id')
            )
            
            # Estructura de voz según API v2 de HeyGen
            voice_config = {
                "type": "text",  # Campo requerido por HeyGen
                "voice_id": voice_config_result['voice_id'],
                "speed": kwargs.get('voice_speed', 1.0),
            }

            if 'voice_pitch' in kwargs and kwargs['voice_pitch'] is not None:
                voice_config["pitch"] = kwargs['voice_pitch']
            
            logger.info(f"Voz configurada: {voice_config_result['voice_id']} (fuente: {voice_config_result['source']})")
            
        except ValueError as e:
            logger.error(f"Error configurando voz para reel: {str(e)}")
            raise HeyGenError(f"Error de configuración de voz: {str(e)}")
        
        # Configuración de fondo
        background_type = kwargs.get('background_type', 'color')
        background_value = kwargs.get('background_value', '#FFFFFF')
        
        # El script va dentro del objeto voice cuando type="text"
        voice_config["input_text"] = script
        
        # Estructura nueva de HeyGen API v2 - video_inputs
        video_inputs = [{
            "character": {
                "type": "avatar",
                "avatar_id": avatar_id,
                "avatar_style": "normal"
            },
            "voice": voice_config,
            "background": {
                "type": background_type,
                "value": background_value if background_type == 'color' else background_value,
                "url": background_value if background_type in ['image', 'video'] else None
            }
        }]
        
        video_data = {
            "video_inputs": video_inputs,
            "dimension": dimension_dict,
            "aspect_ratio": "9:16",
            "title": kwargs.get('title', f"Reel - {datetime.now().strftime('%Y%m%d_%H%M%S')}")
        }
        
        # URL de webhook para notificaciones (opcional)
        if 'webhook_url' in kwargs:
            video_data['webhook_url'] = kwargs['webhook_url']
        
        # Configuraciones adicionales para optimización de reel
        video_data.update({
            "test": False,  # Producción
            "caption"               : False,  # Sin subtítulos automáticos
            "optimize_for_mobile"   : True  # Optimización móvil
        })
        
        try:
            logger.info(f"Creando reel con avatar {avatar_id} - Script: {script[:50]}...")
            result = self.create_video(video_data)
            
            if result:
                logger.info("Reel creado exitosamente - optimizado para formato vertical")
            
            return result
            
        except Exception as e:
            logger.error(f"Error creando reel: {str(e)}")
            return None


    def _prepare_background_config(self, bg_type: str, bg_value: str, local_path: str = None) -> Optional[Dict[str, Any]]:
        """
        Prepara la configuración de fondo, subiendo archivos locales si es necesario.
        
        Args:
            bg_type (str): Tipo de fondo ('color', 'image', 'video')
            bg_value (str): Valor del fondo (color hex o URL)
            local_path (str, opcional): Ruta local del archivo a subir
        
        Returns:
            Optional[Dict]: Configuración de fondo para la API
        """
        try:
            if bg_type == 'color':
                return {
                    "type": "color",
                    "value": bg_value
                }
            
            elif bg_type in ['image', 'video'] and local_path:
                # Si hay una ruta local, subir el archivo primero
                logger.info(f"📤 Subiendo {bg_type} de fondo: {local_path}")
                
                # Detectar content-type
                import mimetypes
                content_type, _ = mimetypes.guess_type(local_path)
                
                if not content_type:
                    logger.error(f"❌ No se pudo detectar el tipo MIME de {local_path}")
                    return None
                
                # Subir el asset
                asset_result = self.upload_asset(local_path, content_type)
                
                if not asset_result or asset_result.get('code') != 100:
                    logger.error(f"❌ Error subiendo {bg_type}: {local_path}")
                    return None
                
                asset_id = asset_result['data']['id']
                logger.info(f"✅ {bg_type.capitalize()} subida exitosamente: {asset_id}")
                
                # Configurar usando asset_id
                config = {
                    "type": bg_type,
                    f"{bg_type}_asset_id": asset_id
                }
                
                # Para videos, agregar configuración de reproducción
                if bg_type == 'video':
                    config["play_style"] = "loop"
                    config["fit"] = "cover"
                
                return config
                
            elif bg_type in ['image', 'video'] and bg_value:
                # Usar URL directa (solo si no es localhost)
                if 'localhost' in bg_value or '127.0.0.1' in bg_value:
                    logger.warning(f"⚠️ URL localhost detectada: {bg_value} - No funcionará con HeyGen")
                    return None
                
                config = {
                    "type": bg_type,
                    "url": bg_value
                }
                
                if bg_type == 'video':
                    config["play_style"] = "loop"
                    config["fit"] = "cover"
                
                return config
            
            else:
                logger.error(f"❌ Configuración de fondo inválida: tipo={bg_type}, valor={bg_value}, ruta={local_path}")
                return None
                
        except Exception as e:
            logger.error(f"💥 Error preparando configuración de fondo: {str(e)}")
            return None


    # ============================================================================
    # MÉTODOS DE GESTIÓN DE ARCHIVOS Y RECURSOS
    # ============================================================================


    def upload_asset(self, file_path: str, content_type: str = None) -> Optional[Dict[str, Any]]:
        """
        Sube un archivo (imagen, video, audio) a HeyGen y retorna el asset ID.
        
        Este método soluciona el problema de URLs localhost subiendo los archivos
        directamente a HeyGen para que puedan ser accesibles desde su API.
        
        Args:
            file_path (str): Ruta local del archivo a subir
            content_type (str, opcional): MIME type del archivo
        
        Returns:
            Optional[Dict]: Información del asset subido:
                - id (str): ID único del asset en HeyGen
                - url (str): URL pública del asset
                - file_type (str): Tipo de archivo (image, video, audio)
                - created_ts (int): Timestamp de creación
        
        Example:
            >>> asset = service.upload_asset('./background.jpg', 'image/jpeg')
            >>> asset_id = asset['data']['id']
        """
        try:
            import mimetypes
            
            if not os.path.exists(file_path):
                logger.error(f"Archivo no encontrado: {file_path}")
                return None
            
            # Detectar content-type automáticamente si no se proporciona
            if not content_type:
                content_type, _ = mimetypes.guess_type(file_path)
                if not content_type:
                    logger.error(f"No se pudo detectar el tipo MIME de {file_path}")
                    return None
            
            logger.info(f"📤 Subiendo asset: {file_path} ({content_type})")
            
            # Leer el archivo como binario
            with open(file_path, 'rb') as file:
                file_data = file.read()
            
            # Headers para upload
            headers = {
                'Content-Type': content_type,
                'X-API-KEY': self.api_key,
                'accept': 'application/json'
            }
            
            # Hacer la petición de upload
            response = requests.post(
                "https://upload.heygen.com/v1/asset",
                headers=headers,
                data=file_data,
                timeout=60  # Upload puede tomar más tiempo
            )
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Asset subido exitosamente: {result.get('data', {}).get('id')}")
                return result
            else:
                logger.error(f"❌ Error subiendo asset - Status: {response.status_code} - Response: {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"💥 Error subiendo asset {file_path}: {str(e)}")
            return None


    def create_video_v2(self, video_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Crea un video usando la API v2 de HeyGen (más potente y estable).
        
        La API v2 ofrece mejores características y manejo de assets.
        
        Args:
            video_data (Dict): Configuración del video según API v2
        
        Returns:
            Optional[Dict]: Respuesta de creación del video
        """
        try:
            logger.info(f"🎬 Creando video con API v2: {video_data.get('title', 'Sin título')}")
            
            response = self.session.post(
                f"{self.base_url}/v2/video/generate",
                json=video_data,
                timeout=self.timeout
            )

            if response.status_code == 200:
                result = response.json()
                logger.info(f"✅ Video v2 creado exitosamente: {result.get('data', {}).get('video_id')}")
                return result
            else:
                error_detail = response.text[:200] if response.text else 'Sin detalles'
                logger.warning(f"❌ Error creando video v2 - Status: {response.status_code} - Detalle: {error_detail}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"💥 Error creando video v2: {str(e)}")
            return None


    def upload_avatar_image(self, 
                           image_path: str, 
                           avatar_name: str = None) -> Optional[Dict[str, Any]]:
        """
        Sube una imagen para crear un avatar personalizado.
        
        Permite subir una imagen local para crear un avatar personalizado.
        La imagen es procesada por IA para generar un avatar digital realista
        que puede ser usado en la creación de videos.
        
        Args:
            image_path (str): Ruta local del archivo de imagen
            avatar_name (str, opcional): Nombre para el avatar personalizado
        
        Returns:
            Optional[Dict]: Respuesta de upload o None si hay error:
                - upload_id (str): ID único del upload
                - avatar_id (str): ID del avatar una vez procesado
                - status (str): Estado del procesamiento
                - preview_url (str): URL de preview una vez completado
                - processing_time_estimate (int): Tiempo estimado en minutos
        
        Raises:
            FileNotFoundError: Si el archivo de imagen no existe
            ValueError: Si el formato de imagen no es soportado
        
        Example:
            >>> result = service.upload_avatar_image(
            ...     image_path="./mi_foto.jpg",
            ...     avatar_name="Mi Avatar Personal"
            ... )
        """
        try:
            # Verificar que el archivo existe
            import os
            if not os.path.isfile(image_path):
                raise FileNotFoundError(f"Archivo no encontrado: {image_path}")
            
            # Validar formato de imagen
            valid_formats = ['.jpg', '.jpeg', '.png', '.webp']
            file_ext = os.path.splitext(image_path)[1].lower()
            if file_ext not in valid_formats:
                raise ValueError(f"Formato no soportado: {file_ext}. Use: {valid_formats}")
            
            with open(image_path, 'rb') as image_file:
                files = {
                    'file': (os.path.basename(image_path), image_file, 'image/jpeg')
                }
                
                data = {}
                if avatar_name:
                    data['avatar_name'] = avatar_name
                
                # Headers específicos para upload (sin Content-Type)
                headers = {'Authorization': f'Bearer {self.api_key}'}
                
                response = requests.post(
                    f"{self.base_url}/v2/avatars/upload",
                    files=files,
                    data=data,
                    headers=headers,
                    timeout=self.timeout * 3  # Timeout extendido para upload
                )
                
                if response.status_code in [200, 201]:
                    result = response.json()
                    logger.info(f"Imagen subida exitosamente: {os.path.basename(image_path)}")
                    return result
                else:
                    logger.warning(f"Error subiendo imagen - Status: {response.status_code}")
                    return None
                    
        except (FileNotFoundError, ValueError) as e:
            logger.error(f"Error de validación: {str(e)}")
            raise
        except requests.RequestException as e:
            logger.error(f"Error subiendo imagen de avatar: {str(e)}")
            return None


    def get_video_download_url(self, video_id: str) -> Optional[str]:
        """
        Obtiene la URL de descarga directa de un video completado.
        
        Recupera la URL de descarga directa para un video que ha sido
        procesado exitosamente. La URL tiene un tiempo de expiración
        limitado y debe ser utilizada inmediatamente.
        
        Args:
            video_id (str): ID del video completado
        
        Returns:
            Optional[str]: URL de descarga directa o None si no está disponible
        
        Note:
            - La URL expira después de cierto tiempo (usualmente 24 horas)
            - Solo disponible para videos con status 'completed'
            - Recomendado descargar inmediatamente después de obtener la URL
        
        Example:
            >>> download_url = service.get_video_download_url("video_789")
            >>> if download_url:
            ...     # Descargar el video inmediatamente
            ...     import requests
            ...     video_content = requests.get(download_url).content
        """
        video_status = self.get_video_status(video_id)
        
        if not video_status:
            return None
        
        data = video_status.get('data', {})
        status = data.get('status', '')
        
        if status == 'completed':
            download_url = data.get('video_url')
            if download_url:
                logger.info(f"URL de descarga obtenida para video {video_id}")
                return download_url
            else:
                logger.warning(f"Video {video_id} completado pero sin URL de descarga")
                return None
        else:
            logger.info(f"Video {video_id} no está completado - Estado: {status}")
            return None


    # ============================================================================
    # MÉTODOS DE CONTROL Y GESTIÓN
    # ============================================================================


    def cancel_video(self, video_id: str) -> bool:
        """
        Cancela la generación de un video en procesamiento.
        
        Detiene el procesamiento de un video que está en cola o siendo
        procesado. Una vez cancelado, el video no podrá ser recuperado
        y se liberará el uso de cuota asociado.
        
        Args:
            video_id (str): ID del video a cancelar
        
        Returns:
            bool: True si se canceló exitosamente, False en caso contrario
        
        Note:
            - Solo se pueden cancelar videos en estado 'pending' o 'processing'
            - Videos completados o fallidos no pueden ser cancelados
            - La cuota utilizada puede ser reembolsada según políticas de HeyGen
        
        Example:
            >>> success = service.cancel_video("video_456")
            >>> if success:
            ...     print("Video cancelado exitosamente")
        """
        try:
            response = self.session.delete(
                f"{self.base_url}/v1/video/{video_id}",
                timeout=self.timeout
            )
            
            success = response.status_code in [200, 204]
            
            if success:
                logger.info(f"Video {video_id} cancelado exitosamente")
            else:
                logger.warning(f"No se pudo cancelar video {video_id} - Status: {response.status_code}")
            
            return success
            
        except requests.RequestException as e:
            logger.error(f"Error cancelando video {video_id}: {str(e)}")
            return False


    def get_usage_statistics(self, 
                           start_date: datetime, 
                           end_date: datetime) -> Optional[Dict[str, Any]]:
        """
        Obtiene estadísticas detalladas de uso en un rango de fechas específico.
        
        Recupera información completa sobre el uso de la API, incluyendo
        videos generados, tiempo de procesamiento, costos y patrones de uso
        en el período especificado.
        
        Args:
            start_date (datetime): Fecha de inicio del período
            end_date (datetime): Fecha de fin del período
        
        Returns:
            Optional[Dict]: Estadísticas de uso o None si hay error:
                - total_videos (int): Total de videos generados
                - successful_videos (int): Videos completados exitosamente
                - failed_videos (int): Videos que fallaron
                - total_duration (float): Duración total en minutos
                - average_processing_time (float): Tiempo promedio de procesamiento
                - quota_used (int): Cuota utilizada en el período
                - peak_usage_day (str): Día de mayor uso
                - most_used_avatar (Dict): Avatar más utilizado
        
        Example:
            >>> from datetime import datetime, timedelta
            >>> end_date = datetime.now()
            >>> start_date = end_date - timedelta(days=30)
            >>> stats = service.get_usage_statistics(start_date, end_date)
        """
        try:
            params = {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                'include_details': True
            }
            
            response = self.session.get(
                f"{self.base_url}/v1/user/usage",
                params=params,
                timeout=self.timeout
            )
            
            if response.status_code == 200:
                stats_data = response.json()
                period_days = (end_date - start_date).days
                logger.info(f"Estadísticas obtenidas para período de {period_days} días")
                return stats_data
            else:
                logger.warning(f"Error obteniendo estadísticas - Status: {response.status_code}")
                return None
                
        except requests.RequestException as e:
            logger.error(f"Error obteniendo estadísticas de uso: {str(e)}")
            return None


# ============================================================================
# CLASES DE EXCEPCIÓN PERSONALIZADAS
# ============================================================================


class HeyGenError(Exception):
    """
    Excepción personalizada para errores específicos de HeyGen.
    
    Proporciona información detallada sobre errores de la API,
    incluyendo códigos de error, mensajes descriptivos y contexto
    de la respuesta HTTP para facilitar la depuración.
    
    Attributes:
        message (str): Mensaje descriptivo del error
        error_code (str): Código específico del error de HeyGen
        response (Dict): Respuesta HTTP completa para análisis
        status_code (int): Código de estado HTTP
    """
    
    def __init__(self, 
                 message: str, 
                 error_code: str = None, 
                 response: Dict = None,
                 status_code: int = None):
        """
        Inicializa una excepción HeyGen con detalles del error.
        
        Args:
            message (str): Mensaje descriptivo del error
            error_code (str, opcional): Código específico del error
            response (Dict, opcional): Respuesta HTTP completa
            status_code (int, opcional): Código de estado HTTP
        """
        self.message = message
        self.error_code = error_code
        self.response = response
        self.status_code = status_code
        super().__init__(self.message)
    
    def __str__(self) -> str:
        """Representación string del error con contexto."""
        error_parts = [self.message]
        
        if self.error_code:
            error_parts.append(f"Código: {self.error_code}")
        
        if self.status_code:
            error_parts.append(f"HTTP {self.status_code}")
        
        return " | ".join(error_parts)


class HeyGenQuotaExceededError(HeyGenError):
    """Excepción específica para errores de cuota excedida."""
    
    def __init__(self, remaining_quota: int, required_quota: int = 60):
        credits_remaining = remaining_quota // 60 if remaining_quota > 0 else 0
        credits_required = required_quota // 60 if required_quota > 0 else 1
        
        message = f"Cuota de HeyGen insuficiente: {remaining_quota} restante ({credits_remaining} créditos), se requieren al menos {required_quota} ({credits_required} créditos)"
        super().__init__(message, error_code="QUOTA_EXCEEDED")
        self.remaining_quota = remaining_quota
        self.required_quota = required_quota
        self.credits_remaining = credits_remaining
        self.credits_required = credits_required


class HeyGenVideoProcessingError(HeyGenError):
    """Excepción específica para errores de procesamiento de video."""
    
    def __init__(self, video_id: str, processing_error: str):
        message = f"Error procesando video {video_id}: {processing_error}"
        super().__init__(message, error_code="VIDEO_PROCESSING_FAILED")
        self.video_id = video_id
        self.processing_error = processing_error


# ============================================================================
# CLASE PROCESADOR ESPECIALIZADO PARA VIDEOS Y REELS
# ============================================================================


class HeyGenVideoProcessor:
    """
    Procesador especializado para videos de HeyGen con manejo avanzado de estados.
    
    Esta clase proporciona una interfaz de alto nivel para el procesamiento
    de videos y reels, incluyendo manejo automático de estados, reintentos,
    notificaciones y integración con el modelo de datos de la aplicación.
    
    Funcionalidades principales:
        - Procesamiento automatizado de reels con manejo de errores
        - Seguimiento de estados con callbacks personalizables
        - Integración directa con modelos de la base de datos
        - Sistema de reintentos para requests fallidos
        - Webhooks y notificaciones automáticas
        - Validación de cuotas antes del procesamiento
        - Cache de respuestas para optimización
    
    Attributes:
        service (HeyGenService): Instancia del servicio principal
        max_retries (int): Número máximo de reintentos por operación
        retry_delay (int): Delay entre reintentos en segundos
        webhook_enabled (bool): Si las notificaciones por webhook están habilitadas
    """
    
    def __init__(self, 
                 api_key: str,
                 max_retries: int = 3,
                 retry_delay: int = 5,
                 processing_mode: str = 'hybrid',
                 webhook_base_url: Optional[str] = None):
        """
        Inicializa el procesador de videos con configuraciones específicas.
        
        Args:
            api_key (str): Clave de API de HeyGen
            max_retries (int): Máximo de reintentos por operación
            retry_delay (int): Segundos entre reintentos
            processing_mode (str): Modo de procesamiento ('webhook', 'polling', 'hybrid')
            webhook_base_url (str): URL base para webhooks (requerido para modo webhook/hybrid)
        """
        self.service = HeyGenService(api_key)
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self.processing_mode = ProcessingMode(processing_mode)
        self.webhook_base_url = webhook_base_url
        
        # Validar configuración según modo
        if self.processing_mode in [ProcessingMode.WEBHOOK, ProcessingMode.HYBRID]:
            if not webhook_base_url:
                if self.processing_mode == ProcessingMode.WEBHOOK:
                    raise ValueError("webhook_base_url es requerido para modo webhook")
                else:
                    logger.warning("No se configuró webhook_base_url, usando solo polling")
                    self.processing_mode = ProcessingMode.POLLING
        
        logger.info(f"HeyGenVideoProcessor inicializado - Modo: {self.processing_mode.value}")


    def process_reel(self, reel_model) -> bool:
        """
        Procesa un reel completo usando HeyGen con manejo automático de estados.
        
        Ejecuta el flujo completo de procesamiento de un reel, desde la
        validación inicial hasta el inicio del procesamiento en HeyGen,
        actualizando automáticamente el estado del modelo en la base de datos.
        
        Args:
            reel_model (Reel): Instancia del modelo Reel de la base de datos
        
        Returns:
            bool: True si el procesamiento inició exitosamente, False en caso contrario
        
        Raises:
            HeyGenQuotaExceededError: Si se ha excedido la cuota de videos
            HeyGenError: Para otros errores específicos de HeyGen
            ValueError: Si el reel o avatar no son válidos
        
        Flow:
            1. Validar reel y avatar
            2. Verificar cuota disponible
            3. Marcar reel como 'processing'
            4. Enviar request a HeyGen
            5. Guardar video_id y actualizar estado
            6. Configurar webhook si está habilitado
        
        Example:
            >>> processor = HeyGenVideoProcessor("api_key")
            >>> success = processor.process_reel(reel_instance)
            >>> if success:
            ...     print("Procesamiento iniciado")
        """
        try:
            # Validación inicial
            if not reel_model or not reel_model.avatar:
                raise ValueError("Reel o avatar no válidos")
            
            if not reel_model.script or len(reel_model.script.strip()) == 0:
                raise ValueError("Script del reel no puede estar vacío")
            
            avatar = reel_model.avatar
            if not avatar.avatar_ref:  # Referencia del avatar en HeyGen
                raise ValueError("Avatar no tiene referencia válida de HeyGen")
            
            # Verificar cuota restante antes del procesamiento
            quota_info = self.service.get_remaining_quota()
            if quota_info:
                data = quota_info.get('data', {})
                remaining_quota = data.get('remaining_quota', 0)
                credits = remaining_quota // 60 if remaining_quota > 0 else 0
                
                if remaining_quota <= 0:
                    raise HeyGenQuotaExceededError(0, 0)  # Sin cuota restante
                
                logger.info(f"Cuota verificada: {remaining_quota} restante ({credits} créditos)")
            else:
                logger.warning("No se pudo verificar cuota - continuando sin verificación")
            
            # Marcar reel como procesando
            reel_model.status = 'processing'
            reel_model.processing_started_at = datetime.utcnow()
            
            # Configurar datos del video para HeyGen
            webhook_url = None
            
            # Determinar si usar webhook según el modo
            if self.processing_mode in [ProcessingMode.WEBHOOK, ProcessingMode.HYBRID]:
                if self.webhook_base_url:
                    webhook_url = f"{self.webhook_base_url}/webhooks/heygen/reel/{reel_model.id}"
                    logger.info(f"Configurando webhook: {webhook_url}")
                elif self.processing_mode == ProcessingMode.WEBHOOK:
                    raise ValueError("Modo webhook requiere webhook_base_url configurado")
            
            # Crear video en HeyGen usando el método especializado para reels
            video_result = self.service.create_reel_video(
                avatar_id=avatar.avatar_ref,
                script=reel_model.script,
                resolution=getattr(reel_model, 'resolution', '720x1280'),
                background_type=getattr(reel_model, 'background_type', 'color'),
                background_value=getattr(reel_model, 'background_value', '#FFFFFF'),
                voice_id=getattr(reel_model, 'voice_id', None),  # Voz del usuario o None para usar default
                title=f"Reel_{reel_model.id}_{reel_model.title}",
                webhook_url=webhook_url
            )
            
            if not video_result:
                raise HeyGenError("Error iniciando procesamiento en HeyGen")
            
            # Extraer ID del video y guardar en el modelo
            video_data = video_result.get('data', {})
            video_id = video_data.get('video_id')
            
            if not video_id:
                raise HeyGenError("HeyGen no devolvió ID del video")
            
            # Actualizar modelo con información del procesamiento
            reel_model.heygen_video_id = video_id
            
            # Guardar cambios en la base de datos
            from app import db
            db.session.commit()
            
            logger.info(f"Reel {reel_model.id} enviado a HeyGen - Video ID: {video_id}")
            logger.info(f"Modo de procesamiento: {self.processing_mode.value}")
            
            # Si no usamos webhooks, programar polling
            if self.processing_mode == ProcessingMode.POLLING:
                logger.info("Modo polling: usar check_video_status() para monitorear progreso")
            elif webhook_url:
                logger.info(f"Webhook configurado: {webhook_url}")
            
            return True
            
        except (HeyGenQuotaExceededError, HeyGenError, ValueError) as e:
            # Errores específicos que deben ser re-lanzados
            logger.error(f"Error específico procesando reel {reel_model.id}: {str(e)}")
            self._mark_reel_failed(reel_model, str(e))
            raise
            
        except Exception as e:
            # Errores generales
            error_msg = f"Error inesperado procesando reel: {str(e)}"
            logger.error(f"Error procesando reel {reel_model.id}: {error_msg}")
            self._mark_reel_failed(reel_model, error_msg)
            return False


    def check_video_status(self, reel_model) -> bool:
        """
        Verifica y actualiza el estado de procesamiento de un video en HeyGen.
        
        Consulta el estado actual del video en HeyGen y actualiza
        automáticamente el modelo del reel en la base de datos según
        el estado obtenido (completed, failed, processing).
        
        Args:
            reel_model (Reel): Instancia del modelo Reel
        
        Returns:
            bool: True si el video está completado, False si aún está procesando o falló
        
        Raises:
            ValueError: Si el reel no tiene video_id de HeyGen
        
        States Handled:
            - completed: Actualiza URLs y marca como completado usando processing_completed_at
            - failed: Marca como fallido con mensaje de error usando error_message
            - processing: Mantiene estado actual
            - pending: Mantiene estado actual
        
        Example:
            >>> completed = processor.check_video_status(reel_instance)
            >>> if completed:
            ...     print(f"Video listo: {reel_instance.video_url}")
        """
        if not reel_model.heygen_video_id:
            raise ValueError("Reel no tiene ID de video de HeyGen")
        
        try:
            # Obtener estado actual del video
            video_status = self.service.get_video_status(reel_model.heygen_video_id)
            
            if not video_status:
                logger.warning(f"No se pudo obtener estado del video {reel_model.heygen_video_id}")
                return False
            
            data = video_status.get('data', {})
            status = data.get('status', 'unknown')
            
            logger.info(f"Video {reel_model.heygen_video_id} - Estado: {status}")
            
            if status == 'completed':
                # Video completado exitosamente
                video_url = data.get('video_url')
                thumbnail_url = data.get('thumbnail_url')
                duration = data.get('duration', 0)
                
                if video_url:
                    # Actualizar modelo con datos del video completado
                    reel_model.status = 'completed'
                    reel_model.video_url = video_url
                    reel_model.thumbnail_url = thumbnail_url
                    reel_model.duration = duration
                    reel_model.processing_completed_at = datetime.utcnow()
                    
                    # 🆕 DESCARGAR VIDEO LOCALMENTE
                    try:
                        from app.services.video_download_service import VideoDownloadService
                        
                        logger.info(f"Iniciando descarga local del video para reel {reel_model.id}")
                        local_path = VideoDownloadService.download_video(
                            video_url=video_url,
                            reel_id=reel_model.id,
                            original_filename=f"reel_{reel_model.id}_{reel_model.title[:50]}.mp4"
                        )
                        
                        if local_path:
                            # Generar URL local para servir el video
                            local_url = VideoDownloadService.get_local_video_url(local_path, reel_model.id)
                            if local_url:
                                # Guardar la ruta local en metadatos
                                if not reel_model.meta_data:
                                    reel_model.meta_data = {}
                                reel_model.meta_data['local_video_path'] = local_path
                                reel_model.meta_data['local_video_url'] = local_url
                                reel_model.meta_data['downloaded_at'] = datetime.utcnow().isoformat()
                                
                                logger.info(f"Video descargado localmente para reel {reel_model.id}: {local_path}")
                        else:
                            logger.warning(f"No se pudo descargar el video localmente para reel {reel_model.id}")
                            
                    except Exception as e:
                        logger.error(f"Error descargando video localmente para reel {reel_model.id}: {str(e)}")
                        # No fallar el proceso completo por error de descarga
                    
                    # Guardar cambios
                    from app import db
                    db.session.commit()
                    
                    logger.info(f"Reel {reel_model.id} completado exitosamente")
                    
                    # Enviar notificación de completado (opcional)
                    # NOTA: Deshabilitado hasta crear template reel_completed.html
                    # self._notify_reel_completed(reel_model)
                    
                    return True
                else:
                    error_msg = "Video marcado como completado pero sin URL de descarga"
                    self._mark_reel_failed(reel_model, error_msg)
                    return False
                    
            elif status == 'failed':
                # Video falló en el procesamiento
                error_message = data.get('error_message', 'Error desconocido en HeyGen')
                self._mark_reel_failed(reel_model, error_message)
                return False
                
            elif status == 'processing':
                # Video aún en procesamiento
                logger.info(f"Video {reel_model.heygen_video_id} en procesamiento")
                return False
                
            elif status == 'pending':
                # Video en cola, mantener estado actual
                logger.info(f"Video {reel_model.heygen_video_id} en cola de procesamiento")
                return False
                
            else:
                # Estado desconocido
                logger.warning(f"Estado desconocido para video {reel_model.heygen_video_id}: {status}")
                return False
                
        except Exception as e:
            error_msg = f"Error verificando estado del video: {str(e)}"
            logger.error(f"Error verificando video {reel_model.heygen_video_id}: {error_msg}")
            self._mark_reel_failed(reel_model, error_msg)
            return False


    def should_use_polling(self) -> bool:
        """
        Determina si debe usarse polling para verificar estado de videos.
        
        Returns:
            bool: True si debe usar polling, False si usa webhooks
        
        Note:
            - POLLING: Siempre True
            - WEBHOOK: Siempre False (usa solo webhooks)
            - HYBRID: True como fallback si webhook falla
        """
        return self.processing_mode in [ProcessingMode.POLLING, ProcessingMode.HYBRID]


    def get_processing_mode_info(self) -> Dict[str, Any]:
        """
        Obtiene información sobre el modo de procesamiento actual.
        
        Returns:
            Dict: Información del modo actual:
                - mode (str): Modo actual
                - uses_webhooks (bool): Si usa webhooks
                - uses_polling (bool): Si requiere polling
                - webhook_url (str): URL base de webhook o None
        """
        return {
            "mode": self.processing_mode.value,
            "uses_webhooks": self.processing_mode in [ProcessingMode.WEBHOOK, ProcessingMode.HYBRID],
            "uses_polling": self.processing_mode in [ProcessingMode.POLLING, ProcessingMode.HYBRID],
            "webhook_url": self.webhook_base_url
        }


    def bulk_check_processing_reels(self, limit: int = 50) -> Dict[str, int]:
        """
        Verifica en lote el estado de múltiples reels en procesamiento.
        
        Consulta la base de datos por reels en estado 'processing' y
        verifica su estado en HeyGen de manera eficiente, actualizando
        todos los modelos según corresponda.
        
        Args:
            limit (int): Máximo número de reels a verificar por lote
        
        Returns:
            Dict[str, int]: Estadísticas de la verificación:
                - checked: Número de reels verificados
                - completed: Número de reels completados
                - failed: Número de reels fallidos
                - still_processing: Número de reels aún procesando
        
        Note:
            Esta función debe ser ejecutada periódicamente (ej: cada 5 minutos)
            por un job scheduler como Celery para mantener actualizados los estados.
        
        Example:
            >>> stats = processor.bulk_check_processing_reels()
            >>> print(f"Verificados: {stats['checked']}, Completados: {stats['completed']}")
        """
        from app.models.reel import Reel
        from app import db
        
        stats = {
            'checked': 0,
            'completed': 0,
            'failed': 0,
            'still_processing': 0
        }
        
        try:
            # Obtener reels en procesamiento
            processing_reels = Reel.query.filter_by(status='processing')\
                                        .filter(Reel.heygen_video_id.isnot(None))\
                                        .limit(limit)\
                                        .all()
            
            logger.info(f"Verificando {len(processing_reels)} reels en procesamiento")
            
            for reel in processing_reels:
                try:
                    stats['checked'] += 1
                    is_completed = self.check_video_status(reel)
                    
                    if is_completed:
                        stats['completed'] += 1
                    elif reel.status == 'failed':
                        stats['failed'] += 1
                    else:
                        stats['still_processing'] += 1
                        
                except Exception as e:
                    logger.error(f"Error verificando reel {reel.id}: {str(e)}")
                    stats['failed'] += 1
            
            logger.info(f"Verificación en lote completada - Stats: {stats}")
            return stats
            
        except Exception as e:
            logger.error(f"Error en verificación en lote: {str(e)}")
            return stats


    # ============================================================================
    # MÉTODOS AUXILIARES PRIVADOS
    # ============================================================================


    def _mark_reel_failed(self, reel_model, error_message: str):
        """
        Marca un reel como fallido y guarda el mensaje de error.
        
        Args:
            reel_model (Reel): Modelo del reel
            error_message (str): Mensaje de error descriptivo
        """
        try:
            reel_model.status = 'failed'
            reel_model.error_message = error_message
            # Usar processing_completed_at para indicar cuando falló
            reel_model.processing_completed_at = datetime.utcnow()
            
            from app import db
            db.session.commit()
            
            logger.error(f"Reel {reel_model.id} marcado como fallido: {error_message}")
            
            # Enviar notificación de falla (opcional)
            # NOTA: Deshabilitado hasta crear template reel_failed.html
            # self._notify_reel_failed(reel_model, error_message)
            
        except Exception as e:
            logger.error(f"Error marcando reel {reel_model.id} como fallido: {str(e)}")


    def _notify_reel_completed(self, reel_model):
        """
        Envía notificaciones cuando un reel se completa exitosamente.
        
        Args:
            reel_model (Reel): Modelo del reel completado
        """
        try:
            # Importar servicio de email para evitar importaciones circulares
            from app.services.email_service import send_reel_completed_notification
            
            user = reel_model.user
            if user and user.email:
                send_reel_completed_notification(
                    user_email=user.email,
                    user_name=user.full_name,
                    reel_title=reel_model.title,
                    video_url=reel_model.video_url,
                    reel_id=reel_model.id
                )
                
        except Exception as e:
            logger.error(f"Error enviando notificación de completado para reel {reel_model.id}: {str(e)}")


    def _notify_reel_failed(self, reel_model, error_message: str):
        """
        Envía notificaciones cuando un reel falla en el procesamiento.
        
        Args:
            reel_model (Reel): Modelo del reel fallido
            error_message (str): Mensaje de error
        """
        try:
            # Importar servicio de email para evitar importaciones circulares
            from app.services.email_service import send_reel_failed_notification
            
            user = reel_model.user
            if user and user.email:
                send_reel_failed_notification(
                    user_email=user.email,
                    user_name=user.full_name,
                    reel_title=reel_model.title,
                    error_message=error_message,
                    reel_id=reel_model.id
                )
                
        except Exception as e:
            logger.error(f"Error enviando notificación de falla para reel {reel_model.id}: {str(e)}")


# ============================================================================
# FUNCIONES DE UTILIDAD Y HELPERS
# ============================================================================


def validate_heygen_config() -> bool:
    """
    Valida que la configuración de HeyGen esté correctamente establecida.
    
    Verifica que todas las configuraciones necesarias para HeyGen estén
    presentes y sean válidas en la configuración de la aplicación.
    
    Returns:
        bool: True si la configuración es válida, False en caso contrario
    
    Example:
        >>> if validate_heygen_config():
        ...     service = HeyGenService(api_key)
        ... else:
        ...     print("Configuración de HeyGen inválida")
    """
    from flask import current_app
    
    required_configs = [
        'HEYGEN_BASE_URL'
    ]
    
    try:
        for config in required_configs:
            if not current_app.config.get(config):
                logger.error(f"Configuración de HeyGen faltante: {config}")
                return False
        
        # Validar formato de URL base
        base_url = current_app.config.get('HEYGEN_BASE_URL')
        if not base_url.startswith(('http://', 'https://')):
            logger.error("HEYGEN_BASE_URL debe ser una URL válida")
            return False
        
        logger.info("Configuración de HeyGen validada exitosamente")
        return True
        
    except Exception as e:
        logger.error(f"Error validando configuración de HeyGen: {str(e)}")
        return False


def create_service_from_producer(producer) -> Optional[HeyGenService]:
    """
    Crea una instancia de HeyGenService usando la API key de un productor.
    
    Extrae y desencripta la API key del productor para crear un servicio
    de HeyGen configurado específicamente para ese productor.
    
    Args:
        producer (Producer): Instancia del modelo Producer
    
    Returns:
        Optional[HeyGenService]: Servicio configurado o None si hay error
    
    Raises:
        ValueError: Si el productor no tiene API key válida
        
    Example:
        >>> service = create_service_from_producer(producer_instance)
        >>> if service:
        ...     avatars = service.list_avatars()
    """
    try:
        if not producer or not producer.heygen_api_key_encrypted:
            raise ValueError("Productor no tiene API key de HeyGen configurada")
        
        # Desencriptar API key del productor
        api_key = producer.get_decrypted_api_key()
        
        if not api_key:
            raise ValueError("No se pudo desencriptar la API key del productor")
        
        # Crear servicio con la API key del productor
        service = HeyGenService(api_key)
        
        # Validar que la API key sea funcional
        if not service.validate_api_key():
            raise ValueError("API key del productor no es válida en HeyGen")
        
        logger.info(f"Servicio HeyGen creado para productor {producer.id}")
        return service
        
    except Exception as e:
        logger.error(f"Error creando servicio para productor {producer.id}: {str(e)}")
        return None


def estimate_video_duration(script_text: str, 
                          words_per_minute: int = 150) -> int:
    """
    Estima la duración de un video basado en el texto del script.
    
    Calcula la duración aproximada del video en segundos basándose
    en la longitud del script y la velocidad promedio de habla.
    
    Args:
        script_text (str): Texto del script
        words_per_minute (int): Velocidad de habla en palabras por minuto
    
    Returns:
        int: Duración estimada en segundos
    
    Example:
        >>> script = "Hola, este es mi mensaje de ejemplo"
        >>> duration = estimate_video_duration(script)
        >>> print(f"Duración estimada: {duration} segundos")
    """
    if not script_text or len(script_text.strip()) == 0:
        return 0
    
    # Contar palabras en el script
    words = len(script_text.split())
    
    # Calcular duración en minutos y convertir a segundos
    duration_minutes = words / words_per_minute
    duration_seconds = int(duration_minutes * 60)
    
    # Agregar buffer mínimo y máximo
    duration_seconds = max(duration_seconds, 5)  # Mínimo 5 segundos
    duration_seconds = min(duration_seconds, 600)  # Máximo 10 minutos
    
    return duration_seconds


def get_available_voices_for_avatar(service: HeyGenService, avatar_id: str, language: str = 'es') -> Dict[str, Any]:
    """
    Obtiene las voces disponibles para un avatar específico, incluyendo su voz predeterminada.
    
    Esta función facilita la selección de voces para el usuario, proporcionando:
    1. La voz predeterminada del avatar (si tiene)
    2. Lista de todas las voces disponibles en el idioma
    3. Información sobre si se requiere selección manual
    
    Args:
        service (HeyGenService): Instancia del servicio de HeyGen
        avatar_id (str) : ID del avatar
        language (str)  : Idioma deseado para las voces
    
    Returns:
        Dict[str, Any]                      : Información completa sobre voces:
            - has_default (bool)            : Si el avatar tiene voz predeterminada
            - default_voice (Dict)          : Información de la voz predeterminada
            - available_voices (List[Dict]) : Lista de voces disponibles
            - requires_selection (bool)     : Si el usuario debe elegir obligatoriamente
    
    Example:
        >>> voice_options = get_available_voices_for_avatar(service, "avatar_123", "es")
        >>> if voice_options['has_default']:
        ...     print(f"Voz predeterminada: {voice_options['default_voice']['name']}")
        >>> else:
        ...     print("Usuario debe elegir voz de la lista")
    """
    result = {
        'has_default'       : False,
        'default_voice'     : None,
        'available_voices'  : [],
        'requires_selection': False
    }
    
    try:
        # Obtener voz predeterminada del avatar
        default_voice_id = service.get_avatar_default_voice(avatar_id)
        
        if default_voice_id:
            default_voice_info           = service.get_voice_details(default_voice_id)
            result['has_default']        = True
            result['default_voice']      = default_voice_info
            result['requires_selection'] = False
        else:
            result['requires_selection'] = True
        
        # Obtener todas las voces disponibles en el idioma
        available_voices = service.list_voices(language=language)
        result['available_voices'] = available_voices
        
        logger.info(f"Avatar {avatar_id}: Voz default={result['has_default']}, Voces disponibles={len(available_voices)}")
        
    except Exception as e:
        logger.error(f"Error obteniendo voces para avatar {avatar_id}: {str(e)}")
    
    return result


def setup_webhook_for_producer(service: HeyGenService, producer, base_url: str) -> Optional[str]:
    """
    Configura automáticamente un webhook para un productor específico.
    
    Crea un webhook personalizado para el productor que recibirá notificaciones
    de todos sus videos y avatares en una URL específica de la aplicación.
    
    Args:
        service (HeyGenService): Instancia del servicio de HeyGen
        producer: Modelo del productor
        base_url (str): URL base de la aplicación
    
    Returns:
        Optional[str]: ID del endpoint creado o None si falló
    
    Example:
        >>> service = create_service_from_producer(producer)
        >>> webhook_id = setup_webhook_for_producer(
        ...     service, producer, "https://mi-app.com"
        ... )
    """
    try:
        # Crear URL específica para el productor
        webhook_url = f"{base_url}/webhooks/heygen/producer/{producer.id}"
        
        # Eventos importantes para productores
        producer_events = [
            "avatar_video.success",
            "avatar_video.fail", 
            "photo_avatar_generation.success",
            "photo_avatar_generation.fail",
            "instant_avatar.success",
            "instant_avatar.fail"
        ]
        
        result = service.add_webhook_endpoint(webhook_url, producer_events)
        
        if result and result.get('code') == 100:
            endpoint_id = result.get('data', {}).get('endpoint_id')
            secret = result.get('data', {}).get('secret')
            
            # Guardar información del webhook en el productor (opcional)
            # producer.heygen_webhook_id = endpoint_id
            # producer.heygen_webhook_secret = secret
            # db.session.commit()
            
            logger.info(f"Webhook configurado para productor {producer.id}: {endpoint_id}")
            return endpoint_id
        
        return None
        
    except Exception as e:
        logger.error(f"Error configurando webhook para productor {producer.id}: {str(e)}")
        return None


def verify_webhook_signature(payload: str, signature: str, secret: str) -> bool:
    """
    Verifica la firma de un webhook de HeyGen para validar autenticidad.
    
    Valida que la notificación webhook realmente proviene de HeyGen
    usando la clave secreta proporcionada al crear el endpoint.
    
    Args:
        payload (str): Cuerpo del payload del webhook
        signature (str): Firma recibida en los headers
        secret (str): Clave secreta del webhook
    
    Returns:
        bool: True si la firma es válida, False en caso contrario
    
    Example:
        >>> is_valid = verify_webhook_signature(
        ...     request.data.decode(),
        ...     request.headers.get('X-HeyGen-Signature'),
        ...     webhook_secret
        ... )
        >>> if is_valid:
        ...     # Procesar webhook
    """
    try:
        import hmac
        import hashlib
        
        # Calcular firma esperada
        expected_signature = hmac.new(
            secret.encode('utf-8'),
            payload.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        # Comparar firmas de manera segura
        return hmac.compare_digest(signature, expected_signature)
        
    except Exception as e:
        logger.error(f"Error verificando firma de webhook: {str(e)}")
        return False


def format_heygen_error(error_response: Dict) -> str:
    """
    Formatea un error de HeyGen en un mensaje amigable para el usuario.
    
    Convierte respuestas de error de la API de HeyGen en mensajes
    comprensibles para mostrar a los usuarios finales.
    
    Args:
        error_response (Dict): Respuesta de error de HeyGen
    
    Returns:
        str: Mensaje de error formateado para el usuario
    
    Example:
        >>> error_msg = format_heygen_error(heygen_error_response)
        >>> flash(error_msg, 'error')
    """
    if not error_response:
        return "Error desconocido en HeyGen"
    
    # Extraer información del error
    error_code = error_response.get('code', 'UNKNOWN')
    error_message = error_response.get('message', 'Error desconocido')
    
    # Mapeo de códigos de error comunes a mensajes amigables
    error_messages = {
        'QUOTA_EXCEEDED'     : 'Has excedido tu cuota mensual de videos. Contacta al administrador.',
        'INVALID_AVATAR'     : 'El avatar seleccionado no es válido o no está disponible.',
        'INVALID_SCRIPT'     : 'El texto del script contiene caracteres no válidos.',
        'PROCESSING_FAILED'  : 'Error en el procesamiento del video. Intenta nuevamente.',
        'INVALID_API_KEY'    : 'Clave de API inválida. Verifica tu configuración.',
        'AVATAR_NOT_READY'   : 'El avatar aún está siendo procesado. Intenta más tarde.',
        'VIDEO_TOO_LONG'     : 'El script es demasiado largo. Reduce el texto.',
        'UNSUPPORTED_FORMAT' : 'Formato de video no soportado para esta configuración.'
    }
    
    # Devolver mensaje amigable si existe, sino el mensaje original
    friendly_message = error_messages.get(error_code, error_message)
    
    return f"{friendly_message}"