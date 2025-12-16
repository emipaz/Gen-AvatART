"""
Módulo de rutas principales para la aplicación Gem-AvatART.

Este módulo contiene las rutas principales de la aplicación, incluyendo la página
de inicio, dashboard principal, páginas informativas y APIs de estadísticas.
Maneja el enrutamiento según los roles de usuario y proporciona endpoints
para obtener datos dinámicos para el frontend.

El módulo incluye:
    - Rutas públicas   : index, about, contact, pricing
    - Rutas protegidas : dashboard, view_reel, view_avatar
    - APIs de datos    : stats, user-stats, recent-activity
    - Sistema de redirección por roles

Funcionalidades principales:
    - Página de inicio con estadísticas públicas
    - Dashboard que redirige según el rol del usuario
    - Visualización de reels y avatares con control de permisos
    - APIs para estadísticas generales y específicas del usuario
    - Sistema de actividad reciente para el dashboard
"""

from flask import Blueprint, render_template, request, jsonify, redirect, url_for, send_file, abort
from flask_login import login_required, current_user
from app import db
from app.models.user import User, UserRole
from app.models.reel import Reel, ReelStatus
from app.models.avatar import Avatar, AvatarStatus
from app.models.commission import Commission
import os

import logging

logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """
    Página principal de la aplicación.
    
    Muestra la landing page con estadísticas públicas del sistema.
    Si el usuario está autenticado, redirige automáticamente al dashboard
    correspondiente según su rol.
    
    Returns:
        Response: Template de index con estadísticas o redirección al dashboard
        
    Note:
        Las estadísticas mostradas incluyen usuarios totales, reels completados,
        avatares aprobados y número de productores registrados.
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    # Estadísticas públicas
    stats = {
        'total_users'     : User.query.count(),
        'total_reels'     : Reel.query.filter_by(  status = ReelStatus.COMPLETED).count(),
        'total_avatars'   : Avatar.query.filter_by(status = AvatarStatus.ACTIVE).count(),
        'total_producers' : User.query.filter_by(  role   = UserRole.PRODUCER).count()
    }
    
    return render_template('main/index.html', stats=stats)

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """
    Dashboard principal que redirige según el rol del usuario.
    
    Analiza el rol del usuario autenticado y redirige al dashboard
    específico correspondiente. Esto proporciona una experiencia
    personalizada según las capacidades de cada tipo de usuario.
    
    Returns:
        Response: Redirección al dashboard específico del rol
        
    Note:
        - ADMIN: Redirige a admin.dashboard
        - PRODUCER: Redirige a producer.dashboard  
        - SUBPRODUCER: Redirige a subproducer.dashboard
        - FINAL_USER: Redirige a user.dashboard (anteriormente affiliate)
    """
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    elif current_user.is_producer():
        return redirect(url_for('producer.dashboard'))
    elif current_user.is_subproducer():
        return redirect(url_for('subproducer.dashboard'))
    else:  # final_user
        return redirect(url_for('user.dashboard'))

@main_bp.route('/about')
def about():
    """
    Página de información sobre la plataforma.
    
    Muestra información detallada sobre Gem-AvatART, sus características,
    funcionalidades y beneficios para los diferentes tipos de usuarios.
    
    Returns:
        Response: Template con información de la plataforma
    """
    return render_template('public/about.html')

@main_bp.route('/contact')
def contact():
    """
    Página de contacto y soporte.
    
    Proporciona formulario de contacto y información para que los usuarios
    puedan comunicarse con el equipo de soporte o ventas.
    
    Returns:
        Response: Template con formulario de contacto
    """
    return render_template('public/contact.html')

@main_bp.route('/pricing')
def pricing():
    """
    Página de planes y precios.
    
    Muestra los diferentes planes disponibles, características incluidas
    y precios para cada tipo de usuario (Producer, Subproducer, etc.).
    
    Returns:
        Response: Template con información de precios y planes
    """
    return render_template('public/pricing.html')

@main_bp.route('/api/stats')
def api_stats():
    """
    API para obtener estadísticas generales del sistema.
    
    Proporciona datos estadísticos generales de la plataforma que pueden
    ser consumidos por el frontend para mostrar métricas en tiempo real.
    
    Returns:
        JSON: Diccionario con estadísticas generales del sistema
        
    Note:
        Incluye contadores de usuarios, reels, avatares, productores y comisiones.
        Los datos están disponibles públicamente para mostrar el crecimiento.
    """
    stats = {
        'total_users'        : User.query.count(),
        'active_users'       : User.query.filter_by(status='active').count(),
        'total_reels'        : Reel.query.count(),
        'completed_reels'    : Reel.query.filter_by(status=ReelStatus.COMPLETED).count(),
        'total_avatars'      : Avatar.query.count(),
        'approved_avatars'   : Avatar.query.filter_by(status=AvatarStatus.ACTIVE).count(),
        'total_producers'    : User.query.filter_by(role=UserRole.PRODUCER).count(),
        'total_commissions'  : Commission.query.count()
    }
    
    return jsonify(stats)

@main_bp.route('/api/user-stats')
@login_required
def api_user_stats():
    """
    API para obtener estadísticas específicas del usuario autenticado.
    
    Proporciona métricas personalizadas según el rol del usuario, incluyendo
    reels creados, ganancias, avatares disponibles y otros datos relevantes
    para el dashboard específico de cada rol.
    
    Returns:
        JSON: Diccionario con estadísticas específicas del usuario
        
    Note:
        Los datos varían según el rol:
        - PRODUCER    : Reels, avatares, subproductores, ganancias, API calls
        - SUBPRODUCER : Reels, avatares creados, ganancias, productor asociado
        - FINAL_USER  : Reels creados, ganancias, productor asociado
        - ADMIN       : Estadísticas generales del sistema y tareas pendientes
    """
    user_stats = {}
    
    if current_user.is_producer():
        producer = current_user.producer_profile
        user_stats = {
            'total_reels'         : current_user.reels.count(),
            'completed_reels'     : current_user.reels.filter_by(status = ReelStatus.COMPLETED).count(),
            'total_avatars'       : producer.avatars.count() if producer else 0,
            'approved_avatars'    : producer.avatars.filter_by( status = AvatarStatus.ACTIVE).count() if producer else 0,
            'subproducers_count'  : producer.current_subproducers_count if producer else 0,
            'final_users_count'   : producer.current_final_users_count  if producer else 0,
            
            # Necesitamos implementar método seguro para earnings
            'total_earnings'      : current_user.get_total_earnings(),  # USAR MÉTODO DEL USER
            'pending_earnings'    : 0,  # TODO: Implementar método para earnings pendientes
            
            'api_calls_remaining' : (producer.monthly_api_limit - producer.api_calls_this_month) if producer else 0
        }
    elif current_user.is_subproducer():
        producer = current_user.get_producer()
        user_stats = {
            'total_reels'      : current_user.reels.count(),
            'completed_reels'  : current_user.reels.filter_by( status = ReelStatus.COMPLETED).count(),
            'total_avatars'    : current_user.created_avatars.count(),
            'approved_avatars' : current_user.created_avatars.filter_by( status = AvatarStatus.ACTIVE).count(),
            'total_earnings'   : current_user.get_total_earnings(),  # USAR MÉTODO DEL USER
            'pending_earnings' : 0,  # TODO: Implementar método para earnings pendientes
            'producer_name'    : producer.user.full_name if producer else 'N/A'
        }
    elif current_user.is_affiliate():
        producer = current_user.get_producer()
        user_stats = {
            'total_reels'      : current_user.reels.count(),
            'completed_reels'  : current_user.reels.filter_by(status=ReelStatus.COMPLETED).count(),
            'total_earnings'   : Commission.get_user_total_earnings(current_user.id, 'paid'),
            'pending_earnings' : Commission.get_user_total_earnings(current_user.id, 'approved'),
            'producer_name'    : producer.user.full_name if producer else 'N/A'
        }
    else:  # admin
        user_stats = {
            'total_users'         : User.query.count(),
            'pending_users'       : User.query.filter_by( status = 'pending').count(),
            'total_producers'     : User.query.filter_by( role = UserRole.PRODUCER).count(),
            'total_reels'         : Reel.query.count(),
            'pending_approvals'   : Reel.query.filter_by( status = ReelStatus.PENDING).count(),
            'total_earnings'      : current_user.get_total_earnings(),  # USAR MÉTODO DEL USER
            'pending_earnings' : 0,  # TODO: Implementar método para earnings pendientes
        }
    
    return jsonify(user_stats)

@main_bp.route('/api/recent-activity')
@login_required
def api_recent_activity():
    """
    API para obtener la actividad reciente del usuario autenticado.
    
    Proporciona una lista de las actividades más recientes del usuario,
    incluyendo reels creados, comisiones ganadas y otros eventos relevantes
    para mostrar en el dashboard.
    
    Returns:
        JSON: Lista de actividades recientes ordenadas por fecha
        
    Note:
        Combina diferentes tipos de actividades (reels, comisiones) y las
        ordena cronológicamente. Limitado a las últimas 10 actividades.
    """
    activities = []
    
    # Reels recientes del usuario
    recent_reels = current_user.reels.order_by( Reel.created_at.desc() ).limit(5).all()
    for reel in recent_reels:
        activities.append({
            'type'     : 'reel_created',
            'title'    : f'Reel creado: {reel.title}',
            'status'   : reel.status.value,
            'timestamp' : reel.created_at.isoformat(),
            'url'       : url_for('main.view_reel', id=reel.id)
        })
    
    # Comisiones recientes
    recent_commissions = current_user.commissions_earned.order_by( Commission.created_at.desc() ).limit(5).all()
    for commission in recent_commissions:
        activities.append({
            'type'       : 'commission_earned',
            'title'      : f'Comisión ganada: ${commission.amount:.2f}',
            'status'     : commission.status.value,
            'timestamp'  : commission.created_at.isoformat(),
            'reel_title' : commission.reel_title
        })
    
    # Ordenar por fecha
    activities.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return jsonify(activities[:10])  # Últimas 10 actividades

@main_bp.route('/reel/<int:id>')
@login_required
def view_reel(id):
    """
    Visualización detallada de un reel específico.
    
    Muestra la información completa de un reel, incluyendo video, estadísticas,
    configuración y metadatos. Incluye control de permisos para verificar
    que el usuario tenga acceso al reel solicitado.
    
    Args:
        id (int): ID único del reel a visualizar
        
    Returns:
        Response: Template con detalles del reel o error 403/404
        
    Note:
        Control de permisos:
        - Administradores  : Acceso completo
        - Creador del reel : Acceso completo
        - Productores      : Acceso a reels de su equipo
        - Otros            : Sin acceso (403)
    """
    reel = Reel.query.get_or_404(id)
    
    # Verificar permisos
    if not ( 
            current_user.is_admin() or 
            reel.creator_id == current_user.id or 
                ( 
                current_user.is_producer() and current_user.producer_profile and 
                reel.creator.get_producer() and 
                reel.creator.get_producer().id == current_user.producer_profile.id
                )
            ):
        return render_template('errors/403.html'), 403
    
    return render_template('main/view_reel.html', reel=reel)

@main_bp.route('/avatar/<int:id>')
@login_required
def view_avatar(id):
    """
    Visualización detallada de un avatar específico.
    
    Muestra la información completa de un avatar/clone, incluyendo preview,
    configuración, estadísticas de uso y metadatos. Incluye control de
    permisos para verificar acceso autorizado.
    
    Args:
        id (int): ID único del avatar a visualizar
        
    Returns:
        Response: Template con detalles del avatar o error 403/404
        
    Note:
        Control de permisos:
        - Administradores       : Acceso completo
        - Creador del avatar    : Acceso completo  
        - Productor propietario : Acceso completo
        - Otros                 : Sin acceso (403)
    """
    avatar = Avatar.query.get_or_404(id)
    
    # Verificar permisos
    if not ( 
            current_user.is_admin() or 
            avatar.created_by_id == current_user.id or 
              ( current_user.is_producer() and 
                current_user.producer_profile and 
                avatar.producer_id == current_user.producer_profile.id 
              ) 
            ):
        return render_template('errors/403.html'), 403
    
    return render_template('main/view_avatar.html', avatar=avatar)


@main_bp.route('/video/<int:reel_id>')
@login_required
def serve_video(reel_id):
    """
    Servir video descargado localmente desde el almacenamiento del servidor.
    
    Args:
        reel_id: ID del reel cuyo video se quiere servir
        
    Returns:
        send_file: Archivo de video desde el almacenamiento local
        
    Raises:
        403: Si el usuario no tiene permisos para ver el video
        404: Si el video no existe o no se encuentra localmente
    """
    try:
        # Buscar el reel en la base de datos
        reel = Reel.query.get_or_404(reel_id)
        
        # Verificar permisos de acceso
        # El usuario debe ser el propietario o un administrador
        if current_user.id != reel.user_id and current_user.role != UserRole.ADMIN:
            # Para productores y subproductores, verificar si tienen acceso a este usuario
            if current_user.role in [UserRole.PRODUCER, UserRole.SUB_PRODUCER]:
                # Verificar si el usuario está asignado a este productor/subproductor
                if not hasattr(current_user, 'assigned_users') or reel.user_id not in [u.id for u in current_user.assigned_users]:
                    abort(403)
            else:
                abort(403)
        
        # Verificar que el reel tenga video_url local
        if not reel.local_video_path:
            logger.warning(f"Reel {reel_id} no tiene video local disponible")
            abort(404)
        
        # Construir la ruta completa del archivo
        video_path = os.path.join(os.getcwd(), reel.local_video_path)
        
        # Verificar que el archivo existe físicamente
        if not os.path.exists(video_path):
            logger.error(f"Video local no encontrado en: {video_path}")
            abort(404)
        
        # Servir el archivo
        return send_file(
            video_path,
            as_attachment=False,
            mimetype='video/mp4'
        )
        
    except Exception as e:
        logger.error(f"Error sirviendo video {reel_id}: {str(e)}")
        abort(500)