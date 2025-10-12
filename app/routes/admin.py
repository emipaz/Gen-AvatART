"""
Módulo de rutas de administración para la aplicación Gen-AvatART.

Este módulo maneja todas las rutas administrativas del sistema, proporcionando
un panel de control completo para la gestión de usuarios, productores, avatares,
reels y comisiones. Incluye funcionalidades avanzadas de supervisión y control.

El módulo incluye:
    - Dashboard administrativo    : Estadísticas y resumen general del sistema
    - Gestión de usuarios         : CRUD completo con aprobaciones y suspensiones
    - Creación de productores     : Onboarding automático con validación de API
    - Gestión de avatares         : Aprobación/rechazo de clones digitales
    - Supervisión de reels        : Monitoreo de generación de videos
    - Control de comisiones       : Aprobación y marcado de pagos
    - APIs de estadísticas        : Endpoints REST para dashboards

Funcionalidades principales:
    - Sistema de permisos con decorador @admin_required
    - Estadísticas en tiempo real de toda la plataforma
    - Gestión completa del ciclo de vida de usuarios
    - Onboarding automatizado de productores con validación HeyGen
    - Flujo de aprobación para avatares digitales
    - Control financiero de comisiones y pagos
    - Filtrado y búsqueda avanzada en todas las entidades
    - Paginación automática para rendimiento

Características técnicas:
    - Decorador personalizado para verificación de permisos
    - Consultas optimizadas con filtros dinámicos
    - Paginación automática (20 elementos por página)
    - APIs REST para integración con dashboards
    - Validaciones de integridad antes de operaciones críticas
    - Manejo robusto de errores con rollback automático
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models.user import User, UserRole, UserStatus
from app.models.producer import Producer
from app.models.avatar import Avatar, AvatarStatus
from app.models.reel import Reel, ReelStatus
from app.models.commission import Commission, CommissionStatus

admin_bp = Blueprint('admin', __name__)

def admin_required(f):
    """
    Decorador para requerir permisos de administrador.
    
    Este decorador verifica que el usuario actual tenga permisos
    administrativos antes de permitir el acceso a rutas sensibles.
    Proporciona una capa adicional de seguridad específica para admin.
    
    Args:
        f (function): Función de vista a proteger
    
    Returns:
        function: Función decorada con verificación de permisos
    
    Note:
        - Se ejecuta después de @login_required
        - Redirige a index si no tiene permisos
        - Mensaje flash informativo para feedback al usuario
        - Complementa la autenticación básica de Flask-Login
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_admin():
            flash('Acceso denegado. Permisos de administrador requeridos.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@admin_bp.route('/dashboard')
@login_required
@admin_required
def dashboard():
    """
    Dashboard principal del administrador con estadísticas del sistema.
    
    Proporciona una vista general completa del estado de la plataforma,
    incluyendo métricas de usuarios, reels, avatares y comisiones.
    Incluye elementos pendientes que requieren atención administrativa.
    
    Returns:
        Template: 'admin/dashboard.html' con estadísticas y elementos pendientes
    
    Context Variables:
            - stats (dict)              : Estadísticas generales del sistema
            - total_users (int)         : Total de usuarios registrados
            - pending_users (int)       : Usuarios pendientes de aprobación
            - active_users (int)        : Usuarios activos en el sistema
            - total_producers (int)     : Número de productores
            - total_subproducers (int)  : Número de subproductores
            - total_affiliates (int)    : Número de afiliados
            - total_reels (int)         : Total de reels generados
            - pending_reels (int)       : Reels pendientes de procesamiento
            - completed_reels (int)     : Reels completados exitosamente
            - total_avatars (int)       : Total de avatares en el sistema
            - pending_avatars (int)     : Avatares pendientes de aprobación
            - approved_avatars (int)    : Avatares aprobados y activos
            - total_commissions (int)   : Total de comisiones generadas
            - pending_commissions (int) : Comisiones pendientes de pago

            - recent_users (list)        : 5 usuarios más recientes
            - recent_reels (list)        : 5 reels más recientes
            - pending_avatars (list)     : 5 avatares pendientes de aprobación
            - pending_reels (list)       : 5 reels pendientes de procesamiento

    Note:
        - Estadísticas calculadas en tiempo real para precisión
        - Elementos pendientes limpiados a 5 para evitar sobrecarga
        - Dashboard responsive para diferentes dispositivos
        - Acceso rápido a funcionalidades administrativas principales
    """

    # Estadísticas generales
    stats = {
        'total_users'         : User.query.count(),
        'pending_users'       : User.query.filter_by( status = UserStatus.PENDING).count(),
        'active_users'        : User.query.filter_by( status = UserStatus.ACTIVE).count(),
        'total_producers'     : User.query.filter_by( role = UserRole.PRODUCER).count(),
        'total_subproducers'  : User.query.filter_by( role = UserRole.SUBPRODUCER).count(),
        'total_affiliates'    : User.query.filter_by( role = UserRole.FINAL_USER).count(),
        'total_reels'         : Reel.query.count(),
        'pending_reels'       : Reel.query.filter_by( status = ReelStatus.PENDING).count(),
        'completed_reels'     : Reel.query.filter_by( status = ReelStatus.COMPLETED).count(),
        'total_avatars'       : Avatar.query.count(),
        'pending_avatars'     : Avatar.query.filter_by( status = AvatarStatus.PROCESSING).count(),
        'approved_avatars'    : Avatar.query.filter_by( status = AvatarStatus.ACTIVE).count(),
        'total_commissions'   : Commission.query.count(),
        'pending_commissions' : Commission.query.filter_by( status = CommissionStatus.PENDING).count()
    }
    
    # Usuarios recientes
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    
    # Reels recientes
    recent_reels = Reel.query.order_by(Reel.created_at.desc()).limit(5).all()
    
    # Elementos pendientes para el template
    pending_avatars = Avatar.query.filter_by(status = AvatarStatus.PROCESSING).limit(5).all()
    pending_reels   = Reel.query.filter_by(  status = ReelStatus.PENDING).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                         stats           = stats, 
                         recent_users    = recent_users, 
                         recent_reels    = =recent_reels,
                         pending_avatars = pending_avatars,
                         pending_reels   = pending_reels)


