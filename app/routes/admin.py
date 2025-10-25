
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
from datetime import datetime
from app import db
from app.models.user import User, UserRole, UserStatus
from app.models.producer import Producer, ProducerStatus
from app.models.avatar import Avatar, AvatarStatus
from app.models.reel import Reel, ReelStatus
from app.models.commission import Commission, CommissionStatus

# Importación del modelo de solicitudes de productor
from app.models.producer_request import ProducerRequest, ProducerRequestStatus

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
        'pending_avatars'     : Avatar.query.filter_by( status = AvatarStatus.PENDING).count(),
        'approved_avatars'    : Avatar.query.filter_by( status = AvatarStatus.APPROVED).count(),
        'total_commissions'   : Commission.query.count(),
        'pending_commissions' : Commission.query.filter_by( status = CommissionStatus.PENDING).count()
    }
    
    # Usuarios recientes
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    
    # Reels recientes
    recent_reels = Reel.query.order_by(Reel.created_at.desc()).limit(5).all()
    
    # Elementos pendientes para el template
    pending_avatars = Avatar.query.filter_by(status = AvatarStatus.PENDING).limit(5).all()
    pending_reels   = Reel.query.filter_by(  status = ReelStatus.PENDING).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                         stats           = stats, 
                         recent_users    = recent_users, 
                         recent_reels    = recent_reels,
                         pending_avatars = pending_avatars,
                         pending_reels   = pending_reels)

