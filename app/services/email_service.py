"""
Módulo de servicio de Email para la aplicación Gem-AvatART.

Este módulo proporciona funcionalidades completas para el envío de emails
en la aplicación, incluyendo plantillas, emails transaccionales, notificaciones
del sistema y comunicaciones relacionadas con el flujo de trabajo de HeyGen.

FUNCIONALIDADES SEGÚN README:
    - Notificaciones de registro y verificación de usuarios
    - Comunicaciones del sistema de comisiones y pagos
    - Notificaciones de procesamiento de videos (HeyGen webhooks)
    - Emails de gestión de permisos de clones
    - Comunicaciones de productores y Stripe Connect
    - Templates HTML responsivos para diferentes tipos de emails

El módulo incluye:
    - Función básica send_email(): Envío de emails simple
    - Templates predefinidos para casos de uso comunes
    - Manejo de errores y logging de emails
    - Soporte para emails HTML con fallback a texto plano
    - Queue system para emails masivos (futuro)
    - Integración con el sistema de notificaciones

Dependencias:
    - Flask-Mail: Para el envío de emails
    - Jinja2: Para renderizado de templates
    - app.config: Para configuración SMTP
"""

from flask import current_app, render_template
from flask_mail import Message
from app import mail
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime

# Configurar logging para el servicio de emails
logger = logging.getLogger(__name__)


# ============================================================================
# FUNCIONES BÁSICAS DE ENVÍO
# ============================================================================


def send_email(subject     : str, 
               recipients  : List[str], 
               body        : str, 
               html        : Optional[str]        = None,
               sender      : Optional[str]        = None, 
               cc          : Optional[List[str]]  = None, 
               bcc         : Optional[List[str]]  = None, 
               attachments : Optional[List[Dict]] = None) -> bool:
    """
    Envía un email básico con soporte para HTML y archivos adjuntos.
    
    Args:
        subject (str)             : Asunto del email
        recipients (List[str])    : Lista de destinatarios
        body (str)                : Contenido del email en texto plano
        html (str, opcional)      : Contenido HTML del email
        sender (str, opcional)    : Remitente (usa configuración por defecto si no se especifica)
        cc (List[str], opcional)  : Lista de destinatarios en copia
        bcc (List[str], opcional) : Lista de destinatarios en copia oculta
        
        attachments (List[Dict], opcional): Lista de archivos adjuntos
            Formato: [{'filename'    : 'file.pdf', 
                       'content_type': 'application/pdf', 
                       'data'        : bytes}]
    
    Returns:
        bool: True si el email se envió correctamente, False en caso contrario
    
    Example:
        >>> send_email(
        ...     subject="Bienvenido a Gem-AvatART",
        ...     recipients=["usuario@example.com"],
        ...     body="Texto plano del mensaje",
        ...     html="<h1>HTML del mensaje</h1>"
        ... )
        True
    """
    try:
        # Usar remitente por defecto si no se especifica
        if not sender:
            sender = current_app.config.get('MAIL_DEFAULT_SENDER')
        
        # Crear mensaje
        msg = Message(
            subject     = subject,
            recipients  = recipients,
            body        = body,
            html        = html,
            sender      = sender,
            cc          = cc,
            bcc         = bcc
        )
        
        # Agregar archivos adjuntos si existen
        if attachments:
            for attachment in attachments:
                msg.attach(
                    filename      = attachment['filename'],
                    content_type  = attachment['content_type'],
                    data          = attachment['data']
                )
        
        # Enviar email
        mail.send(msg)
        
        # Log exitoso
        logger.info(f"Email enviado exitosamente a {recipients}: {subject}")
        return True
        
    except Exception as e:
        # Log error
        logger.error(f"Error enviando email a {recipients}: {str(e)}")
        return False

def send_template_email(template_name : str, 
                        subject       : str, 
                        recipients    : List[str],
                        template_vars : Dict[str, Any], 
                        sender        : Optional[str] = None) -> bool:
    """
    Envía un email usando una plantilla HTML predefinida.
    
    Args:
        template_name (str)            : Nombre del archivo de plantilla (sin extensión)
        subject (str)                  : Asunto del email
        recipients (List[str])         : Lista de destinatarios
        template_vars (Dict[str, Any]) : Variables para renderizar en la plantilla
        sender (str, opcional)         : Remitente personalizado

    Returns:
        bool: True si el email se envió correctamente, False en caso contrario
    
    Example:
        >>> send_template_email(
        ...     template_name="welcome",
        ...     subject="Bienvenido a Gem-AvatART",
        ...     recipients=["usuario@example.com"],
        ...     template_vars={
        ...         "user_name": "Juan Pérez",
        ...         "verification_link": "https://app.com/verify/123"
        ...     }
        ... )
        True
    """
    try:
        # Renderizar plantilla HTML
        html_content = render_template(f'emails/{template_name}.html', **template_vars)
        
        # Intentar renderizar versión de texto plano
        try:
            text_content = render_template(f'emails/{template_name}.txt', **template_vars)
        except:
            # Si no existe plantilla .txt, usar versión simplificada del HTML
            text_content = _html_to_text(html_content)
        
        # Enviar email usando la función básica
        return send_email(
            subject    = subject,
            recipients = recipients,
            body       = text_content,
            html       = html_content,
            sender     = sender
        )
        
    except Exception as e:
        logger.error(f"Error enviando email con template {template_name}: {str(e)}")
        return False