@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """
    Lista paginada de todos los usuarios con filtros avanzados.
    
    Proporciona una vista completa de usuarios registrados con capacidades
    de filtrado por rol, estado y búsqueda por texto. Incluye paginación
    automática para mejorar el rendimiento con grandes volúmenes de datos.
    
    Query Parameters:
        page (int, opcional): Número de página (default: 1)
        role (str, opcional): Filtro por rol (admin, producer, subproducer, affiliate)
        status (str, opcional): Filtro por estado (active, pending, suspended)
        search (str, opcional): Búsqueda por username, email, nombre o apellido
    
    Returns:
        Template: 'admin/users.html' con lista paginada de usuarios
    
    Context Variables:
        users (Pagination): Objeto de paginación con usuarios filtrados
    
    Note:
        - Búsqueda funciona en múltiples campos simultáneamente
        - Filtros se pueden combinar para búsquedas específicas
        - Paginación de 20 elementos por página para rendimiento
        - Ordenamiento por fecha de creación (más recientes primero)
    """
    # Parámetros de consulta
    page          = request.args.get('page', 1, type=int)
    role_filter   = request.args.get('role')
    status_filter = request.args.get('status')
    search        = request.args.get('search', '')
    
    # Consulta con filtros aplicados
    query = User.query
    
    # Filtros
    if role_filter:
        query = query.filter_by( role = UserRole(role_filter))
    if status_filter:
        query = query.filter_by(status = UserStatus(status_filter))
    if search:
        query = query.filter(
            db.or_(
                User.username.contains(search),
                User.email.contains(search),
                User.first_name.contains(search),
                User.last_name.contains(search)
            )
        )
    # ejecutar consulta con paginación
    users = query.order_by(User.created_at.desc()).paginate(
        page = page, per_page = 20, error_out = False
    )
    
    return render_template('admin/users.html', users=users)

