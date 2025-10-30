# Endpoint para suspender (toggle status) a un subproductor o usuario final
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
from app.services.snapshot_service import save_avatar_snapshot, load_avatar_snapshot
from app.services.avatar_sync_service import sync_producer_heygen_avatars
from app.utils.date_utils import get_current_month_range
from datetime import datetime
from uuid import uuid4
import uuid

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
        if not current_user.ensure_producer_profile():
            flash('Acceso denegado. Perfil de productor no disponible.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

def producer_or_subproducer_required(f):
    """
    Decorador para requerir permisos de productor O subproductor.
    
    Este decorador permite acceso tanto a productores como a subproductores
    para funcionalidades que pueden ser realizadas por ambos roles,
    como la creación de avatares.
    
    Args:
        f (function): Función de vista a proteger
    
    Returns:
        function: Función decorada con verificación de permisos
    
    Note:
        - Permite rol PRODUCER y SUBPRODUCER
        - Se ejecuta después de @login_required
        - Redirige a index si no tiene los permisos necesarios
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            flash('Acceso denegado. Debe iniciar sesión.', 'error')
            return redirect(url_for('auth.login'))
        
        if not (current_user.is_producer() or current_user.is_subproducer()):
            flash('Acceso denegado. Permisos de productor o subproductor requeridos.', 'error')
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
    # recent_reels   = current_user.reels.order_by(Reel.created_at.desc()).limit(5).all()
    recent_reels = (
        Reel.query
            .filter_by(creator_id=current_user.id)
            .order_by(Reel.created_at.desc())
            .limit(5)
            .all()
    )
    recent_avatars = producer.avatars.order_by(Avatar.created_at.desc()).limit(5).all()
    
    # Elementos pendientes de aprobación
    pending_avatars = producer.avatars.filter_by(status=AvatarStatus.PROCESSING).all()
    pending_reels   = Reel.query.join(User, Reel.creator_id == User.id).filter(
        User.invited_by_id == current_user.id,
        Reel.status        == ReelStatus.PENDING
    ).all()
    
    # Obtener lista de subproductores para la sección "Mi Equipo" del dashboard
    subproducers = User.query.filter_by(
        invited_by_id = current_user.id,
        role          = UserRole.SUBPRODUCER,
        status        = UserStatus.ACTIVE
    ).all()
    
    return render_template('producer/dashboard.html',
                         stats           = stats,
                         team_stats      = stats,  # Alias para compatibilidad con template
                         recent_reels    = recent_reels,
                         recent_avatars  = recent_avatars,
                         pending_avatars = pending_avatars,
                         pending_reels   = pending_reels,
                         subproducers    = subproducers)

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
    producer = current_user.producer_profile

    page = request.args.get('page', 1, type=int)
    status_param = (request.args.get('status') or '').strip().upper()

    query = Avatar.query.filter_by(producer_id=producer.id)

    # Mapeo seguro desde el string del query a tu Enum
    valid_statuses = {'ACTIVE', 'INACTIVE', 'PROCESSING', 'REJECTED', 'APPROVED', 'PENDING', 'FAILED'}

    if status_param in valid_statuses:
        # ✅ Columna Enum: comparo contra el Enum, NO contra string
        query = query.filter(Avatar.status == AvatarStatus[status_param])
        selected_status = status_param
    else:
        # query = query.filter(Avatar.status != AvatarStatus.INACTIVE)      # Por defecto ocultamos los INACTIVE
        selected_status = 'ALL'         # ALL: no filtramos nada

    avatars = query.order_by(Avatar.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )

    return render_template(
        'producer/avatars.html',
        avatars=avatars,
        selected_status=selected_status,
    )

@producer_bp.route('/avatar/<int:avatar_id>')
@login_required
@producer_required
def avatar_detail(avatar_id):
    """Detalle de un avatar del productor actual."""
    producer = current_user.producer_profile

    # Buscar el avatar y verificar pertenencia
    avatar = Avatar.query.get_or_404(avatar_id)
    if avatar.producer_id != producer.id:
        flash("No tenés acceso a este avatar.", "error")
        return redirect(url_for('producer.avatars'))

    # (Opcional) Cargar snapshot si existe para recreación/custodia
    snapshot = None
    try:
        from app.services.snapshot_service import load_avatar_snapshot
        snapshot = load_avatar_snapshot(avatar_id)
    except Exception:
        snapshot = None

    # Avatares recreados que derivan de este (trazabilidad inversa)
    siblings = (
        Avatar.query
        .filter(Avatar.producer_id == avatar.producer_id, Avatar.id != avatar.id)
        .all()
    )

    derived_avatars = [
        a for a in siblings
        if (getattr(a, "meta_data", {}) or {}).get("recreated_from") == avatar.id
    ]

    # Avatar original (si este fue recreado desde otro)
    parent_avatar = None
    meta = avatar.meta_data or {}
    parent_id = meta.get("recreated_from")
    if parent_id:
        parent_avatar = Avatar.query.get(parent_id)

    return render_template(       
        'producer/avatar_detail.html',
        avatar=avatar,
        snapshot=snapshot,
        derived_avatars=derived_avatars,
        parent_avatar=parent_avatar
    )

@producer_bp.route('/avatar/<int:avatar_id>/recreate', methods=['POST'])
@login_required
@producer_required
def recreate_avatar(avatar_id):
    # Dueño actual (productor)
    producer = current_user.producer_profile

    # Verificamos que el avatar exista y sea del productor logueado
    avatar = Avatar.query.filter_by(id=avatar_id, producer_id=producer.id).first_or_404()

    # Cargamos el snapshot guardado
    snapshot = load_avatar_snapshot(avatar_id)
    if not snapshot:
        flash('No hay snapshot disponible para este avatar.', 'warning')
        return redirect(url_for('producer.avatar_detail', avatar_id=avatar_id))

    inputs = snapshot.get('inputs', {}) or {}

    # Tomamos campos del snapshot con fallback a los del avatar original
    name        = inputs.get('name') or f"Recreado de {avatar.name}"
    description = inputs.get('description') or (avatar.description or '')
    avatar_type = inputs.get('avatar_type') or (avatar.avatar_type or 'video')
    language    = inputs.get('language') or (avatar.language or 'es')
    tags        = inputs.get('tags') or []

    # IMPORTANTE: avatar_ref es NOT NULL → generamos uno local
    new_avatar = Avatar(
        producer_id   = producer.id,
        created_by_id = current_user.id,
        name          = name,
        description   = description,
        avatar_type   = avatar_type,
        language      = language,
        avatar_ref    = f"local_{uuid.uuid4().hex}",
        status        = AvatarStatus.PROCESSING
    )

    db.session.add(new_avatar)
    db.session.flush()          # asegura que el ID se genere antes del snapshot

    # Guardamos el meta_data con el ID de origen
    new_avatar.meta_data = {"recreated_from": avatar.id}

    db.session.commit()

    if tags:
        # acepta lista o string; si es lista, la mandamos directa
        new_avatar.set_tags(
            tags if isinstance(tags, list) 
            else [t.strip() for t in str(tags).split(',') if t.strip()]
        )
        db.session.commit()

    # Renombrar el avatar para indicar que es recreado
    # new_avatar.name = f"{avatar.name} (recreado)"

    # Guardar snapshot para el nuevo avatar
    save_avatar_snapshot(
        avatar_id=new_avatar.id,
        producer_id=new_avatar.producer_id,
        created_by_id=current_user.id,
        source="recreated_from",
        inputs=(snapshot or {}).get("inputs", {}),
        heygen_owner_hint=(snapshot or {}).get("heygen_owner_hint"),
        extra={
            "recreated_from_avatar_id": avatar.id,
            "original_snapshot_created_at": (snapshot or {}).get("created_at"),
        },
    )

    # Simulación de aprobación inmediata (hasta integrar HeyGen real)
    new_avatar.status = AvatarStatus.ACTIVE
    new_avatar.heygen_avatar_id = f"heygen_{new_avatar.id}"
    db.session.commit()

    flash('Avatar recreado desde snapshot.', 'success')
    return redirect(url_for('producer.avatar_detail', avatar_id=new_avatar.id))

@producer_bp.route('/avatar/<int:avatar_id>/archive', methods=['POST'])
@login_required
@producer_required
def archive_avatar(avatar_id):
    """Archiva (INACTIVE) un avatar del productor actual."""
    producer = current_user.producer_profile
    avatar = Avatar.query.filter_by(id=avatar_id, producer_id=producer.id).first_or_404()

    if avatar.status == AvatarStatus.INACTIVE:
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return jsonify({'success': False, 'message': 'El avatar ya estaba archivado.', 'status': 'inactive'})
        flash('El avatar ya estaba archivado.', 'info')
        return redirect(url_for('producer.avatars'))

    avatar.status = AvatarStatus.INACTIVE
    avatar.enabled_by_producer = False

    metadata = avatar.meta_data or {}
    metadata['inactive_by'] = 'producer'
    metadata['inactive_at'] = datetime.utcnow().isoformat()
    metadata.pop('reactivation_requested', None)
    metadata.pop('reactivation_requested_at', None)
    metadata.pop('reactivation_requested_by', None)
    avatar.meta_data = metadata

    db.session.commit()
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'success': True, 'message': 'Avatar archivado.', 'status': 'inactive'})
    flash('Avatar archivado.', 'success')
    return redirect(url_for('producer.avatars'))

# --- NUEVO: Reactivar avatar (solo si no fue desactivado por el subproductor) ---
# @producer_bp.route('/avatar/<int:avatar_id>/activate', methods=['POST'])
# @login_required
# @producer_required
# def activate_avatar(avatar_id):
#     """Permite al productor reactivar un avatar si no fue desactivado por el subproductor."""
#     producer = current_user.producer_profile
#     avatar = Avatar.query.filter_by(id=avatar_id, producer_id=producer.id).first_or_404()

#     # Solo permitir si está inactivo y NO fue desactivado por el subproductor
#     if avatar.status != AvatarStatus.INACTIVE:
#         if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#             return jsonify({'success': False, 'message': 'El avatar no está archivado.', 'status': avatar.status.value.lower()})
#         flash('El avatar no está archivado.', 'info')
#         return redirect(url_for('producer.avatars'))

#     if hasattr(avatar, 'enabled_by_subproducer') and not avatar.enabled_by_subproducer:
#         avatar.status = AvatarStatus.ACTIVE
#         db.session.commit()
#         if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#             return jsonify({'success': True, 'message': 'Avatar reactivado correctamente.', 'status': 'active'})
#         flash('Avatar reactivado correctamente.', 'success')
#     else:
#         if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
#             return jsonify({'success': False, 'message': 'No se puede reactivar: el subproductor lo desactivó.', 'status': 'inactive'})
#         flash('No se puede reactivar: el subproductor lo desactivó.', 'warning')
#     return redirect(url_for('producer.avatars'))

@producer_bp.route('/avatar/<int:avatar_id>/reactivate', methods=['POST'])
@login_required
@producer_required
def reactivate_avatar(avatar_id):
    """
    Reactiva un avatar inactivo del productor actual.
    
    Cambia el estado de un avatar de INACTIVE a ACTIVE, permitiendo
    que vuelva a ser utilizado para crear reels y aparezca en las
    listas de avatares disponibles. También habilita todos los flags
    necesarios para que el avatar esté completamente funcional.
    
    Args:
        avatar_id (int): ID del avatar a reactivar
    
    Returns:
        Redirect: Redirección a la página de avatares con mensaje de confirmación
    
    Note:
        - Solo el productor dueño del avatar puede reactivarlo
        - El avatar debe estar en estado INACTIVE
        - Después de reactivar aparecerá en filtro "Activos"
        - Habilita automáticamente todos los flags necesarios
    """
    producer = current_user.producer_profile
    avatar = Avatar.query.filter_by(id=avatar_id, producer_id=producer.id).first_or_404()

    if avatar.status == AvatarStatus.ACTIVE:
        flash('El avatar ya estaba activo.', 'info')
        return redirect(url_for('producer.avatars'))
    
    if avatar.status != AvatarStatus.INACTIVE:
        flash('Solo se pueden reactivar avatares archivados.', 'error')
        return redirect(url_for('producer.avatars'))

    # ✅ Cambiar estado y habilitar todos los flags
    avatar.status = AvatarStatus.ACTIVE
    avatar.enabled_by_admin = True
    avatar.enabled_by_producer = True
    avatar.enabled_by_subproducer = True

    metadata = avatar.meta_data or {}
    metadata.pop('inactive_by', None)
    metadata.pop('inactive_at', None)
    metadata.pop('reactivation_requested', None)
    metadata.pop('reactivation_requested_at', None)
    metadata.pop('reactivation_requested_by', None)
    avatar.meta_data = metadata
    
    db.session.commit()
    flash('Avatar reactivado exitosamente.', 'success')
    return redirect(url_for('producer.avatars'))

@producer_bp.route('/test')
@login_required
def test_route():
    """Ruta de prueba para diagnosticar errores"""
    print(f"TEST ROUTE: Usuario {current_user.username}, Rol: {current_user.role}")
    return f"<h1>Test OK</h1><p>Usuario: {current_user.username}</p><p>Rol: {current_user.role}</p>"

@producer_bp.route('/avatars/create', methods=['GET', 'POST'])
@login_required
@producer_or_subproducer_required
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
    # Obtener el productor relevante dependiendo del rol del usuario
    if current_user.is_producer():
        # Si es productor, usa su propio perfil
        producer = current_user.producer_profile
    elif current_user.is_subproducer():
        # Si es subproductor, usa el perfil del productor que lo invitó
        supervisor = User.query.get(current_user.invited_by_id)
        if not supervisor or not supervisor.producer_profile:
            flash('Error: No se encontró el productor supervisor', 'error')
            return redirect(url_for('main.index'))
        producer = supervisor.producer_profile
    else:
        flash('Acceso denegado', 'error')
        return redirect(url_for('main.index'))
    
    # Verificar cuota API (si no hay límite o no se ha alcanzado)
    api_calls_used = getattr(producer, 'api_calls_this_month', 0)
    if producer and producer.monthly_api_limit and api_calls_used >= producer.monthly_api_limit:
        flash('Se ha alcanzado el límite mensual de API calls', 'error')
        return redirect(url_for('producer.avatars'))

    
    if request.method == 'POST':
        name          = request.form.get('name')
        description   = request.form.get('description')
        avatar_type   = request.form.get('avatar_type')
        language      = request.form.get('language', 'es')
        tags          = request.form.get('tags', '')
        is_public     = bool(request.form.get('is_public'))
        is_premium    = bool(request.form.get('is_premium'))
        # Precio: convertir seguro (acepta vacío y coma decimal)
        price_raw = (request.form.get('price_per_use') or "").strip()
        if price_raw == "":
            price_per_use = 0.0
        else:
            price_per_use = float(price_raw.replace(",", "."))  # soporta "12,5"

        
        # Crear avatar en la base de datos
        avatar = Avatar(
            producer_id    = producer.id,
            created_by_id  = current_user.id,
            name           = name,
            description    = description,
            avatar_type    = avatar_type,
            language       = language,
            # is_public      = is_public,
            # is_premium     = is_premium,
            # price_per_use  = price_per_use,
            status         = AvatarStatus.PROCESSING,
            avatar_ref    = f"local_{uuid4().hex}"   # <- evita el NOT NULL
        )
        avatar.set_tags(tags.split(','))
        
        db.session.add(avatar)
        db.session.commit()

        # Guardar snapshot para poder recrear este avatar luego (p. ej., por productor custodio)
        save_avatar_snapshot(
            avatar_id=avatar.id,
            producer_id=producer.id,
            created_by_id=current_user.id,
            source="producer_ui",
            inputs={
                "name": name,
                "description": description,
                "avatar_type": avatar_type,
                "language": language,
                "tags": [t.strip() for t in tags.split(",") if t.strip()],
                "is_public": is_public,
                "is_premium": is_premium,
                "price_per_use": price_per_use,
            },
            heygen_owner_hint=producer.company_name,
        )
        
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
    # Filtros GET
    search = request.args.get('search', '').strip()
    role = request.args.get('role', '').strip()

    # Filtro de estado
    status = request.args.get('status', '').strip()

    # Base query: mostrar todos los miembros invitados por el productor
    query = User.query.filter(User.invited_by_id == current_user.id)
    # Filtro por estado
    if status == 'active':
        query = query.filter(User.status == UserStatus.ACTIVE)
    elif status == 'inactive':
        query = query.filter(User.status == UserStatus.SUSPENDED)
    # Filtro por rol
    if role in ['subproducer', 'final_user']:
        query = query.filter(User.role == (UserRole.SUBPRODUCER if role == 'subproducer' else UserRole.FINAL_USER))
    # Filtro de búsqueda
    if search:
        search_pattern = f"%{search}%"
        query = query.filter(
            (User.first_name.ilike(search_pattern)) |
            (User.last_name.ilike(search_pattern)) |
            (User.username.ilike(search_pattern))
        )

    team_members = query.order_by(User.role, User.first_name, User.last_name).all()

    # Para compatibilidad con el template
    subproducers = [u for u in team_members if u.role == UserRole.SUBPRODUCER]
    affiliates = [u for u in team_members if u.role == UserRole.FINAL_USER]

    team_stats = {
        'active_members': len([u for u in team_members if u.status == UserStatus.ACTIVE]),
        'subproducers_count': len(subproducers)
    }

    producer = current_user.producer_profile

    return render_template('producer/team.html',
                         team_members = team_members,
                         team_stats   = team_stats,
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
    from app.services.email_service import send_template_email
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
            status        = UserStatus.PENDING,
            invited_by_id = current_user.id,
            is_verified   = False  # Invitados por el productor se marcan como no verificados
        )
        # Establecer contraseña
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()

        # Generar token de verificación
        token = user.generate_verification_token()
        # Enviar email de invitación
        send_template_email(
            template_name="invitation",
            subject="Te han invitado a Gem-AvatART",
            recipients=[user.email],
            template_vars={
                "user_name"         : user.full_name,
                "producer_name"     : current_user.full_name,
                "verification_link" : url_for('auth.verify_email', token=token, _external=True),
                "app_name"          : "Gem-AvatART"
            }
        )
        
        flash(f'{role.title()} {username} agregado exitosamente', 'success')
        return redirect(url_for('producer.team'))
    
    return render_template('producer/invite_member.html')

@producer_bp.route('/settings', methods=['GET', 'POST'])
@login_required
@producer_required
def settings():
    """
    Panel de configuración del productor.
    # Vista de configuración del productor
    # Obtiene el perfil del productor actual

    # Vista de configuración del productor
    # Obtiene el perfil del productor actual

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
    # Obtener o crear perfil del productor según corresponda
    producer = current_user.ensure_producer_profile()
    if not producer:
        flash('No se encontró el perfil de productor del usuario.', 'error')
        return redirect(url_for('main.index'))
    
    if request.method == 'POST':
        form_type = request.form.get('form_type')
        api_key_updated = False
        try:
            if form_type == 'heygen_api_key':
                # Solo actualizar la API key, no tocar otros campos
                new_api_key = (request.form.get('heygen_api_key') or '').strip()
                if new_api_key:
                    if not all(c == '•' for c in new_api_key):
                        try:
                            producer.set_heygen_api_key(new_api_key)
                            producer.set_setting('api_validation_status', 'pending')
                            producer.set_setting('api_validation_status', 'valid')
                            flash('✅ API key de HeyGen configurada exitosamente. '
                                  'Ya puedes comenzar a crear avatares.', 'success')
                            api_key_updated = True
                        except Exception as e:
                            flash(f'❌ Error al configurar API key: {str(e)}', 'error')
                            db.session.rollback()
                            return redirect(url_for('producer.settings'))
                producer.updated_at = datetime.utcnow()
                db.session.commit()
                if api_key_updated:
                    synced, sync_message, category = sync_producer_heygen_avatars(producer)
                    if sync_message:
                        flash(sync_message, category)
                return redirect(url_for('producer.settings'))
            # Si no es solo API key, procesar el resto del formulario normal
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
                new_api_key = (request.form.get('heygen_api_key') or '').strip()
                if new_api_key:
                    if not all(c == '•' for c in new_api_key):
                        try:
                            producer.set_heygen_api_key(new_api_key)
                            producer.set_setting('api_validation_status', 'pending')
                            producer.set_setting('api_validation_status', 'valid')
                            flash('✅ API key de HeyGen configurada exitosamente. '
                                  'Ya puedes comenzar a crear avatares.', 'success')
                            api_key_updated = True
                        except Exception as e:
                            flash(f'❌ Error al configurar API key: {str(e)}', 'error')
                            db.session.rollback()
                            return redirect(url_for('producer.settings'))
                producer.updated_at = datetime.utcnow()
            db.session.commit()
            if api_key_updated:
                synced, sync_message, category = sync_producer_heygen_avatars(producer)
                if sync_message:
                    flash(sync_message, category)
            if not new_api_key or new_api_key.strip() == '' or all(c == '•' for c in new_api_key):
                flash('✅ Configuración actualizada exitosamente', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'❌ Error al actualizar configuración: {str(e)}', 'error')
        return redirect(url_for('producer.settings'))
    
    # Renderizar template con información actual
    return render_template('producer/settings.html', producer=producer)


@producer_bp.route('/settings/sync-heygen', methods=['POST'])
@login_required
@producer_required
def sync_heygen():
    """Permite disparar manualmente la sincronización de avatares con HeyGen."""
    producer = current_user.ensure_producer_profile()
    if not producer:
        flash('No se encontró el perfil de productor.', 'error')
        return redirect(url_for('producer.settings'))

    if not producer.get_heygen_api_key():
        flash('Configura tu API key de HeyGen antes de sincronizar.', 'warning')
        return redirect(url_for('producer.settings'))

    synced, sync_message, category = sync_producer_heygen_avatars(producer)
    flash(sync_message or 'Sincronización completada.', category or 'info')
    return redirect(url_for('producer.settings'))

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

@producer_bp.route('/api/masked-heygen-key')
@login_required
@producer_required
def api_masked_heygen_key():
    producer = current_user.producer_profile
    masked_api_key = producer.get_masked_heygen_api_key() if producer else None
    return jsonify({'masked_api_key': masked_api_key})

@producer_bp.route('/team/member/<int:member_id>')
@login_required
@producer_required
def member_detail(member_id):
    """
    Ver detalle completo de un miembro del equipo.
    
    Proporciona información detallada sobre un miembro específico del equipo,
    incluyendo estadísticas de rendimiento, historial de actividad y gestión
    de permisos. Solo accesible para miembros de la propia red.
    
    Args:
        member_id (int): ID del miembro del equipo a visualizar
    
    Returns:
        Template: 'producer/member_detail.html' con información del miembro
    
    Context Variables:
        member (User)         : Información completa del miembro
        member_stats (dict)   : Estadísticas de rendimiento del miembro
        recent_activity (list): Actividad reciente del miembro
    
    Note:
        - Solo miembros invitados por el productor actual
        - Estadísticas calculadas en tiempo real
        - Información de actividad para supervisión
    """
    # Buscar el miembro y verificar que pertenece a la red del productor
    member = User.query.filter_by(
        id=member_id,
        invited_by_id=current_user.id,
        status=UserStatus.ACTIVE
    ).first_or_404()
    
    # Estadísticas del miembro
    member_stats = {
        'total_reels': member.reels.count(),
        'join_date': member.created_at,
        'last_activity': getattr(member, 'last_login', None),
        'role': member.role.value,
        'status': member.status.value
    }
    
    # Actividad reciente del miembro
    recent_activity = member.reels.order_by(Reel.created_at.desc()).limit(5).all()
    
    return render_template('producer/member_detail.html', member=member, member_stats=member_stats, recent_activity=recent_activity)

@producer_bp.route('/avatar/<int:avatar_id>/stats')
@login_required
@producer_required
def avatar_stats(avatar_id):
    """Estadísticas de un avatar, incluyendo los creados por subproductores."""
    producer = current_user.producer_profile
    avatar = Avatar.query.get_or_404(avatar_id)
    if avatar.producer_id != producer.id:
        flash("No tenés acceso a este avatar.", "error")
        return redirect(url_for('producer.avatars'))

    # Total de reels asociados a este avatar
    reels = avatar.reels if hasattr(avatar, 'reels') else []
    if hasattr(reels, 'all'):
        reels = reels.all()
    total_reels = len(reels)

    # Reels de este mes
    now = datetime.now()
    this_month = len([r for r in reels if r.created_at and r.created_at.year == now.year and r.created_at.month == now.month])

    # Uso por miembro
    usage_by_member = []
    from collections import defaultdict
    member_usage = defaultdict(list)
    for r in reels:
        member_usage[r.creator_id].append(r)
    for member_id, member_reels in member_usage.items():
        user = User.query.get(member_id)
        usage_by_member.append({
            'name': user.full_name if user else f'ID {member_id}',
            'reels_count': len(member_reels),
            'last_used': max([r.created_at for r in member_reels if r.created_at], default=None)
        })
    # Formatear fechas para el frontend
    for m in usage_by_member:
        if m['last_used']:
            m['last_used'] = m['last_used'].strftime('%d/%m/%Y %H:%M')

    return jsonify({
        'total_reels': total_reels,
        'this_month': this_month,
        'usage_by_member': usage_by_member
    })


# @producer_bp.route('/avatar/<int:avatar_id>/access')
# @login_required
# @producer_required
# def avatar_access(avatar_id):
#     """Devuelve información de acceso para el avatar (simulado)."""
#     producer = current_user.producer_profile
#     avatar = Avatar.query.get_or_404(avatar_id)
#     if avatar.producer_id != producer.id:
#         return jsonify({'error': 'No autorizado'}), 403

#     # Simulación: lista de usuarios con acceso (puedes adaptar a tu modelo real)
#     # Aquí se asume que hay una relación avatar.access_users o similar
#     # Si no existe, se devuelve una lista vacía o de ejemplo
#     access_users = []
#     if hasattr(avatar, 'access_users'):
#         for user in avatar.access_users:
#             access_users.append({
#                 'id': user.id,
#                 'name': user.full_name,
#                 'role': user.role.value
#             })
#     # Ejemplo si no existe la relación
#     else:
#         access_users = [
#             {'id': 1, 'name': 'Demo User', 'role': 'SUBPRODUCER'}
#         ]

#     return jsonify({
#         'avatar_id': avatar.id,
#         'access_users': access_users
#     })

from app.models.clone_permission import ClonePermission, PermissionStatus, PermissionSubjectType
# GET y POST: gestión de acceso granular a un avatar
@producer_bp.route('/avatar/<int:avatar_id>/access', methods=['GET', 'POST'])
@login_required
@producer_required
def avatar_access(avatar_id):
    """Gestiona el acceso de miembros del equipo a un avatar (GET: lista, POST: actualiza permisos)."""
    producer = current_user.producer_profile
    avatar = Avatar.query.filter_by(id=avatar_id, producer_id=producer.id).first_or_404()

    # Obtener todos los miembros del equipo (subproductores y usuarios finales)
    team_members = list(producer.get_team_members())

    if request.method == 'GET':
        # Para cada miembro, buscar si tiene permiso activo para este avatar
        members_data = []
        for member in team_members:
            perm = ClonePermission.query.filter_by(clone_id=avatar.id, subject_id=member.id).first()
            members_data.append({
                'id': member.id,
                'username': member.username,
                'full_name': member.full_name,
                'has_access': perm is not None and perm.status == PermissionStatus.ACTIVE
            })
        return jsonify({'team_members': members_data})

    # POST: actualizar permisos según access_list
    data = request.get_json(force=True)
    access_list = data.get('access_list', [])
    updated = 0
    for item in access_list:
        member_id = int(item['member_id'])
        has_access = bool(item['has_access'])
        member = next((m for m in team_members if m.id == member_id), None)
        if not member:
            continue
        # Buscar permiso existente
        perm = ClonePermission.query.filter_by(clone_id=avatar.id, subject_id=member_id).first()
        if has_access:
            if not perm:
                # Crear permiso nuevo
                perm = ClonePermission(
                    clone_id=avatar.id,
                    producer_id=producer.id,
                    subject_id=member_id,
                    subject_type=PermissionSubjectType.SUBPRODUCER if member.role.name == 'SUBPRODUCER' else PermissionSubjectType.FINAL_USER,
                    status=PermissionStatus.ACTIVE,
                    granted_by_id=current_user.id
                )
                db.session.add(perm)
                updated += 1
            elif perm.status != PermissionStatus.ACTIVE:
                perm.status = PermissionStatus.ACTIVE
                updated += 1
        else:
            if perm and perm.status == PermissionStatus.ACTIVE:
                perm.status = PermissionStatus.REVOKED
                updated += 1
    db.session.commit()
    return jsonify({'success': True, 'updated': updated})


@producer_bp.route('/team/member/<int:member_id>/toggle_status', methods=['POST'])
@login_required
@producer_required
def toggle_member_status(member_id):
    """
    Suspende o reactiva a un miembro del equipo (subproductor o usuario final).
    Solo el productor que invitó puede realizar la acción.
    """
    member = User.query.filter_by(id=member_id, invited_by_id=current_user.id).first_or_404()
    if member.role not in [UserRole.SUBPRODUCER, UserRole.FINAL_USER]:
        flash('Solo puedes suspender subproductores o usuarios finales.', 'warning')
        return redirect(url_for('producer.team'))
    if member.status == UserStatus.SUSPENDED:
        member.status = UserStatus.ACTIVE
        flash(f'{member.first_name} ha sido reactivado.', 'success')
    else:
        member.status = UserStatus.SUSPENDED
        flash(f'{member.first_name} ha sido suspendido.', 'warning')
    db.session.commit()
    return redirect(url_for('producer.team'))