from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models.user import User, UserRole, UserStatus
from app.models.producer import Producer
from app.models.avatar import Avatar, AvatarStatus
from app.models.reel import Reel, ReelStatus
from app.models.commission import Commission
from app.services.heygen_service import HeyGenService

producer_bp = Blueprint('producer', __name__)

def producer_required(f):
    """Decorador para requerir permisos de productor"""
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
    """Dashboard del productor"""
    producer = current_user.producer_profile
    
    # Estadísticas del productor
    stats = {
        'total_reels': current_user.reels.count(),
        'completed_reels': current_user.reels.filter_by(status=ReelStatus.COMPLETED).count(),
        'pending_reels': current_user.reels.filter_by(status=ReelStatus.PENDING).count(),
        'total_avatars': producer.avatars.count(),
        'approved_avatars': producer.avatars.filter_by(status=AvatarStatus.APPROVED).count(),
        'pending_avatars': producer.avatars.filter_by(status=AvatarStatus.PENDING).count(),
        'subproducers_count': producer.current_subproducers_count,
        'affiliates_count': producer.current_affiliates_count,
        'total_earnings': Commission.get_user_total_earnings(current_user.id, 'approved'),
        'pending_earnings': Commission.get_user_total_earnings(current_user.id, 'pending'),
        'api_calls_used': producer.api_calls_this_month,
        'api_calls_limit': producer.monthly_api_limit,
        'api_key_status': producer.api_key_status
    }
    
    # Actividad reciente
    recent_reels = current_user.reels.order_by(Reel.created_at.desc()).limit(5).all()
    recent_avatars = producer.avatars.order_by(Avatar.created_at.desc()).limit(5).all()
    
    # Elementos pendientes de aprobación
    pending_avatars = producer.avatars.filter_by(status=AvatarStatus.PENDING).all()
    pending_reels = Reel.query.join(User).filter(
        User.invited_by_id == current_user.id,
        Reel.status == ReelStatus.PENDING
    ).all()
    
    return render_template('producer/dashboard.html',
                         stats=stats,
                         recent_reels=recent_reels,
                         recent_avatars=recent_avatars,
                         pending_avatars=pending_avatars,
                         pending_reels=pending_reels)

