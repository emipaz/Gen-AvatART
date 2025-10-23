"""
Módulo de rutas de autenticación para la aplicación Gen-AvatART.

Este módulo maneja todas las rutas relacionadas con la autenticación y gestión
de usuarios, incluyendo login, registro, perfiles y validaciones. Implementa
un sistema de roles jerárquico y gestión de estados de usuario.

El módulo incluye:
    - Rutas de autenticación    : Login, logout, registro
    - Gestión de perfiles       : Visualización y edición de datos
    - Cambio de contraseñas     : Validación y actualización segura
    - APIs de validación        : Username y email en tiempo real
    - Sistema de invitaciones   : Registro por tokens (futuro)

Funcionalidades principales:
    - Autenticación con Flask-Login y session management
    - Registro público para afiliados con estado PENDING
    - Sistema de roles con redirección automática al dashboard
    - Validación de unicidad de datos (email, username)
    - Gestión de perfiles diferenciada por rol de usuario
    - APIs REST para validaciones en frontend
    - Sistema de tokens de invitación (preparado para implementar)

Roles soportados:
    - ADMIN        : Acceso completo al sistema
    - PRODUCER     : Gestión de clones y subproductores  
    - SUBPRODUCER  : Gestión de afiliados bajo su productor
    - FINAL_USER   : Uso de clones según permisos asignados

Estados de usuario:
    - ACTIVE  : Usuario habilitado para usar el sistema
    - PENDING : Esperando aprobación del administrador
    - INACTIVE: Usuario deshabilitado temporalmente
"""


from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from functools import wraps
from werkzeug.security import check_password_hash
from app import db
from app.models.user import User, UserRole, UserStatus
from app.models.producer import Producer
from app.services.email_service import send_verification_email
from datetime import datetime

auth_bp = Blueprint('auth', __name__)

