from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app import db
from app.models.user import User, UserRole, UserStatus
from app.models.producer import Producer
from app.models.avatar import Avatar, AvatarStatus
from app.models.reel import Reel, ReelStatus
from app.models.commission import Commission
from app.services.heygen_service import HeyGenService, HeyGenVideoProcessor

api_bp = Blueprint('api', __name__)

# Autenticación JWT
@api_bp.route('/auth/login', methods=['POST'])
def api_login():
    """Login para API con JWT"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    
    if not email or not password:
        return jsonify({'error': 'Email y password requeridos'}), 400
    
    user = User.query.filter_by(email=email).first()
    
    if user and user.check_password(password) and user.status == UserStatus.ACTIVE:
        access_token = create_access_token(identity=user.id)
        return jsonify({
            'access_token': access_token,
            'user': user.to_dict()
        })
    
    return jsonify({'error': 'Credenciales inválidas'}), 401

# Endpoints de Usuarios
@api_bp.route('/users/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """Obtener información del usuario actual"""
    user_id = get_jwt_identity()
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())

@api_bp.route('/users/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    """Obtener información de un usuario específico"""
    current_user_id = get_jwt_identity()
    current_user = User.query.get(current_user_id)
    
    # Solo admins pueden ver otros usuarios
    if not current_user.is_admin() and current_user_id != user_id:
        return jsonify({'error': 'Acceso denegado'}), 403
    
    user = User.query.get_or_404(user_id)
    return jsonify(user.to_dict())

# Endpoints de Avatars
@api_bp.route('/avatars', methods=['GET'])
@jwt_required()
def list_avatars():
    """Listar avatars disponibles"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status_filter = request.args.get('status')
    
    if user.is_admin():
        query = Avatar.query
    elif user.is_producer():
        query = user.producer_profile.avatars
    elif user.is_subproducer():
        query = user.created_avatars
    else:  # affiliate
        producer = user.get_producer()
        if producer:
            query = producer.avatars.filter_by(is_public=True, status=AvatarStatus.APPROVED)
        else:
            return jsonify({'avatars': [], 'total': 0})
    
    if status_filter:
        query = query.filter_by(status=AvatarStatus(status_filter))
    
    avatars = query.order_by(Avatar.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'avatars': [avatar.to_dict() for avatar in avatars.items],
        'total': avatars.total,
        'pages': avatars.pages,
        'current_page': page
    })

@api_bp.route('/avatars/<int:avatar_id>', methods=['GET'])
@jwt_required()
def get_avatar(avatar_id):
    """Obtener detalles de un avatar"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    avatar = Avatar.query.get_or_404(avatar_id)
    
    # Verificar permisos
    if not avatar.can_be_used_by(user) and not user.is_admin():
        return jsonify({'error': 'Acceso denegado'}), 403
    
    return jsonify(avatar.to_dict())

@api_bp.route('/avatars', methods=['POST'])
@jwt_required()
def create_avatar():
    """Crear un nuevo avatar"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user.can_create_avatars():
        return jsonify({'error': 'No tienes permisos para crear avatars'}), 403
    
    data = request.get_json()
    
    # Validar datos requeridos
    required_fields = ['name', 'description', 'avatar_type']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Campo {field} requerido'}), 400
    
    producer = user.get_producer()
    if not producer:
        return jsonify({'error': 'Productor no encontrado'}), 404
    
    if not producer.has_api_quota():
        return jsonify({'error': 'Límite de API alcanzado'}), 429
    
    avatar = Avatar(
        producer_id=producer.id,
        created_by_id=user.id,
        name=data['name'],
        description=data['description'],
        avatar_type=data['avatar_type'],
        language=data.get('language', 'es'),
        is_public=data.get('is_public', False),
        is_premium=data.get('is_premium', False),
        price_per_use=data.get('price_per_use', 0.0),
        status=AvatarStatus.PENDING if user.is_subproducer() else AvatarStatus.PROCESSING
    )
    
    if 'tags' in data:
        avatar.set_tags(data['tags'])
    
    db.session.add(avatar)
    db.session.commit()
    
    return jsonify(avatar.to_dict()), 201