# ============================================================================
# EMAILS ESPECÍFICOS DEL SISTEMA GEM-AVATAART
# ============================================================================

def send_verification_email(user):
    """
    Envía el email de verificación al usuario.
    Genera/actualiza el token y arma el enlace absoluto.
    """
    from flask import url_for
    # genera y guarda token + timestamp en el usuario
    token = user.generate_verification_token()

    # enlace que usaremos en el próximo paso (ruta verify_email todavía no creada)
    verify_url = url_for('auth.verify_email', token=token, _external=True)

    sender = current_app.config.get("MAIL_DEFAULT_SENDER") or current_app.config.get("MAIL_USERNAME")

    msg = Message(
        subject="Verificá tu email - Gem-AvatART",
        recipients=[user.email],
        sender=sender,
        body=(
            f"Hola {user.first_name}!\n\n"
            "Gracias por registrarte en Gem-AvatART.\n"
            "Por favor verificá tu email haciendo click en el siguiente enlace:\n\n"
            f"{verify_url}\n\n"
            "Si no fuiste vos, podés ignorar este mensaje."
        ),
    )
    mail.send(msg)

def send_welcome_email(user_email : str, user_name : str, verification_token : str) -> bool:
    """
    Envía email de bienvenida con enlace de verificación.
    
    Args:
        user_email (str)         : Email del usuario
        user_name (str)          : Nombre completo del usuario
        verification_token (str) : Token para verificación de cuenta
    
    Returns:
        bool : True si se envió correctamente
    """
    verification_link = f"{current_app.config['FRONTEND_URL']}/verify-email/{verification_token}"
    
    return send_template_email(
        template_name = "welcome",
        subject       = "¡Bienvenido a Gem-AvatART!",
        recipients    = [user_email],
        template_vars = {
            "user_name"         : user_name,
            "verification_link" : verification_link,
            "app_name"          : "Gem-AvatART",
            "company_name"      : current_app.config.get('COMPANY_NAME', 'PassportAI')
        }
    )

def send_producer_application_notification(user_email : str, 
                                           user_name  : str, 
                                           status     : str) -> bool:
    """
    Notifica sobre el estado de la aplicación para ser productor.
    
    Args:
        user_email (str): Email del usuario
        user_name (str): Nombre del usuario
        status (str): Estado de la aplicación (approved, rejected, pending)
    
    Returns:
        bool: True si se envió correctamente
    """
    subject_map = {
        'approved': '🎉 ¡Tu aplicación como Productor ha sido aprobada!',
        'rejected': '❌ Tu aplicación como Productor ha sido rechazada',
        'pending' : '⏳ Tu aplicación como Productor está en revisión'
    }
    
    return send_template_email(
        template_name = f"producer_application_{status}",
        subject       = subject_map.get(status, "Actualización de tu aplicación"),
        recipients    = [user_email],
        template_vars = {
            "user_name"      : user_name,
            "status"         : status,
            "dashboard_link" : f"{current_app.config['FRONTEND_URL']}/dashboard"
        }
    )

def send_reel_completed_notification(user_email: str, user_name: str, reel_title: str, 
                                   video_url: str, reel_id: int) -> bool:
    """
    Notifica cuando un reel ha sido procesado exitosamente por HeyGen.
    
    Args:
        user_email (str): Email del creador del reel
        user_name (str): Nombre del creador
        reel_title (str): Título del reel
        video_url (str): URL del video generado
        reel_id (int): ID del reel
    
    Returns:
        bool: True si se envió correctamente
    """
    return send_template_email(
        template_name="reel_completed",
        subject=f"✅ Tu video '{reel_title}' está listo!",
        recipients=[user_email],
        template_vars={
            "user_name": user_name,
            "reel_title": reel_title,
            "video_url": video_url,
            "reel_view_link": f"{current_app.config['FRONTEND_URL']}/reels/{reel_id}",
            "dashboard_link": f"{current_app.config['FRONTEND_URL']}/dashboard"
        }
    )

