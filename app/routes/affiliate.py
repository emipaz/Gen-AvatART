"""
Módulo de rutas de afiliado/usuario final para la aplicación Gen-AvatART.

Este módulo maneja todas las rutas específicas de los afiliados/usuarios finales del sistema,
proporcionando un panel de control de consumo que permite únicamente la creación
de reels pagando por cada generación. Es el consumidor final que paga por el servicio.

El módulo incluye:
    - Dashboard de consumo        : Estadísticas de uso y gastos
    - Visualización de avatares   : Solo avatares públicos del productor
    - Gestión de reels           : Creación pagada con avatares públicos
    - Panel de facturación       : Control de gastos y pagos realizados
    - Historial de consumo       : Registro de reels generados y pagados

Funcionalidades principales:
    - Sistema de permisos con decorador @affiliate_required
    - Acceso limitado solo a avatares públicos del productor
    - Creación de reels con cobro automático por generación
    - Control de gastos y facturación personal
    - Relación jerárquica estricta con el productor asignado
    - Estados de pago y procesamiento para cada reel

Características técnicas:
    - Decorador personalizado para verificación de permisos de afiliado
    - Integración con sistema de pagos para cobro por uso
    - Consultas filtradas para mostrar solo contenido propio
    - Acceso restringido a avatares públicos únicamente
    - Validación de métodos de pago antes de crear reels
    - Paginación automática para mejor rendimiento
    - Cálculo de costos usando el modelo Reel (campo cost)
    - Restricciones de acceso como consumidor final
"""

from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models.user import User, UserRole
from app.models.avatar import Avatar, AvatarStatus
from app.models.reel import Reel, ReelStatus
from app.models.commission import Commission, CommissionStatus
from app.utils.date_utils import get_current_month_range, get_last_month_range, filter_by_date_range
from datetime import datetime, date

affiliate_bp = Blueprint('affiliate', __name__)