@admin_bp.route('/users/create_admin', methods=['POST'])
@login_required
def create_admin():
    """
    Endpoint para crear un nuevo administrador. Solo el dueño puede acceder.

    query Parameters:
        email (str)      : Correo electrónico del nuevo administrador
        username (str)   : Nombre de usuario del nuevo administrador
        first_name (str) : Nombre del nuevo administrador
        last_name (str)  : Apellido del nuevo administrador
        password (str)   : Contraseña del nuevo administrador 
    
    Returns:
        JSON: {'success': True, 'user_id': int} o {'error': str} con código HTTP apropiado

    """
    if not current_user.is_owner:
        return jsonify({'error': 'Solo el dueño puede crear administradores.'}), 403
    
    # Obtener datos del formulario
    data        = request.form
    email       = data.get('email')
    username    = data.get('username')
    first_name  = data.get('first_name')
    last_name   = data.get('last_name')
    # password    = data.get('password')

    if not all([email, username, first_name, last_name, password]):
        return jsonify({'error': 'Todos los campos son obligatorios.'}), 400
    if User.query.filter_by(email=email).first() or User.query.filter_by(username=username).first():
        return jsonify({'error': 'El email o username ya existe.'}), 400
    
    user = User(
        email      = email,
        username   = username,
        first_name = first_name,
        last_name  = last_name,
        role       = UserRole.ADMIN,
        status     = UserStatus.ACTIVE,
        is_verified= True
    )
    
    # user.set_password(password) # password configura al verificar el mail
    db.session.add(user)
    db.session.commit()
    return jsonify({'success': True, 'user_id': user.id})


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
    
    # Si es productor, sumar métricas opcionales sin romper si no existen
    if user.is_producer() and getattr(user, 'producer_profile', None):
        producer = user.producer_profile
        user_stats.update({
            'subproducers_count'  : getattr(producer, 'current_subproducers_count', 0) or 0,
            'affiliates_count'    : getattr(producer, 'current_affiliates_count', 0) or 0,
            'avatars_count'       : (producer.avatars.count() if hasattr(producer, 'avatars') and producer.avatars is not None else 0),
            'api_calls_this_month': getattr(producer, 'api_calls_this_month', 0) or 0,
            'monthly_api_limit'   : getattr(producer, 'monthly_api_limit', None),
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

    # 1) Actualiza el usuario
    user.status = UserStatus.ACTIVE
    user.is_verified = True

    # 2) Si es productor, sincroniza su Producer
    if user.is_producer() and getattr(user, "producer_profile", None):
        p = user.producer_profile
        p.status = ProducerStatus.ACTIVE
        p.is_verified = True
        if not p.verified_at:
            p.verified_at = datetime.utcnow()

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
    from app.models.producer import ProducerStatus

    user         = User.query.get_or_404(user_id)

    # Suspender al usuario
    user.status  = UserStatus.SUSPENDED

    # Si es producer, sincronizar su perfil de productor
    if user.is_producer() and getattr(user, 'producer_profile', None):
        p = user.producer_profile
        p.status = ProducerStatus.SUSPENDED
        p.is_verified = False

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
    
    # Permitir que el dueño elimine administradores secundarios, pero nunca a sí mismo ni a otros dueños
    if user.role == UserRole.ADMIN:
        if user.is_owner:
            flash('No se puede eliminar al dueño de la plataforma.', 'error')
            return redirect(url_for('admin.user_detail', user_id=user_id))
        if not current_user.is_owner:
            flash('Solo el dueño puede eliminar administradores.', 'error')
            return redirect(url_for('admin.user_detail', user_id=user_id))
    
    # Si estoy eliminando a un PRODUCTOR: dejar huérfanos a sus subproductores
    if user.is_producer():
        producer = getattr(user, "producer_profile", None)

        # Solo si el modelo User tiene el vínculo al productor (p.ej. users.producer_id)
        if hasattr(User, "producer_id") and producer:
            subs = User.query.filter_by(
                producer_id=producer.id,
                role=UserRole.SUBPRODUCER
            ).all()

            for s in subs:
                # quedan huérfanos
                s.producer_id = None
                # sin acceso hasta ser reasignados
                s.status = UserStatus.SUSPENDED
                s.updated_at = datetime.utcnow()

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
        email (str)           : Email único del productor
        username (str)        : Username único del productor
        password (str)        : Contraseña para la cuenta
        first_name (str)      : Nombre del productor
        last_name (str)       : Apellido del productor
        phone (str, opcional) : Teléfono de contacto
        
        # Datos específicos del productor:
        heygen_api_key (str)          : API key de HeyGen para integración
        company_name (str, opcional)  : Nombre de la empresa
        business_type (str, opcional) : Tipo de negocio
        website (str, opcional)       : Sitio web corporativo
        max_subproducers (int)        : Límite de subproductores (default: 10)
        max_affiliates (int)          : Límite de afiliados (default: 100)
        monthly_api_limit (int)       : Límite mensual de llamadas API (default: 1000)

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
            user_id                  = user.id,
            heygen_api_key_encrypted = heygen_api_key,
            company_name             = company_name,
            business_type            = business_type,
            website                  = website,
            max_subproducers         = max_subproducers,
            max_affiliates           = max_affiliates,
            monthly_api_limit        = monthly_api_limit
        )
        
        db.session.add(producer)
        db.session.commit()
        
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
    producers = (
        Producer.query
        .join(User)
        .order_by(User.created_at.desc())
        .paginate(page=page, per_page=20, error_out=False)
    )

    # 🔧 Normalizar business_type para que el template no falle al agrupar
    for p in producers.items:
        if p.business_type is None:
            p.business_type = ""

    # Renderizar template con productores
    return render_template('admin/producers.html', producers=producers)

@admin_bp.route('/producers/<int:producer_id>')
@login_required
@admin_required
def producer_detail(producer_id):
    """
    Vista detallada de un productor específico con estadísticas completas.
    
    Proporciona información exhaustiva sobre un productor, incluyendo
    sus estadísticas de actividad, métricas de producción y estado
    de verificación. Incluye datos del usuario asociado y su red.
    
    Args:
        producer_id (int): ID único del productor a mostrar
    
    Returns:
        Template: 'admin/producer_detail.html' con información completa del productor
    
    Context Variables:
        producer (Producer) : Objeto productor con toda la información
        user (User)         : Usuario asociado al perfil de productor
        stats (dict)        : Estadísticas específicas del productor
        
        stats contiene:
            - avatars_count (int)      : Número de avatares creados
            - total_commissions (int)  : Total de comisiones generadas
            - total_reels (int)        : Total de reels creados
            - completed_reels (int)    : Reels completados exitosamente

    Note:
        - Carga segura de atributos opcionales del modelo
        - Estadísticas calculadas con validación de existencia
        - Join manual con tabla User para información completa
        - Métricas adaptadas según capacidades del productor
        - Manejo robusto de relaciones que pueden no existir
    """
    # Cargar productor y su usuario asociado (sin depender de backrefs)
    producer = Producer.query.get_or_404(producer_id)
    user = User.query.get(producer.user_id)

    # Métricas básicas seguras (evitan atributos que quizás no existan)
    avatars_count = producer.avatars.count() if hasattr(producer, 'avatars') else 0
    commissions_count = producer.commissions.count() if hasattr(producer, 'commissions') else 0

    # Reels del usuario (si hay user)
    total_reels = Reel.query.filter_by(creator_id=user.id).count() if user else 0
    completed_reels = (
        Reel.query.filter_by(creator_id=user.id, status=ReelStatus.COMPLETED).count()
        if user else 0
    )

    stats = {
        "avatars_count"      : avatars_count,
        "total_commissions"  : commissions_count,
        "total_reels"        : total_reels,
        "completed_reels"    : completed_reels,
    }

    return render_template('admin/producer_detail.html', producer=producer, user=user, stats=stats)

@admin_bp.post("/producers/<int:producer_id>/approve")
@login_required
@admin_required
def approve_producer(producer_id):
    """
    Aprobar y activar un productor con sincronización de usuario.
    
    Activa el perfil de productor y sincroniza el estado con su usuario
    asociado, marcando ambos como verificados. Registra timestamp de
    verificación para auditoría administrativa.
    
    Args:
        producer_id (int): ID del productor a aprobar
    
    Returns:
        Redirect: Redirección al detalle del productor con mensaje de confirmación
    
    Note:
        - Sincronización automática entre Producer y User
        - Registra timestamp de verificación para auditoría
        - Productor obtiene acceso inmediato a funcionalidades completas
        - Usuario asociado también es marcado como verificado
        - Transacción atómica para evitar estados inconsistentes
    """
    producer = Producer.query.get_or_404(producer_id)
    user = User.query.get(producer.user_id)

    producer.status = ProducerStatus.ACTIVE
    producer.is_verified = True
    producer.verified_at = datetime.utcnow()

    if user:
        user.status = UserStatus.ACTIVE
        user.is_verified = True
        user.updated_at = datetime.utcnow()

    db.session.commit()
    flash(f"✅ Productor {producer.company_name or user.username} activado correctamente.", "success")
    return redirect(url_for("admin.producer_detail", producer_id=producer.id))

@admin_bp.post("/producers/<int:producer_id>/suspend")
@login_required
@admin_required
def suspend_producer(producer_id):
    """
    Suspender temporalmente un productor con sincronización de usuario.
    
    Suspende el perfil de productor y sincroniza el estado con su usuario
    asociado, bloqueando el acceso a funcionalidades de productor mientras
    mantiene los datos intactos para futura reactivación.
    
    Args:
        producer_id (int): ID del productor a suspender
    
    Returns:
        Redirect: Redirección al detalle del productor con mensaje de confirmación
    
    Note:
        - Suspensión temporal y reversible mediante nueva aprobación
        - Sincronización automática entre Producer y User
        - Usuario asociado también es suspendido del sistema
        - Datos y configuraciones se mantienen intactas
        - Útil para medidas disciplinarias o investigaciones
        - Actualiza timestamp de modificación para auditoría
    """
    producer = Producer.query.get_or_404(producer_id)
    user = User.query.get(producer.user_id)

    producer.status = ProducerStatus.SUSPENDED

    if user:
        user.status = UserStatus.SUSPENDED
        user.updated_at = datetime.utcnow()

    db.session.commit()
    flash(f"⚠️ Productor {producer.company_name or user.username} suspendido correctamente.", "warning")
    return redirect(url_for("admin.producer_detail", producer_id=producer.id))

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
        page (int, opcional)   : Número de página para paginación (default: 1)
        status (str, opcional) : Filtro por estado (pending, processing, completed, failed)
    
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

@admin_bp.route('/reels/<int:reel_id>')
@login_required
@admin_required
def reel_detail(reel_id):
    """
    Vista detallada de un reel específico con información completa.
    
    Proporciona información exhaustiva sobre un reel generado,
    incluyendo metadatos técnicos, estado de procesamiento,
    estadísticas de rendimiento y opciones administrativas.
    
    Args:
        reel_id (int): ID único del reel a mostrar
    
    Returns:
        Template: 'admin/reel_detail.html' con información completa del reel
    
    Context Variables:
        reel (Reel): Objeto reel con toda la información técnica
    
    Note:
        - Información técnica completa del proceso de generación
        - Estado actual y historial de procesamiento
        - Metadatos del avatar y configuraciones utilizadas
        - Acceso a logs de generación para debugging
        - Opciones de re-procesamiento si es necesario
        - Estadísticas de rendimiento y calidad
    """
    reel = Reel.query.get_or_404(reel_id)
    return render_template('admin/reel_detail.html', reel=reel)

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
        payment_reference (str) : Referencia del pago (número de transacción, etc.)
        payment_method (str)    : Método de pago utilizado (transferencia, PayPal, etc.)
    
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
        page (int, opcional)  : Número de página para paginación (default: 1)
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
    """
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
            'affiliates'   : User.query.filter_by(role=UserRole.FINAL_USER).count()
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

@admin_bp.route('/producer-requests')
@login_required
@admin_required
def producer_requests():
    """
    Lista paginada de todas las solicitudes de productor.
    
    Proporciona una vista administrativa completa de todas las solicitudes
    para convertirse en productor, incluyendo filtrado por estado y
    búsqueda por usuario. Esencial para el flujo de aprobación.
    
    Query Parameters:
        page (int, opcional)  : Número de página para paginación (default: 1)
        status (str, opcional): Filtro por estado (pending, approved, rejected)
        search (str, opcional): Búsqueda por nombre de usuario o email
    
    Returns:
        Template: 'admin/producer_requests.html' con lista paginada de solicitudes
    
    Context Variables:
        requests (Pagination): Objeto de paginación con solicitudes filtradas
        pending_count (int): Número de solicitudes pendientes (para badges)
    
    Note:
        - Vista crítica para administradores gestionar solicitudes
        - Incluye información del usuario solicitante con join optimizado
        - Ordenamiento por fecha de creación (más recientes primero)
        - Acceso directo a funciones de aprobación/rechazo
        - Badge con número de solicitudes pendientes para priorización
    """
    # Parámetros de consulta para filtrado y paginación
    page          = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status')
    search        = request.args.get('search', '')
    
    # Consulta base con join para información del usuario
    query = ProducerRequest.query.join(ProducerRequest.user)
    
    # Aplicar filtros dinámicamente
    if status_filter:
        try:
            status_enum = ProducerRequestStatus(status_filter)
            query       = query.filter(ProducerRequest.status == status_enum)
        except ValueError:
            # Estado inválido, ignorar filtro
            pass
    
    # Búsqueda por información del usuario
    if search:
        from app.models.user import User
        query = query.filter(
            db.or_(
                User.username.contains(search),
                User.email.contains(search),
                User.first_name.contains(search),
                User.last_name.contains(search),
                ProducerRequest.company_name.contains(search)
            )
        )
    
    # Ejecutar consulta con paginación (más recientes primero)
    requests = query.order_by(ProducerRequest.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Contar solicitudes pendientes para badge informativo
    pending_count = ProducerRequest.query.filter_by(
        status=ProducerRequestStatus.PENDING
    ).count()
    
    return render_template('admin/producer_requests.html', 
                         requests=requests, 
                         pending_count=pending_count)

@admin_bp.route('/producer-requests/<int:request_id>')
@login_required
@admin_required  
def producer_request_detail(request_id):
    """
    Vista detallada de una solicitud específica de productor.
    
    Muestra información completa de la solicitud incluyendo datos
    del solicitante, motivación, información empresarial y historial
    de revisión. Incluye opciones de aprobación/rechazo.
    
    Args:
        request_id (int): ID único de la solicitud a mostrar
    
    Returns:
        Template: 'admin/producer_request_detail.html' con información completa
    
    Context Variables:
        producer_request (ProducerRequest): Objeto solicitud con toda la información
        user_stats (dict): Estadísticas del usuario solicitante
    
    Note:
        - Información completa del usuario y su actividad en la plataforma
        - Historial de revisiones anteriores si las hay
        - Formularios inline para aprobar/rechazar con motivos
        - Estadísticas del usuario para evaluar experiencia previa
    """
    # Obtener solicitud con información relacionada
    producer_request = ProducerRequest.query.options(
        db.joinedload(ProducerRequest.user),
        db.joinedload(ProducerRequest.reviewed_by)
    ).get_or_404(request_id)
    
    # Estadísticas del usuario solicitante para contexto
    user = producer_request.user
    user_stats = {
        'total_reels'       : user.reels.count(),
        'completed_reels'   : user.reels.filter_by(status=ReelStatus.COMPLETED).count(),
        'total_commissions' : user.commissions_earned.count(),
        'member_since'      : user.created_at,
        'last_login'        : user.last_login,
        'previous_requests' : ProducerRequest.query.filter(
            ProducerRequest.user_id == user.id,
            ProducerRequest.id != request_id
        ).count()
    }
    
    return render_template('admin/producer_request_detail.html',
                         producer_request=producer_request,
                         user_stats=user_stats)

@admin_bp.route('/producer-requests/<int:request_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_producer_request(request_id):
    """
    Aprobar una solicitud de productor y elevar permisos de usuario.
    
    Procesa una solicitud de productor marcándola como aprobada y
    actualizando el rol del usuario solicitante a PRODUCER. Utiliza
    el método approve() del modelo para garantizar consistencia.
    
    Args:
        request_id (int): ID de la solicitud a aprobar
    
    Returns:
        Redirect: Redirección a lista de solicitudes con mensaje de confirmación
    
    Form Data (POST):
        notes (str, opcional): Notas administrativas sobre la aprobación
    
    Note:
        - Utiliza método approve() del modelo para transacción atómica
        - Cambio de rol es permanente hasta nueva intervención administrativa
        - Usuario obtiene acceso inmediato a funcionalidades de productor
        - Se registra auditoría completa automáticamente
        - Manejo de errores robusto con rollback automático
        - Notificación automática al usuario (futuro enhancement)
    """
    # Obtener solicitud con información relacionada
    producer_request = ProducerRequest.query.get_or_404(request_id)
    
    # Capturar notas administrativas opcionales
    notes = request.form.get('notes')
    
    try:
        # Usar método del modelo para aprobación atómica
        producer_request.approve(current_user, notes=notes)
        
        # Mensaje de éxito con información del usuario
        user = producer_request.user
        flash(f"Solicitud de {user.username} aprobada exitosamente. "
              f"Ahora tiene permisos de productor.", "success")
              
    except ValueError as e:
        # Error de validación (solicitud no en estado correcto)
        flash(f"Error al aprobar solicitud: {str(e)}", "error")
        
    except Exception as e:
        # Error inesperado durante el proceso
        db.session.rollback()
        flash(f"Error interno al procesar la solicitud: {str(e)}", "error")

    return redirect(url_for('admin.producer_requests'))

@admin_bp.route('/producer-requests/<int:request_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_producer_request(request_id):
    """
    Rechazar una solicitud de productor por no cumplir criterios.
    
    Marca una solicitud de productor como REJECTED, denegando
    el acceso a funcionalidades de productor. Utiliza el método
    reject() del modelo para garantizar consistencia de datos.
    
    Args:
        request_id (int): ID de la solicitud a rechazar
    
    Returns:
        Redirect: Redirección a lista de solicitudes con mensaje de confirmación
    
    Form Data (POST):
        rejection_reason (str, opcional): Motivo del rechazo para el usuario
        notes (str, opcional): Notas internas del administrador
    
    Note:
        - Utiliza método reject() del modelo para transacción consistente
        - Acción reversible, usuario puede volver a solicitar
        - Se registra auditoría completa automáticamente
        - Usuario no cambia de rol, mantiene permisos actuales
        - Motivo del rechazo ayuda al usuario para futuras solicitudes
        - Notificación automática al usuario (futuro enhancement)
    """
    # Obtener solicitud con información relacionada
    producer_request = ProducerRequest.query.get_or_404(request_id)
    
    # Capturar datos del formulario
    rejection_reason = request.form.get('rejection_reason')
    notes = request.form.get('notes')
    
    try:
        # Usar método del modelo para rechazo consistente
        producer_request.reject(current_user, reason=rejection_reason, notes=notes)
        
        # Mensaje de confirmación con información del usuario
        user = producer_request.user
        flash(f"Solicitud de {user.username} rechazada.", "info")
        
    except ValueError as e:
        # Error de validación (solicitud no en estado correcto)
        flash(f"Error al rechazar solicitud: {str(e)}", "error")
        
    except Exception as e:
        # Error inesperado durante el proceso
        db.session.rollback()
        flash(f"Error interno al procesar la solicitud: {str(e)}", "error")

    return redirect(url_for('admin.producer_requests'))

@admin_bp.route('/producers/<int:producer_id>/approve-api-key', methods=['GET', 'POST'])
@login_required
@admin_required
def approve_api_key(producer_id):
    """
    Aprobar manualmente la API key de HeyGen de un productor.
    
    Marca la API key del productor como válida sin realizar validación
    automática. Útil cuando la validación automática falla pero el
    administrador confirma manualmente que la key es funcional.
    
    Args:
        producer_id (int): ID del productor cuya API key se aprobará
    
    Returns:
        Redirect: Redirección a lista de productores con mensaje de confirmación
    
    Note:
        - Bypass de validación automática para casos especiales
        - Útil cuando HeyGen API tiene problemas temporales
        - Administrador asume responsabilidad de la validez de la key
        - Cambio se refleja inmediatamente en capacidades del productor
        - Incluye rollback automático en caso de error de base de datos
        - Manejo graceful de errores para campos opcionales del modelo
    """
    # Obtener productor por ID
    producer = Producer.query.get_or_404(producer_id)
    
    # Intentar marcar API key como válida con manejo de errores
    try:
        # Campo opcional que puede no existir en todas las versiones del modelo
        producer.api_key_status = 'valid'
        db.session.commit()
        flash('API key marcada como válida.', 'success')
    except Exception as e:
        # Rollback en caso de error y notificar problema
        db.session.rollback()
        flash(f'No se pudo actualizar el estado de la API key: {e}', 'danger')

    return redirect(url_for('admin.producers'))

@admin_bp.route('/producers/<int:producer_id>/reset-limits', methods=['GET', 'POST'])
@login_required
@admin_required
def reset_producer_limits(producer_id):
    """
    Resetear los límites y contadores mensuales de un productor.
    
    Restablece a cero todos los contadores mensuales del productor,
    incluyendo llamadas API y uso de recursos. Útil para resolver
    problemas de límites o conceder uso adicional excepcional.
    
    Args:
        producer_id (int): ID del productor cuyos límites se resetearán
    
    Returns:
        Redirect: Redirección a lista de productores con mensaje de confirmación
    
    Note:
        - Resetea contadores sin cambiar los límites máximos configurados
        - Útil para casos excepcionales o resolución de problemas
        - Registra timestamp del reset para auditoría
        - Manejo graceful de campos opcionales del modelo Producer
        - Permite uso inmediato después del reset
        - Acción potencialmente crítica que puede afectar costos de API
    """
    # Obtener productor por ID
    producer = Producer.query.get_or_404(producer_id)

    # Resetear contadores con manejo de atributos opcionales
    # Estos campos pueden variar según la versión del modelo
    try:
        # Contador de llamadas API del mes actual
        producer.api_calls_this_month = 0
    except AttributeError:
        # Campo opcional, ignorar si no existe en el modelo
        pass

    try:
        # Contador general de uso mensual
        producer.used_this_month = 0
    except AttributeError:
        # Campo opcional, ignorar si no existe en el modelo
        pass

    try:
        # Timestamp del último reset para auditoría
        producer.last_reset_at = datetime.utcnow()
    except AttributeError:
        # Campo opcional, ignorar si no existe en el modelo
        pass

    # Actualizar timestamp de modificación (campo estándar)
    producer.updated_at = datetime.utcnow()
    db.session.commit()

    flash('Límites mensuales reseteados correctamente.', 'success')
    return redirect(url_for('admin.producers'))

@admin_bp.route('/users/<int:user_id>/promote-to-producer', methods=['POST'])
@login_required
@admin_required
def promote_to_producer(user_id):
    """
    Cambiar el rol de un usuario final a productor.
    
    Convierte un usuario con rol FINAL_USER a PRODUCER y crea
    automáticamente su perfil de productor con configuraciones por defecto.
    Solo permite promoción desde FINAL_USER para mantener integridad.
    
    Args:
        user_id (int): ID del usuario a promocionar
    
    Returns:
        Redirect: Redirección al detalle del usuario con mensaje de confirmación
    
    Form Data (POST):
        company_name (str, opcional)   : Nombre de la empresa/marca
        business_type (str, opcional)  : Tipo de negocio
        website (str, opcional)        : Sitio web corporativo
        max_subproducers (int)         : Límite de subproductores (default: 10)
        max_affiliates (int)           : Límite de afiliados (default: 100)
        monthly_api_limit (int)        : Límite mensual de API (default: 1000)

    Note:
        - Solo permite promoción desde FINAL_USER por seguridad
        - Crea perfil Producer automáticamente con valores por defecto
        - Usuario mantiene sus datos personales existentes
        - Transacción atómica para evitar estados inconsistentes
        - API key de HeyGen debe configurarse por separado
        - Registra auditoría completa del cambio de rol
    """
    # Obtener usuario y validar que existe
    user = User.query.get_or_404(user_id)
    
    # Validar que el usuario actual sea FINAL_USER
    if user.role != UserRole.FINAL_USER:
        flash(f'Error: Solo usuarios finales pueden ser promocionados a productor. '
              f'Usuario actual tiene rol: {user.role.value}', 'error')
        return redirect(url_for('admin.user_detail', user_id=user_id))
    
    # Validar que no tenga ya un perfil de productor
    if hasattr(user, 'producer_profile') and user.producer_profile:
        flash('Error: El usuario ya tiene un perfil de productor asociado.', 'error')
        return redirect(url_for('admin.user_detail', user_id=user_id))
    
    try:
        # Capturar datos del formulario con valores por defecto
        company_name      = request.form.get('company_name') or f'{user.full_name} Productions'
        business_type     = request.form.get('business_type') or 'Creador de Contenido'
        website           = request.form.get('website', '')
        max_subproducers  = request.form.get('max_subproducers', 10, type=int)
        max_affiliates    = request.form.get('max_affiliates', 100, type=int)
        monthly_api_limit = request.form.get('monthly_api_limit', 1000, type=int)
        
        # 1. Cambiar rol del usuario
        user.role = UserRole.PRODUCER
        user.updated_at = datetime.utcnow()
        
        # 2. Crear perfil de productor con configuraciones por defecto
        producer = Producer(
            user_id           = user.id,
            company_name      = company_name,
            business_type     = business_type,
            website           = website,
            max_subproducers   = max_subproducers,
            max_affiliates     = max_affiliates,
            monthly_api_limit  = monthly_api_limit,
            status             = ProducerStatus.PENDING,  # Requiere configuración de API key
            is_verified        = False,
            settings           = {}  # Configuraciones adicionales vacías
        )
        
        # 3. Guardar cambios de forma atómica
        db.session.add(producer)
        db.session.commit()
        
        # Mensaje de éxito con instrucciones
        flash(f'✅ Usuario {user.username} promocionado a productor exitosamente. '
              f'Ahora debe configurar su API key de HeyGen para completar la configuración.', 'success')
              
    except Exception as e:
        # Rollback en caso de error y mostrar mensaje
        db.session.rollback()
        flash(f'Error al promocionar usuario: {str(e)}', 'error')
    
    return redirect(url_for('admin.user_detail', user_id=user_id))