def send_reel_failed_notification(user_email: str, user_name: str, reel_title: str, 
                                error_message: str, reel_id: int) -> bool:
    """
    Notifica cuando falla el procesamiento de un reel en HeyGen.
    
    Args:
        user_email (str): Email del creador del reel
        user_name (str): Nombre del creador
        reel_title (str): Título del reel
        error_message (str): Descripción del error
        reel_id (int): ID del reel
    
    Returns:
        bool: True si se envió correctamente
    """
    return send_template_email(
        template_name="reel_failed",
        subject=f"❌ Error procesando tu video '{reel_title}'",
        recipients=[user_email],
        template_vars={
            "user_name": user_name,
            "reel_title": reel_title,
            "error_message": error_message,
            "reel_edit_link": f"{current_app.config['FRONTEND_URL']}/reels/{reel_id}/edit",
            "support_email": current_app.config.get('SUPPORT_EMAIL', 'support@gem-avataart.com')
        }
    )

def send_commission_payment_notification(user_email: str, user_name: str, amount: float, 
                                       commission_type: str, reel_title: str) -> bool:
    """
    Notifica sobre el pago de una comisión.
    
    Args:
        user_email (str): Email del beneficiario
        user_name (str): Nombre del beneficiario
        amount (float): Monto de la comisión
        commission_type (str): Tipo de comisión (producer, subproducer, etc.)
        reel_title (str): Título del reel que generó la comisión
    
    Returns:
        bool: True si se envió correctamente
    """
    return send_template_email(
        template_name="commission_payment",
        subject=f"💰 Has recibido una comisión de ${amount:.2f}",
        recipients=[user_email],
        template_vars={
            "user_name": user_name,
            "amount": amount,
            "commission_type": commission_type,
            "reel_title": reel_title,
            "earnings_link": f"{current_app.config['FRONTEND_URL']}/earnings",
            "payment_date": datetime.utcnow().strftime("%d/%m/%Y")
        }
    )

def send_clone_permission_granted(user_email: str, user_name: str, clone_name: str, 
                                producer_name: str, daily_limit: int, monthly_limit: int) -> bool:
    """
    Notifica cuando se otorga permiso para usar un clone.
    
    Args:
        user_email (str): Email del beneficiario del permiso
        user_name (str): Nombre del beneficiario
        clone_name (str): Nombre del clone/avatar
        producer_name (str): Nombre del productor que otorga el permiso
        daily_limit (int): Límite diario de uso
        monthly_limit (int): Límite mensual de uso
    
    Returns:
        bool: True si se envió correctamente
    """
    return send_template_email(
        template_name = "clone_permission_granted",
        subject       = f"🎭 Tienes acceso al clone '{clone_name}'",
        recipients    = [user_email],
        template_vars = {
            "user_name"        : user_name,
            "clone_name"       : clone_name,
            "producer_name"    : producer_name,
            "daily_limit"      : daily_limit if daily_limit > 0 else "Ilimitado",
            "monthly_limit"    : monthly_limit if monthly_limit > 0 else "Ilimitado",
            "create_reel_link" : f"{current_app.config['FRONTEND_URL']}/create-reel"
        }
    )

def send_stripe_connect_setup_notification(user_email: str, user_name: str, 
                                         onboarding_link: str) -> bool:
    """
    Notifica a productores sobre la configuración de Stripe Connect.
    
    Args:
        user_email (str): Email del productor
        user_name (str): Nombre del productor
        onboarding_link (str): Link de onboarding de Stripe
    
    Returns:
        bool: True si se envió correctamente
    """
    return send_template_email(
        template_name = "stripe_connect_setup",
        subject       = "💳 Configura tu cuenta de pagos en Stripe",
        recipients    = [user_email],
        template_vars = {
            "user_name"       : user_name,
            "onboarding_link" : onboarding_link,
            "benefits"        : [
                "Recibe pagos directamente en tu cuenta",
                "Gestiona automáticamente las comisiones",
                "Acceso a reportes detallados de ingresos",
                "Soporte para múltiples métodos de pago"
            ]
        }
    )

# ============================================================================
# EMAILS ADMINISTRATIVOS
# ============================================================================

def send_admin_notification(subject: str, message: str, level: str = "info") -> bool:
    """
    Envía notificación a los administradores del sistema.
    
    Args:
        subject (str): Asunto del email
        message (str): Contenido del mensaje
        level (str): Nivel de importancia (info, warning, error, critical)
    
    Returns:
        bool: True si se envió correctamente
    """
    admin_emails = current_app.config.get('ADMIN_EMAILS', [])
    if not admin_emails:
        logger.warning("No hay emails de administradores configurados")
        return False
    
    emoji_map = {
        'info': 'ℹ️',
        'warning': '⚠️',
        'error': '❌',
        'critical': '🚨'
    }
    
    emoji = emoji_map.get(level, 'ℹ️')
    
    return send_template_email(
        template_name="admin_notification",
        subject=f"{emoji} {subject}",
        recipients=admin_emails,
        template_vars={
            "subject": subject,
            "message": message,
            "level": level,
            "timestamp": datetime.utcnow().strftime("%d/%m/%Y %H:%M:%S UTC"),
            "app_name": "Gem-AvatART"
        }
    )

