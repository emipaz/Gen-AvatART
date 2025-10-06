from flask import Blueprint, render_template, request, jsonify, redirect, url_for
from flask_login import login_required, current_user
from app import db
from app.models.user import User, UserRole
from app.models.reel import Reel, ReelStatus
from app.models.avatar import Avatar, AvatarStatus
from app.models.commission import Commission

main_bp = Blueprint('main', __name__)

@main_bp.route('/')
def index():
    """Página principal"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    # Estadísticas públicas
    stats = {
        'total_users': User.query.count(),
        'total_reels': Reel.query.filter_by(status=ReelStatus.COMPLETED).count(),
        'total_avatars': Avatar.query.filter_by(status=AvatarStatus.APPROVED).count(),
        'total_producers': User.query.filter_by(role=UserRole.PRODUCER).count()
    }
    
    return render_template('main/index.html', stats=stats)

@main_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard principal - redirige según el rol"""
    if current_user.is_admin():
        return redirect(url_for('admin.dashboard'))
    elif current_user.is_producer():
        return redirect(url_for('producer.dashboard'))
    elif current_user.is_subproducer():
        return redirect(url_for('subproducer.dashboard'))
    else:  # affiliate
        return redirect(url_for('affiliate.dashboard'))

@main_bp.route('/about')
def about():
    """Página de información"""
    return render_template('main/about.html')

@main_bp.route('/contact')
def contact():
    """Página de contacto"""
    return render_template('main/contact.html')

@main_bp.route('/pricing')
def pricing():
    """Página de precios"""
    return render_template('main/pricing.html')

@main_bp.route('/api/stats')
def api_stats():
    """API para obtener estadísticas generales"""
    stats = {
        'total_users': User.query.count(),
        'active_users': User.query.filter_by(status='active').count(),
        'total_reels': Reel.query.count(),
        'completed_reels': Reel.query.filter_by(status=ReelStatus.COMPLETED).count(),
        'total_avatars': Avatar.query.count(),
        'approved_avatars': Avatar.query.filter_by(status=AvatarStatus.APPROVED).count(),
        'total_producers': User.query.filter_by(role=UserRole.PRODUCER).count(),
        'total_commissions': Commission.query.count()
    }
    
    return jsonify(stats)

@main_bp.route('/api/user-stats')
@login_required
def api_user_stats():
    """API para obtener estadísticas del usuario actual"""
    user_stats = {}
    
    if current_user.is_producer():
        producer = current_user.producer_profile
        user_stats = {
            'total_reels': current_user.reels.count(),
            'completed_reels': current_user.reels.filter_by(status=ReelStatus.COMPLETED).count(),
            'total_avatars': producer.avatars.count() if producer else 0,
            'approved_avatars': producer.avatars.filter_by(status=AvatarStatus.APPROVED).count() if producer else 0,
            'subproducers_count': producer.current_subproducers_count if producer else 0,
            'affiliates_count': producer.current_affiliates_count if producer else 0,
            'total_earnings': Commission.get_user_total_earnings(current_user.id, 'approved'),
            'pending_earnings': Commission.get_user_total_earnings(current_user.id, 'pending'),
            'api_calls_remaining': (producer.monthly_api_limit - producer.api_calls_this_month) if producer else 0
        }
    elif current_user.is_subproducer():
        producer = current_user.get_producer()
        user_stats = {
            'total_reels': current_user.reels.count(),
            'completed_reels': current_user.reels.filter_by(status=ReelStatus.COMPLETED).count(),
            'total_avatars': current_user.created_avatars.count(),
            'approved_avatars': current_user.created_avatars.filter_by(status=AvatarStatus.APPROVED).count(),
            'total_earnings': Commission.get_user_total_earnings(current_user.id, 'approved'),
            'pending_earnings': Commission.get_user_total_earnings(current_user.id, 'pending'),
            'producer_name': producer.user.full_name if producer else 'N/A'
        }
    elif current_user.is_affiliate():
        producer = current_user.get_producer()
        user_stats = {
            'total_reels': current_user.reels.count(),
            'completed_reels': current_user.reels.filter_by(status=ReelStatus.COMPLETED).count(),
            'total_earnings': Commission.get_user_total_earnings(current_user.id, 'approved'),
            'pending_earnings': Commission.get_user_total_earnings(current_user.id, 'pending'),
            'producer_name': producer.user.full_name if producer else 'N/A'
        }
    else:  # admin
        user_stats = {
            'total_users': User.query.count(),
            'pending_users': User.query.filter_by(status='pending').count(),
            'total_producers': User.query.filter_by(role=UserRole.PRODUCER).count(),
            'total_reels': Reel.query.count(),
            'pending_approvals': Reel.query.filter_by(status=ReelStatus.PENDING).count(),
            'total_commissions': Commission.query.count(),
            'pending_commissions': Commission.query.filter_by(status='pending').count()
        }
    
    return jsonify(user_stats)

@main_bp.route('/api/recent-activity')
@login_required
def api_recent_activity():
    """API para obtener actividad reciente del usuario"""
    activities = []
    
    # Reels recientes del usuario
    recent_reels = current_user.reels.order_by(Reel.created_at.desc()).limit(5).all()
    for reel in recent_reels:
        activities.append({
            'type': 'reel_created',
            'title': f'Reel creado: {reel.title}',
            'status': reel.status.value,
            'timestamp': reel.created_at.isoformat(),
            'url': url_for('main.view_reel', id=reel.id)
        })
    
    # Comisiones recientes
    recent_commissions = current_user.commissions_earned.order_by(Commission.created_at.desc()).limit(5).all()
    for commission in recent_commissions:
        activities.append({
            'type': 'commission_earned',
            'title': f'Comisión ganada: ${commission.amount:.2f}',
            'status': commission.status.value,
            'timestamp': commission.created_at.isoformat(),
            'reel_title': commission.reel_title
        })
    
    # Ordenar por fecha
    activities.sort(key=lambda x: x['timestamp'], reverse=True)
    
    return jsonify(activities[:10])  # Últimas 10 actividades

@main_bp.route('/reel/<int:id>')
@login_required
def view_reel(id):
    """Ver detalles de un reel"""
    reel = Reel.query.get_or_404(id)
    
    # Verificar permisos
    if not (current_user.is_admin() or 
            reel.creator_id == current_user.id or 
            (current_user.is_producer() and current_user.producer_profile and 
             reel.creator.get_producer() and 
             reel.creator.get_producer().id == current_user.producer_profile.id)):
        return render_template('errors/403.html'), 403
    
    return render_template('main/view_reel.html', reel=reel)

@main_bp.route('/avatar/<int:id>')
@login_required
def view_avatar(id):
    """Ver detalles de un avatar"""
    avatar = Avatar.query.get_or_404(id)
    
    # Verificar permisos
    if not (current_user.is_admin() or 
            avatar.created_by_id == current_user.id or 
            (current_user.is_producer() and current_user.producer_profile and 
             avatar.producer_id == current_user.producer_profile.id)):
        return render_template('errors/403.html'), 403
    
    return render_template('main/view_avatar.html', avatar=avatar)