@admin_bp.route('/users/<int:user_id>')
@login_required
@admin_required
def user_detail(user_id):
    """
    Vista detallada de un usuario específico con estadísticas completas.
    
    Proporciona información exhaustiva sobre un usuario, incluyendo
    estadísticas de actividad, ganancias y configuraciones específicas
    según el rol. Para productores incluye métricas adicionales.
    
    Args:
        user_id (int): ID único del usuario a mostrar
    
    Returns:
        Template: 'admin/user_detail.html' con información completa del usuario
    
    Context Variables:
            - user (User)      : Objeto usuario con toda la información
            - stats (dict)     : Estadísticas específicas del usuario
            
            - total_reels (int)        : Total de reels creados por el usuario
            - completed_reels (int)    : Reels completados exitosamente
            - total_commissions (int)  : Número total de comisiones
            - total_earnings (float)   : Ganancias totales aprobadas
            - pending_earnings (float) : Ganancias pendientes de aprobación
            
            Para productores adicional:
            - subproducers_count (int)   : Subproductores bajo su gestión
            - affiliates_count (int)     : Afiliados bajo su red
            - avatars_count (int)        : Avatares creados
            - api_calls_this_month (int) : Llamadas API del mes actual
            - monthly_api_limit (int)    :  Límite mensual de API
    
    Note:
        - Estadísticas se adaptan dinámicamente según el rol
        - Cálculos de ganancias diferenciados por estado de comisión
        - Para productores se incluyen métricas de gestión de red
        - Información de límites API para control de uso
    """
    user = User.query.get_or_404(user_id)
    
    # Estadísticas del usuario
    user_stats = {
        'total_reels'       : user.reels.count(),
        'completed_reels'   : user.reels.filter_by(status=ReelStatus.COMPLETED).count(),
        'total_commissions' : user.commissions_earned.count(),
        'total_earnings'    : sum([c.amount for c in user.commissions_earned.filter_by(status=CommissionStatus.APPROVED)]),
        'pending_earnings'  : sum([c.amount for c in user.commissions_earned.filter_by(status=CommissionStatus.PENDING)])
    }
    
    # Si es productor, obtener estadísticas adicionales
    if user.is_producer() and user.producer_profile:
        producer = user.producer_profile
        user_stats.update({
            'subproducers_count'   : producer.current_subproducers_count,
            'affiliates_count'     : producer.current_affiliates_count,
            'avatars_count'        : producer.avatars.count(),
            'api_calls_this_month' : producer.api_calls_this_month,
            'monthly_api_limit'    : producer.monthly_api_limit
        })
    
    return render_template('admin/user_detail.html', user=user, stats=user_stats)

@admin_bp.route('/users/<int:user_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_user(user_id):
    """
    Aprobar un usuario pendiente para activar su cuenta.
    
    Cambia el estado del usuario de PENDING a ACTIVE, permitiendo
    el acceso completo al sistema. Acción crítica que requiere
    permisos administrativos.
    
    Args:
        user_id (int): ID del usuario a aprobar
    
    Returns:
        Redirect: Redirección al detalle del usuario con mensaje de confirmación
    
    Note:
        - Solo usuarios con estado PENDING deberían ser aprobados
        - Acción irreversible que otorga acceso completo al sistema
        - Genera notificación automática al usuario (futuro)
        - Actualización inmediata en base de datos
    """

    user = User.query.get_or_404(user_id)
    user.status = UserStatus.ACTIVE
    db.session.commit()
    
    flash(f'Usuario {user.username} aprobado exitosamente', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))

@admin_bp.route('/users/<int:user_id>/suspend', methods=['POST'])
@login_required
@admin_required
def suspend_user(user_id):
    """
    Suspender temporalmente un usuario activo.
    
    Cambia el estado del usuario a SUSPENDED, bloqueando su acceso
    al sistema manteniendo sus datos intactos. Útil para medidas
    disciplinarias temporales o investigaciones.
    
    Args:
        user_id (int): ID del usuario a suspender
    
    Returns:
        Redirect: Redirección al detalle del usuario con mensaje de confirmación
    
    Note:
        - Suspensión es temporal y reversible
        - Usuario no puede iniciar sesión mientras esté suspendido
        - Datos y relaciones se mantienen intactos
        - Puede reactivarse cambiando estado a ACTIVE
    """
    user         = User.query.get_or_404(user_id)
    user.status  = UserStatus.SUSPENDED
    db.session.commit()
    
    flash(f'Usuario {user.username} suspendido', 'warning')
    return redirect(url_for('admin.user_detail', user_id=user_id))

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """
    Eliminar permanentemente un usuario del sistema.
    
    Elimina completamente el usuario y sus datos asociados.
    Acción irreversible que requiere validaciones especiales
    para prevenir eliminación accidental de administradores.
    
    Args:
        user_id (int): ID del usuario a eliminar
    
    Returns:
        Redirect: Redirección a lista de usuarios con mensaje de confirmación
    
    Note:
        - Acción IRREVERSIBLE que elimina todos los datos
        - Protección especial: no se pueden eliminar administradores
        - Se eliminan cascada: reels, comisiones, relaciones
        - Usar con extrema precaución en producción
    """
    # Obtener usuario y su nombre
    user     = User.query.get_or_404(user_id)
    username = user.username
    
    # No permitir eliminar otros administradores
    if user.is_admin():
        flash('No se puede eliminar un administrador', 'error')
        return redirect(url_for('admin.user_detail', user_id=user_id))
    
    # Eliminar usuario y sus datos asociados
    db.session.delete(user)
    db.session.commit()
    
    flash(f'Usuario {username} eliminado', 'info')
    return redirect(url_for('admin.users'))