# ============================================================================
# UTILIDADES Y HELPERS
# ============================================================================

def _html_to_text(html_content: str) -> str:
    """
    Convierte contenido HTML a texto plano simple.
    
    Args:
        html_content (str): Contenido HTML
    
    Returns:
        str: Versión en texto plano
    """
    # Implementación básica - en producción usar biblioteca como BeautifulSoup
    import re
    
    # Remover tags HTML
    text = re.sub(r'<[^>]+>', '', html_content)
    
    # Convertir entidades HTML comunes
    text = text.replace('&nbsp;', ' ')
    text = text.replace('&amp;', '&')
    text = text.replace('&lt;', '<')
    text = text.replace('&gt;', '>')
    text = text.replace('&quot;', '"')
    
    # Limpiar espacios en blanco excesivos
    text = re.sub(r'\s+', ' ', text)
    text = text.strip()
    
    return text

def validate_email_config() -> bool:
    """
    Valida que la configuración de email esté correctamente establecida.
    
    Returns:
        bool: True si la configuración es válida
    """
    required_configs = [
        'MAIL_SERVER',
        'MAIL_PORT',
        'MAIL_USERNAME',
        'MAIL_PASSWORD',
        'MAIL_DEFAULT_SENDER'
    ]
    
    for config in required_configs:
        if not current_app.config.get(config):
            logger.error(f"Configuración de email faltante: {config}")
            return False
    
    return True

def test_email_connection() -> bool:
    """
    Prueba la conexión con el servidor SMTP.
    
    Returns:
        bool: True si la conexión es exitosa
    """
    try:
        with mail.connect() as conn:
            logger.info("Conexión SMTP exitosa")
            return True
    except Exception as e:
        logger.error(f"Error conectando con SMTP: {str(e)}")
        return False

# ============================================================================
# FUNCIONES PARA IMPLEMENTACIÓN FUTURA
# ============================================================================

def send_bulk_email(template_name   : str, 
                    subject         : str, 
                    recipients_data : List[Dict[str, Any]]) -> Dict[str, int]:
    """
    Envía emails masivos usando una plantilla (implementación futura con queue).
    
    Args:
        template_name (str)          : Nombre de la plantilla
        subject (str)                : Asunto del email
        recipients_data (List[Dict]) : Lista de datos por recipient
            Formato: [{'email': 'user@example.com', 
                        'vars': {...}}]
    
    Returns:
        Dict[str, int]: Estadísticas de envío {'sent': X, 'failed': Y}
    
    Note:
        Esta función debe implementarse con un sistema de colas (Celery/RQ)
        para manejar grandes volúmenes de emails sin bloquear la aplicación.
    """
    # TODO: Implementar con Celery para emails asincrónicos
    stats = {'sent': 0, 'failed': 0}
    
    for recipient_data in recipients_data:
        success = send_template_email(
            template_name = template_name,
            subject       = subject,
            recipients    = [recipient_data['email']],
            template_vars = recipient_data.get('vars', {})
        )
        
        if success:
            stats['sent'] += 1
        else:
            stats['failed'] += 1
    
    return stats

def schedule_email(template_name: str, subject: str, recipients: List[str], 
                  template_vars: Dict[str, Any], send_at: datetime) -> bool:
    """
    Programa un email para envío futuro (implementación futura).
    
    Args:
        template_name (str): Nombre de la plantilla
        subject (str): Asunto del email
        recipients (List[str]): Lista de destinatarios
        template_vars (Dict): Variables de la plantilla
        send_at (datetime): Fecha y hora de envío
    
    Returns:
        bool: True si se programó correctamente
    
    Note:
        Requiere implementación de sistema de tareas programadas (Celery Beat)
    """
    # TODO: Implementar scheduling con Celery Beat
    logger.info(f"Email programado para {send_at}: {subject}")
    return True

def get_email_analytics(start_date: datetime, end_date: datetime) -> Dict[str, Any]:
    """
    Obtiene analíticas de emails enviados (implementación futura).
    
    Args:
        start_date (datetime): Fecha de inicio
        end_date (datetime): Fecha de fin
    
    Returns:
        Dict[str, Any]: Estadísticas de emails
    
    Note:
        Requiere base de datos para tracking de emails enviados
    """
    # TODO: Implementar tracking de emails en base de datos
    return {
        'total_sent': 0,
        'total_failed': 0,
        'bounce_rate': 0.0,
        'open_rate': 0.0,  # Requiere tracking pixels
        'click_rate': 0.0  # Requiere tracking links
    }