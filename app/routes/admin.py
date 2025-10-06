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
    """Decorador para requerir permisos de administrador"""
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
    """Dashboard del administrador"""
    # Estadísticas generales
    stats = {
        'total_users': User.query.count(),
        'pending_users': User.query.filter_by(status=UserStatus.PENDING).count(),
        'active_users': User.query.filter_by(status=UserStatus.ACTIVE).count(),
        'total_producers': User.query.filter_by(role=UserRole.PRODUCER).count(),
        'total_subproducers': User.query.filter_by(role=UserRole.SUBPRODUCER).count(),
        'total_affiliates': User.query.filter_by(role=UserRole.AFFILIATE).count(),
        'total_reels': Reel.query.count(),
        'pending_reels': Reel.query.filter_by(status=ReelStatus.PENDING).count(),
        'completed_reels': Reel.query.filter_by(status=ReelStatus.COMPLETED).count(),
        'total_avatars': Avatar.query.count(),
        'pending_avatars': Avatar.query.filter_by(status=AvatarStatus.PENDING).count(),
        'approved_avatars': Avatar.query.filter_by(status=AvatarStatus.APPROVED).count(),
        'total_commissions': Commission.query.count(),
        'pending_commissions': Commission.query.filter_by(status=CommissionStatus.PENDING).count()
    }
    
    # Usuarios recientes
    recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
    
    # Reels recientes
    recent_reels = Reel.query.order_by(Reel.created_at.desc()).limit(5).all()
    
    # Elementos pendientes para el template
    pending_avatars = Avatar.query.filter_by(status=AvatarStatus.PENDING).limit(5).all()
    pending_reels = Reel.query.filter_by(status=ReelStatus.PENDING).limit(5).all()
    
    return render_template('admin/dashboard.html', 
                         stats=stats, 
                         recent_users=recent_users, 
                         recent_reels=recent_reels,
                         pending_avatars=pending_avatars,
                         pending_reels=pending_reels)

@admin_bp.route('/users')
@login_required
@admin_required
def users():
    """Lista de todos los usuarios"""
    page = request.args.get('page', 1, type=int)
    role_filter = request.args.get('role')
    status_filter = request.args.get('status')
    search = request.args.get('search', '')
    
    query = User.query
    
    # Filtros
    if role_filter:
        query = query.filter_by(role=UserRole(role_filter))
    if status_filter:
        query = query.filter_by(status=UserStatus(status_filter))
    if search:
        query = query.filter(
            db.or_(
                User.username.contains(search),
                User.email.contains(search),
                User.first_name.contains(search),
                User.last_name.contains(search)
            )
        )
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/users.html', users=users)

@admin_bp.route('/users/<int:user_id>')
@login_required
@admin_required
def user_detail(user_id):
    """Detalle de un usuario específico"""
    user = User.query.get_or_404(user_id)
    
    # Estadísticas del usuario
    user_stats = {
        'total_reels': user.reels.count(),
        'completed_reels': user.reels.filter_by(status=ReelStatus.COMPLETED).count(),
        'total_commissions': user.commissions_earned.count(),
        'total_earnings': sum([c.amount for c in user.commissions_earned.filter_by(status=CommissionStatus.APPROVED)]),
        'pending_earnings': sum([c.amount for c in user.commissions_earned.filter_by(status=CommissionStatus.PENDING)])
    }
    
    # Si es productor, obtener estadísticas adicionales
    if user.is_producer() and user.producer_profile:
        producer = user.producer_profile
        user_stats.update({
            'subproducers_count': producer.current_subproducers_count,
            'affiliates_count': producer.current_affiliates_count,
            'avatars_count': producer.avatars.count(),
            'api_calls_this_month': producer.api_calls_this_month,
            'monthly_api_limit': producer.monthly_api_limit
        })
    
    return render_template('admin/user_detail.html', user=user, stats=user_stats)