def affiliate_required(f):
    """
    Decorador para requerir permisos de afiliado/usuario final.
    
    Este decorador verifica que el usuario actual tenga permisos
    de afiliado antes de permitir el acceso a rutas específicas.
    Los afiliados son los consumidores finales que pagan por el servicio.
    
    Args:
        f (function): Función de vista a proteger
    
    Returns:
        function: Función decorada con verificación de permisos
    
    Note:
        - Se ejecuta después de @login_required
        - Redirige a index si no tiene permisos de afiliado
        - Mensaje flash informativo para feedback al usuario
        - Nivel de consumidor final en la jerarquía del sistema
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_affiliate():
            flash('Acceso denegado. Permisos de afiliado requeridos.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@affiliate_bp.route('/dashboard')
@login_required
@affiliate_required
def dashboard():
    """
    Dashboard principal del afiliado con estadísticas de consumo.
    
    Proporciona una vista general del consumo y gastos del afiliado,
    enfocándose en reels generados, costos asociados y estadísticas
    de uso del servicio. Es un dashboard de consumidor final.
    
    Returns:
        Template: 'affiliate/dashboard.html' con estadísticas de consumo y actividad
    
    Context Variables:

            - stats (dict)                  : Estadísticas de consumo del afiliado
            - total_reels (int)             : Total de reels generados
            - completed_reels (int)         : Reels completados exitosamente
            - pending_reels (int)           : Reels pendientes de procesamiento
            - failed_reels (int)            : Reels que fallaron en la generación
            - total_spent (float)           : Total gastado en reels (suma de reel.cost)
            - this_month_spent (float)      : Gastos del mes actual
            - average_cost_per_reel (float) : Costo promedio por reel
            - producer_name (str)           : Nombre del productor proveedor
        
            - recent_reels (list)  : 5 reels más recientes generados
    
    Note:
        - Estadísticas se enfocan en consumo y gastos, no ganancias
        - Total_spent calculado desde reel.cost (campo existente)
        - Relación jerárquica con productor como proveedor de servicio
        - Información financiera desde perspectiva de consumidor
    """
    # Obtener productor proveedor del servicio
    producer = current_user.get_producer()
    
    # Calcular estadísticas de consumo usando campos existentes
    user_reels  = current_user.reels
    total_reels = user_reels.count()
    
    # Calcular total gastado sumando el campo cost de cada reel
    total_spent = sum([reel.cost or 0 for reel in user_reels.all()])
    
    # Calcular gastos del mes actual usando utilidades de fecha (compatible universalmente)
    month_start, month_end = get_current_month_range()
    
    # Filtrar usando la utilidad de rangos de fechas
    this_month_reels = filter_by_date_range(
        user_reels, 
        Reel.created_at, 
        month_start, 
        month_end
    ).all()
    this_month_spent = sum([reel.cost or 0 for reel in this_month_reels])
    
    stats = {
        'total_reels'           : total_reels,
        'completed_reels'       : user_reels.filter_by( status = ReelStatus.COMPLETED).count(),
        'pending_reels'         : user_reels.filter_by( status = ReelStatus.PENDING).count(),
        'failed_reels'          : user_reels.filter_by( status = ReelStatus.FAILED).count(),
        'total_spent'           : total_spent,
        'this_month_spent'      : this_month_spent,
        'average_cost_per_reel' : total_spent / total_reels if total_reels > 0 else 0,
        'producer_name'         : producer.user.full_name if producer else 'N/A'
    }
    
    # Obtener actividad reciente para vista rápida
    recent_reels = user_reels.order_by(Reel.created_at.desc()).limit(5).all()
    
    return render_template('affiliate/dashboard.html',
                         stats        = stats,
                         recent_reels = recent_reels)

@affiliate_bp.route('/reels')
@login_required
@affiliate_required
def reels():
    """
    Lista paginada de reels generados por el afiliado con información de costos.
    
    Proporciona una vista completa de todos los reels generados por
    el afiliado, incluyendo estado de procesamiento, costos asociados
    y información de pagos realizados.
    
    Query Parameters:
        page (int, opcional): Número de página para paginación (default: 1)
        status (str, opcional): Filtro por estado (pending, processing, completed, failed)
    
    Returns:
        Template: 'affiliate/reels.html' con lista paginada de reels y costos
    
    Context Variables:
        reels (Pagination): Objeto de paginación con reels filtrados
        total_spent (float): Total gastado en todos los reels mostrados
    
    Note:
        - Solo muestra reels generados por el afiliado actual
        - Incluye información de costos (reel.cost) por cada reel
        - Filtrado dinámico por estado de procesamiento
        - Paginación de 20 elementos por página para rendimiento
    """
    # Capturar parámetros de filtrado y paginación
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status')
    
    # Construir consulta base con reels propios únicamente
    query = current_user.reels
    
    # Aplicar filtro por estado si se especifica
    if status_filter:
        query = query.filter_by(status=ReelStatus(status_filter))
    
    # Ejecutar consulta con paginación
    reels = query.order_by(Reel.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    # Calcular total gastado en los reels mostrados
    total_spent = sum([reel.cost or 0 for reel in reels.items])
    
    return render_template('affiliate/reels.html', 
                         reels       = reels, 
                         total_spent = total_spent)

@affiliate_bp.route('/reels/create', methods=['GET', 'POST'])
@login_required
@affiliate_required
def create_reel():
    """
    Crear un nuevo reel con cobro automático por generación.
    
    Maneja la creación de reels por parte del afiliado con procesamiento
    de pago automático. Solo puede utilizar avatares públicos del productor
    y debe pagar por cada reel generado.
    
    Methods:
        GET  : Muestra el formulario de creación con precios y avatares disponibles
        POST : Procesa el pago y crea el reel para procesamiento
    
    Form Data (POST):
        
        title (str)            : Título del reel
        description (str)      : Descripción del contenido
        script (str)           : Texto que el avatar pronunciará
        avatar_id (int)        : ID del avatar público a utilizar
        resolution (str)       : Resolución del video (afecta el precio)
        background_type (str)  : Tipo de fondo
        category (str)         : Categoría del contenido
    
    Returns:
        GET : Template 'affiliate/create_reel.html' con avatares y precios
        POST: Redirección a lista de reels o template con errores de pago
    
    Context Variables (GET):
        avatars (list) : Lista de avatares públicos disponibles
        pricing (dict) : Estructura de precios por resolución y características
    
    Note:
        - COBRO AUTOMÁTICO: Se procesa pago antes de crear el reel
        - Solo avatares públicos del productor disponibles
        - Precio se calcula y se guarda en reel.cost
        - Reel se crea con estado PENDING hasta procesamiento
        - Genera comisiones para la jerarquía (productor, subproductor)
    """
    # Obtener productor proveedor y validar relación
    producer = current_user.get_producer()
    
    if not producer:
        flash('No tienes un productor asignado', 'error')
        return redirect(url_for('affiliate.dashboard'))
    
    # Obtener avatares públicos disponibles
    available_avatars = producer.avatars.filter_by(
        status        = AvatarStatus.ACTIVE,  # Solo avatares aprobados
        is_public     = True                  # RESTRICCIÓN: Solo públicos
    ).all()
    
    if not available_avatars:
        flash('No hay avatars públicos disponibles', 'warning')
        return redirect(url_for('affiliate.reels'))
    
    # Obtener estructura de precios (esto debería venir de configuración)
    pricing = {
        '720p'  : {'base_price': 5.0, 'premium_multiplier': 1.5},
        '1080p' : {'base_price': 10.0, 'premium_multiplier': 2.0},
        '4K'    : {'base_price': 20.0, 'premium_multiplier': 3.0}
    }
    
    if request.method == 'POST':
        # Capturar datos del formulario
        title           = request.form.get('title')
        description     = request.form.get('description')
        script          = request.form.get('script')
        avatar_id       = request.form.get('avatar_id')
        resolution      = request.form.get('resolution', '1080p')
        background_type = request.form.get('background_type', 'default')
        category        = request.form.get('category')
        
        # Validar avatar seleccionado
        avatar = Avatar.query.get_or_404(avatar_id)
        
        if not (avatar.is_public and avatar.producer_id == producer.id):
            flash('Avatar no válido', 'error')
            return render_template('affiliate/create_reel.html', 
                                 avatars=available_avatars, 
                                 pricing=pricing)
        
        # Calcular costo del reel basado en configuración
        base_price = pricing.get(resolution, {}).get('base_price', 10.0)
        multiplier = pricing.get(resolution, {}).get('premium_multiplier', 1.0) if avatar.is_premium else 1.0
        cost = base_price * (avatar.price_per_use or multiplier)
        
        try:
            # TODO: Aquí iría la integración real con sistema de pagos
            # Por ahora simulamos el pago exitoso
            payment_successful = True
            
            if payment_successful:
                #  Crear reel con el costo calculado
                reel = Reel(
                    creator_id      = current_user.id,
                    avatar_id       = avatar_id,
                    title           = title,
                    description     = description,
                    script          = script,
                    resolution      = resolution,
                    background_type = background_type,
                    category        = category,
                    cost            = cost,    # GUARDAR COSTO EN EL CAMPO EXISTENTE
                    status          = ReelStatus.PENDING  # Estado inicial para procesamiento
                )
                
                db.session.add(reel)
                db.session.flush()  # Para obtener el ID del reel
                
                # Crear comisiones para la jerarquía usando modelo existente
                # Comisión para el productor (ej: 70% del costo)
                producer_commission = Commission(
                    user_id         = producer.user_id,
                    reel_id         = reel.id,
                    commission_type = 'producer',
                    amount          = cost * 0.70,  # 70% para el productor
                    percentage      = 70.0,
                    status          = CommissionStatus.PENDING
                )
                db.session.add(producer_commission)
                
                # Si el avatar fue creado por un subproductor, crear su comisión
                if avatar.created_by_id != producer.user_id:
                    subproducer_commission = Commission(
                        user_id         = avatar.created_by_id,
                        reel_id         = reel.id,
                        commission_type = 'subproducer',
                        amount          = cost * 0.20,  # 20% para el subproductor
                        percentage      = 20.0,
                        status          = CommissionStatus.PENDING
                    )
                    db.session.add(subproducer_commission)
                
                # Comisión de plataforma (ej: 10% restante)
                platform_commission = Commission(
                    user_id          = 1,  # Usuario administrador de la plataforma
                    reel_id          = reel.id,
                    commission_type  = 'platform',
                    amount           = cost * 0.10,  # 10% para la plataforma
                    percentage       = 10.0,
                    status           = CommissionStatus.PENDING
                )
                db.session.add(platform_commission)
                
                db.session.commit()
                
                flash(f'Reel creado exitosamente. Costo: ${cost:.2f}', 'success')
                return redirect(url_for('affiliate.reels'))
            else:
                flash('Error al procesar el pago. Intenta de nuevo.', 'error')
                
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear el reel: {str(e)}', 'error')
    
    # Mostrar formulario con avatares y precios (GET)
    return render_template('affiliate/create_reel.html', 
                         avatars=available_avatars,
                         pricing=pricing)

@affiliate_bp.route('/avatars')
@login_required
@affiliate_required
def avatars():
    """
    Lista paginada de avatares públicos disponibles con precios.
    
    Proporciona una vista de catálogo de los avatares públicos
    que el afiliado puede utilizar para crear reels, incluyendo
    información de precios y características.
    
    Query Parameters:
        page (int, opcional): Número de página para paginación (default: 1)
    
    Returns:
        Template: 'affiliate/avatars.html' con catálogo de avatares y precios
    
    Context Variables:
        avatars (Pagination): Objeto de paginación con avatares públicos disponibles
        pricing (dict): Estructura de precios base para referencia
    
    Note:
        - CATÁLOGO DE PRODUCTOS: Vista de avatares como productos disponibles
        - Filtrado automático: Solo avatares públicos y aprobados
        - Incluye información de precios por uso
        - Paginación de 12 elementos por página (optimizado para grids)
    """
    # Obtener productor proveedor y validar relación
    producer = current_user.get_producer()
    
    if not producer:
        flash('No tienes un productor asignado', 'error')
        return redirect(url_for('affiliate.dashboard'))
    
    # Obtener parámetro de paginación
    page = request.args.get('page', 1, type=int)
    
    # Consulta con restricciones de afiliado: solo avatares públicos y aprobados
    avatars = producer.avatars.filter_by(
        status    = AvatarStatus.ACTIVE,  # Solo avatares aprobados
        is_public = True               # RESTRICCIÓN: Solo públicos
    ).order_by( Avatar.created_at.desc()).paginate(
        page = page, per_page = 12, error_out = False
    )
    
    # Obtener estructura de precios para mostrar en el catálogo
    pricing = {
        '720p' : {'base_price': 5.0,  'premium_multiplier': 1.5},
        '1080p': {'base_price': 10.0, 'premium_multiplier': 2.0},
        '4K'   : {'base_price': 20.0, 'premium_multiplier': 3.0}
    }
    
    return render_template('affiliate/avatars.html', 
                         avatars=avatars, 
                         pricing=pricing)

@affiliate_bp.route('/billing')
@login_required
@affiliate_required
def billing():
    """
    Panel de facturación y gastos del afiliado.
    
    Proporciona una vista completa de todos los gastos del afiliado,
    calculados desde los costos de los reels generados. Muestra
    historial de gastos y estadísticas de consumo.
    
    Query Parameters:
        page (int, opcional): Número de página para historial (default: 1)
    
    Returns:
        Template: 'affiliate/billing.html' con información de facturación
    
    Context Variables:
        
            - reels (Pagination) : Historial paginado de reels con costos
        
            - stats (dict)       : Estadísticas de gastos del afiliado
            
            - total_spent (float)         : Total gastado en el servicio
            - this_month_spent (float)    : Gastos del mes actual
            - last_month_spent (float)    : Gastos del mes anterior
            - total_reels_purchased (int) : Total de reels comprados
    
    Note:
        - PERSPECTIVA DE CONSUMIDOR: Se enfoca en gastos usando reel.cost
        - Historial de reels ordenado cronológicamente con costos
        - Estadísticas de consumo y gastos mensuales
        - Información útil para control de presupuesto personal
    """
    # Obtener parámetro de paginación
    page = request.args.get('page', 1, type=int)
    
    # Obtener historial de reels paginado (que representan los "gastos")
    reels = current_user.reels.order_by(
        Reel.created_at.desc()
    ).paginate(page = page, per_page = 20, error_out = False)
    
    # Calcular estadísticas de gastos usando utilidades de fecha (compatible universalmente)
    all_reels = current_user.reels.all()
    
    # Obtener rangos de fechas usando utilidades
    current_month_start, current_month_end = get_current_month_range()
    last_month_start, last_month_end = get_last_month_range()
    
    # Obtener reels por rango de fechas usando utilidades
    this_month_reels = filter_by_date_range(
        current_user.reels,
        Reel.created_at,
        current_month_start,
        current_month_end
    ).all()
    
    # Obtener reels del mes anterior
    last_month_reels = filter_by_date_range(
        current_user.reels,
        Reel.created_at,
        last_month_start,
        last_month_end
    ).all()
    
    billing_stats = {
        'total_spent'           : sum([reel.cost or 0 for reel in all_reels]),
        'this_month_spent'      : sum([reel.cost or 0 for reel in this_month_reels]),
        'last_month_spent'      : sum([reel.cost or 0 for reel in last_month_reels]),
        'total_reels_purchased' : len(all_reels)
    }
    
    return render_template('affiliate/billing.html',
                         reels=reels,
                         stats=billing_stats)

@affiliate_bp.route('/profile')
@login_required
@affiliate_required
def profile():
    """
    Perfil personal del afiliado con información de consumo.
    
    Proporciona una vista del perfil del afiliado desde la perspectiva
    de consumidor, incluyendo información personal, relación con el
    productor y estadísticas de uso del servicio.
    
    Returns:
        Template: 'affiliate/profile.html' con información del perfil
    
    Context Variables:
        profile (dict): Información completa del perfil del afiliado
            - user (User): Objeto usuario con información personal
            - producer (Producer): Productor proveedor del servicio
            - total_reels (int): Total de reels comprados/generados
            - total_spent (float): Total gastado en el servicio
            - join_date (datetime): Fecha de registro en el sistema
    
    Note:
        - PERSPECTIVA DE CONSUMIDOR: Enfoque en consumo y gastos
        - Información básica del usuario y relación con proveedor
        - Estadísticas de uso y gastos resumidas usando reel.cost
    """
    # Obtener productor proveedor del servicio
    producer = current_user.get_producer()
    
    # Calcular total gastado desde el campo cost de los reels
    total_spent = sum([reel.cost or 0 for reel in current_user.reels.all()])
    
    # Compilar información completa del perfil desde perspectiva de consumidor
    profile_info = {
        'user'        : current_user,
        'producer'    : producer,
        'total_reels' : current_user.reels.count(),
        'total_spent' : total_spent,
        'join_date'   : current_user.created_at
    }
    
    return render_template('affiliate/profile.html', profile=profile_info)