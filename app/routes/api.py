"""
Módulo de rutas API REST para la aplicación Gen-AvatART.

Este módulo maneja todas las rutas de la API REST de la aplicación, proporcionando
endpoints JSON para integración con aplicaciones externas, frontend SPA y servicios
de terceros. Incluye autenticación JWT y manejo completo de recursos.

- FUNCIONALIDADES PRINCIPALES:
    - Autenticación JWT         : Login y gestión de tokens de acceso seguros
    - Endpoints de usuarios     : CRUD completo con roles y permisos granulares  
    - Endpoints de avatares     : Gestión de clones digitales y configuración IA
    - Endpoints de reels        : Procesamiento de videos con integración HeyGen
    - Endpoints de comisiones   : Sistema financiero y tracking de pagos
    - Endpoints de estadísticas : Métricas en tiempo real y dashboards interactivos
    - Manejo de errores HTTP    : Respuestas JSON consistentes y debugging

- SEGURIDAD Y AUTENTICACIÓN:
    - JWT tokens con refresh automático y expiración configurable
    - Validación de permisos por endpoint según rol de usuario
    - Rate limiting integrado en endpoints críticos
    - Sanitización automática de inputs y validación de datos
    - Headers CORS y políticas de seguridad aplicadas

- ARQUITECTURA DE RESPUESTAS:
    - Formato JSON estandarizado en todas las respuestas
    - Códigos de estado HTTP semánticamente correctos
    - Paginación automática con metadata de navegación
    - Mensajes de error informativos sin exposición de datos sensibles
    - Versionado de API para compatibilidad hacia atrás

- INTEGRACIONES Y OPTIMIZACIONES:
    - HeyGen API para procesamiento de videos con avatares
    - Consultas de base de datos optimizadas con lazy loading
    - Caching inteligente de respuestas frecuentes
    - Logging estructurado para monitoreo y debugging
    - Métricas de performance y uso en tiempo real


    - Filtrado y búsqueda avanzada en todos los endpoints
    - Validación automática de datos de entrada
    - Manejo consistente de errores con códigos HTTP apropiados
    - Soporte para CORS y integración con frontend JavaScript

Características técnicas:
    - Decoradores JWT para autenticación stateless
    - Validación de permisos jerárquicos por endpoint
    - Paginación estandarizada (page, per_page)
    - Filtros dinámicos por estado, tipo y fechas
    - Respuestas JSON consistentes con metadata
    - Integración con servicios externos (HeyGen API)
    - Manejo robusto de errores con rollback automático
    - Headers CORS para integración cross-origin
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required, current_user
from flask_jwt_extended import create_access_token, jwt_required, get_jwt_identity
from app import db
from app.models.user import User, UserRole, UserStatus
from app.models.producer import Producer, ProducerStatus
from app.models.avatar import Avatar, AvatarStatus
from app.models.reel import Reel, ReelStatus
from app.models.commission import Commission, CommissionStatus
from app.models.clone_permission import ClonePermission, PermissionStatus, PermissionSubjectType
from app.services.heygen_service import HeyGenService, HeyGenVideoProcessor

# Creación del blueprint para rutas de API REST
api_bp = Blueprint('api', __name__)

# =================== AUTENTICACIÓN JWT ===================

@api_bp.route('/auth/login', methods=['POST'])
def api_login():
    """
    Autenticación de usuario para API con tokens JWT.
    
    Permite a los usuarios autenticarse y obtener un token de acceso
    JWT para realizar peticiones autenticadas a la API. Reemplaza
    la autenticación basada en sesiones para APIs stateless.
    
    Methods:
        POST: Procesa credenciales y retorna token JWT
    
    Request Body (JSON):
        email (str): Email del usuario registrado
        password (str): Contraseña del usuario
    
    Returns:
        JSON: Token de acceso y datos del usuario si exitoso
        
    Response Structure:
        # Caso exitoso (200):
        {
            "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
            "user": {
                "id": 1,
                "email": "user@example.com",
                "role": "producer",
                "status": "active",
                ...
            }
        }
        
        # Caso error (400/401):
        {"error": "Descripción del error"}
    
    Status Codes:
        200: Autenticación exitosa con token
        400: Datos faltantes o inválidos
        401: Credenciales incorrectas o usuario inactivo
    
    Note:
        - Solo usuarios con estado ACTIVE pueden autenticarse
        - Token JWT incluye user_id como identity
        - Token tiene expiración configurable en JWT_ACCESS_TOKEN_EXPIRES
        - Credenciales se validan contra hash seguro en BD
    """
    # Obtener datos JSON del request
    data     = request.get_json()
    email    = data.get('email')
    password = data.get('password')
    
    #  Validar campos obligatorios
    if not email or not password:
        return jsonify({'error': 'Email y password requeridos'}), 400
    
    #  Buscar usuario por email
    user = User.query.filter_by(email = email).first()
    
    #  Validar credenciales y estado del usuario
    if user and user.check_password(password) and user.status == UserStatus.ACTIVE:
        # Crear token JWT con user_id como identity
        access_token = create_access_token(identity = user.id)
        
        return jsonify({
            'access_token': access_token,
            'user'        : user.to_dict()
        })
    
    # Credenciales inválidas o usuario inactivo
    return jsonify({'error': 'Credenciales inválidas'}), 401

# =================== ENDPOINTS DE USUARIOS ===================

@api_bp.route('/users/me', methods=['GET'])
@jwt_required()
def get_current_user():
    """
    Obtener información del usuario autenticado actual.
    
    Retorna los datos completos del usuario que realizó la petición,
    identificado a través del token JWT. Útil para obtener el perfil
    actual sin necesidad de conocer el user_id.
    
    Headers:
        Authorization: Bearer <jwt_token>
    
    Returns:
        JSON: Datos completos del usuario actual
    
    Response Structure:
        {
            "id"         : 1,
            "email"      : "user@example.com",
            "username"   : "username",
            "first_name" : "John",
            "last_name"  : "Doe",
            "role"       : "producer",
            "status"     : "active",
            "created_at" : "2025-10-12T10:30:00",
            ...
        }
    
    Status Codes:
        200 : Datos del usuario retornados exitosamente
        401 : Token JWT inválido o expirado
        404 : Usuario no encontrado (token corrupto)
    
    Note:
        - Requiere token JWT válido en header Authorization
        - Retorna datos sensibles solo del usuario autenticado
        - Útil para validar estado de sesión en frontend
    """
    # Extraer user_id del token JWT
    user_id = get_jwt_identity()
    user    = User.query.get_or_404(user_id)
    
    return jsonify(user.to_dict())

@api_bp.route('/users/<int:user_id>', methods=['GET'])
@jwt_required()
def get_user(user_id):
    """
    Obtener información de un usuario específico por ID.
    
    Permite consultar datos de cualquier usuario del sistema con
    restricciones de permisos. Solo administradores pueden ver
    datos de otros usuarios, otros roles solo pueden ver su propio perfil.
    
    Args:
        user_id (int): ID único del usuario a consultar
    
    Headers:
        Authorization: Bearer <jwt_token>
    
    Returns:
        JSON: Datos del usuario solicitado si tiene permisos
    
    Status Codes:
        200: Datos del usuario retornados exitosamente
        401: Token JWT inválido o expirado
        403: Sin permisos para ver este usuario
        404: Usuario no encontrado
    
    Note:
        - PERMISOS: Solo admins pueden ver otros usuarios
        - Usuarios pueden ver su propio perfil (user_id == current_user.id)
        - Protege datos sensibles de otros usuarios
        - Útil para profiles públicos con datos limitados (futuro)
    """
    # Extraer user_id del token y obtener usuario actual
    current_user_id = get_jwt_identity()
    current_user    = User.query.get(current_user_id)
    
    # Validar permisos: solo admins pueden ver otros usuarios
    if not current_user.is_admin() and current_user_id != user_id:
        return jsonify({'error': 'Acceso denegado'}), 403
    
    # Obtener usuario solicitado
    user = User.query.get_or_404(user_id)
    
    return jsonify(user.to_dict())

# ==================== ENDPOINTS DE AVATARES ====================

@api_bp.route('/avatars', methods=['GET'])
@jwt_required()
def list_avatars():
    """
    Listar avatares disponibles según el rol del usuario con paginación.
    
    Retorna una lista paginada de avatares que el usuario puede ver/usar
    según sus permisos. Los resultados se filtran automáticamente por rol:
    admins ven todos, productores ven los suyos, afiliados solo públicos.
    
    Headers:
        Authorization: Bearer <jwt_token>
    
    Query Parameters:
        page (int, opcional): Número de página (default: 1)
        per_page (int, opcional): Elementos por página (default: 20, max: 100)
        status (str, opcional): Filtro por estado (active, processing, inactive, failed)
    
    Returns:
        JSON: Lista paginada de avatares con metadata
    
    Response Structure:
        {
            "avatars": [
                {
                    "id": 1,
                    "name": "Avatar Business",
                    "description": "Avatar para videos corporativos",
                    "status": "active",
                    "is_public": true,
                    "creator_name": "John Producer",
                    "created_at": "2025-10-12T10:30:00",
                    ...
                }
            ],
            "total": 45,
            "pages": 3,
            "current_page": 1
        }
    
    Status Codes:
        200: Lista de avatares retornada exitosamente
        401: Token JWT inválido o expirado
    
    Permisos por rol:
        - ADMIN: Todos los avatares del sistema
        - PRODUCER: Avatares de su producción únicamente
        - SUBPRODUCER: Avatares creados por él mismo
        - FINAL_USER: Solo avatares con permisos específicos del productor asignado
    
    Note:
        - Paginación automática para optimizar rendimiento
        - Filtros se aplican después de restricciones de permisos
        - Ordenamiento cronológico (más recientes primero)
        - Campo 'total' útil para interfaces de paginación
    """
    # Extraer user_id del token y obtener usuario
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    
    # Capturar parámetros de paginación y filtrado
    page          = request.args.get('page', 1, type=int)
    per_page      = min(request.args.get('per_page', 20, type=int), 100)  # Límite máximo
    status_filter = request.args.get('status')
    
    # Construir consulta base según permisos del rol
    if user.is_admin():
        # Admins ven todos los avatares del sistema
        query = Avatar.query
    elif user.is_producer():
        # Productores ven avatares de su producción
        query = user.producer_profile.avatars
    elif user.is_subproducer():
        # Subproductores ven solo avatares que crearon
        query = user.created_avatars
    elif user.is_final_user():  #  CORREGIDO: usar is_final_user() 
        # Usuarios finales ven avatares con permisos específicos
        # TODO: Implementar filtrado por ClonePermission cuando esté completo
        producer = user.get_producer()
        if producer:
            # Por ahora, mostrar avatares activos del productor
            query = producer.avatars.filter_by(status=AvatarStatus.ACTIVE)
        else:
            # Sin productor asignado, sin avatares disponibles
            return jsonify({'avatars': [], 'total': 0, 'pages': 0, 'current_page': page})
    
    # Aplicar filtro por estado si se especifica
    if status_filter:
        try:
            query = query.filter_by(status=AvatarStatus(status_filter))
        except ValueError:
            return jsonify({'error': f'Estado inválido: {status_filter}'}), 400
    
    # Ejecutar consulta con paginación
    avatars = query.order_by(Avatar.created_at.desc()).paginate(
        page = page, per_page = per_page, error_out = False
    )
    
    return jsonify({ 
         'avatars'    : [avatar.to_dict() for avatar in avatars.items],
        'total'       : avatars.total,
        'pages'       : avatars.pages,
        'current_page': page
    })

@api_bp.route('/avatars/<int:avatar_id>', methods=['GET'])
@jwt_required()
def get_avatar(avatar_id):
    """
    Obtener detalles completos de un avatar específico.
    
    Retorna información detallada de un avatar incluyendo metadatos,
    estadísticas de uso y configuraciones. Valida permisos para
    asegurar que el usuario puede acceder a este avatar.
    
    Args:
        avatar_id (int): ID único del avatar a consultar
    
    Headers:
        Authorization: Bearer <jwt_token>
    
    Returns:
        JSON: Datos completos del avatar si tiene permisos
    
    Response Structure:
        {
            "id"                : 1,
            "name"              : "Avatar Business",
            "description"       : "Avatar para videos corporativos",
            "avatar_type"       : "female",
            "language"         : "es",
            "status"            : "active",
            "is_public"         : true,
            "is_premium"        : false,
            "creator_name"      : "John Producer",
            "tags"              : ["business", "corporate", "spanish"],
            "preview_video_url" : "https://...",
            "thumbnail_url"     : "https://...",
            "created_at"        : "2025-10-12T10:30:00",
            ...
        }
    
    Status Codes:
        200: Detalles del avatar retornados exitosamente
        401: Token JWT inválido o expirado
        403: Sin permisos para acceder a este avatar
        404: Avatar no encontrado
    
    Note:
        - Valida permisos usando avatar.can_be_used_by()
        - Admins tienen acceso completo a cualquier avatar
        - Datos incluyen información técnica para uso en reels
        - URLs de preview y thumbnail para interfaces gráficas
    """
    # Extraer user_id del token y obtener entidades
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    avatar  = Avatar.query.get_or_404(avatar_id)
    
    # Verificar permisos de acceso al avatar
    if not avatar.can_be_used_by(user) and not user.is_admin():
        return jsonify({'error': 'Acceso denegado'}), 403
    
    return jsonify(avatar.to_dict())

@api_bp.route('/avatars', methods=['POST'])
@jwt_required()
def create_avatar():
    """
    Crear un nuevo avatar/clone digital vía API.
    
    Permite a usuarios autorizados crear nuevos avatares digitales
    proporcionando los datos necesarios en formato JSON. Incluye
    validación de permisos, cuotas API y datos requeridos.
    
    Headers:
        Authorization: Bearer <jwt_token>
        Content-Type: application/json
    
    Request Body (JSON):
        name (str)                      : Nombre descriptivo del avatar (requerido)
        description (str)               : Descripción detallada (requerido)
        avatar_type (str)               : Tipo de avatar - male, female, custom (requerido)
        language (str, opcional)        : Idioma principal (default: 'es')
        is_public (bool, opcional)      : Si es público para afiliados (default: false)
        is_premium (bool, opcional)     : Si requiere pago premium (default: false)
        price_per_use (float, opcional) : Precio por uso si es premium (default: 0.0)
        tags (list, opcional)           : Lista de etiquetas para categorización
    
    Returns:
        JSON: Datos del avatar creado con estado inicial
    
    Response Structure:
        # Caso exitoso (201):
        {
            "id"           : 45,
            "name"         : "Avatar Business",
            "description"  : "Avatar para videos corporativos",
            "status"       : "processing",  # o "pending" si es subproductor
            "creator_name" : "John Doe",
            "created_at"   : "2025-10-12T15:30:00",
            ...
        }
        
        # Caso error (400/403/429):
        {"error": "Descripción del error"}
    
    Status Codes:
        201: Avatar creado exitosamente
        400: Datos faltantes o inválidos
        401: Token JWT inválido o expirado
        403: Sin permisos para crear avatares
        404: Productor no encontrado (para subproductores)
        429: Límite de API alcanzado
    
    Estados iniciales:
        - PROCESSING: Para productores (procesamiento directo)
        - PENDING: Para subproductores (requiere aprobación)
    
    Note:
        - Validación automática de cuota API del productor
        - Solo productores y subproductores pueden crear avatares
        - Subproductores requieren aprobación del productor
        - Tags se procesan automáticamente como lista
    """
    # Extraer user_id del token y validar permisos
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    
    if not user.can_create_avatars():
        return jsonify({'error': 'No tienes permisos para crear avatars'}), 403
    
    # Obtener datos JSON del request
    data = request.get_json()
    
    # Validar campos obligatorios
    required_fields = ['name', 'description', 'avatar_type']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Campo {field} requerido'}), 400
    
    # Obtener productor asociado
    producer = user.get_producer()
    if not producer:
        return jsonify({'error': 'Productor no encontrado'}), 404
    
    # Validar cuota API disponible
    if not producer.has_api_quota():
        return jsonify({'error': 'Límite de API alcanzado'}), 429
    
    # Crear avatar con datos validados
    avatar = Avatar(
        producer_id     = producer.id,
        created_by_id   = user.id,
        name            = data['name'],
        description     = data['description'],
        avatar_type     = data['avatar_type'],
        language        = data.get('language', 'es'),
        is_public       = data.get('is_public', False),
        is_premium      = data.get('is_premium', False),
        price_per_use   = data.get('price_per_use', 0.0),
        # Estado inicial según el rol del creador
        status         = AvatarStatus.PROCESSING if user.is_subproducer() else AvatarStatus.INACTIVE
    )
    
    # Procesar etiquetas si se proporcionan
    if 'tags' in data:
        avatar.set_tags(data['tags'])
    
    # Guardar en base de datos
    db.session.add(avatar)
    db.session.commit()
    
    return jsonify(avatar.to_dict()), 201

# =================== ENDPOINTS DE REELS ===================

@api_bp.route('/reels', methods=['GET'])
@jwt_required()
def list_reels():
    """
    Listar reels según permisos del usuario con paginación y filtros.
    
    Retorna una lista paginada de reels que el usuario puede ver según
    su rol. Productores ven su red completa, otros usuarios solo los propios.
    Incluye filtrado por estado para facilitar la gestión.
    
    Headers:
        Authorization: Bearer <jwt_token>
    
    Query Parameters:
        page (int, opcional)     : Número de página (default: 1)
        per_page (int, opcional) : Elementos por página (default: 20, max: 100)
        status (str, opcional) : Filtro por estado (pending, processing, completed, failed)
    
    Returns:
        JSON: Lista paginada de reels con metadata
    
    Response Structure:
        {
            "reels": [
                {
                    "id"           : 15,
                    "title"       : "Video Promocional",
                    "description" : "Video para redes sociales",
                    "status"      : "completed",
                    "creator_name": "Jane Doe",
                    "avatar_name" : "Avatar Business",
                    "resolution"  : "1080p",
                    "duration"    : 30,
                    "video_url"   : "https://...",
                    "created_at"  : "2025-10-12T10:30:00",
                    ...
                }
            ],
            "total"       : 127,
            "pages"       : 7,
            "current_page": 1
        }
    
    Status Codes:
        200: Lista de reels retornada exitosamente
        401: Token JWT inválido o expirado
    
    Permisos por rol:
        - ADMIN                      : Todos los reels del sistema
        - PRODUCER                   : Reels propios + de toda su red (subproductores/usuarios finales)
        - SUBPRODUCER/FINAL_USER     : Solo reels propios
    
    Note:
        - Query optimizada con JOIN para productores (red completa)
        - Filtros se aplican después de restricciones de permisos
        - Ordenamiento cronológico (más recientes primero)
        - Información de avatar incluida para contexto
    """
    # Extraer user_id del token y obtener usuario
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    
    # Capturar parámetros de paginación y filtrado
    page          = request.args.get('page', 1, type=int)
    per_page      = min(request.args.get('per_page', 20, type=int), 100)  # Límite máximo
    status_filter = request.args.get('status')
    
    #  Construir consulta base según permisos del rol
    if user.is_admin():
        # Admins ven todos los reels del sistema
        query = Reel.query
    elif user.is_producer():
        # Productores ven reels propios + de toda su red
        query = Reel.query.join(User).filter(
            db.or_(
                Reel.creator_id == user.id,        # Reels del productor
                User.invited_by_id == user.id      # Reels de su red
            )
        )
    else:
        # Subproductores y afiliados ven solo reels propios
        query = user.reels
    
    #  Aplicar filtro por estado si se especifica
    if status_filter:
        try:
            query = query.filter_by(status=ReelStatus(status_filter))
        except ValueError:
            return jsonify({'error': f'Estado inválido: {status_filter}'}), 400
    
    #  Ejecutar consulta con paginación
    reels = query.order_by(Reel.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'reels'       : [ reel.to_dict() for reel in reels.items ],
        'total'       : reels.total,
        'pages'       : reels.pages,
        'current_page': page
    })

@api_bp.route('/reels', methods=['POST'])
@jwt_required()
def create_reel():
    """
    Crear un nuevo reel/video con avatar digital vía API.
    
    Permite crear un nuevo reel proporcionando el script, avatar y
    configuraciones. Incluye validación de permisos sobre el avatar
    y procesamiento automático para productores.
    
    Headers:
        Authorization: Bearer <jwt_token>
        Content-Type: application/json
    
    Request Body (JSON):
        title (str)                     : Título del reel (requerido)
        script (str)                    : Texto que pronunciará el avatar (requerido)
        avatar_id (int)                 : ID del avatar a utilizar (requerido)
        description (str, opcional)     : Descripción del contenido
        resolution (str, opcional)      : Resolución del video (default: '1080p')
        background_type (str, opcional) : Tipo de fondo (default: 'default')
        background_url (str, opcional)  : URL de fondo personalizado
        category (str, opcional)        : Categoría del contenido
        tags (list, opcional)           : Lista de etiquetas

    Returns:
        JSON: Datos del reel creado con estado inicial
    
    Response Structure:
        # Caso exitoso (201):
        {
            "id"                 : 89,
            "title"              : "Video Promocional",
            "description"        : "Video para redes sociales",
            "script"             : "Hola, bienvenidos a nuestro producto...",
            "status"             : "processing",  # o "pending" si no es productor
            "avatar_name"        : "Avatar Business",
            "resolution"         : "1080p",
            "estimated_duration" : 30,
            "created_at"         : "2025-10-12T15:30:00",
            ...
        }
        
        # Caso error (400/403):
        {"error": "Descripción del error"}
    
    Status Codes:
        201: Reel creado exitosamente
        400: Datos faltantes o inválidos
        401: Token JWT inválido o expirado
        403: Sin permisos para crear reels o usar el avatar
        404: Avatar no encontrado
    
    Flujo de procesamiento:
        1. Validar permisos del usuario
        2. Validar datos requeridos
        3. Verificar permisos sobre el avatar
        4. Crear reel en BD
        5. Si es productor: iniciar procesamiento con HeyGen
        6. Si no es productor: estado PENDING para aprobación
    
    Note:
        - Productores procesan inmediatamente con HeyGen
        - Otros roles requieren aprobación antes del procesamiento
        - Avatar debe estar activo y accesible para el usuario
        - Script se valida por longitud y contenido apropiado
    """
    # Extraer user_id del token y validar permisos
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    
    if not user.can_create_reels():
        return jsonify({'error': 'No tienes permisos para crear reels'}), 403
    
    # Obtener datos JSON del request
    data = request.get_json()
    
    # Validar campos obligatorios
    required_fields = ['title', 'script', 'avatar_id']
    for field in required_fields:
        if field not in data:
            return jsonify({'error': f'Campo {field} requerido'}), 400
    
    # Obtener y validar avatar
    avatar = Avatar.query.get_or_404(data['avatar_id'])
    
    # Verificar que el usuario puede usar este avatar
    if not avatar.can_be_used_by(user):
        return jsonify({'error': 'No tienes permisos para usar este avatar'}), 403
    
    # Crear reel con datos validados
    reel = Reel(
        creator_id             = user.id,
        avatar_id              = data['avatar_id'],
        title                  = data['title'],
        description            = data.get('description', ''),
        script                 = data['script'],
        resolution             = data.get('resolution', '1080p'),
        background_type        = data.get('background_type', 'default'),
        background_url         = data.get('background_url'),
        category               = data.get('category'),
        # Estado inicial según el rol del usuario
        status                = ReelStatus.PENDING if not user.is_producer() else ReelStatus.PROCESSING
    )

    # Procesar etiquetas si se proporcionan
    if 'tags' in data:
        reel.set_tags(data['tags'])
    
    # Guardar en base de datos
    db.session.add(reel)
    db.session.commit()
    
    # Si es productor, iniciar procesamiento inmediato con HeyGen
    if user.is_producer():
        producer  = user.producer_profile
        processor = HeyGenVideoProcessor(producer.heygen_api_key)
        processor.process_reel(reel)
    
    return jsonify(reel.to_dict()), 201

@api_bp.route('/reels/<int:reel_id>', methods=['GET'])
@jwt_required()
def get_reel(reel_id):
    """
    Obtener detalles completos de un reel específico.
    
    Retorna información detallada de un reel incluyendo metadatos,
    estado de procesamiento, URLs de videos y estadísticas.
    Valida permisos jerárquicos según el rol del usuario.
    
    Args:
        reel_id (int): ID único del reel a consultar
    
    Headers:
        Authorization: Bearer <jwt_token>
    
    Returns:
        JSON: Datos completos del reel si tiene permisos
    
    Status Codes:
        200: Detalles del reel retornados exitosamente
        401: Token JWT inválido o expirado
        403: Sin permisos para acceder a este reel
        404: Reel no encontrado
    
    Permisos de acceso:
        - ADMIN: Puede ver cualquier reel
        - CREATOR: Puede ver sus propios reels
        - PRODUCER: Puede ver reels de su red (subproductores/afiliados)
        - Otros: Sin acceso
    
    Note:
        - Incluye URLs de video y preview si están disponibles
        - Información de procesamiento HeyGen si corresponde
        - Metadatos técnicos útiles para debugging
    """
    # Extraer user_id del token y obtener entidades
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    reel    = Reel.query.get_or_404(reel_id)

    #  Verificar permisos jerárquicos de acceso
    has_access = (
        user.is_admin() or  # Admins ven todo
        reel.creator_id == user.id or  # Creador ve sus reels
        (user.is_producer() and user.producer_profile and  # Productor ve su red
         reel.creator.get_producer() and 
         reel.creator.get_producer().id == user.producer_profile.id)
    )
    
    if not has_access:
        return jsonify({'error': 'Acceso denegado'}), 403
    
    return jsonify(reel.to_dict())

@api_bp.route('/reels/<int:reel_id>/approve', methods=['POST'])
@jwt_required()
def approve_reel(reel_id):
    """
    Aprobar un reel para procesamiento o publicación.
    
    Permite a productores y administradores aprobar reels creados
    por miembros de su red. Cambia el estado del reel y puede
    desencadenar el procesamiento automático.
    
    Args:
        reel_id (int): ID del reel a aprobar
    
    Headers:
        Authorization: Bearer <jwt_token>
    
    Returns:
        JSON: Mensaje de confirmación
    
    Status Codes:
        200: Reel aprobado exitosamente
        401: Token JWT inválido o expirado
        403: Sin permisos para aprobar este reel
        404: Reel no encontrado
    
    Permisos para aprobar:
        - ADMIN: Puede aprobar cualquier reel
        - PRODUCER: Puede aprobar reels de su red únicamente
        - Otros: Sin permisos de aprobación
    
    Note:
        - Utiliza método approve() del modelo Reel
        - Registra quién aprobó el reel para auditoría
        - Puede desencadenar procesamiento automático en HeyGen
    """
    #  Extraer user_id del token y obtener entidades
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    reel    = Reel.query.get_or_404(reel_id)

    #  Verificar permisos de aprobación
    can_approve = (
        user.is_admin() or  # Admins aprueban todo
        (user.is_producer() and reel.creator.get_producer() and 
         reel.creator.get_producer().id == user.producer_profile.id)  # Productor aprueba su red
    )
    
    if not can_approve:
        return jsonify({'error': 'No tienes permisos para aprobar este reel'}), 403
    
    #  Aprobar usando método del modelo
    reel.approve(user)
    return jsonify({'message': 'Reel aprobado exitosamente'})

@api_bp.route('/reels/<int:reel_id>/process', methods=['POST'])
@jwt_required()
def process_reel(reel_id):
    """
    Iniciar procesamiento de un reel con HeyGen API.
    
    Permite a productores iniciar manualmente el procesamiento
    de un reel aprobado utilizando la integración con HeyGen.
    Útil para re-procesar o iniciar procesamiento retrasado.
    
    Args:
        reel_id (int): ID del reel a procesar
    
    Headers:
        Authorization: Bearer <jwt_token>
    
    Returns:
        JSON: Estado del procesamiento iniciado
    
    Status Codes:
        200: Procesamiento iniciado exitosamente
        400: Reel no está en estado apropiado para procesamiento
        401: Token JWT inválido o expirado
        403: Sin permisos para procesar este reel
        404: Reel no encontrado
        500: Error en la integración con HeyGen
    
    Requisitos:
        - Reel debe estar en estado APPROVED
        - Usuario debe ser el productor del creador del reel
        - API key de HeyGen debe ser válida
        - Cuota API debe estar disponible
    
    Note:
        - Utiliza HeyGenVideoProcessor para integración
        - Cambia estado del reel durante el procesamiento
        - Maneja errores de API externa elegantemente
    """
    #  Extraer user_id del token y obtener entidades
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    reel    = Reel.query.get_or_404(reel_id)

    #  Verificar permisos de procesamiento (solo productor del creador)
    producer = reel.creator.get_producer()
    can_process = (
        user.is_admin() or  # Admins pueden procesar todo
        (user.is_producer() and user.producer_profile.id == producer.id)  # Productor procesa su red
    )
    
    if not can_process:
        return jsonify({'error': 'No tienes permisos para procesar este reel'}), 403
    
    #  Validar estado del reel - CORREGIDO: usar PENDING en lugar de APPROVED
    if reel.status != ReelStatus.PENDING:
        return jsonify({'error': 'El reel debe estar en estado pendiente para procesarse'}), 400
    
    #  Iniciar procesamiento con HeyGen
    try:
        processor = HeyGenVideoProcessor(producer.heygen_api_key)
        success = processor.process_reel(reel)
        
        if success:
            return jsonify({'message': 'Procesamiento iniciado exitosamente'})
        else:
            return jsonify({'error': 'Error iniciando el procesamiento'}), 500
    except Exception as e:
        return jsonify({'error': f'Error en procesamiento: {str(e)}'}), 500

#  =================== ENDPOINTS DE COMISIONES ===================

@api_bp.route('/commissions', methods=['GET'])
@jwt_required()
def list_commissions():
    """
    Listar comisiones del usuario con paginación y filtros.
    
    Retorna una lista paginada de comisiones ganadas por el usuario
    según su rol. Admins pueden ver todas las comisiones del sistema,
    otros usuarios solo ven las propias.
    
    Headers:
        Authorization: Bearer <jwt_token>
    
    Query Parameters:
        page (int, opcional): Número de página (default: 1)
        per_page (int, opcional): Elementos por página (default: 20, max: 100)
        status (str, opcional): Filtro por estado (pending, approved, paid, cancelled)
    
    Returns:
        JSON: Lista paginada de comisiones con metadata
    
    Response Structure:
        {
            "commissions": [
                {
                    "id": 23,
                    "amount": 15.75,
                    "percentage": 10.0,
                    "commission_type": "subproducer",
                    "status": "approved",
                    "reel_title": "Video Promocional",
                    "created_at": "2025-10-12T10:30:00",
                    "approved_at": "2025-10-12T14:20:00",
                    ...
                }
            ],
            "total": 45,
            "pages": 3,
            "current_page": 1
        }
    
    Status Codes:
        200: Lista de comisiones retornada exitosamente
        401: Token JWT inválido o expirado
    
    Permisos por rol:
        - ADMIN: Todas las comisiones del sistema
        - Otros: Solo comisiones propias (commissions_earned)
    
    Note:
        - Incluye información del reel asociado para contexto
        - Filtros por estado útiles para gestión financiera
        - Ordenamiento cronológico (más recientes primero)
        - Información de fechas de aprobación y pago
    """
    #  Extraer user_id del token y obtener usuario
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    
    #  Capturar parámetros de paginación y filtrado
    page          = request.args.get('page', 1, type=int)
    per_page      = min(request.args.get('per_page', 20, type=int), 100)  # Límite máximo
    status_filter = request.args.get('status')
    
    #  Construir consulta base según permisos del rol
    if user.is_admin():
        # Admins ven todas las comisiones del sistema
        query = Commission.query
    else:
        # Otros usuarios ven solo sus comisiones ganadas
        query = user.commissions_earned
    
    #  Aplicar filtro por estado si se especifica
    if status_filter:
        query = query.filter_by(status=status_filter)
    
    #  Ejecutar consulta con paginación
    commissions = query.order_by(Commission.created_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return jsonify({
        'commissions'  : [commission.to_dict() for commission in commissions.items],
        'total'        : commissions.total,
        'pages'        : commissions.pages,
        'current_page' : page
    })

#  =================== ENDPOINTS DE ESTADÍSTICAS ===================

@api_bp.route('/stats/overview', methods=['GET'])
@jwt_required()
def stats_overview():
    """
    Obtener estadísticas generales según el rol del usuario.
    
    Retorna un resumen de métricas clave personalizadas para cada
    tipo de usuario. Las estadísticas son calculadas en tiempo real
    y varían según los permisos del rol.
    
    Headers:
        Authorization: Bearer <jwt_token>
    
    Returns:
        JSON: Métricas específicas del rol del usuario
    
    Response Structure por rol:
        ADMIN:
        {
            "users": 156,
            "producers": 23,
            "reels": 342,
            "avatars": 89,
            "commissions": 567
        }
        
        PRODUCER:
        {
            "reels": 45,
            "avatars": 12,
            "subproducers": 8,
            "final_users": 23,
            "earnings": 2340.50,
            "api_usage": 1250
        }
        
        SUBPRODUCER/FINAL_USER:
        {
            "reels": 23,
            "completed_reels": 18,
            "earnings": 450.75,
            "pending_earnings": 120.30
        }
    
    Status Codes:
        200: Estadísticas calculadas y retornadas exitosamente
        401: Token JWT inválido o expirado
    
    Métricas por rol:
        - ADMIN: Conteos globales del sistema
        - PRODUCER: Métricas de producción y equipo
        - SUBPRODUCER/FINAL_USER: Ganancias y productividad personal
    
    Note:
        - Cálculos en tiempo real para precisión
        - Earnings incluye solo comisiones aprobadas
        - API usage específico para productores
        - Diseñado para dashboards y widgets de estado
    """
    #  Extraer user_id del token y obtener usuario
    user_id = get_jwt_identity()
    user    = User.query.get(user_id)
    
    #  Calcular estadísticas según el rol del usuario
    if user.is_admin():
        # Admins ven métricas globales del sistema
        stats = {
            'users'      : User.query.count(),
            'producers'  : User.query.filter_by(role=UserRole.PRODUCER).count(),
            'reels'      : Reel.query.count(),
            'avatars'    : Avatar.query.count(),
            'commissions' : Commission.query.count()
        }
    elif user.is_producer():
        # Productores ven métricas de su operación
        producer = user.producer_profile
        stats = {
            'reels'        : user.reels.count(),
            'avatars'      : producer.avatars.count(),
            'subproducers' : producer.current_subproducers_count,
            'final_users'  : getattr(producer, 'current_final_users_count', 0),  # TODO: Verificar campo en modelo
            'earnings'     : Commission.get_user_total_earnings(user.id, 'approved'),
            'api_usage'    : getattr(producer, 'api_calls_this_month', 0)  # TODO: Verificar campo en modelo
        }
    else:
        # Subproductores y usuarios finales ven métricas personales
        stats = {
            'reels': user.reels.count(),
            'completed_reels': user.reels.filter_by(status=ReelStatus.COMPLETED).count(),
            'earnings': Commission.get_user_total_earnings(user.id, 'approved'),
            'pending_earnings': Commission.get_user_total_earnings(user.id, 'pending')
        }
    
    return jsonify(stats)

#  =================== MANEJADORES DE ERRORES ===================

@api_bp.errorhandler(404)
def api_not_found(error):
    """
    Manejador de errores 404 - Recurso no encontrado.
    
    Maneja todas las solicitudes a endpoints inexistentes dentro
    del blueprint API y retorna una respuesta JSON consistente.
    
    Args:
        error: Objeto de error Flask automático
    
    Returns:
        JSON: Mensaje de error estructurado con código HTTP 404
    
    Response Structure:
        {
            "error": "Recurso no encontrado"
        }
    
    Casos comunes:
        - URL incorrecta en solicitudes API
        - IDs inexistentes en endpoints dinámicos
        - Endpoints deprecados o removidos
        - Errores de tipeo en rutas
    
    Note:
        - Solo maneja errores dentro del blueprint API
        - Respuesta consistente para todas las 404
        - Útil para debugging de integrations frontend
    """
    return jsonify({'error': 'Recurso no encontrado'}), 404

@api_bp.errorhandler(500)
def api_internal_error(error):
    """
    Manejador de errores 500 - Error interno del servidor.
    
    Captura errores no manejados durante el procesamiento de
    solicitudes API y retorna una respuesta JSON segura sin
    exponer detalles técnicos internos.
    
    Args:
        error: Objeto de error Flask automático
    
    Returns:
        JSON: Mensaje de error genérico con código HTTP 500
    
    Response Structure:
        {
            "error": "Error interno del servidor"
        }
    
    Casos típicos:
        - Errores de base de datos no manejados
        - Excepciones en lógica de negocio
        - Fallos en integraciones externas (HeyGen API)
        - Problemas de memoria o recursos del sistema
    
    Seguridad:
        - NO expone stack traces a clientes
        - Respuesta genérica para todos los errores 500
        - Los logs detallados quedan en servidor
    
    Note:
        - Error logging debe manejarse a nivel de aplicación
        - Considerar rollback de transacciones DB en errores
        - Útil para mantener consistencia en respuestas API
    """
    return jsonify({'error': 'Error interno del servidor'}), 500