@admin_bp.route('/users/<int:user_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_user(user_id):
    """Aprobar un usuario"""
    user = User.query.get_or_404(user_id)
    user.status = UserStatus.ACTIVE
    db.session.commit()
    
    flash(f'Usuario {user.username} aprobado exitosamente', 'success')
    return redirect(url_for('admin.user_detail', user_id=user_id))

@admin_bp.route('/users/<int:user_id>/suspend', methods=['POST'])
@login_required
@admin_required
def suspend_user(user_id):
    """Suspender un usuario"""
    user = User.query.get_or_404(user_id)
    user.status = UserStatus.SUSPENDED
    db.session.commit()
    
    flash(f'Usuario {user.username} suspendido', 'warning')
    return redirect(url_for('admin.user_detail', user_id=user_id))

@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@login_required
@admin_required
def delete_user(user_id):
    """Eliminar un usuario"""
    user = User.query.get_or_404(user_id)
    username = user.username
    
    # No permitir eliminar otros administradores
    if user.is_admin():
        flash('No se puede eliminar un administrador', 'error')
        return redirect(url_for('admin.user_detail', user_id=user_id))
    
    db.session.delete(user)
    db.session.commit()
    
    flash(f'Usuario {username} eliminado', 'info')
    return redirect(url_for('admin.users'))

@admin_bp.route('/create-producer', methods=['GET', 'POST'])
@login_required
@admin_required
def create_producer():
    """Crear un nuevo productor"""
    if request.method == 'POST':
        # Datos del usuario
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')
        
        # Datos del productor
        heygen_api_key = request.form.get('heygen_api_key')
        company_name = request.form.get('company_name')
        business_type = request.form.get('business_type')
        website = request.form.get('website')
        max_subproducers = request.form.get('max_subproducers', 10, type=int)
        max_affiliates = request.form.get('max_affiliates', 100, type=int)
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
            email=email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role=UserRole.PRODUCER,
            status=UserStatus.ACTIVE
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.flush()  # Para obtener el ID del usuario
        
        # Crear perfil de productor
        producer = Producer(
            user_id=user.id,
            heygen_api_key=heygen_api_key,
            company_name=company_name,
            business_type=business_type,
            website=website,
            max_subproducers=max_subproducers,
            max_affiliates=max_affiliates,
            monthly_api_limit=monthly_api_limit
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
    """Lista de productores"""
    page = request.args.get('page', 1, type=int)
    
    producers = Producer.query.join(User).order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/producers.html', producers=producers)

@admin_bp.route('/reels')
@login_required
@admin_required
def reels():
    """Lista de todos los reels"""
    page = request.args.get('page', 1, type=int)
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
    """Lista de todas las comisiones"""
    page = request.args.get('page', 1, type=int)
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
    """Aprobar una comisión"""
    commission = Commission.query.get_or_404(commission_id)
    commission.approve()
    
    flash('Comisión aprobada exitosamente', 'success')
    return redirect(url_for('admin.commissions'))

@admin_bp.route('/commissions/<int:commission_id>/mark-paid', methods=['POST'])
@login_required
@admin_required
def mark_commission_paid(commission_id):
    """Marcar comisión como pagada"""
    commission = Commission.query.get_or_404(commission_id)
    payment_reference = request.form.get('payment_reference')
    payment_method = request.form.get('payment_method')
    
    commission.mark_as_paid(payment_reference, payment_method)
    
    flash('Comisión marcada como pagada', 'success')
    return redirect(url_for('admin.commissions'))

@admin_bp.route('/avatars')
@login_required
@admin_required
def avatars():
    """Lista de todos los avatars"""
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status')
    
    query = Avatar.query
    
    if status_filter:
        query = query.filter_by(status=AvatarStatus(status_filter))
    
    avatars = query.order_by(Avatar.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/avatars.html', avatars=avatars)

@admin_bp.route('/avatars/<int:avatar_id>')
@login_required
@admin_required
def avatar_detail(avatar_id):
    """Detalle de un avatar específico"""
    avatar = Avatar.query.get_or_404(avatar_id)
    return render_template('admin/avatar_detail.html', avatar=avatar)

@admin_bp.route('/avatars/<int:avatar_id>/approve', methods=['POST'])
@login_required
@admin_required
def approve_avatar(avatar_id):
    """Aprobar un avatar"""
    avatar = Avatar.query.get_or_404(avatar_id)
    avatar.approve(current_user)
    
    flash(f'Avatar {avatar.name} aprobado exitosamente', 'success')
    return redirect(url_for('admin.avatar_detail', avatar_id=avatar_id))

@admin_bp.route('/avatars/<int:avatar_id>/reject', methods=['POST'])
@login_required
@admin_required
def reject_avatar(avatar_id):
    """Rechazar un avatar"""
    avatar = Avatar.query.get_or_404(avatar_id)
    avatar.reject()
    
    flash(f'Avatar {avatar.name} rechazado', 'warning')
    return redirect(url_for('admin.avatar_detail', avatar_id=avatar_id))

@admin_bp.route('/api/stats')
@login_required
@admin_required
def api_stats():
    """API para estadísticas del admin"""
    stats = {
        'users': {
            'total': User.query.count(),
            'active': User.query.filter_by(status=UserStatus.ACTIVE).count(),
            'pending': User.query.filter_by(status=UserStatus.PENDING).count(),
            'suspended': User.query.filter_by(status=UserStatus.SUSPENDED).count()
        },
        'roles': {
            'admins': User.query.filter_by(role=UserRole.ADMIN).count(),
            'producers': User.query.filter_by(role=UserRole.PRODUCER).count(),
            'subproducers': User.query.filter_by(role=UserRole.SUBPRODUCER).count(),
            'affiliates': User.query.filter_by(role=UserRole.AFFILIATE).count()
        },
        'reels': {
            'total': Reel.query.count(),
            'pending': Reel.query.filter_by(status=ReelStatus.PENDING).count(),
            'processing': Reel.query.filter_by(status=ReelStatus.PROCESSING).count(),
            'completed': Reel.query.filter_by(status=ReelStatus.COMPLETED).count(),
            'failed': Reel.query.filter_by(status=ReelStatus.FAILED).count()
        },
        'avatars': {
            'total': Avatar.query.count(),
            'pending': Avatar.query.filter_by(status=AvatarStatus.PENDING).count(),
            'approved': Avatar.query.filter_by(status=AvatarStatus.APPROVED).count(),
            'rejected': Avatar.query.filter_by(status=AvatarStatus.REJECTED).count()
        },
        'commissions': {
            'total': Commission.query.count(),
            'pending': Commission.query.filter_by(status=CommissionStatus.PENDING).count(),
            'approved': Commission.query.filter_by(status=CommissionStatus.APPROVED).count(),
            'paid': Commission.query.filter_by(status=CommissionStatus.PAID).count(),
            'total_amount': sum([c.amount for c in Commission.query.all()])
        }
    }
    
    return jsonify(stats)