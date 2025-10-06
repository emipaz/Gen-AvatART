import requests
import json
from typing import Dict, Optional, List
from datetime import datetime

class HeyGenService:
    """Servicio para interactuar con la API de HeyGen"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.heygen.com"):
        self.api_key = api_key
        self.base_url = base_url
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'Bearer {api_key}',
            'Content-Type': 'application/json'
        })
    
    def validate_api_key(self) -> bool:
        """Valida si la API key es válida"""
        try:
            response = self.session.get(f"{self.base_url}/v1/user")
            return response.status_code == 200
        except Exception as e:
            print(f"Error validando API key: {e}")
            return False
    
    def get_user_info(self) -> Optional[Dict]:
        """Obtiene información del usuario"""
        try:
            response = self.session.get(f"{self.base_url}/v1/user")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error obteniendo info del usuario: {e}")
            return None
    
    def list_avatars(self) -> List[Dict]:
        """Lista todos los avatars disponibles"""
        try:
            response = self.session.get(f"{self.base_url}/v1/avatars")
            if response.status_code == 200:
                data = response.json()
                return data.get('data', [])
            return []
        except Exception as e:
            print(f"Error listando avatars: {e}")
            return []
    
    def create_avatar(self, avatar_data: Dict) -> Optional[Dict]:
        """Crea un nuevo avatar"""
        try:
            response = self.session.post(
                f"{self.base_url}/v1/avatars",
                json=avatar_data
            )
            if response.status_code in [200, 201]:
                return response.json()
            return None
        except Exception as e:
            print(f"Error creando avatar: {e}")
            return None
    
    def get_avatar(self, avatar_id: str) -> Optional[Dict]:
        """Obtiene información de un avatar específico"""
        try:
            response = self.session.get(f"{self.base_url}/v1/avatars/{avatar_id}")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error obteniendo avatar {avatar_id}: {e}")
            return None
    
    def create_video(self, video_data: Dict) -> Optional[Dict]:
        """Crea un nuevo video con avatar"""
        try:
            response = self.session.post(
                f"{self.base_url}/v1/videos",
                json=video_data
            )
            if response.status_code in [200, 201]:
                return response.json()
            return None
        except Exception as e:
            print(f"Error creando video: {e}")
            return None
    
    def get_video_status(self, video_id: str) -> Optional[Dict]:
        """Obtiene el estado de generación de un video"""
        try:
            response = self.session.get(f"{self.base_url}/v1/videos/{video_id}")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error obteniendo estado del video {video_id}: {e}")
            return None
    
    def list_voices(self, language: str = 'es') -> List[Dict]:
        """Lista las voces disponibles para un idioma"""
        try:
            response = self.session.get(
                f"{self.base_url}/v1/voices",
                params={'language': language}
            )
            if response.status_code == 200:
                data = response.json()
                return data.get('data', [])
            return []
        except Exception as e:
            print(f"Error listando voces: {e}")
            return []
    
    def get_quota_info(self) -> Optional[Dict]:
        """Obtiene información de la cuota de la API"""
        try:
            response = self.session.get(f"{self.base_url}/v1/user/quota")
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error obteniendo cuota: {e}")
            return None
    
    def create_reel_video(self, avatar_id: str, script: str, **kwargs) -> Optional[Dict]:
        """
        Crea un video reel con configuración específica
        
        Args:
            avatar_id: ID del avatar a usar
            script: Texto que dirá el avatar
            **kwargs: Configuraciones adicionales (background, voice, etc.)
        """
        video_data = {
            "avatar_id": avatar_id,
            "script": script,
            "aspect_ratio": kwargs.get('aspect_ratio', '9:16'),  # Formato reel
            "resolution": kwargs.get('resolution', '1080p'),
            "background": {
                "type": kwargs.get('background_type', 'color'),
                "value": kwargs.get('background_value', '#ffffff')
            }
        }
        
        # Agregar configuración de voz si se especifica
        if 'voice_id' in kwargs:
            video_data['voice'] = {
                "voice_id": kwargs['voice_id'],
                "speed": kwargs.get('voice_speed', 1.0),
                "pitch": kwargs.get('voice_pitch', 1.0)
            }
        
        # Agregar configuración de video si se especifica
        if 'video_settings' in kwargs:
            video_data.update(kwargs['video_settings'])
        
        return self.create_video(video_data)
    
    def upload_avatar_image(self, image_path: str) -> Optional[Dict]:
        """Sube una imagen para crear un avatar personalizado"""
        try:
            with open(image_path, 'rb') as image_file:
                files = {'file': image_file}
                headers = {'Authorization': f'Bearer {self.api_key}'}
                
                response = requests.post(
                    f"{self.base_url}/v1/avatars/upload",
                    files=files,
                    headers=headers
                )
                
                if response.status_code in [200, 201]:
                    return response.json()
                return None
        except Exception as e:
            print(f"Error subiendo imagen de avatar: {e}")
            return None
    
    def get_video_download_url(self, video_id: str) -> Optional[str]:
        """Obtiene la URL de descarga de un video completado"""
        video_info = self.get_video_status(video_id)
        if video_info and video_info.get('status') == 'completed':
            return video_info.get('download_url')
        return None
    
    def cancel_video(self, video_id: str) -> bool:
        """Cancela la generación de un video"""
        try:
            response = self.session.delete(f"{self.base_url}/v1/videos/{video_id}")
            return response.status_code in [200, 204]
        except Exception as e:
            print(f"Error cancelando video {video_id}: {e}")
            return False
    
    def get_usage_statistics(self, start_date: datetime, end_date: datetime) -> Optional[Dict]:
        """Obtiene estadísticas de uso en un rango de fechas"""
        try:
            params = {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            }
            response = self.session.get(
                f"{self.base_url}/v1/user/usage",
                params=params
            )
            if response.status_code == 200:
                return response.json()
            return None
        except Exception as e:
            print(f"Error obteniendo estadísticas de uso: {e}")
            return None


class HeyGenError(Exception):
    """Excepción personalizada para errores de HeyGen"""
    
    def __init__(self, message: str, error_code: str = None, response: Dict = None):
        self.message = message
        self.error_code = error_code
        self.response = response
        super().__init__(self.message)


class HeyGenVideoProcessor:
    """Procesador de videos de HeyGen con manejo de estados"""
    
    def __init__(self, api_key: str):
        self.service = HeyGenService(api_key)
    
    def process_reel(self, reel_model) -> bool:
        """
        Procesa un reel usando HeyGen
        
        Args:
            reel_model: Instancia del modelo Reel
            
        Returns:
            bool: True si el procesamiento inició correctamente
        """
        try:
            # Marcar como procesando
            reel_model.start_processing()
            
            # Obtener configuración del avatar
            avatar = reel_model.avatar
            if not avatar.heygen_avatar_id:
                raise HeyGenError("Avatar no tiene ID de HeyGen válido")
            
            # Crear video en HeyGen
            video_data = self.service.create_reel_video(
                avatar_id=avatar.heygen_avatar_id,
                script=reel_model.script,
                resolution=reel_model.resolution,
                background_type=reel_model.background_type,
                background_value=reel_model.background_url
            )
            
            if not video_data:
                raise HeyGenError("Error creando video en HeyGen")
            
            # Guardar ID del video
            reel_model.heygen_video_id = video_data.get('id')
            
            return True
            
        except Exception as e:
            reel_model.fail_processing(str(e))
            return False
    
    def check_video_status(self, reel_model) -> bool:
        """
        Verifica el estado de procesamiento de un video
        
        Returns:
            bool: True si el video está completado
        """
        if not reel_model.heygen_video_id:
            return False
        
        try:
            video_info = self.service.get_video_status(reel_model.heygen_video_id)
            
            if not video_info:
                return False
            
            status = video_info.get('status')
            
            if status == 'completed':
                # Video completado
                download_url = video_info.get('download_url')
                thumbnail_url = video_info.get('thumbnail_url')
                
                reel_model.complete_processing(download_url, thumbnail_url)
                return True
                
            elif status == 'failed':
                # Video falló
                error_msg = video_info.get('error', 'Error desconocido en HeyGen')
                reel_model.fail_processing(error_msg)
                return False
            
            # Aún en procesamiento
            return False
            
        except Exception as e:
            reel_model.fail_processing(f"Error verificando estado: {str(e)}")
            return False