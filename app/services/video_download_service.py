import os
import requests
import logging
from urllib.parse import urlparse
from datetime import datetime
from flask import current_app

logger = logging.getLogger(__name__)

class VideoDownloadService:
    """
    Servicio para descargar y almacenar videos de HeyGen localmente.
    
    Este servicio se encarga de descargar videos desde HeyGen y guardarlos
    en el servidor local para preservación a largo plazo, ya que HeyGen
    puede eliminar los videos después de cierto tiempo.
    """
    
    @staticmethod
    def get_downloads_directory():
        """Obtiene el directorio base para descargas de videos."""
        base_dir = current_app.config.get('VIDEO_DOWNLOAD_DIR', 'static/videos')
        if not os.path.isabs(base_dir):
            base_dir = os.path.join(current_app.root_path, base_dir)
        
        os.makedirs(base_dir, exist_ok=True)
        return base_dir
    
    @staticmethod
    def download_video(video_url, reel_id, original_filename=None):
        """
        Descarga un video desde HeyGen y lo guarda localmente.
        
        Args:
            video_url (str): URL del video en HeyGen
            reel_id (int): ID del reel en nuestra base de datos
            original_filename (str): Nombre original del archivo (opcional)
            
        Returns:
            str: Ruta local del archivo descargado, o None si falla
        """
        try:
            logger.info(f"Iniciando descarga de video para reel {reel_id}")
            
            # Generar nombre de archivo único con timestamp
            if not original_filename:
                # Usar timestamp para evitar duplicados como en user.py
                import time
                timestamp = int(time.time())
                original_filename = f"reel_{reel_id}_{timestamp}.mp4"
            
            # Asegurar que tenga extensión
            if not os.path.splitext(original_filename)[1]:
                original_filename += '.mp4'
            
            # Obtener directorio de destino
            download_dir = VideoDownloadService.get_downloads_directory()
            local_path = os.path.join(download_dir, original_filename)
            
            # Verificar si ya existe
            if os.path.exists(local_path):
                logger.info(f"Video ya descargado en: {local_path}")
                return local_path
            
            # Descargar el video
            logger.info(f"Descargando video de: {video_url}")
            response = requests.get(video_url, stream=True, timeout=300)
            response.raise_for_status()
            
            # Guardar el archivo
            with open(local_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            
            file_size = os.path.getsize(local_path)
            logger.info(f"Video descargado exitosamente: {local_path} ({file_size} bytes)")
            
            return local_path
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Error de red descargando video para reel {reel_id}: {str(e)}")
            return None
        except OSError as e:
            logger.error(f"Error de sistema descargando video para reel {reel_id}: {str(e)}")
            return None
        except Exception as e:
            logger.error(f"Error inesperado descargando video para reel {reel_id}: {str(e)}")
            return None
    
    @staticmethod
    def get_local_video_url(local_path, reel_id):
        """
        Genera una URL local para acceder al video descargado.
        
        Args:
            local_path (str): Ruta local del archivo
            reel_id (int): ID del reel
            
        Returns:
            str: URL relativa para acceder al video
        """
        if not local_path or not os.path.exists(local_path):
            return None
        
        # Convertir ruta absoluta a URL relativa para static/videos
        try:
            # Para static/videos, generar URL relativa desde la raíz de la app
            if 'static' in local_path and 'videos' in local_path:
                # Extraer solo el nombre del archivo
                filename = os.path.basename(local_path)
                return f"/static/videos/{filename}"
            
            # Fallback para otros directorios
            filename = os.path.basename(local_path)
            return f"/static/videos/{filename}"
            
        except Exception as e:
            logger.error(f"Error generando URL local para reel {reel_id}: {str(e)}")
            return None
    
    @staticmethod
    def cleanup_old_downloads(days_old=90):
        """
        Limpia descargas antiguas para liberar espacio.
        
        Args:
            days_old (int): Días de antigüedad para considerar archivos viejos
        """
        try:
            base_dir = VideoDownloadService.get_downloads_directory()
            cutoff_time = datetime.now().timestamp() - (days_old * 24 * 60 * 60)
            
            cleaned_count = 0
            cleaned_size = 0
            
            # Iterar archivos en el directorio base (sin subdirectorios)
            for file in os.listdir(base_dir):
                file_path = os.path.join(base_dir, file)
                if os.path.isfile(file_path) and os.path.getmtime(file_path) < cutoff_time:
                    try:
                        file_size = os.path.getsize(file_path)
                        os.remove(file_path)
                        cleaned_count += 1
                        cleaned_size += file_size
                        logger.info(f"Archivo eliminado: {file_path}")
                    except Exception as e:
                        logger.warning(f"No se pudo eliminar {file_path}: {str(e)}")
            
            logger.info(f"Limpieza completada: {cleaned_count} archivos, {cleaned_size} bytes liberados")
            
        except Exception as e:
            logger.error(f"Error en limpieza de archivos: {str(e)}")