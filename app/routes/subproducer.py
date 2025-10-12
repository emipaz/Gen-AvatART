"""
Módulo de rutas de subproductor para la aplicación Gen-AvatART.

Este módulo maneja todas las rutas específicas de los subproductores del sistema,
proporcionando un panel de control intermedio que permite la creación de avatares
y reels bajo la supervisión de un productor. Incluye gestión de permisos jerárquicos.

El módulo incluye:
    - Dashboard de subproductor   : Estadísticas y resumen de actividad propia
    - Gestión de avatares         : Creación con aprobación del productor
    - Gestión de reels           : Creación usando avatares del productor
    - Panel de ganancias         : Control de comisiones personales
    - Validación jerárquica      : Verificación de permisos del productor padre

Funcionalidades principales:
    - Sistema de permisos con decorador @subproducer_required
    - Creación de avatares sujeta a aprobación del productor
    - Uso de avatares aprobados del productor para crear reels
    - Validación automática de cuotas API del productor padre
    - Control financiero de comisiones ganadas personalmente
    - Relación jerárquica estricta con el productor asignado
    - Estados iniciales PENDING para supervisión y aprobación

Características técnicas:
    - Decorador personalizado para verificación de permisos de subproductor
    - Consultas filtradas por creador para mostrar solo contenido propio
    - Validación jerárquica de recursos (avatares, cuotas API)
    - Paginación automática para mejor rendimiento
    - Estados iniciales que requieren aprobación del productor
    - Cálculo de estadísticas personales usando métodos del modelo
    - Manejo robusto de errores con validación de relaciones
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models.user import User, UserRole
from app.models.avatar import Avatar, AvatarStatus
from app.models.reel import Reel, ReelStatus
from app.models.commission import Commission
from app.utils.date_utils import get_current_month_range
from datetime import datetime
subproducer_bp = Blueprint('subproducer', __name__)

def subproducer_required(f):
    """
    Decorador para requerir permisos de subproductor.
    
    Este decorador verifica que el usuario actual tenga permisos
    de subproductor antes de permitir el acceso a rutas específicas.
    Proporciona una capa adicional de seguridad para funcionalidades
    exclusivas de subproductores.
    
    Args:
        f (function): Función de vista a proteger
    
    Returns:
        function: Función decorada con verificación de permisos
    
    Note:
        - Se ejecuta después de @login_required
        - Redirige a index si no tiene permisos de subproductor
        - Mensaje flash informativo para feedback al usuario
        - Complementa la autenticación básica con validación de rol
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # verificar si el usuario tiene rol de subproductor
        if not current_user.is_authenticated or not current_user.is_subproducer():
            flash('Acceso denegado. Permisos de subproductor requeridos.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@subproducer_bp.route('/dashboard')
@login_required
@subproducer_required
def dashboard():
    """
    Dashboard principal del subproductor con estadísticas personales.
    
    Proporciona una vista general de la actividad personal del subproductor,
    incluyendo métricas de avatares creados, reels generados, ganancias
    y relación con el productor padre. Enfoque en actividad propia.
    
    Returns:
        Template: 'subproducer/dashboard.html' con estadísticas y actividad reciente
    
    Context Variables:
            
            - stats (dict)             : Estadísticas personales del subproductor
            - total_avatars (int)      : Total de avatares creados personalmente
            - approved_avatars (int)   : Avatares aprobados por el productor
            - pending_avatars (int)    : Avatares pendientes de aprobación
            - total_reels (int)        : Total de reels creados personalmente
            - completed_reels (int)    : Reels completados exitosamente
            - total_earnings (float)   : Ganancias totales aprobadas
            - pending_earnings (float) : Ganancias pendientes de aprobación
            - producer_name (str)      : Nombre del productor supervisor
        
            - recent_avatars (list)    : 5 avatares más recientes creados
            - recent_reels (list)      : 5 reels más recientes creados

    Note:
        - Estadísticas se enfocan en actividad personal del subproductor
        - Relación jerárquica con productor es fundamental
        - Sin acceso a estadísticas de otros subproductores
        - Información de ganancias personal únicamente
    """
    producer = current_user.get_producer()
    
    stats = {
        'total_avatars' : current_user.created_avatars.count(),
        'approved_avatars' : current_user.created_avatars.filter_by( status = AvatarStatus.ACTIVE).count(),
        'pending_avatars'  : current_user.created_avatars.filter_by( status = AvatarStatus.PROCESSING).count(),
        'total_reels'      : current_user.reels.count(),
        'completed_reels'  : current_user.reels.filter_by( status = ReelStatus.COMPLETED).count(),
        'total_earnings'   : Commission.get_user_total_earnings(current_user.id, 'approved'),
        'pending_earnings' : Commission.get_user_total_earnings(current_user.id, 'pending'),
        'producer_name'    : producer.user.full_name if producer else 'N/A'
    }
    
    recent_avatars = current_user.created_avatars.order_by(Avatar.created_at.desc()).limit(5).all()
    recent_reels   = current_user.reels.order_by(Reel.created_at.desc()).limit(5).all()
    
    return render_template('subproducer/dashboard.html',
                         stats          = stats,
                         recent_avatars = recent_avatars,
                         recent_reels   = recent_reels)

@subproducer_bp.route('/avatars')
@login_required
@subproducer_required
def avatars():
    """
    Lista paginada de avatares creados por el subproductor con filtros.
    
    Proporciona una vista completa de todos los avatares creados por
    el subproductor actual, con capacidades de filtrado por estado
    y paginación automática. Solo muestra avatares propios.
    
    Query Parameters:
        page (int, opcional): Número de página para paginación (default: 1)
        status (str, opcional): Filtro por estado (active, processing, inactive, failed)
    
    Returns:
        Template: 'subproducer/avatars.html' con lista paginada de avatares
    
    Context Variables:
        avatars (Pagination): Objeto de paginación con avatares filtrados
    
    Note:
        - Solo muestra avatares creados por el subproductor actual
        - Filtrado dinámico por estado de avatar
        - Paginación de 12 elementos por página (optimizado para grids)
        - Ordenamiento por fecha de creación (más recientes primero)
        - No incluye avatares de otros subproductores del mismo productor
    """
    page          = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status')
    
    query = current_user.created_avatars
    
    if status_filter:
        query = query.filter_by(status=AvatarStatus(status_filter))
    
    avatars = query.order_by(Avatar.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )
    
    return render_template('subproducer/avatars.html', avatars=avatars)

@subproducer_bp.route('/avatars/create', methods=['GET', 'POST'])
@login_required
@subproducer_required
def create_avatar():
    """
    Crear un nuevo avatar bajo la supervisión del productor.
    
    Maneja la creación de avatares por parte del subproductor,
    incluyendo validación de cuotas API del productor y establecimiento
    del estado inicial PENDING para aprobación. Requiere productor asignado.
    
    Methods:
        GET  : Muestra el formulario de creación de avatar
        POST : Procesa los datos y crea el avatar para aprobación
    
    Form Data (POST):
        name (str): Nombre descriptivo del avatar
        description (str): Descripción detallada del avatar
        avatar_type (str): Tipo de avatar (male, female, custom)
        language (str): Idioma principal (default: 'es')
        tags (str): Etiquetas separadas por comas
    
    Returns:
        GET : Template 'subproducer/create_avatar.html'
        POST: Redirección a lista de avatares o template con errores
    
    Note:
        - Requiere productor asignado para validar cuotas
        - Estado inicial PROCESSING hasta aprobación del productor
        - No se incrementa uso de API hasta aprobación
        - Avatar se asigna al productor pero creado por el subproductor
        - Validación automática de cuota API del productor padre
    """
    # Obtener productor asignado
    producer = current_user.get_producer()
    
    # Validar que el subproductor tiene un productor asignado
    if not producer:
        flash('No tienes un productor asignado', 'error')
        return redirect(url_for('subproducer.dashboard'))
    
    # Validar que el productor tiene cuota API disponible<
    if not producer.has_api_quota():
        flash('El productor ha alcanzado su límite mensual de API calls', 'error')
        return redirect(url_for('subproducer.avatars'))
    
    # Manejar formulario
    if request.method == 'POST':
        name         = request.form.get('name')
        description  = request.form.get('description')
        avatar_type  = request.form.get('avatar_type')
        language     = request.form.get('language', 'es')
        tags         = request.form.get('tags', '')
        
        avatar = Avatar(
            producer_id   = producer.id,
            created_by_id = current_user.id,
            name          = name,
            description   = description,
            avatar_type   = avatar_type,
            language      = language,
            status        = AvatarStatus.PROCESSING
        )
        # Asignar etiquetas si se proporcionan
        avatar.set_tags(tags.split(','))
        
        # Guardar en base de datos
        db.session.add(avatar)
        db.session.commit()
        
        flash('Avatar creado y enviado para aprobación', 'success')
        return redirect(url_for('subproducer.avatars'))
    
    return render_template('subproducer/create_avatar.html')

@subproducer_bp.route('/reels')
@login_required
@subproducer_required
def reels():
    """
    Lista paginada de reels creados por el subproductor con filtros.
    
    Proporciona una vista completa de todos los reels creados por
    el subproductor actual, con capacidades de filtrado por estado
    y paginación automática. Solo muestra reels propios.
    
    Query Parameters:
        page (int, opcional): Número de página para paginación (default: 1)
        status (str, opcional): Filtro por estado (pending, processing, completed, failed)
    
    Returns:
        Template: 'subproducer/reels.html' con lista paginada de reels
    
    Context Variables:
        reels (Pagination): Objeto de paginación con reels filtrados
    
    Note:
        - Solo muestra reels creados por el subproductor actual
        - Filtrado dinámico por estado de procesamiento
        - Paginación de 20 elementos por página para rendimiento
        - Ordenamiento por fecha de creación (más recientes primero)
        - No incluye reels de otros usuarios de la red
    """
    # Obtener parámetros de consulta
    page          = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status')
    
    # Construir consulta base
    
    query = current_user.reels
    
    # Aplicar filtro si se proporciona
    
    if status_filter:
        query = query.filter_by(status=ReelStatus(status_filter))

    reels = query.order_by(Reel.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('subproducer/reels.html', reels=reels)

@subproducer_bp.route('/reels/create', methods=['GET', 'POST'])
@login_required
@subproducer_required
def create_reel():
    """
    Crear un nuevo reel usando avatares aprobados del productor.
    
    Maneja la creación de reels por parte del subproductor,
    utilizando únicamente avatares aprobados del productor supervisor.
    Incluye validación de relaciones jerárquicas y permisos.
    
    Methods:
        GET  : Muestra el formulario de creación con avatares disponibles
        POST : Procesa los datos y crea el reel para procesamiento
    
    Form Data (POST):
        
        title (str)           : Título del reel
        description (str)     : Descripción del contenido
        script (str)          : Texto que el avatar pronunciará
        avatar_id (int)       : ID del avatar a utilizar
        resolution (str)      : Resolución del video (default: '1080p')
        background_type (str) : Tipo de fondo (default: 'default')
        category (str)        : Categoría del contenido
        tags (str)            : Etiquetas separadas por comas

    Returns:
        GET : Template 'subproducer/create_reel.html' con avatares disponibles
        POST: Redirección a lista de reels o template con errores
    
    Context Variables (GET):
        avatars (list): Lista de avatares aprobados disponibles
    
    Note:
        - Solo puede usar avatares ACTIVE del productor supervisor
        - Validación estricta de permisos sobre el avatar seleccionado
        - Estado inicial PENDING hasta aprobación/procesamiento
        - Sin acceso a avatares de otros productores
        - Requiere al menos un avatar aprobado para crear reels
    """

    producer = current_user.get_producer()
    
    if not producer:
        flash('No tienes un productor asignado', 'error')
        return redirect(url_for('subproducer.dashboard'))
    
    # Obtener avatars disponibles
    available_avatars = producer.avatars.filter_by(status=AvatarStatus.APPROVED).all()
    
    if not available_avatars:
        flash('No hay avatars aprobados disponibles', 'warning')
        return redirect(url_for('subproducer.reels'))
    
    # Manejar formulario de creación
    if request.method == 'POST':
        title            = request.form.get('title')
        description      = request.form.get('description')
        script           = request.form.get('script')
        avatar_id        = request.form.get('avatar_id')
        resolution       = request.form.get('resolution', '1080p')
        background_type  = request.form.get('background_type', 'default')
        category         = request.form.get('category')
        tags             = request.form.get('tags', '')
   
        # Validar que el avatar pertenece al productor
        avatar = Avatar.query.get_or_404(avatar_id)
        
        # Verificar que el avatar pertenece al productor
        if avatar.producer_id != producer.id:
            flash('Avatar no válido', 'error')
            return render_template('subproducer/create_reel.html', avatars=available_avatars)
        
        reel = Reel(
            creator_id       = current_user.id,
            avatar_id        = avatar_id,
            title            = title,
            description      = description,
            script           = script,
            resolution       = resolution,
            background_type  = background_type,
            category         = category,
            status           = ReelStatus.PENDING
        )
        reel.set_tags(tags.split(','))
        
        db.session.add(reel)
        db.session.commit()
        
        flash('Reel creado y enviado para aprobación', 'success')
        return redirect(url_for('subproducer.reels'))
    
    return render_template('subproducer/create_reel.html', avatars=available_avatars)

@subproducer_bp.route('/earnings')
@login_required
@subproducer_required
def earnings():
    """
    Panel de ganancias personales del subproductor.
    
    Proporciona una vista completa de las ganancias personales del
    subproductor, incluyendo comisiones históricas y estadísticas
    financieras. Solo muestra ganancias propias, no de la red.
    
    Query Parameters:
        page (int, opcional): Número de página para historial (default: 1)
    
    Returns:
        Template: 'subproducer/earnings.html' con información financiera personal
    
    Context Variables:
        commissions (Pagination): Historial paginado de comisiones personales
        stats (dict): Estadísticas financieras del subproductor
            - total_approved (float): Total de ganancias aprobadas
            - total_pending (float): Ganancias pendientes de aprobación
            - total_paid (float): Total ya pagado al subproductor
            - this_month (float): Ganancias del mes actual
    
    Note:
        - Estadísticas calculadas usando métodos del modelo Commission
        - Solo incluye comisiones ganadas personalmente por el subproductor
        - Historial ordenado cronológicamente (más recientes primero)
        - Paginación de 20 elementos para rendimiento
        - Sin acceso a ganancias de otros miembros de la red
    """
    # Obtener página para paginación
    page = request.args.get('page', 1, type=int)
    
    # Consultar comisiones ganadas por el subproductor
    commissions = current_user.commissions_earned.order_by(
        Commission.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    
    # ✅ Calcular estadísticas financieras usando utilidades de fecha
    current_date = datetime.now()
    earnings_stats = {
        'total_approved' : Commission.get_user_total_earnings(current_user.id, 'approved'),
        'total_pending'  : Commission.get_user_total_earnings(current_user.id, 'pending'),
        'total_paid'     : Commission.get_user_total_earnings(current_user.id, 'paid'),
        'this_month'     : Commission.get_monthly_earnings(current_user.id, 
                                                    current_date.year, 
                                                    current_date.month)
    }
    
    return render_template('subproducer/earnings.html',
                         commissions = commissions,
                         stats       = earnings_stats)