@producer_bp.route('/avatars')
@login_required
@producer_required
def avatars():
    """Lista de avatars del productor"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status')
    
    query = current_user.producer_profile.avatars
    
    if status_filter:
        query = query.filter_by(status=AvatarStatus(status_filter))
    
    avatars = query.order_by(Avatar.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )
    
    return render_template('producer/avatars.html', avatars=avatars)

@producer_bp.route('/avatars/create', methods=['GET', 'POST'])
@login_required
@producer_required
def create_avatar():
    """Crear un nuevo avatar"""
    producer = current_user.producer_profile
    
    if not producer.has_api_quota():
        flash('Has alcanzado tu límite mensual de API calls', 'error')
        return redirect(url_for('producer.avatars'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        avatar_type = request.form.get('avatar_type')
        language = request.form.get('language', 'es')
        tags = request.form.get('tags', '')
        is_public = bool(request.form.get('is_public'))
        is_premium = bool(request.form.get('is_premium'))
        price_per_use = float(request.form.get('price_per_use', 0))
        
        # Crear avatar en la base de datos
        avatar = Avatar(
            producer_id=producer.id,
            created_by_id=current_user.id,
            name=name,
            description=description,
            avatar_type=avatar_type,
            language=language,
            is_public=is_public,
            is_premium=is_premium,
            price_per_use=price_per_use,
            status=AvatarStatus.PROCESSING
        )
        avatar.set_tags(tags.split(','))
        
        db.session.add(avatar)
        db.session.commit()
        
        # TODO: Integrar con HeyGen para crear el avatar
        # Por ahora, simplemente marcarlo como aprobado
        avatar.status = AvatarStatus.APPROVED
        avatar.heygen_avatar_id = f"heygen_{avatar.id}"
        db.session.commit()
        
        producer.increment_api_usage()
        
        flash('Avatar creado exitosamente', 'success')
        return redirect(url_for('producer.avatars'))
    
    return render_template('producer/create_avatar.html')

@producer_bp.route('/avatars/<int:avatar_id>/approve', methods=['POST'])
@login_required
@producer_required
def approve_avatar(avatar_id):
    """Aprobar un avatar creado por subproductor"""
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
    """Rechazar un avatar"""
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
    """Lista de reels del productor y su red"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status')
    creator_filter = request.args.get('creator')
    
    # Obtener reels del productor y su red
    query = Reel.query.join(User).filter(
        db.or_(
            Reel.creator_id == current_user.id,  # Reels del productor
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
        db.or_(
            User.id == current_user.id,
            User.invited_by_id == current_user.id
        )
    ).all()
    
    return render_template('producer/reels.html', reels=reels, creators=creators)

@producer_bp.route('/reels/<int:reel_id>/approve', methods=['POST'])
@login_required
@producer_required
def approve_reel(reel_id):
    """Aprobar un reel"""
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
    """Rechazar un reel"""
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
    """Gestión del equipo (subproductores y afiliados)"""
    subproducers = User.query.filter_by(
        invited_by_id=current_user.id,
        role=UserRole.SUBPRODUCER
    ).all()
    
    affiliates = User.query.filter_by(
        invited_by_id=current_user.id,
        role=UserRole.AFFILIATE
    ).all()
    
    producer = current_user.producer_profile
    
    return render_template('producer/team.html',
                         subproducers=subproducers,
                         affiliates=affiliates,
                         producer=producer)

@producer_bp.route('/team/invite', methods=['GET', 'POST'])
@login_required
@producer_required
def invite_member():
    """Invitar nuevo miembro al equipo"""
    producer = current_user.producer_profile
    
    if request.method == 'POST':
        role = request.form.get('role')
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        
        # Validar límites
        if role == 'subproducer' and not producer.can_add_subproducer():
            flash('Has alcanzado el límite máximo de subproductores', 'error')
            return render_template('producer/invite_member.html')
        
        if role == 'affiliate' and not producer.can_add_affiliate():
            flash('Has alcanzado el límite máximo de afiliados', 'error')
            return render_template('producer/invite_member.html')
        
        # Verificar si el usuario ya existe
        if User.query.filter_by(email=email).first():
            flash('Ya existe un usuario con este email', 'error')
            return render_template('producer/invite_member.html')
        
        # Crear usuario
        user = User(
            email=email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            role=UserRole(role),
            status=UserStatus.ACTIVE,
            invited_by_id=current_user.id
        )
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
    """Configuración del productor"""
    producer = current_user.producer_profile
    
    if request.method == 'POST':
        # Actualizar información del usuario
        current_user.first_name = request.form.get('first_name')
        current_user.last_name = request.form.get('last_name')
        current_user.phone = request.form.get('phone')
        
        # Actualizar información del productor
        producer.company_name = request.form.get('company_name')
        producer.business_type = request.form.get('business_type')
        producer.website = request.form.get('website')
        
        # Actualizar API key si se proporciona una nueva
        new_api_key = request.form.get('heygen_api_key')
        if new_api_key and new_api_key != producer.heygen_api_key:
            producer.heygen_api_key = new_api_key
            producer.api_key_status = 'pending'
            # Validar nueva API key
            producer.validate_api_key()
        
        db.session.commit()
        flash('Configuración actualizada exitosamente', 'success')
        return redirect(url_for('producer.settings'))
    
    return render_template('producer/settings.html', producer=producer)

@producer_bp.route('/earnings')
@login_required
@producer_required
def earnings():
    """Panel de ganancias y comisiones"""
    page = request.args.get('page', 1, type=int)
    
    # Comisiones del productor
    commissions = current_user.commissions_earned.order_by(
        Commission.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    
    # Estadísticas de ganancias
    earnings_stats = {
        'total_approved': Commission.get_user_total_earnings(current_user.id, 'approved'),
        'total_pending': Commission.get_user_total_earnings(current_user.id, 'pending'),
        'total_paid': Commission.get_user_total_earnings(current_user.id, 'paid'),
        'this_month': Commission.get_monthly_earnings(current_user.id, 
                                                    datetime.now().year, 
                                                    datetime.now().month)
    }
    
    return render_template('producer/earnings.html',
                         commissions=commissions,
                         stats=earnings_stats)

@producer_bp.route('/api/heygen-status')
@login_required
@producer_required
def api_heygen_status():
    """API para verificar el estado de HeyGen"""
    producer = current_user.producer_profile
    
    if not producer.heygen_api_key:
        return jsonify({'status': 'no_key', 'message': 'API key no configurada'})
    
    try:
        service = HeyGenService(producer.heygen_api_key)
        user_info = service.get_user_info()
        quota_info = service.get_quota_info()
        
        if user_info:
            return jsonify({
                'status': 'active',
                'user_info': user_info,
                'quota_info': quota_info,
                'api_calls_used': producer.api_calls_this_month,
                'api_calls_limit': producer.monthly_api_limit
            })
        else:
            return jsonify({'status': 'invalid', 'message': 'API key inválida'})
    
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)})

# Importar datetime para uso en earnings
from datetime import datetime