@admin_bp.route('/create-producer', methods=['GET', 'POST'])
@login_required
@admin_required
def create_producer():
    """
    Crear un nuevo productor con perfil completo y validación de API.
    
    Maneja el onboarding completo de productores, creando tanto el usuario
    como su perfil de productor con configuraciones específicas. Incluye
    validación automática de la API key de HeyGen.
    
    Methods:
        GET  : Muestra el formulario de creación de productor
        POST : Procesa los datos y crea el productor completo
    
    Form Data (POST):
        # Datos del usuario base:
        email (str): Email único del productor
        username (str): Username único del productor
        password (str): Contraseña para la cuenta
        first_name (str): Nombre del productor
        last_name (str): Apellido del productor  
        phone (str, opcional): Teléfono de contacto
        
        # Datos específicos del productor:
        heygen_api_key (str): API key de HeyGen para integración
        company_name (str, opcional): Nombre de la empresa
        business_type (str, opcional): Tipo de negocio
        website (str, opcional): Sitio web corporativo
        max_subproducers (int): Límite de subproductores (default: 10)
        max_affiliates (int): Límite de afiliados (default: 100)
        monthly_api_limit (int): Límite mensual de llamadas API (default: 1000)
    
    Returns:
        GET : Template 'admin/create_producer.html'
        POST: Redirección al detalle del usuario creado o template con errores
    
    Note:
        - Crear usuario y productor es una transacción atómica
        - Validación automática de API key después de creación
        - Usuario se crea con rol PRODUCER y estado ACTIVE
        - Configuraciones tienen valores por defecto sensatos
        - Validación de unicidad para email y username
    """

    if request.method == 'POST':
        # Datos del usuario
        email      = request.form.get('email')
        username   = request.form.get('username')
        password   = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name  = request.form.get('last_name')
        phone      = request.form.get('phone')

        # Datos del productor
        heygen_api_key    = request.form.get('heygen_api_key')
        company_name      = request.form.get('company_name')
        business_type     = request.form.get('business_type')
        website           = request.form.get('website')
        max_subproducers  = request.form.get('max_subproducers', 10, type=int)
        max_affiliates    = request.form.get('max_affiliates', 100, type=int)
        monthly_api_limit = request.form.get('monthly_api_limit', 1000, type=int)
        
        # Validaciones
        if User.query.filter_by(email=email).first():
            flash('Ya existe un usuario con este email', 'error')
            return render_template('admin/create_producer.html')
        
        if User.query.filter_by(username=username).first():
            flash('Ya existe un usuario con este username', 'error')
            return render_template('admin/create_producer.html')
        
        # Crear usuario
        user = User(
            email      = email,
            username   = username,
            first_name = first_name,
            last_name  = last_name,
            phone      = phone,
            role       = UserRole.PRODUCER,
            status     = UserStatus.ACTIVE
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.flush()  # Para obtener el ID del usuario
        
        # Crear perfil de productor
        producer = Producer(
            user_id            = user.id,
            heygen_api_key     = heygen_api_key,
            company_name       = company_name,
            business_type      = business_type,
            website            = website,
            max_subproducers   = max_subproducers,
            max_affiliates    = max_affiliates,
            monthly_api_limit  = monthly_api_limit
        )
        
        db.session.add(producer)
        db.session.commit()
        
        # Validar API key
        producer.validate_api_key()
        
        flash(f'Productor {username} creado exitosamente', 'success')
        return redirect(url_for('admin.user_detail', user_id=user.id))
    
    return render_template('admin/create_producer.html')

@admin_bp.route('/producers')
@login_required
@admin_required
def producers():
    """
    Lista paginada de todos los productores del sistema.
    
    Proporciona una vista específica de productores con información
    relevante para administradores, incluyendo estado de API,
    límites y estadísticas de uso.
    
    Query Parameters:
        page (int, opcional): Número de página para paginación (default: 1)
    
    Returns:
        Template: 'admin/producers.html' con lista paginada de productores
    
    Context Variables:
        producers (Pagination): Objeto de paginación con productores
    
    Note:
        - Join automático con tabla User para información completa
        - Ordenamiento por fecha de creación (más recientes primero)
        - Paginación de 20 elementos por página
        - Acceso directo a métricas de cada productor
    """
    # Parámetro de consulta
    page = request.args.get('page', 1, type=int)

    # Consulta con join a User para información completa
    producers = Producer.query.join(User).order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    # Renderizar template con productores
    return render_template('admin/producers.html', producers=producers)

@admin_bp.route('/reels')
@login_required
@admin_required
def reels():
    """
    Lista paginada de todos los reels con filtrado por estado.
    
    Proporciona supervisión completa de la generación de videos,
    permitiendo filtrar por estado para identificar problemas
    o reels que requieren atención administrativa.
    
    Query Parameters:
        page (int, opcional): Número de página para paginación (default: 1)
        status (str, opcional): Filtro por estado (pending, processing, completed, failed)
    
    Returns:
        Template: 'admin/reels.html' con lista paginada de reels
    
    Context Variables:
        reels (Pagination): Objeto de paginación con reels filtrados
    
    Note:
        - Filtrado dinámico por estado de procesamiento
        - Ordenamiento por fecha de creación (más recientes primero)
        - Útil para identificar cuellos de botella en procesamiento
        - Acceso rápido a reels que requieren intervención manual
    """
    # Parámetros de consulta
    page          = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status')
    
    query = Reel.query
    
    if status_filter:
        query = query.filter_by(status=ReelStatus(status_filter))
    
    reels = query.order_by(Reel.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/reels.html', reels=reels)

@admin_bp.route('/commissions')
@login_required
@admin_required
def commissions():
    """
    Lista paginada de todas las comisiones con control financiero.
    
    Proporciona control completo sobre el sistema de comisiones,
    permitiendo supervisar pagos pendientes, aprobaciones y
    el flujo financiero general de la plataforma.
    
    Query Parameters:
        page (int, opcional): Número de página para paginación (default: 1)
        status (str, opcional): Filtro por estado (pending, approved, paid, rejected)
    
    Returns:
        Template: 'admin/commissions.html' con lista paginada de comisiones
    
    Context Variables:
        commissions (Pagination): Objeto de paginación con comisiones filtradas
    
    Note:
        - Control financiero completo de la plataforma
        - Filtrado por estado para gestión de flujo de caja
        - Ordenamiento cronológico para auditoría
        - Acceso a funciones de aprobación y marcado de pagos
    """
    # Capturar parámetros de filtrado y paginación
    page          = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status')
    
    query = Commission.query
    
    if status_filter:
        query = query.filter_by(status=CommissionStatus(status_filter))
    
    commissions = query.order_by(Commission.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/commissions.html', commissions=commissions)

@admin_bp.route('/commissions/<int:commission_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_commission(commission_id):
    """
    Aprobar una comisión pendiente para liberarla para pago.
    
    Cambia el estado de la comisión de PENDING a APPROVED,
    indicando que ha sido verificada y está lista para el
    proceso de pago. Acción crítica para el flujo financiero.
    
    Args:
        commission_id (int): ID de la comisión a aprobar
    
    Returns:
        Redirect: Redirección a lista de comisiones con mensaje de confirmación
    
    Note:
        - Paso crítico en el flujo de pagos
        - Una vez aprobada, la comisión se considera deuda confirmada
        - Acción irreversible que afecta el balance financiero
        - Debe incluir validaciones de negocio según el modelo
    """
    commission = Commission.query.get_or_404(commission_id)
    commission.approve()
    
    flash('Comisión aprobada exitosamente', 'success')
    return redirect(url_for('admin.commissions'))

@admin_bp.route('/commissions/<int:commission_id>/mark-paid', methods=['POST'])
@login_required
@admin_required
def mark_commission_paid(commission_id):
    """
    Marcar una comisión como pagada con información de pago.
    
    Registra el pago efectivo de una comisión aprobada, incluyendo
    referencia de pago y método utilizado. Completa el ciclo
    financiero de la comisión.
    
    Args:
        commission_id (int): ID de la comisión pagada
    
    Form Data (POST):
        payment_reference (str): Referencia del pago (número de transacción, etc.)
        payment_method (str): Método de pago utilizado (transferencia, PayPal, etc.)
    
    Returns:
        Redirect: Redirección a lista de comisiones con mensaje de confirmación
    
    Note:
        - Acción final en el ciclo de vida de una comisión
        - Información de pago se almacena para auditoría
        - Cambio de estado afecta estadísticas financieras
        - Registra timestamp automático del pago
    """
    # Obtener comisión y datos del formulario
    commission        = Commission.query.get_or_404(commission_id)
    payment_reference = request.form.get('payment_reference')
    payment_method    = request.form.get('payment_method')
    
    # Marcar como pagada
    commission.mark_as_paid(payment_reference, payment_method)
    
    flash('Comisión marcada como pagada', 'success')
    return redirect(url_for('admin.commissions'))

@admin_bp.route('/avatars')
@login_required
@admin_required
def avatars():
    """
    Lista paginada de todos los avatares con filtrado por estado.
    
    Proporciona supervisión completa de los avatares/clones digitales
    en el sistema, permitiendo filtrar por estado de aprobación
    para gestionar el flujo de creación y aprobación.
    
    Query Parameters:
        page (int, opcional): Número de página para paginación (default: 1)
        status (str, opcional): Filtro por estado (processing, active, inactive, failed)
    
    Returns:
        Template: 'admin/avatars.html' con lista paginada de avatares
    
    Context Variables:
        avatars (Pagination): Objeto de paginación con avatares filtrados
    
    Note:
        - Control completo sobre clones digitales de la plataforma
        - Filtrado por estado para gestión de aprobaciones
        - Ordenamiento cronológico para auditoría de creación
        - Acceso a funciones de aprobación/rechazo
    """
    # Capturar parámetros de filtrado y paginación
    page          = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status')
    
    query = Avatar.query

    # Aplicar filtro si se proporciona
    if status_filter:
        query = query.filter_by(status=AvatarStatus(status_filter))
   
    # Ejecutar consulta con paginación
    avatars = query.order_by(Avatar.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/avatars.html', avatars=avatars)

@admin_bp.route('/avatars/<int:avatar_id>')
@login_required
@admin_required
def avatar_detail(avatar_id):
    """
    Vista detallada de un avatar específico con información completa.
    
    Proporciona información exhaustiva sobre un avatar/clone digital,
    incluyendo metadatos, estado de procesamiento, estadísticas de uso
    y opciones administrativas.
    
    Args:
        avatar_id (int): ID único del avatar a mostrar
    
    Returns:
        Template: 'admin/avatar_detail.html' con información completa del avatar
    
    Context Variables:
        avatar (Avatar): Objeto avatar con toda la información
    
    Note:
        - Información técnica completa del clone digital
        - Estadísticas de uso y rendimiento
        - Acceso a funciones de aprobación/rechazo directo
        - Historial de cambios de estado
    """
    avatar = Avatar.query.get_or_404(avatar_id)
    return render_template('admin/avatar_detail.html', avatar=avatar)

@admin_bp.route('/avatars/<int:avatar_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_avatar(avatar_id):
    """
    Aprobar un avatar para activarlo en el sistema.
    
    Cambia el estado del avatar de PROCESSING a ACTIVE,
    haciéndolo disponible para uso en la generación de reels.
    Acción crítica que afecta la disponibilidad de recursos.
    
    Args:
        avatar_id (int): ID del avatar a aprobar
    
    Returns:
        Redirect: Redirección al detalle del avatar con mensaje de confirmación
    
    Note:
        - Aprobación hace el avatar disponible para uso
        - Debe validar calidad y cumplimiento antes de aprobar
        - Afecta los avatares disponibles para productores
        - Puede incluir notificación automática al creador
    """
    # btener avatar y aprobar usando método del modelo
    avatar = Avatar.query.get_or_404(avatar_id)
    avatar.approve(current_user)
    
    flash(f'Avatar {avatar.name} aprobado exitosamente', 'success')
    return redirect(url_for('admin.avatar_detail', avatar_id=avatar_id))

@admin_bp.route('/avatars/<int:avatar_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_avatar(avatar_id):
    """
    Rechazar un avatar por no cumplir criterios de calidad.
    
    Cambia el estado del avatar a INACTIVE, impidiendo su uso
    en el sistema. Útil para avatares que no cumplen estándares
    de calidad o políticas de contenido.
    
    Args:
        avatar_id (int): ID del avatar a rechazar
    
    Returns:
        Redirect: Redirección al detalle del avatar con mensaje de confirmación
    
    Note:
        - Rechazo previene uso del avatar en la plataforma
        - Debe incluir motivo del rechazo para el creador
        - Avatar permanece en sistema para auditoría
        - Puede ser revertido cambiando estado manualmente
    """
    # Obtener avatar y rechazar usando método del modelo
    avatar = Avatar.query.get_or_404(avatar_id)
    avatar.reject()
    
    flash(f'Avatar {avatar.name} rechazado', 'warning')
    return redirect(url_for('admin.avatar_detail', avatar_id=avatar_id))

@admin_bp.route('/api/stats')
@login_required
@admin_required
def api_stats():
    """"
    API REST para estadísticas administrativas en tiempo real.
    
    Proporciona estadísticas completas del sistema en formato JSON
    para integración con dashboards dinámicos o aplicaciones externas.
    Incluye métricas de usuarios, reels, avatares y comisiones.
    
    Returns:
        JSON: Objeto con estadísticas completas del sistema
        
    Response Structure:
        {
            "users": {
                "total": int,
                "active": int,
                "pending": int,
                "suspended": int
            },
            "roles": {
                "admins": int,
                "producers": int,
                "subproducers": int,
                "affiliates": int
            },
            "reels": {
                "total": int,
                "pending": int,
                "processing": int,
                "completed": int,
                "failed": int
            },
            "avatars": {
                "total": int,
                "pending": int,
                "approved": int,
                "rejected": int
            },
            "commissions": {
                "total": int,
                "pending": int,
                "approved": int,
                "paid": int,
                "total_amount": float
            }
        }
    
    Note:
        - Estadísticas calculadas en tiempo real para precisión
        - Compatible con frameworks de visualización JavaScript
        - Útil para dashboards dinámicos y monitoreo
        - Incluye métricas financieras para control de flujo de caja
        - Endpoint seguro que requiere autenticación administrativa
    """
    stats = {
        'users': {
            'total'     : User.query.count(),
            'active'    : User.query.filter_by(status=UserStatus.ACTIVE).count(),
            'pending'   : User.query.filter_by(status=UserStatus.PENDING).count(),
            'suspended' : User.query.filter_by(status=UserStatus.SUSPENDED).count()
        },
        'roles': {
            'admins'       : User.query.filter_by(role=UserRole.ADMIN).count(),
            'producers'    : User.query.filter_by(role=UserRole.PRODUCER).count(),
            'subproducers' : User.query.filter_by(role=UserRole.SUBPRODUCER).count(),
            'affiliates'   : User.query.filter_by(role=UserRole.AFFILIATE).count()
        },
        'reels': {
            'total'      : Reel.query.count(),
            'pending'    : Reel.query.filter_by(status=ReelStatus.PENDING).count(),
            'processing' : Reel.query.filter_by(status=ReelStatus.PROCESSING).count(),
            'completed'  : Reel.query.filter_by(status=ReelStatus.COMPLETED).count(),
            'failed'     : Reel.query.filter_by(status=ReelStatus.FAILED).count()
        },
        'avatars': {
            'total'    : Avatar.query.count(),
            'pending'  : Avatar.query.filter_by(status=AvatarStatus.PENDING).count(),
            'approved' : Avatar.query.filter_by(status=AvatarStatus.APPROVED).count(),
            'rejected' : Avatar.query.filter_by(status=AvatarStatus.REJECTED).count()
        },
        'commissions': {
            'total'       : Commission.query.count(),
            'pending'     : Commission.query.filter_by(status=CommissionStatus.PENDING).count(),
            'approved'    : Commission.query.filter_by(status=CommissionStatus.APPROVED).count(),
            'paid'        : Commission.query.filter_by(status=CommissionStatus.PAID).count(),
            'total_amount': sum([c.amount for c in Commission.query.all()])
        }
    }
    
    return jsonify(stats)