from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models.user import User, UserRole
from app.models.avatar import Avatar, AvatarStatus
from app.models.reel import Reel, ReelStatus
from app.models.commission import Commission

subproducer_bp = Blueprint('subproducer', __name__)

def subproducer_required(f):
    """Decorador para requerir permisos de subproductor"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_subproducer():
            flash('Acceso denegado. Permisos de subproductor requeridos.', 'error')
            return redirect(url_for('main.index'))
        return f(*args, **kwargs)
    return decorated_function

@subproducer_bp.route('/dashboard')
@login_required
@subproducer_required
def dashboard():
    """Dashboard del subproductor"""
    producer = current_user.get_producer()
    
    stats = {
        'total_avatars': current_user.created_avatars.count(),
        'approved_avatars': current_user.created_avatars.filter_by(status=AvatarStatus.APPROVED).count(),
        'pending_avatars': current_user.created_avatars.filter_by(status=AvatarStatus.PENDING).count(),
        'total_reels': current_user.reels.count(),
        'completed_reels': current_user.reels.filter_by(status=ReelStatus.COMPLETED).count(),
        'total_earnings': Commission.get_user_total_earnings(current_user.id, 'approved'),
        'pending_earnings': Commission.get_user_total_earnings(current_user.id, 'pending'),
        'producer_name': producer.user.full_name if producer else 'N/A'
    }
    
    recent_avatars = current_user.created_avatars.order_by(Avatar.created_at.desc()).limit(5).all()
    recent_reels = current_user.reels.order_by(Reel.created_at.desc()).limit(5).all()
    
    return render_template('subproducer/dashboard.html',
                         stats=stats,
                         recent_avatars=recent_avatars,
                         recent_reels=recent_reels)

@subproducer_bp.route('/avatars')
@login_required
@subproducer_required
def avatars():
    """Lista de avatars del subproductor"""
    page = request.args.get('page', 1, type=int)
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
    """Crear un nuevo avatar"""
    producer = current_user.get_producer()
    
    if not producer:
        flash('No tienes un productor asignado', 'error')
        return redirect(url_for('subproducer.dashboard'))
    
    if not producer.has_api_quota():
        flash('El productor ha alcanzado su límite mensual de API calls', 'error')
        return redirect(url_for('subproducer.avatars'))
    
    if request.method == 'POST':
        name = request.form.get('name')
        description = request.form.get('description')
        avatar_type = request.form.get('avatar_type')
        language = request.form.get('language', 'es')
        tags = request.form.get('tags', '')
        
        avatar = Avatar(
            producer_id=producer.id,
            created_by_id=current_user.id,
            name=name,
            description=description,
            avatar_type=avatar_type,
            language=language,
            status=AvatarStatus.PENDING
        )
        avatar.set_tags(tags.split(','))
        
        db.session.add(avatar)
        db.session.commit()
        
        flash('Avatar creado y enviado para aprobación', 'success')
        return redirect(url_for('subproducer.avatars'))
    
    return render_template('subproducer/create_avatar.html')

@subproducer_bp.route('/reels')
@login_required
@subproducer_required
def reels():
    """Lista de reels del subproductor"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status')
    
    query = current_user.reels
    
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
    """Crear un nuevo reel"""
    producer = current_user.get_producer()
    
    if not producer:
        flash('No tienes un productor asignado', 'error')
        return redirect(url_for('subproducer.dashboard'))
    
    # Obtener avatars disponibles
    available_avatars = producer.avatars.filter_by(status=AvatarStatus.APPROVED).all()
    
    if not available_avatars:
        flash('No hay avatars aprobados disponibles', 'warning')
        return redirect(url_for('subproducer.reels'))
    
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        script = request.form.get('script')
        avatar_id = request.form.get('avatar_id')
        resolution = request.form.get('resolution', '1080p')
        background_type = request.form.get('background_type', 'default')
        category = request.form.get('category')
        tags = request.form.get('tags', '')
        
        avatar = Avatar.query.get_or_404(avatar_id)
        
        # Verificar que el avatar pertenece al productor
        if avatar.producer_id != producer.id:
            flash('Avatar no válido', 'error')
            return render_template('subproducer/create_reel.html', avatars=available_avatars)
        
        reel = Reel(
            creator_id=current_user.id,
            avatar_id=avatar_id,
            title=title,
            description=description,
            script=script,
            resolution=resolution,
            background_type=background_type,
            category=category,
            status=ReelStatus.PENDING
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
    """Panel de ganancias del subproductor"""
    page = request.args.get('page', 1, type=int)
    
    commissions = current_user.commissions_earned.order_by(
        Commission.created_at.desc()
    ).paginate(page=page, per_page=20, error_out=False)
    
    earnings_stats = {
        'total_approved': Commission.get_user_total_earnings(current_user.id, 'approved'),
        'total_pending': Commission.get_user_total_earnings(current_user.id, 'pending'),
        'total_paid': Commission.get_user_total_earnings(current_user.id, 'paid'),
        'this_month': Commission.get_monthly_earnings(current_user.id, 
                                                    datetime.now().year, 
                                                    datetime.now().month)
    }
    
    return render_template('subproducer/earnings.html',
                         commissions=commissions,
                         stats=earnings_stats)

# Importar datetime
from datetime import datetime