# Endpoints de Reels
@api_bp.route('/reels', methods=['GET'])
@jwt_required()
def list_reels():
    """Listar reels"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status_filter = request.args.get('status')
    
    if user.is_admin():
        query = Reel.query
    elif user.is_producer():
        # Reels del productor y su red
        query = Reel.query.join(User).filter(
            db.or_(
                Reel.creator_id == user.id,
                User.invited_by_id == user.id
            )
        )
    else:
        query = user.reels
    
    if status_filter:
        query = query.filter_by(status=ReelStatus(status_filter))
    
    reels = query.order_by(Reel.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'reels': [reel.to_dict() for reel in reels.items],
        'total': reels.total,
        'pages': reels.pages,
        'current_page': page
    })

@api_bp.route('/reels', methods=['POST'])
@jwt_required()
def create_reel():
    """Crear un nuevo reel"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if not user.can_create_reels():
        return jsonify({'error': 'No tienes permisos para crear reels'}), 403
    
    data = request.get_json()
    
    # Validar datos requeridos
    required_fields = ['title', 'script', 'avatar_id']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Campo {field} requerido'}), 400
    
    avatar = Avatar.query.get_or_404(data['avatar_id'])
    
    # Verificar que el usuario puede usar este avatar
    if not avatar.can_be_used_by(user):
        return jsonify({'error': 'No tienes permisos para usar este avatar'}), 403
    
    reel = Reel(
        creator_id=user.id,
        avatar_id=data['avatar_id'],
        title=data['title'],
        description=data.get('description', ''),
        script=data['script'],
        resolution=data.get('resolution', '1080p'),
        background_type=data.get('background_type', 'default'),
        background_url=data.get('background_url'),
        category=data.get('category'),
        status=ReelStatus.PENDING if not user.is_producer() else ReelStatus.PROCESSING
    )
    
    if 'tags' in data:
        reel.set_tags(data['tags'])
    
    db.session.add(reel)
    db.session.commit()
    
    # Si es productor, procesar inmediatamente
    if user.is_producer():
        producer = user.producer_profile
        processor = HeyGenVideoProcessor(producer.heygen_api_key)
        processor.process_reel(reel)
    
    return jsonify(reel.to_dict()), 201

@api_bp.route('/reels/<int:reel_id>', methods=['GET'])
@jwt_required()
def get_reel(reel_id):
    """Obtener detalles de un reel"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    reel = Reel.query.get_or_404(reel_id)
    
    # Verificar permisos
    if not (user.is_admin() or 
            reel.creator_id == user.id or 
            (user.is_producer() and user.producer_profile and 
             reel.creator.get_producer() and 
             reel.creator.get_producer().id == user.producer_profile.id)):
        return jsonify({'error': 'Acceso denegado'}), 403
    
    return jsonify(reel.to_dict())

@api_bp.route('/reels/<int:reel_id>/approve', methods=['POST'])
@jwt_required()
def approve_reel(reel_id):
    """Aprobar un reel"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    reel = Reel.query.get_or_404(reel_id)
    
    # Solo productores y admins pueden aprobar
    if not (user.is_admin() or 
            (user.is_producer() and reel.creator.get_producer() and 
             reel.creator.get_producer().id == user.producer_profile.id)):
        return jsonify({'error': 'No tienes permisos para aprobar este reel'}), 403
    
    reel.approve(user)
    return jsonify({'message': 'Reel aprobado exitosamente'})

@api_bp.route('/reels/<int:reel_id>/process', methods=['POST'])
@jwt_required()
def process_reel(reel_id):
    """Procesar un reel con HeyGen"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    reel = Reel.query.get_or_404(reel_id)
    
    # Solo el productor puede procesar
    producer = reel.creator.get_producer()
    if not (user.is_admin() or 
            (user.is_producer() and user.producer_profile.id == producer.id)):
        return jsonify({'error': 'No tienes permisos para procesar este reel'}), 403
    
    if reel.status != ReelStatus.APPROVED:
        return jsonify({'error': 'El reel debe estar aprobado para procesarse'}), 400
    
    processor = HeyGenVideoProcessor(producer.heygen_api_key)
    success = processor.process_reel(reel)
    
    if success:
        return jsonify({'message': 'Procesamiento iniciado exitosamente'})
    else:
        return jsonify({'error': 'Error iniciando el procesamiento'}), 500

# Endpoints de Comisiones
@api_bp.route('/commissions', methods=['GET'])
@jwt_required()
def list_commissions():
    """Listar comisiones del usuario"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 20, type=int)
    status_filter = request.args.get('status')
    
    if user.is_admin():
        query = Commission.query
    else:
        query = user.commissions_earned
    
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    commissions = query.order_by(Commission.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'commissions': [commission.to_dict() for commission in commissions.items],
        'total': commissions.total,
        'pages': commissions.pages,
        'current_page': page
    })

# Endpoints de Estadísticas
@api_bp.route('/stats/overview', methods=['GET'])
@jwt_required()
def stats_overview():
    """Estadísticas generales del usuario"""
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    
    if user.is_admin():
        stats = {
            'users': User.query.count(),
            'producers': User.query.filter_by(role=UserRole.PRODUCER).count(),
            'reels': Reel.query.count(),
            'avatars': Avatar.query.count(),
            'commissions': Commission.query.count()
        }
    elif user.is_producer():
        producer = user.producer_profile
        stats = {
            'reels': user.reels.count(),
            'avatars': producer.avatars.count(),
            'subproducers': producer.current_subproducers_count,
            'affiliates': producer.current_affiliates_count,
            'earnings': Commission.get_user_total_earnings(user.id, 'approved'),
            'api_usage': producer.api_calls_this_month
        }
    else:
        stats = {
            'reels': user.reels.count(),
            'completed_reels': user.reels.filter_by(status=ReelStatus.COMPLETED).count(),
            'earnings': Commission.get_user_total_earnings(user.id, 'approved'),
            'pending_earnings': Commission.get_user_total_earnings(user.id, 'pending')
        }
    
    return jsonify(stats)

# Error handlers
@api_bp.errorhandler(404)
def api_not_found(error):
    return jsonify({'error': 'Recurso no encontrado'}), 404

@api_bp.errorhandler(500)
def api_internal_error(error):
    return jsonify({'error': 'Error interno del servidor'}), 500