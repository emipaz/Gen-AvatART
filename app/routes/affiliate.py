from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_required, current_user
from functools import wraps
from app import db
from app.models.user import User, UserRole
from app.models.avatar import Avatar, AvatarStatus
from app.models.reel import Reel, ReelStatus
from app.models.commission import Commission
from datetime import datetime

affiliate_bp = Blueprint('affiliate', __name__)

def affiliate_required(f):
    """Decorador para requerir permisos de afiliado"""
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
    """Dashboard del afiliado"""
    producer = current_user.get_producer()
    
    stats = {
        'total_reels': current_user.reels.count(),
        'completed_reels': current_user.reels.filter_by(status=ReelStatus.COMPLETED).count(),
        'pending_reels': current_user.reels.filter_by(status=ReelStatus.PENDING).count(),
        'total_earnings': Commission.get_user_total_earnings(current_user.id, 'approved'),
        'pending_earnings': Commission.get_user_total_earnings(current_user.id, 'pending'),
        'producer_name': producer.user.full_name if producer else 'N/A'
    }
    
    recent_reels = current_user.reels.order_by(Reel.created_at.desc()).limit(5).all()
    
    return render_template('affiliate/dashboard.html',
                         stats=stats,
                         recent_reels=recent_reels)

@affiliate_bp.route('/reels')
@login_required
@affiliate_required
def reels():
    """Lista de reels del afiliado"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status')
    
    query = current_user.reels
    
    if status_filter:
        query = query.filter_by(status=ReelStatus(status_filter))
    
    reels = query.order_by(Reel.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('affiliate/reels.html', reels=reels)

@affiliate_bp.route('/reels/create', methods=['GET', 'POST'])
@login_required
@affiliate_required
def create_reel():
    """Crear un nuevo reel"""
    producer = current_user.get_producer()
    
    if not producer:
        flash('No tienes un productor asignado', 'error')
        return redirect(url_for('affiliate.dashboard'))
    
    # Obtener avatars públicos disponibles
    available_avatars = producer.avatars.filter_by(
        status=AvatarStatus.APPROVED,
        is_public=True
    ).all()
    
    if not available_avatars:
        flash('No hay avatars públicos disponibles', 'warning')
        return redirect(url_for('affiliate.reels'))
    
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
        
        # Verificar que el avatar es público y del productor correcto
        if not (avatar.is_public and avatar.producer_id == producer.id):
            flash('Avatar no válido', 'error')
            return render_template('affiliate/create_reel.html', avatars=available_avatars)
        
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
        return redirect(url_for('affiliate.reels'))
    
    return render_template('affiliate/create_reel.html', avatars=available_avatars)

@affiliate_bp.route('/avatars')
@login_required
@affiliate_required
def avatars():
    """Lista de avatars disponibles para el afiliado"""
    producer = current_user.get_producer()
    
    if not producer:
        flash('No tienes un productor asignado', 'error')
        return redirect(url_for('affiliate.dashboard'))
    
    page = request.args.get('page', 1, type=int)
    
    # Solo avatars públicos y aprobados
    avatars = producer.avatars.filter_by(
        status=AvatarStatus.APPROVED,
        is_public=True
    ).order_by(Avatar.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )
    
    return render_template('affiliate/avatars.html', avatars=avatars)

@affiliate_bp.route('/earnings')
@login_required
@affiliate_required
def earnings():
    """Panel de ganancias del afiliado"""
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
    
    return render_template('affiliate/earnings.html',
                         commissions=commissions,
                         stats=earnings_stats)

@affiliate_bp.route('/profile')
@login_required
@affiliate_required
def profile():
    """Perfil del afiliado"""
    producer = current_user.get_producer()
    
    profile_info = {
        'user': current_user,
        'producer': producer,
        'total_reels': current_user.reels.count(),
        'total_earnings': Commission.get_user_total_earnings(current_user.id, 'approved'),
        'join_date': current_user.created_at
    }
    
    return render_template('affiliate/profile.html', profile=profile_info)