def email_verified_required(f):
    """
    Decorador que restringe acceso si el usuario no verificó su email.
    
    Este decorador verifica que el usuario autenticado tenga el campo
    email_verified en True antes de permitir acceso a rutas protegidas.
    Si no está verificado, redirige a completar perfil/verificación.
    
    Args:
        f: Función de vista a proteger
    
    Returns:
        function: Función decorada con validación de verificación
    
    Note:
        - Debe usarse después de @login_required
        - Redirige a 'auth.complete_profile' si no está verificado
        - Complementa la autenticación básica de Flask-Login
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Si no hay usuario logueado, que el @login_required se ocupe
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))

        # Si el user no está verificado, lo mandamos a completar perfil/verificación
        if not getattr(current_user, 'email_verified', False):
            flash('Verificá tu email para continuar.', 'warning')
            return redirect(url_for('auth.complete_profile'))

        return f(*args, **kwargs)
    return decorated_function

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """
    Ruta de inicio de sesión para usuarios registrados.
    
    Maneja tanto la visualización del formulario de login (GET) como
    el procesamiento de credenciales (POST). Incluye validación de
    estado de usuario y redirección automática según el rol.
    
    Methods:
        GET  : Muestra el formulario de login
        POST : Procesa las credenciales y autentica al usuario
    
    Form Data (POST):
        email (str)    : Email del usuario
        password (str) : Contraseña del usuario
        remember (bool): Opcional, para recordar la sesión
    
    Returns:
        GET : Template 'auth/login.html'
        POST: Redirección al dashboard correspondiente o template con errores
    
    Note:
        - Usuarios ya autenticados son redirigidos al dashboard
        - Solo usuarios con estado ACTIVE pueden iniciar sesión
        - Redirección automática según rol: admin, producer, subproducer, final_user
        - Actualiza last_login en cada inicio de sesión exitoso
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        email    = request.form.get('email')
        password = request.form.get('password')
        remember = bool(request.form.get('remember'))
        
        if not email or not password:
            flash('Por favor completa todos los campos', 'error')
            return render_template('auth/login.html')
        
        user = User.query.filter_by( email = email ).first()
        
        if user and user.check_password(password):
            if user.status != UserStatus.ACTIVE:
                flash('Tu cuenta está pendiente de aprobación o ha sido suspendida', 'warning')
                return render_template('auth/login.html')
            
            login_user(user, remember = remember)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Redirigir según el rol
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            
            if user.is_admin():
                return redirect( url_for( 'admin.dashboard' ))
            elif user.is_producer():
                return redirect( url_for( 'producer.dashboard' ))
            elif user.is_subproducer():
                return redirect( url_for( 'subproducer.dashboard' ))
            else:  # final_user / affiliate
                return redirect( url_for( 'affiliate.dashboard' ))
        else:
            flash('Email o contraseña incorrectos', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """""
    Ruta de registro público para nuevos usuarios (solo afiliados).
    
    Permite el registro público únicamente para el rol FINAL_USER,
    con estado inicial PENDING que requiere aprobación administrativa.
    Otros roles (producer, subproducer) se crean mediante invitación.
    
    Methods:
        GET  : Muestra el formulario de registro
        POST : Procesa los datos y crea el nuevo usuario
    
    Form Data (POST):
        email (str)            : Email único del usuario
        username (str)         : Username único del usuario  
        password (str)         : Contraseña (mínimo 6 caracteres)
        confirm_password (str) : Confirmación de contraseña
        first_name (str)       : Nombre del usuario
        last_name (str)        : Apellido del usuario
        phone (str, opcional)  : Teléfono de contacto
    
    Returns:
        GET : Template 'auth/register.html'
        POST: Redirección a login si exitoso, template con errores si falla
    
    Note:
        - Solo se permite registro público para FINAL_USER
        - Estado inicial siempre es PENDING (requiere aprobación)
        - Validación de unicidad para email y username
        - Contraseña se hashea automáticamente con set_password()
        - Productores y subproductores requieren invitación específica
    """
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        email            = request.form.get('email')
        username         = request.form.get('username')
        password         = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        first_name       = request.form.get('first_name')
        last_name        = request.form.get('last_name')
        phone            = request.form.get('phone')
        
        # Validaciones
        if not all([email, username, password, first_name, last_name]):
            flash('Por favor completa todos los campos obligatorios', 'error')
            return render_template('auth/register.html')
        
        if password != confirm_password:
            flash('Las contraseñas no coinciden', 'error')
            return render_template('auth/register.html')
        
        if len(password) < 6:
            flash('La contraseña debe tener al menos 6 caracteres', 'error')
            return render_template('auth/register.html')
        
        # Verificar si el usuario ya existe
        if User.query.filter_by(email=email).first():
            flash('Ya existe un usuario con este email', 'error')
            return render_template('auth/register.html')
        
        if User.query.filter_by(username=username).first():
            flash('Ya existe un usuario con este nombre de usuario', 'error')
            return render_template('auth/register.html')
        
        # Crear nuevo usuario con verificación pendiente
        user = User(
            email          = email,
            username       = username,
            first_name     = first_name,
            last_name      = last_name,
            phone          = phone,
            role           = UserRole.FINAL_USER,
            status         = UserStatus.PENDING, # cambiar a PENDING si se requiere aprobación
            email_verified = False  # nuevo campo para verificación de email
        )
        user.set_password(password)
        user.generate_verification_token()  # genera token único
        
        db.session.add(user)
        db.session.commit()

        # Enviar correo de verificación
        try:
            send_verification_email(user)
            flash('Registro exitoso. Revisá tu correo para verificar tu cuenta.', 'success')
        except Exception as e:
            flash(f'Usuario creado, pero no se pudo enviar el correo: {str(e)}', 'warning')

        # Mostrar página de confirmación
        return render_template('auth/verification_sent.html', email=user.email)
    
    return render_template('auth/register.html')

@auth_bp.route('/register/invite/<token>')
def register_invite(token):
    """
    Ruta de registro por invitación con token (preparada para implementar).
    
    Esta ruta manejará el registro de productores y subproductores
    mediante tokens de invitación seguros. Por ahora redirige al
    registro normal como placeholder.
    
    Args:
        token (str): Token de invitación único y temporal
    
    Returns:
        Redirect: Redirección al registro normal (temporal)
    
    TODO:
        - Implementar validación de tokens de invitación
        - Desencriptar datos del rol y permisos desde el token
        - Crear usuario con rol específico (PRODUCER/SUBPRODUCER)
        - Establecer relaciones jerárquicas automáticamente
        - Invalidar token después del uso
    
    Note:
        - Necesario para onboarding de productores y subproductores
        - Tokens deben incluir rol, expiración y datos del invitador
        - Importante para mantener la jerarquía del sistema
    """
    # TODO: Implementar sistema de tokens de invitación
    # Por ahora, simplemente redirigir al registro normal
    return redirect(url_for('auth.register'))

@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    """
    Verifica el email del usuario mediante el token recibido.
    
    Esta ruta maneja la verificación de email cuando el usuario hace clic
    en el enlace enviado por correo. Marca el email como verificado y
    redirige al flujo de completar perfil.
    
    Args:
        token (str): Token único de verificación generado al registrarse
    
    Returns:
        Template o Redirect: Página de éxito/error según validez del token
    
    Process:
        1. Buscar usuario por token en la base de datos
        2. Si existe, marcar email_verified = True
        3. Limpiar token de verificación
        4. Hacer login automático del usuario
        5. Redirigir a completar perfil
    
    Note:
        - Token se invalida después del primer uso
        - Login automático para mejor UX
        - Redirige a completar perfil después de verificación
    """
    # Buscar al usuario por el token guardado en la BD
    user = User.query.filter_by(email_verification_token=token).first()

    if not user:
        return render_template('auth/verification_failed.html')

    # Marcar como verificado y limpiar token
    user.email_verified           = True
    user.status                   = UserStatus.ACTIVE  # Activar cuenta al verificar email
    user.email_verification_token = None
    db.session.commit()

    # Iniciar sesión automáticamente para mejor UX
    login_user(user)

    flash("Tu correo fue verificado correctamente. Completá tu perfil para continuar.", "success")
    return redirect(url_for('auth.complete_profile'))

@auth_bp.route('/resend-verification')
@login_required
def resend_verification():
    """
    Reenvía el email de verificación al usuario logueado.
    
    Permite al usuario solicitar un nuevo email de verificación si no
    recibió el original o expiró. Genera un nuevo token y reenvía el email.
    
    Returns:
        Redirect: Redirige al index con mensaje de confirmación o error
    
    Note:
        - Solo usuarios no verificados pueden usar esta función
        - Genera nuevo token invalidando el anterior
        - Manejo elegante de errores de envío de email
    """
    # Si ya está verificado, no hace falta reenviar
    if getattr(current_user, "email_verified", False):
        flash("Tu email ya está verificado.", "info")
        return redirect(url_for('main.index'))

    # Genera un token nuevo y guarda
    current_user.generate_verification_token()
    db.session.commit()

    # Envía el correo
    try:
        send_verification_email(current_user)
        flash("Te enviamos un nuevo correo de verificación.", "success")
    except Exception as e:
        flash(f"No pudimos enviar el correo: {e}", "error")

    return redirect(url_for('main.index'))

@auth_bp.route('/complete-profile', methods=['GET', 'POST'])
@login_required
def complete_profile():
    """
    Permite al usuario completar información adicional de su perfil.
    
    Esta ruta se utiliza después de verificar el email para recopilar
    información adicional del perfil como país, ciudad, teléfono e
    información profesional.
    
    Methods:
        GET  : Muestra el formulario de completar perfil
        POST : Procesa la información adicional del perfil
    
    Form Data (POST):
        phone (str, opcional)            : Teléfono del usuario
        country (str, opcional)          : País de residencia
        city (str, opcional)             : Ciudad de residencia
        professional_info (str, opcional): Información profesional
        terms (bool, opcional)           : Aceptación de términos
    
    Returns:
        GET : Template 'auth/complete_profile.html'
        POST: Redirección al dashboard si exitoso
    
    Note:
        - Solo accesible para usuarios con email verificado
        - Información opcional pero recomendada
        - Mejora la experiencia de onboarding
    """
    user = current_user

    if request.method == 'POST':
        user.phone            = request.form.get('phone')
        user.country          = request.form.get('country')
        user.city             = request.form.get('city')
        user.professional_info = request.form.get('professional_info')

        db.session.commit()
        flash('Perfil actualizado correctamente.', 'success')
        return redirect(url_for('main.index'))

    return render_template('auth/complete_profile.html', user=user)

# @auth_bp.route('/resend-verification')
# @login_required
# def resend_verification():
#     """
#     Reenvía el email de verificación al usuario logueado.
    
#     Permite a los usuarios solicitar un nuevo email de verificación
#     si no recibieron el original o si expiró el token.
    
#     Returns:
#         Redirect: Redirección al index con mensaje de estado
    
#     Note:
#         - Solo funciona si el usuario no está ya verificado
#         - Genera un nuevo token antes de reenviar
#         - Maneja errores de envío de email elegantemente
#     """
#     # Si ya está verificado, no hace falta reenviar
#     if getattr(current_user, "email_verified", False):
#         flash("Tu email ya está verificado.", "info")
#         return redirect(url_for('main.index'))

#     # Genera un token nuevo y guarda
#     if hasattr(current_user, "generate_verification_token"):
#         current_user.generate_verification_token()
#         db.session.commit()

#     # Envía el correo
#     try:
#         send_verification_email(current_user)
#         flash("Te enviamos un nuevo correo de verificación.", "success")
#     except Exception as e:
#         flash(f"No pudimos enviar el correo: {e}", "danger")

#     return redirect(url_for('main.index'))

@auth_bp.route('/logout')
@login_required
def logout():
    """
    Ruta para cerrar sesión del usuario actual.
    
    Termina la sesión del usuario autenticado y redirige
    a la página principal con mensaje de confirmación.
    
    Returns:
        Redirect: Redirección a la página principal
    
    Note:
        - Requiere autenticación (@login_required)
        - Flask-Login maneja automáticamente la limpieza de sesión
        - Mensaje flash confirma el cierre exitoso
    """
    logout_user()
    flash('Has cerrado sesión exitosamente', 'info')
    return redirect(url_for('main.index'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """"
    Ruta de gestión del perfil de usuario.
    
    Permite visualizar y editar la información personal del usuario.
    Incluye campos específicos para productores con información comercial
    adicional si tienen un perfil de productor asociado.
    
    Methods:
        GET  : Muestra el perfil actual del usuario
        POST : Actualiza la información del perfil
    
    Form Data (POST):
        first_name (str)            : Nombre del usuario
        last_name (str)             : Apellido del usuario
        phone (str)                 : Teléfono de contacto
        company_name (str, opcional): Nombre de empresa (solo productores)
        business_type (str, opcional): Tipo de negocio (solo productores)
        website (str, opcional)     : Sitio web (solo productores)
    
    Returns:
        GET : Template 'auth/profile.html' con datos del usuario
        POST: Redirección al perfil actualizado o template con errores
    
    Note:
        - Campos comerciales solo disponibles para usuarios con rol PRODUCER
        - Actualización diferenciada según el tipo de usuario
        - Validación automática de permisos por rol
    """
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name', current_user.first_name)
        current_user.last_name  = request.form.get('last_name' , current_user.last_name)
        current_user.phone      = request.form.get('phone'     , current_user.phone)
        
        # Si es productor, actualizar información comercial
        if current_user.is_producer() and current_user.producer_profile:
            producer = current_user.producer_profile
            producer.company_name  = request.form.get('company_name',  producer.company_name)
            producer.business_type = request.form.get('business_type', producer.business_type)
            producer.website       = request.form.get('website',       producer.website)
        
        db.session.commit()
        flash('Perfil actualizado exitosamente', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/profile.html', user=current_user)

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """
    Ruta para cambio de contraseña del usuario autenticado.
    
    Permite al usuario cambiar su contraseña validando la contraseña
    actual y estableciendo una nueva con confirmación. Implementa
    validaciones de seguridad estándar.
    
    Methods:
        GET  : Muestra el formulario de cambio de contraseña
        POST : Procesa el cambio de contraseña
    
    Form Data (POST):
        current_password (str) : Contraseña actual del usuario
        new_password (str)     : Nueva contraseña deseada
        confirm_password (str) : Confirmación de la nueva contraseña
    
    Returns:
        GET : Template 'auth/change_password.html'
        POST: Redirección al perfil si exitoso, template con errores si falla
    
    Note:
        - Requiere validación de contraseña actual por seguridad
        - Nueva contraseña debe cumplir longitud mínima (6 caracteres)
        - Confirmación obligatoria para evitar errores de tipeo
        - Hash automático con set_password() para seguridad
    """
    if request.method == 'POST':
        # Obtener datos del formulario
        current_password = request.form.get('current_password')
        new_password     = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        # Validaciones
        if not current_user.check_password(current_password):
            flash('La contraseña actual es incorrecta', 'error')
            return render_template('auth/change_password.html')
        # Validar nueva contraseña
        if new_password != confirm_password:
            flash('Las nuevas contraseñas no coinciden', 'error')
            return render_template('auth/change_password.html')
        # Validar longitud mínima
        if len(new_password) < 6:
            flash('La nueva contraseña debe tener al menos 6 caracteres', 'error')
            return render_template('auth/change_password.html')
        # Actualizar contraseña
        current_user.set_password(new_password)
        db.session.commit()
        # Mostrar mensaje de éxito
        flash('Contraseña cambiada exitosamente', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/change_password.html')

@auth_bp.route('/api/validate-username')
def validate_username():
    """
    API REST para validar disponibilidad de username en tiempo real.
    
    Endpoint para validaciones AJAX del frontend, permitiendo verificar
    la disponibilidad de un username sin enviar el formulario completo.
    Mejora la experiencia de usuario con feedback inmediato.
    
    Query Parameters:
        username (str): Username a validar
    
    Returns:
        JSON: Respuesta con estado de validación
              - valid (bool): True si está disponible, False si no
              - message (str): Mensaje explicativo del resultado
    
    Example Response:
        {"valid": true, "message": "Username disponible"}
        {"valid": false, "message": "Username no disponible"}
    
    Note:
        - Respuesta inmediata para mejor UX
        - No requiere autenticación (endpoint público)
        - Útil para validaciones en vivo durante el registro
    """
    username = request.args.get('username')
    # Validar que se proporcionó un username
    if not username:
        return jsonify({'valid': False, 'message': 'Username requerido'})
    # Verificar si el username ya existe
    user = User.query.filter_by(username=username).first()
    if user:
        return jsonify({'valid': False, 'message': 'Username no disponible'})
    
    return jsonify({'valid': True, 'message': 'Username disponible'})

@auth_bp.route('/api/validate-email')
def validate_email():
    """
    API REST para validar disponibilidad de email en tiempo real.
    
    Endpoint para validaciones AJAX del frontend, permitiendo verificar
    la disponibilidad de un email sin enviar el formulario completo.
    Complementa validate_username para validación completa de datos únicos.
    
    Query Parameters:
        email (str): Email a validar
    
    Returns:
        JSON: Respuesta con estado de validación
              - valid (bool): True si está disponible, False si no
              - message (str): Mensaje explicativo del resultado
    
    Example Response:
        {"valid": true, "message": "Email disponible"}
        {"valid": false, "message": "Email no disponible"}
    
    Note:
        - Mejora significativa en UX del formulario de registro
        - Previene errores antes del envío del formulario
        - Endpoint público accesible sin autenticación
        - Compatible con validaciones JavaScript del frontend
    """
    email = request.args.get('email')
    # Validar que se proporcionó un email
    if not email:
        return jsonify({'valid': False, 'message': 'Email requerido'})
    # Verificar si el email ya existe
    user = User.query.filter_by(email=email).first()
    if user:
        return jsonify({'valid': False, 'message': 'Email no disponible'})
    
    return jsonify({'valid': True, 'message': 'Email disponible'})

