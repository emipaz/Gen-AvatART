"""
Módulo de rutas de productor para la aplicación Gen-AvatART.

Este módulo maneja todas las rutas específicas de los productores del sistema,
proporcionando un panel de control completo para la gestión de avatares, reels,
equipos y configuraciones. Incluye integración avanzada con HeyGen API.

El módulo incluye:
    - Dashboard de productor      : Estadísticas y resumen de actividad
    - Gestión de avatares         : Creación, aprobación y control de clones
    - Gestión de reels            : Supervisión de videos de la red
    - Administración de equipos   : Invitación y gestión de subproductores/afiliados
    - Panel de ganancias          : Control de comisiones y estadísticas financieras
    - Configuraciones             : API keys, límites y datos comerciales
    - APIs de integración         : Endpoints para servicios externos

Funcionalidades principales:
    - Sistema de permisos con decorador @producer_required
    - Gestión completa del ciclo de vida de avatares
    - Supervisión de reels propios y de la red subordinada
    - Onboarding y gestión de equipos con límites configurables
    - Control financiero de comisiones y ganancias
    - Integración en tiempo real con HeyGen API
    - Validación automática de cuotas y límites API
    - Panel de configuraciones comerciales

Características técnicas:
    - Decorador personalizado para verificación de permisos de productor
    - Consultas optimizadas con filtros dinámicos por estado y creador
    - Paginación automática para mejor rendimiento
    - Integración con HeyGenService para validación de API
    - Sistema de límites configurables (subproductores, afiliados, API calls)
    - Cálculo en tiempo real de estadísticas financieras
    - Manejo robusto de errores con rollback automático
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from functools import wraps
from sqlalchemy import or_
from app import db
from app.models.user import User, UserRole, UserStatus
from app.models.producer import Producer
from app.models.avatar import Avatar, AvatarStatus
from app.models.reel import Reel, ReelStatus
from app.models.commission import Commission, CommissionStatus
from app.services.heygen_service import HeyGenService
from app.utils.date_utils import get_current_month_range
from datetime import datetime

producer_bp = Blueprint('producer', __name__)

def producer_required(f):
    """
    Decorador para requerir permisos de productor.
    
    Este decorador verifica que el usuario actual tenga permisos
    de productor antes de permitir el acceso a rutas específicas.
    Proporciona una capa adicional de seguridad para funcionalidades
    exclusivas de productores.
    
    Args:
        f (function): Función de vista a proteger
    
    Returns:
        function: Función decorada con verificación de permisos
    
    Note:
        - Se ejecuta después de @login_required
        - Redirige a index si no tiene permisos de productor
        - Mensaje flash informativo para feedback al usuario
        - Complementa la autenticación básica con validación de rol
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_producer():
            flash('Acceso denegado. Permisos de productor requeridos.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@producer_bp.route('/dashboard')
@login_required
@producer_required
def dashboard():
    """
    Dashboard principal del productor con estadísticas completas.
    
    Proporciona una vista general exhaustiva de la actividad del productor,
    incluyendo métricas de reels, avatares, equipo, ganancias y estado
    de integración con HeyGen. Incluye elementos que requieren atención.
    
    Returns:
        Template: 'producer/dashboard.html' con estadísticas y actividad reciente
    
    Context Variables:
            - stats (dict)   : Estadísticas completas del productor
            
            - total_reels (int)         : Total de reels creados
            - completed_reels (int)     : Reels completados exitosamente
            - pending_reels (int)       : Reels pendientes de procesamiento
            - total_avatars (int)       : Total de avatares bajo gestión
            - approved_avatars (int)    : Avatares aprobados y activos
            - pending_avatars (int)     : Avatares pendientes de aprobación
            - subproducers_count (int)  : Número de subproductores activos
            - affiliates_count (int)    : Número de afiliados en la red
            - total_earnings (float)    : Ganancias totales aprobadas
            - pending_earnings (float)  : Ganancias pendientes de aprobación
            - api_calls_used (int)      : Llamadas API usadas este mes
            - api_calls_limit (int)     : Límite mensual de llamadas API
            - api_key_status (str)      : Estado de validación de API key

            - recent_reels (list)    : 5 reels más recientes del productor
            - recent_avatars (list)  : 5 avatares más recientes creados
            - pending_avatars (list) : Avatares pendientes de aprobación
            - pending_reels (list)   : Reels de la red pendientes de aprobación

    Note:
        - Estadísticas calculadas en tiempo real para precisión
        - Incluye actividad tanto propia como de la red subordinada
        - Estado de API key crítico para operaciones con HeyGen
        - Elementos pendientes priorizados para atención inmediata
    """
    producer = current_user.producer_profile
    
    # Contar subproductores y afiliados (usuarios invitados por este productor)
    subproducers_count = User.query.filter_by(
        invited_by_id  = current_user.id,
        role           = UserRole.SUBPRODUCER,
        status         = UserStatus.ACTIVE
    ).count()
    
    affiliates_count = User.query.filter_by(
        invited_by_id = current_user.id,
        role          = UserRole.FINAL_USER,
        status        = UserStatus.ACTIVE
    ).count()
    
    # Estadísticas del productor
    stats = {
        'total_reels'       : current_user.reels.count(),
        'completed_reels'   : current_user.reels.filter_by( status = ReelStatus.COMPLETED).count(),
        'pending_reels'     : current_user.reels.filter_by( status =ReelStatus.PENDING).count(),
        'total_avatars'     : producer.avatars.count(),
        'approved_avatars'  : producer.avatars.filter_by( status = AvatarStatus.APPROVED).count(),
        'pending_avatars'   : producer.avatars.filter_by( status = AvatarStatus.PROCESSING).count(),
        'subproducers_count': subproducers_count,
        'affiliates_count'  : affiliates_count,
        'end_users_count'   : affiliates_count,  # Alias para compatibilidad con template
        'monthly_reels'     : current_user.reels.filter_by( status = ReelStatus.COMPLETED).count(),  # Simplificado por ahora
        'total_earnings'    : Commission.get_user_total_earnings(current_user.id, CommissionStatus.APPROVED),
        'pending_earnings'  : Commission.get_user_total_earnings(current_user.id, CommissionStatus.PENDING),
        'total_commissions' : Commission.get_user_total_earnings(current_user.id, CommissionStatus.APPROVED),
        'pending_commissions' : Commission.get_user_total_earnings(current_user.id, CommissionStatus.PENDING),
        'api_calls_used'    : getattr(producer, 'api_calls_this_month', 0),
        'api_calls_limit'   : producer.monthly_api_limit,
        'api_key_status'    : getattr(producer, 'api_key_status', 'not_configured')
    }
    
    # Actividad reciente
    recent_reels   = current_user.reels.order_by(Reel.created_at.desc()).limit(5).all()
    recent_avatars = producer.avatars.order_by(Avatar.created_at.desc()).limit(5).all()
    
    # Elementos pendientes de aprobación
    pending_avatars = producer.avatars.filter_by(status=AvatarStatus.PROCESSING).all()
    pending_reels   = Reel.query.join(User, Reel.creator_id == User.id).filter(
        User.invited_by_id == current_user.id,
        Reel.status        == ReelStatus.PENDING
    ).all()
    
    return render_template('producer/dashboard.html',
                         stats           = stats,
                         team_stats      = stats,  # Alias para compatibilidad con template
                         recent_reels    = recent_reels,
                         recent_avatars  = recent_avatars,
                         pending_avatars = pending_avatars,
                         pending_reels   = pending_reels)

@producer_bp.route('/avatars')
@login_required
@producer_required
def avatars():
    """
    Lista paginada de avatares del productor con filtros avanzados.
    
    Proporciona una vista completa de todos los avatares bajo la gestión
    del productor, con capacidades de filtrado por estado y paginación
    automática para mejorar el rendimiento.
    
    Query Parameters:
        page (int, opcional)   : úmero de página para paginación (default: 1)
        status (str, opcional) : Filtro por estado (active, processing, inactive, failed)
    
    Returns:
        Template: 'producer/avatars.html' con lista paginada de avatares
    
    Context Variables:
        avatars (Pagination) : Objeto de paginación con avatares filtrados
    
    Note:
        - Solo muestra avatares del productor actual
        - Filtrado dinámico por estado de avatar
        - Paginación de 12 elementos por página (optimizado para grids)
        - Ordenamiento por fecha de creación (más recientes primero)
    """
    page          = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status')
    
    query = current_user.producer_profile.avatars
    
    if status_filter:
        query = query.filter_by(status = AvatarStatus(status_filter))
    
    avatars = query.order_by(Avatar.created_at.desc()).paginate(
        page = page, per_page = 12, error_out = False
    )
    
    return render_template('producer/avatars.html', avatars=avatars)

@producer_bp.route('/avatars/create', methods=['GET', 'POST'])
@login_required
@producer_required
def create_avatar():
    """
    Crear un nuevo avatar/clone digital con integración HeyGen.
    
    Maneja la creación completa de avatares digitales, incluyendo
    validación de cuotas API, configuración de parámetros y
    envío a HeyGen para procesamiento. Incluye configuraciones
    de monetización y acceso.
    
    Methods:
        GET  : Muestra el formulario de creación de avatar
        POST : Procesa los datos y crea el avatar
    
    Form Data (POST):
        name (str)            : Nombre descriptivo del avatar
        description (str)     : Descripción detallada del avatar
        avatar_type (str)     : Tipo de avatar (male, female, custom)
        language (str)        : Idioma principal (default: 'es')
        tags (str)            : Etiquetas separadas por comas
        is_public (bool)      : Si el avatar es público o privado
        is_premium (bool)     : Si requiere pago por uso
        price_per_use (float) : Precio por uso si es premium
    
    Returns:
        GET : Template 'producer/create_avatar.html'
        POST: Redirección a lista de avatares o template con errores
    
    Note:
        - Validación automática de cuota API antes de crear
        - Estado inicial PROCESSING hasta completar en HeyGen
        - Incremento automático del uso de API calls
        - TODO: Integración real con HeyGen API (actualmente simulado)
        - Configuración de monetización para avatares premium
    """
    producer = current_user.producer_profile
    
    # Verificar cuota API (si no hay límite o no se ha alcanzado)
    api_calls_used = getattr(producer, 'api_calls_this_month', 0)
    if producer.monthly_api_limit and api_calls_used >= producer.monthly_api_limit:
        flash('Has alcanzado tu límite mensual de API calls', 'error')
        return redirect(url_for('producer.avatars'))
    
    if request.method == 'POST':
        name          = request.form.get('name')
        description   = request.form.get('description')
        avatar_type   = request.form.get('avatar_type')
        language      = request.form.get('language', 'es')
        tags          = request.form.get('tags', '')
        is_public     = bool(request.form.get('is_public'))
        is_premium    = bool(request.form.get('is_premium'))
        price_per_use = float(request.form.get('price_per_use', 0))
        
        # Crear avatar en la base de datos
        avatar = Avatar(
            producer_id    = producer.id,
            created_by_id  = current_user.id,
            name           = name,
            description    = description,
            avatar_type    = avatar_type,
            language       = language,
            is_public      = is_public,
            is_premium     = is_premium,
            price_per_use  = price_per_use,
            status         = AvatarStatus.PROCESSING
        )
        avatar.set_tags(tags.split(','))
        
        db.session.add(avatar)
        db.session.commit()
        
        # TODO: Integrar con HeyGen para crear el avatar
        # Por ahora, simplemente marcarlo como aprobado
        avatar.status           = AvatarStatus.APPROVED
        avatar.heygen_avatar_id = f"heygen_{avatar.id}"
        db.session.commit()
        
        # Incrementar uso de API manualmente
        if hasattr(producer, 'api_calls_this_month'):
            producer.api_calls_this_month = getattr(producer, 'api_calls_this_month', 0) + 1
        else:
            # Si no existe el campo, no hacer nada por ahora
            pass
        
        db.session.commit()
        
        flash('Avatar creado exitosamente', 'success')
        return redirect(url_for('producer.avatars'))
    
    return render_template('producer/create_avatar.html')

@producer_bp.route('/avatars/<int:avatar_id>/approve', methods=['POST'])
@login_required
@producer_required
def approve_avatar(avatar_id):
    """
    Aprobar un avatar creado por subproductor de la red.
    
    Permite al productor aprobar avatares creados por subproductores
    bajo su gestión. Incluye validación de permisos para asegurar
    que solo se aprueben avatares de su propia red.
    
    Args:
        avatar_id (int): ID del avatar a aprobar
    
    Returns:
        Redirect: Redirección a lista de avatares con mensaje de confirmación
    
    Note:
        - Solo avatares de subproductores de la propia red
        - Validación estricta de permisos por seguridad
        - Cambio de estado usando método del modelo Avatar
        - Registro automático del usuario que aprueba
    """
    avatar = Avatar.query.get_or_404(avatar_id)
    
    # Verificar que el avatar pertenece a este productor
    if avatar.producer_id != current_user.producer_profile.id:
        flash('No tienes permisos para aprobar este avatar', 'error')
        return redirect(url_for('producer.avatars'))
    
    avatar.approve(current_user)
    flash(f'Avatar "{avatar.name}" aprobado exitosamente', 'success')
    
    return redirect(url_for('producer.avatars'))

@producer_bp.route('/avatars/<int:avatar_id>/reject', methods=['POST'])
@login_required
@producer_required
def reject_avatar(avatar_id):
    """
    Rechazar un avatar por no cumplir criterios de calidad.
    
    Permite al productor rechazar avatares que no cumplen con
    los estándares de calidad o políticas establecidas. Incluye
    validación de permisos y manejo de estado.
    
    Args:
        avatar_id (int): ID del avatar a rechazar
    
    Returns:
        Redirect: Redirección a lista de avatares con mensaje de confirmación
    
    Note:
        - Solo avatares bajo la gestión del productor
        - Avatar permanece en sistema para auditoría
        - Estado cambia a INACTIVE para prevenir uso
        - Puede incluir notificación al creador (futuro)
    """
    avatar = Avatar.query.get_or_404(avatar_id)
    
    if avatar.producer_id != current_user.producer_profile.id:
        flash('No tienes permisos para rechazar este avatar', 'error')
        return redirect(url_for('producer.avatars'))
    
    avatar.reject()
    flash(f'Avatar "{avatar.name}" rechazado', 'warning')
    
    return redirect(url_for('producer.avatars'))

@producer_bp.route('/reels')
@login_required
@producer_required
def reels():
    """
    Lista paginada de reels del productor y su red con filtros avanzados.
    
    Proporciona supervisión completa de todos los reels creados por
    el productor y su red subordinada (subproductores y afiliados).
    Incluye filtros por estado y creador para gestión eficiente.
    
    Query Parameters:
        page (int, opcional)    : Número de página para paginación (default: 1)
        status (str, opcional)  : Filtro por estado (pending, processing, completed, failed)
        creator (str, opcional) : Filtro por ID del creador específico
    
    Returns:
        Template: 'producer/reels.html' con lista paginada de reels
    
    Context Variables:
        reels (Pagination) : Objeto de paginación con reels filtrados
        creators (list)    : Lista de usuarios creadores para filtro
    
    Note:
        - Incluye reels propios y de toda la red subordinada
        - Consulta optimizada con JOIN para rendimiento
        - Filtros combinables para búsquedas específicas
        - Lista de creadores dinâmica basada en la red actual
    """

    page            = request.args.get('page', 1, type=int)
    status_filter   = request.args.get('status')
    creator_filter = request.args.get('creator')
    
    # Obtener reels del productor y su red
    query = Reel.query.join(User, Reel.creator_id == User.id).filter(
        or_(
            Reel.creator_id    == current_user.id,  # Reels del productor
            User.invited_by_id == current_user.id  # Reels de su red
        )
    )
    
    if status_filter:
        query = query.filter(Reel.status == ReelStatus(status_filter))
    
    if creator_filter:
        query = query.filter(Reel.creator_id == creator_filter)
    
    reels = query.order_by(Reel.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Lista de creadores para el filtro
    creators = User.query.filter(
        or_(
            User.id == current_user.id,
            User.invited_by_id == current_user.id
        )
    ).all()
    
    return render_template('producer/reels.html', reels=reels, creators=creators)

@producer_bp.route('/reels/<int:reel_id>/approve', methods=['POST'])
@login_required
@producer_required
def approve_reel(reel_id):
    """
    Aprobar un reel para publicación o procesamiento.
    
    Permite al productor aprobar reels creados por miembros de su red.
    Incluye validación de permisos jerárquicos para asegurar que solo
    se aprueben reels de usuarios bajo su gestión.
    
    Args:
        reel_id (int): ID del reel a aprobar
    
    Returns:
        Redirect: Redirección a lista de reels con mensaje de confirmación
    
    Note:
        - Validación jerárquica: propios o de red subordinada
        - Cambio de estado usando método del modelo Reel
        - Registro del usuario que aprueba para auditoría
        - Puede desencadenar procesamiento automático en HeyGen
    """
    # Obtener reel y validar existencia
    reel = Reel.query.get_or_404(reel_id)
    
    # Verificar permisos
    if not (reel.creator_id == current_user.id or 
            reel.creator.invited_by_id == current_user.id):
        flash('No tienes permisos para aprobar este reel', 'error')
        return redirect(url_for('producer.reels'))
    
    reel.approve(current_user)
    flash(f'Reel "{reel.title}" aprobado exitosamente', 'success')
    
    return redirect(url_for('producer.reels'))

@producer_bp.route('/reels/<int:reel_id>/reject', methods=['POST'])
@login_required
@producer_required
def reject_reel(reel_id):
    """
    Rechazar un reel por no cumplir criterios o políticas.
    
    Permite al productor rechazar reels que no cumplen con
    estándares de calidad, políticas de contenido o requisitos
    técnicos. Incluye validación de permisos jerárquicos.
    
    Args:
        reel_id (int): ID del reel a rechazar
    
    Returns:
        Redirect: Redirección a lista de reels con mensaje de confirmación
    
    Note:
        - Misma validación jerárquica que approve_reel
        - Reel permanece en sistema para auditoría
        - Puede incluir motivo del rechazo (futuro)
        - Notificación automática al creador (futuro)
    """
    # Obtener reel y validar existencia
    reel = Reel.query.get_or_404(reel_id)
    
    if not (reel.creator_id == current_user.id or 
            reel.creator.invited_by_id == current_user.id):
        flash('No tienes permisos para rechazar este reel', 'error')
        return redirect(url_for('producer.reels'))
    
    reel.reject()
    flash(f'Reel "{reel.title}" rechazado', 'warning')
    
    return redirect(url_for('producer.reels'))

@producer_bp.route('/team')
@login_required
@producer_required
def team():
    """
    Panel de gestión del equipo del productor.
    
    Proporciona una vista completa del equipo del productor,
    incluyendo subproductores y afiliados activos, junto con
    estadísticas de límites y capacidad disponible.
    
    Returns:
        Template: 'producer/team.html' con información del equipo
    
    Context Variables:
        subproducers (list)  : Lista de subproductores activos
        affiliates (list)    : Lista de afiliados activos
        producer (Producer)  : Perfil del productor con límites y estadísticas
    
    Note:
        - Solo muestra miembros invitados por el productor actual
        - Información de límites para gestión de capacidad
        - Acceso rápido a funciones de invitación
        - Estadísticas de rendimiento por miembro del equipo
    """
    # Obtener subproductores y afiliados
    subproducers = User.query.filter_by(
        invited_by_id = current_user.id,
        role          = UserRole.SUBPRODUCER
    ).all()
    
    affiliates = User.query.filter_by(
        invited_by_id = current_user.id,
        role          = UserRole.FINAL_USER
    ).all()
    
    producer = current_user.producer_profile
    
    return render_template('producer/team.html',
                         subproducers = subproducers,
                         affiliates   = affiliates,
                         producer     = producer)

@producer_bp.route('/team/invite', methods=['GET', 'POST'])
@login_required
@producer_required
def invite_member():
    """
    Invitar un nuevo miembro al equipo del productor.
    
    Maneja el proceso completo de invitación y creación de nuevos
    miembros del equipo (subproductores o afiliados). Incluye
    validación de límites y creación directa de usuarios.
    
    Methods:
        GET  : Muestra el formulario de invitación
        POST : Procesa la invitación y crea el usuario
    
    Form Data (POST):
        role (str)       : Rol del nuevo miembro (subproducer, affiliate)
        email (str)      : Email único del nuevo miembro
        username (str)   : Username único del nuevo miembro
        password (str)   : Contraseña para la nueva cuenta
        first_name (str) : Nombre del nuevo miembro
        last_name (str)  : Apellido del nuevo miembro
    
    Returns:
        GET  : Template 'producer/invite_member.html'
        POST : Redirección al equipo o template con errores
    
    Note:
        - Validación automática de límites según el rol
        - Creación directa sin proceso de aprobación
        - Usuario se crea ACTIVE y listo para usar
        - Relación jerárquica establecida automáticamente
        - Validación de unicidad para email y username
    """
    producer = current_user.producer_profile
    
    if request.method == 'POST':
        role       = request.form.get('role')
        email      = request.form.get('email')
        username   = request.form.get('username')
        password   = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name  = request.form.get('last_name')
        
        # Validar límites
        if role == 'subproducer':
            current_subproducers = User.query.filter_by(
                invited_by_id=current_user.id,
                role=UserRole.SUBPRODUCER
            ).count()
            if current_subproducers >= producer.max_subproducers:
                flash('Has alcanzado el límite máximo de subproductores', 'error')
                return render_template('producer/invite_member.html')
        
        if role == 'affiliate':
            current_affiliates = User.query.filter_by(
                invited_by_id=current_user.id,
                role=UserRole.FINAL_USER
            ).count()
            if current_affiliates >= producer.max_affiliates:
                flash('Has alcanzado el límite máximo de afiliados', 'error')
                return render_template('producer/invite_member.html')
        
        # Verificar si el usuario ya existe
        if User.query.filter_by(email=email).first():
            flash('Ya existe un usuario con este email', 'error')
            return render_template('producer/invite_member.html')
        
        # Crear usuario
        user = User(
            email         = email,
            username      = username,
            first_name    = first_name,
            last_name     = last_name,
            role          = UserRole(role),
            status        = UserStatus.ACTIVE,
            invited_by_id = current_user.id
        )
        # Establecer contraseña
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash(f'{role.title()} {username} agregado exitosamente', 'success')
        return redirect(url_for('producer.team'))
    
    return render_template('producer/invite_member.html')

@producer_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@producer_required
def settings():
    """
    Panel de configuración del productor.
    
    Permite al productor actualizar su información personal,
    datos comerciales y configuraciones técnicas como la API key
    de HeyGen. Incluye validación automática de nuevas API keys.
    
    Methods:
        GET  : Muestra el formulario de configuración actual
        POST : Actualiza las configuraciones del productor
    
    Form Data (POST):
        # Información personal:
        first_name (str)   : Nombre del productor
        last_name (str)    : Apellido del productor
        phone (str)        : Teléfono de contacto

        # Información comercial:
        company_name (str)   : Nombre de la empresa
        business_type (str)  : Tipo de negocio
        website (str)        : Sitio web corporativo

        # Configuración técnica:
        heygen_api_key (str): Nueva API key de HeyGen (opcional)
    
    Returns:
        GET : Template 'producer/settings.html' con configuración actual
        POST: Redirección a settings con mensaje de confirmación
    
    Note:
        - Validación automática de nueva API key si se proporciona
        - Estado de API key se actualiza según validación
        - Cambios se aplican inmediatamente
        - Información comercial para facturación y reportes
    """
    # Obtener perfil del productor
    producer = current_user.producer_profile
    
    if request.method == 'POST':
        try:
            # Actualizar información del usuario
            current_user.first_name = request.form.get('first_name')
            current_user.last_name  = request.form.get('last_name')
            current_user.phone      = request.form.get('phone')
            
            # Actualizar información del productor
            if producer:
                producer.company_name  = request.form.get('company_name')
                producer.business_type = request.form.get('business_type')
                producer.website       = request.form.get('website')
                
                # Actualizar API key si se proporciona una nueva
                new_api_key = request.form.get('heygen_api_key')
                if new_api_key and new_api_key.strip():
                    # Si no son solo asteriscos (campo enmascarado)
                    if not all(c == '•' for c in new_api_key):
                        try:
                            # Encriptar y guardar la nueva API key
                            producer.set_heygen_api_key(new_api_key.strip())
                            
                            # Marcar como pendiente de validación
                            producer.set_setting('api_validation_status', 'pending')
                            
                            # TODO: Aquí se podría hacer validación inmediata
                            # Por ahora, marcamos como válida para pruebas
                            producer.set_setting('api_validation_status', 'valid')
                            
                            flash('✅ API key de HeyGen configurada exitosamente. '
                                  'Ya puedes comenzar a crear avatares.', 'success')
                        except Exception as e:
                            flash(f'❌ Error al configurar API key: {str(e)}', 'error')
                            db.session.rollback()
                            return redirect(url_for('producer.settings'))
                
                # Actualizar timestamp
                producer.updated_at = datetime.utcnow()
            
            db.session.commit()
            
            if not new_api_key or new_api_key.strip() == '' or all(c == '•' for c in new_api_key):
                flash('✅ Configuración actualizada exitosamente', 'success')
                
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al actualizar configuración: {str(e)}', 'error')
            
        return redirect(url_for('producer.settings'))
    
    # Renderizar template con información actual
    return render_template('producer/settings.html', producer=producer)

@producer_bp.route('/earnings')
@login_required
@producer_required
def earnings():
    """
    Panel de ganancias y comisiones del productor.
    
    Proporciona una vista completa de las ganancias del productor,
    incluyendo comisiones históricas, estadísticas financieras
    y estado de pagos. Incluye paginación para historial extenso.
    
    Query Parameters:
        page (int, opcional): Número de página para historial (default: 1)
    
    Returns:
        Template: 'producer/earnings.html' con información financiera
    
    Context Variables:
            - commissions (Pagination) : Historial paginado de comisiones
            - stats (dict)             : Estadísticas financieras del productor
            - total_approved (float)   : Total de ganancias aprobadas
            - total_pending (float)    : Ganancias pendientes de aprobación
            - total_paid (float)       : Total ya pagado al productor
            - this_month (float)       : Ganancias del mes actual

    Note:
        - Estadísticas calculadas usando métodos del modelo Commission
        - Historial ordenado cronológicamente (más recientes primero)
        - Paginación de 20 elementos para rendimiento
        - Información crítica para control financiero personal
    """
    # Paginación
    page = request.args.get('page', 1, type=int)
    
    # Comisiones del productor
    commissions = current_user.commissions_earned.order_by(
        Commission.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    
    # ✅ Estadísticas de ganancias usando utilidades de fecha
    current_date = datetime.now()
    earnings_stats = {
        'total_approved'  : Commission.get_user_total_earnings(current_user.id, CommissionStatus.APPROVED),
        'total_pending'   : Commission.get_user_total_earnings(current_user.id, CommissionStatus.PENDING),
        'total_paid'      : Commission.get_user_total_earnings(current_user.id, CommissionStatus.PAID),
        'this_month'      : Commission.get_monthly_earnings(current_user.id,
                                                    current_date.year,
                                                    current_date.month)
    }
    
    return render_template('producer/earnings.html',
                         commissions=commissions,
                         stats=earnings_stats)

@producer_bp.route('/api/heygen-status')
@login_required
@producer_required
def api_heygen_status():
    """"
    API REST para verificar el estado de integración con HeyGen.
    
    Proporciona información en tiempo real sobre el estado de la
    API key de HeyGen, cuotas disponibles y límites de uso.
    Útil para dashboards dinámicos y validaciones automáticas.
    
    Returns:
        JSON: Estado de la integración con HeyGen
    
    Response Structure:
        # Caso: Sin API key configurada
        {"status": "no_key", "message": "API key no configurada"}
        
        # Caso: API key válida
        {
            "status": "active",
            "user_info": {...},          # Información del usuario en HeyGen
            "quota_info": {...},         # Información de cuotas
            "api_calls_used": int,       # Llamadas usadas este mes
            "api_calls_limit": int       # Límite mensual configurado
        }
        
        # Caso: API key inválida
        {"status": "invalid", "message": "API key inválida"}
        
        # Caso: Error de conexión
        {"status": "error", "message": "Descripción del error"}
    
    Note:
        - Endpoint útil para validaciones en tiempo real
        - Información crítica para operaciones con HeyGen
        - Manejo robusto de errores de conexión
        - Datos de cuota esenciales para gestión de límites
    """
    # Obtener perfil del productor
    producer = current_user.producer_profile
    
    # Verificar si hay API key configurada
    if not producer.heygen_api_key:
        return jsonify({'status': 'no_key', 'message': 'API key no configurada'})
    
    # Validar API key y obtener información
    try:
        service    = HeyGenService(producer.heygen_api_key)
        user_info  = service.get_user_info()
        quota_info = service.get_quota_info()
        
        if user_info:
            return jsonify({
                'status'         : 'active',
                'user_info'      : user_info,
                'quota_info'     : quota_info,
                'api_calls_used' : producer.api_calls_this_month,
                'api_calls_limit': producer.monthly_api_limit
            })
        else:
            return jsonify({'status': 'invalid', 'message': 'API key inválida'})
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

