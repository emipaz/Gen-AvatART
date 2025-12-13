"""
Módulo de rutas de gestión de usuarios para la aplicación Gen-AvatART.

Este módulo maneja las rutas relacionadas con la gestión del perfil de usuario,
dashboard personal y funcionalidades específicas del usuario autenticado. Incluye
manejo de avatares de perfil, actualización de datos y estadísticas personalizadas.

El módulo incluye:
    - Ruta de perfil de usuario    : Gestión completa de datos personales
    - Ruta de dashboard personal   : Estadísticas y resumen de actividad
    - Gestión de avatares de perfil: Subida y procesamiento de imágenes
    - Formularios con validación   : WTForms para entrada segura de datos
    - Manejo de archivos           : Procesamiento seguro de imágenes

Funcionalidades principales:
    - Actualización completa de perfil con validaciones
    - Cambio de contraseña con verificación de seguridad
    - Subida y procesamiento automático de avatares de perfil
    - Dashboard personalizado con estadísticas por rol
    - Validación de unicidad de email en tiempo real
    - Redimensionamiento automático de imágenes de perfil
    - Manejo de errores elegante con rollback automático

Características técnicas:
    - Procesamiento de imágenes con PIL/Pillow
    - Validación de tipos de archivo permitidos
    - Generación de nombres únicos para evitar colisiones
    - Optimización automática de imágenes (300x300, calidad 85%)
    - Conversión automática RGBA a RGB para compatibilidad
"""

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from datetime import datetime
from app import db
from app.models.user import User
from app.models.producer_request import ProducerRequest, ProducerRequestStatus
from app.models.reel import Reel, ReelStatus
from app.models.avatar import Avatar, AvatarAccessType, AvatarStatus
from app.models.reel_request import ReelRequest, ReelRequestStatus
from app.services.email_service import send_avatar_reel_request_notification
from app.services.heygen_service import HeyGenService
import os
import logging
from PIL import Image
from uuid import uuid4

# Configurar logger para este módulo
logger = logging.getLogger(__name__)

# Crear el blueprint
user_bp = Blueprint('user', __name__, url_prefix='/user')

# Formulario para el perfil
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, FileField, TextAreaField, SelectField, HiddenField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional

class ProfileForm(FlaskForm):
    """
    Formulario para edición del perfil de usuario.
    
    Formulario WTF que maneja la actualización de datos personales,
    incluyendo información básica, avatar de perfil y cambio de contraseña.
    Incluye validaciones cliente y servidor para seguridad de datos.
    
    Attributes:
        first_name (StringField)         : Nombre del usuario (2-50 caracteres)
        last_name (StringField)          : Apellido del usuario (2-50 caracteres)
        email (StringField)              : Email único con validación de formato
        phone (StringField)              : Teléfono opcional (máximo 20 caracteres)
        avatar (FileField)               : Imagen de perfil (JPG, PNG, JPEG)
        current_password (PasswordField) : Contraseña actual para verificación
        new_password (PasswordField)     : Nueva contraseña (mínimo 6 caracteres)
        confirm_password (PasswordField) : Confirmación de nueva contraseña
        submit (SubmitField)             : Botón de envío del formulario
    
    Note:
        - Cambio de contraseña es opcional y requiere verificación
        - Avatar se valida por tipo de archivo y se procesa automáticamente
        - Email se valida por unicidad antes de actualizar
        - Todos los campos de contraseña son opcionales para flexibilidad
    """

    first_name = StringField('Nombre'  , validators = [DataRequired(), Length(min=2, max=50)])
    last_name  = StringField('Apellido', validators = [DataRequired(), Length(min=2, max=50)])
    email      = StringField('Email'   , validators = [DataRequired(), Email()])
    phone      = StringField('Teléfono', validators = [Optional(), Length(max=20)])
    avatar     = FileField('Avatar'    , validators = [FileAllowed(['jpg', 'png', 'jpeg'], 'Solo imágenes!')])
    
    # Campos para cambiar contraseña - todos opcionales
    current_password = PasswordField('Contraseña Actual',          validators = [Optional()])
    new_password     = PasswordField('Nueva Contraseña' ,          validators = [Optional(), Length(min=6)])
    confirm_password = PasswordField('Confirmar Nueva Contraseña', validators = [Optional()])
    
    submit = SubmitField('Guardar Cambios')


class ReelRequestForm(FlaskForm):
    """
    Formulario para solicitud de creación de reel.
    
    Formulario WTF que maneja la solicitud de creación de un reel usando
    un avatar específico. Incluye validaciones y campos necesarios para
    que el productor pueda revisar y aprobar la solicitud.
    
    Attributes:
        avatar_id (HiddenField)       : ID del avatar a usar (oculto)
        title (StringField)           : Título del reel (3-200 caracteres)
        script (TextAreaField)        : Texto que dirá el avatar (requerido)
        background_url (StringField)  : URL del fondo personalizado (opcional)
        background_image (FileField)  : Imagen de fondo para subir (opcional)
        resolution (SelectField)      : Resolución del video
        user_notes (TextAreaField)    : Notas para el productor (opcional)
        submit (SubmitField)          : Botón de envío de solicitud
    
    Note:
        - La solicitud requiere aprobación del productor propietario del avatar
        - Todos los campos son validados antes de crear la solicitud
        - El avatar_id se pasa como parámetro oculto desde la vista
        - El usuario puede proporcionar URL de fondo O subir una imagen (no ambos)
    """
    
    avatar_id        = HiddenField('Avatar ID', validators=[DataRequired()])
    title            = StringField('Título del Reel', validators=[DataRequired(), Length(min=3, max=200)])
    script           = TextAreaField('Script (Texto que dirá el avatar)', validators=[DataRequired(), Length(min=10, max=2000)])
    voice_id         = StringField('Voz del Avatar', validators=[Optional()])
    background_url   = StringField('URL del Fondo', validators=[Optional(), Length(max=500)])
    background_image = FileField('Subir Imagen de Fondo', validators=[Optional(), FileAllowed(['jpg', 'jpeg', 'png', 'webp'], 'Solo imágenes (JPG, PNG, WEBP)')])
    resolution       = SelectField('Resolución', choices=[
        ('720p', '720p (HD)'),
        ('1080p', '1080p (Full HD)'),
        ('4K', '4K (Ultra HD)')
    ], default='1080p')
    user_notes       = TextAreaField('Notas para el Productor (opcional)', validators=[Optional(), Length(max=500)])

    speed = StringField('Velocidad de la voz', default='1.0',
            description ='Rango: 0.50 (lento) a 1.50 (rápido). Valor por defecto: 1.0',
            validators  =[DataRequired(), Length(max=5)])
    
    pitch = StringField('Pitch de la voz', default='0',
            description ='Rango: -50 (grave) a 50 (agudo). Valor por defecto: 0',
            validators  =[DataRequired(), Length(max=4)])
    
    submit = SubmitField('Solicitar Reel')

def save_avatar(form_avatar):
    """
    Procesa y guarda el avatar de perfil del usuario.
    
    Esta función maneja la subida segura de imágenes de perfil, incluyendo
    validación, redimensionamiento automático, optimización y almacenamiento
    en el directorio correspondiente con nombre único.
    
    Args:
        form_avatar (FileStorage): Archivo de imagen desde el formulario
    
    Returns:
        str: URL relativa del avatar guardado
        None: Si hay error en el procesamiento
    
    Process:
        1. Crear directorio de avatares si no existe
        2. Generar nombre único basado en user_id
        3. Redimensionar imagen a 300x300 manteniendo aspecto
        4. Convertir RGBA a RGB para compatibilidad
        5. Optimizar y guardar con calidad 85%
        6. Retornar URL relativa para almacenar en BD
    
    Note:
        - Directorio          : /static/uploads/avatars/
        - Formato final       : user_{id}_{original_name}.ext
        - Redimensionamiento  : 300x300 con thumbnail para mantener aspecto
        - Optimización automática para reducir tamaño de archivo
        - Manejo de errores con mensaje flash al usuario
    """
    if not form_avatar:
        return None
    
    # Crear directorio de avatares si no existe
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars')
    os.makedirs(upload_folder, exist_ok=True)
    
    # Generar nombre único para evitar colisiones
    filename  = secure_filename(form_avatar.filename)
    name, ext = os.path.splitext(filename)
    filename  = f"user_{current_user.id}_{name}{ext}"
    
    # Ruta completa del archivo
    file_path = os.path.join(upload_folder, filename)
    
    # Procesamiento de imagen con PIL/Pillow
    try:
        image = Image.open(form_avatar)
        
        # Redimensionar a 300x300 manteniendo proporción
        image.thumbnail((300, 300), Image.Resampling.LANCZOS)
        
        # Convertir RGBA a RGB para compatibilidad (elimina canal alpha)
        if image.mode == 'RGBA':
            image = image.convert('RGB')
        
        # Guardar imagen optimizada
        image.save(file_path, optimize=True, quality=85)
        
        # Retornar URL relativa para la base de datos
        return f"/static/uploads/avatars/{filename}"
    
    except Exception as e:
        # Manejo elegante de errores de procesamiento
        flash(f'Error al procesar la imagen: {str(e)}', 'error')
        return None


def has_approved_avatar_permission(user, avatar):
    """
    Verifica si el usuario tiene permiso aprobado para usar un avatar premium.
    
    Busca en los metadatos del avatar si existe una solicitud de permiso
    aprobada para el usuario especificado. Utilizado para validar acceso
    a avatares de tipo premium que requieren autorización explícita.
    
    Args:
        user (User): Usuario para verificar permisos
        avatar (Avatar): Avatar premium a verificar
    
    Returns:
        bool: True si tiene permiso aprobado, False en caso contrario
    
    Note:
        - Solo aplica para avatares de tipo premium
        - Los permisos se almacenan en avatar.meta_data['permission_requests']
        - Un permiso aprobado permite al usuario crear reels con el avatar
        - Avatares públicos no requieren esta verificación
    """
    if not avatar or not avatar.meta_data:
        return False

    for request_data in avatar.meta_data.get('permission_requests', []):
        if request_data.get('user_id') == user.id and request_data.get('status') == 'approved':
            return True

    return False


def get_user_permission_status(user, avatar):
    """
    Obtiene información detallada del estado de permiso de un usuario para un avatar.
    
    Busca en los metadatos del avatar todas las solicitudes de permiso del usuario
    y retorna la más relevante según prioridad de estados. Útil para mostrar
    el estado actual de acceso a avatares premium en la interfaz.
    
    Args:
        user (User): Usuario para verificar estado de permisos
        avatar (Avatar): Avatar a consultar
    
    Returns:
        dict: Diccionario con información de la solicitud más relevante:
            - status (str|None)       : Estado del permiso ('approved', 'rejected', 'pending')
            - request_id (str|None)   : ID único de la solicitud
            - reason (str|None)       : Razón de aprobación/rechazo
            - requested_at (str|None) : Fecha de solicitud en formato ISO
    
    Logic:
        - Prioridad de estados: approved > rejected > pending
        - Entre solicitudes del mismo estado, retorna la más reciente
        - Retorna estructura vacía si no hay solicitudes
    
    Note:
        - Devuelve la solicitud más reciente del usuario para este avatar
        - Prioriza estados: approved > rejected > pending (si hay múltiples)
        - Útil para mostrar badges de estado en la UI
    """
    status_data = {
        'status'      : None,
        'request_id'  : None,
        'reason'      : None,
        'requested_at': None,
    }

    if not avatar or not avatar.meta_data:
        return status_data

    # Buscar todas las solicitudes del usuario para este avatar
    user_requests = [
        req for req in avatar.meta_data.get('permission_requests', [])
        if req.get('user_id') == user.id
    ]

    if not user_requests:
        return status_data

    # Si hay solicitudes, priorizar: approved > rejected > pending
    # Y entre iguales, tomar la más reciente
    status_priority = {'approved': 0, 'rejected': 1, 'pending': 2}
    
    best_request = None
    for req in user_requests:
        status = req.get('status', 'pending')
        if best_request is None:
            best_request = req
        else:
            # Comparar por prioridad
            current_priority = status_priority.get(status, 999)
            best_priority = status_priority.get(best_request.get('status', 'pending'), 999)
            
            if current_priority < best_priority:
                best_request = req
            elif current_priority == best_priority:
                # Si tienen igual prioridad, tomar el más reciente
                try:
                    current_date = req.get('requested_at', '')
                    best_date = best_request.get('requested_at', '')
                    if current_date > best_date:
                        best_request = req
                except:
                    pass

    if best_request:
        status_data['status']       = best_request.get('status')
        status_data['request_id']   = best_request.get('request_id')
        status_data['reason']       = best_request.get('reason')
        status_data['requested_at'] = best_request.get('requested_at')

    return status_data

@user_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """
    Ruta de gestión del perfil de usuario.
    
    Permite al usuario visualizar y actualizar su información personal,
    incluyendo datos básicos, avatar de perfil y contraseña. Implementa
    validaciones de seguridad y manejo de errores robusto.
    
    Methods:
        GET  : Muestra el formulario de perfil prellenado con datos actuales
        POST : Procesa la actualización de datos del perfil
    
    Form Data (POST):
        first_name (str)                 : Nombre del usuario
        last_name (str)                  : Apellido del usuario  
        email (str)                      : Email (validado por unicidad)
        phone (str, opcional)            : Teléfono de contacto
        avatar (file, opcional)          : Imagen de perfil (JPG, PNG, JPEG)
        current_password (str, opcional) : Contraseña actual para verificación
        new_password (str, opcional)     : Nueva contraseña si se desea cambiar
        confirm_password (str, opcional) : Confirmación de nueva contraseña
    
    Returns:
        GET : Template 'user/profile.html' con formulario prellenado
        POST: Redirección al perfil actualizado o template con errores
    
    Note:
        - Validación de email único antes de actualizar
        - Cambio de contraseña requiere verificación de contraseña actual
        - Procesamiento automático de avatar con redimensionamiento
        - Rollback automático en caso de error durante la transacción
        - Mensajes flash para feedback inmediato al usuario
    """
    form = ProfileForm()
    
    if form.validate_on_submit():
        try:
            cambios = []  # Rastrear qué cambió
            
            # Actualizar datos básicos
            current_user.first_name = form.first_name.data
            current_user.last_name  = form.last_name.data
            current_user.phone      = form.phone.data
            
            # Verificar si el email cambió y si ya existe
            if form.email.data != current_user.email:
                existing_user = User.query.filter_by(email=form.email.data).first()
                if existing_user:
                    flash('El email ya está en uso por otro usuario', 'error')
                    return render_template('user/profile.html', form=form)
                current_user.email = form.email.data
                cambios.append('email')
            
            # Procesar avatar si se subió uno nuevo
            if form.avatar.data:
                avatar_url = save_avatar(form.avatar.data)
                if avatar_url:
                    current_user.avatar_url = avatar_url
                    cambios.append('avatar')
            
            # Cambiar contraseña SOLO si el usuario proporciona nueva contraseña
            if form.new_password.data:
                # Si proporciona nueva contraseña, validar contraseña actual
                if not form.current_password.data:
                    flash('Debes proporcionar tu contraseña actual para cambiar la contraseña', 'error')
                    return render_template('user/profile.html', form=form)
                
                if not current_user.check_password(form.current_password.data):
                    flash('Contraseña actual incorrecta', 'error')
                    return render_template('user/profile.html', form=form)
                
                if form.new_password.data != form.confirm_password.data:
                    flash('Las nuevas contraseñas no coinciden', 'error')
                    return render_template('user/profile.html', form=form)
                
                current_user.set_password(form.new_password.data)
                cambios.append('contraseña')
            
            # Guardar cambios en la BD
            db.session.commit()
            
            # Mostrar UN solo mensaje con lo que se actualizó
            if cambios:
                cambios_texto = ', '.join(cambios)
                flash(f'Perfil actualizado correctamente ({cambios_texto})', 'success')
            else:
                flash('Perfil actualizado correctamente', 'success')
            
            return redirect(url_for('user.profile'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el perfil: {str(e)}', 'error')
    
    # Prellenar formulario con datos actuales
    if request.method == 'GET':
        form.first_name.data = current_user.first_name
        form.last_name.data  = current_user.last_name
        form.email.data      = current_user.email
        form.phone.data      = current_user.phone
    
    return render_template('user/profile.html', form=form)


def get_available_avatars_for_user(user):
    """
    Obtiene lista de avatares disponibles para un usuario específico.
    
    Incluye avatares públicos activos y avatares premium para los cuales
    el usuario tiene permisos aprobados.
    
    Args:
        user (User): Usuario para el cual obtener avatares
    
    Returns:
        list: Lista de objetos Avatar disponibles para el usuario
    
    Logic:
        - Avatares públicos  : access_type='public', activos y habilitados
        - Avatares premium   : access_type='premium' con permiso aprobado
        - Avatares privados  : solo si el usuario es el creador
    """
    # Avatares públicos activos
    public_avatars = Avatar.query.filter_by(
        access_type           = AvatarAccessType.PUBLIC,
        status                = AvatarStatus.ACTIVE,
        enabled_by_admin      = True,
        enabled_by_producer   = True,
        enabled_by_subproducer = True
    ).all()
    
    # Avatares premium con permisos aprobados
    premium_avatars = Avatar.query.filter_by(
        access_type = AvatarAccessType.PREMIUM,
        status      = AvatarStatus.ACTIVE,
        enabled_by_admin       = True,
        enabled_by_producer    = True,
        enabled_by_subproducer = True
    ).all()
    
    # Filtrar premium avatares con permisos aprobados
    approved_premium = []
    for avatar in premium_avatars:
        if has_approved_avatar_permission(user, avatar):
            approved_premium.append(avatar)
    
    # Avatares privados propios (solo si es creador)
    private_avatars = []
    if user.can_create_avatars():
        private_avatars = Avatar.query.filter_by(
            access_type            = AvatarAccessType.PRIVATE,
            created_by_id          = user.id,
            status                 = AvatarStatus.ACTIVE,
            enabled_by_admin       = True,
            enabled_by_producer    = True,
            enabled_by_subproducer = True
        ).all()
    
    # Combinar todas las listas y eliminar duplicados
    all_avatars = public_avatars + approved_premium + private_avatars
    return list(set(all_avatars))  # Eliminar duplicados potenciales


@user_bp.route('/dashboard')
@login_required
def dashboard():
    """
    Dashboard personalizado del usuario con estadísticas y actividad reciente.
    
    Proporciona una vista general de la actividad del usuario en el sistema,
    incluyendo estadísticas personalizadas según el rol y acceso a funcionalidades
    recientes. El contenido se adapta dinámicamente según los permisos del usuario.
    
    Returns:
        Template : 'user/dashboard.html' con estadísticas y datos de actividad
    
    Context Variables:
            - stats (dict)                     : Diccionario con estadísticas del usuario
            - reels_count (int)                : Número total de reels creados
            - commissions_count (int)          : Comisiones ganadas totales
            - avatars_count (int, condicional) : Avatares creados (solo si puede crearlos)
            - available_avatars_count (int)    : Avatares disponibles para usar
            - recent_reels (list)              : Lista de los 5 reels más recientes del usuario
            - available_avatars (list)         : Lista de avatares disponibles para preview
    
    Note:
        - Estadísticas se adaptan según el rol del usuario
        - Campo avatars_count solo aparece para usuarios con permisos de creación
        - Reels ordenados por fecha de creación descendente
        - Dashboard proporciona acceso rápido a funcionalidades principales
        - Diseño responsive para diferentes dispositivos
        - Available avatars incluye públicos y premium con permisos aprobados
    """
    # Estadísticas básicas
    stats = {
        'reels_count'        : current_user.reels.count(),
        'commissions_count'  : current_user.commissions_earned.count(),
    }
    
    # Agregar avatars si puede crearlos
    if current_user.can_create_avatars():
        stats['avatars_count'] = current_user.created_avatars.count()
    
    # Obtener avatares disponibles para el usuario
    available_avatars = get_available_avatars_for_user(current_user)
    stats['available_avatars_count'] = len(available_avatars)
    
    # Reels recientes - usar Reel.query para orden correcto
    from app.models.reel import Reel
    recent_reels = Reel.query.filter_by(creator_id=current_user.id).order_by(Reel.created_at.desc()).limit(5).all()
    
    return render_template('user/dashboard.html', 
                         stats             = stats, 
                         recent_reels      = recent_reels, 
                         available_avatars = available_avatars)


@user_bp.route('/avatars')
@login_required
def avatars():
    """
    Vista de todos los avatares disponibles para el usuario.
    
    Muestra una página completa con todos los avatares que el usuario
    puede utilizar, incluyendo públicos, premium con permisos y privados propios.
    
    Returns:
        Template: 'user/avatars.html' con lista completa de avatares
    
    Context Variables:
        - available_avatars (list) : Lista completa de avatares disponibles
        - avatar_count (int)       : Número total de avatares disponibles
    """
    available_avatars = get_available_avatars_for_user(current_user)
    
    return render_template('user/avatars.html', 
                         available_avatars = available_avatars,
                         avatar_count      = len(available_avatars))


@user_bp.route('/request-reel/<int:avatar_id>', methods=['GET', 'POST'])
@login_required
def request_reel(avatar_id):
    """
    Ruta para solicitar creación de un reel con un avatar específico.
    
    Permite a los usuarios finales solicitar la creación de un reel usando
    un avatar disponible. La solicitud requiere aprobación del productor
    propietario del avatar antes de proceder con la creación.
    
    Args:
        avatar_id (int): ID del avatar a usar para el reel
    
    Returns:
        GET : Template con formulario de solicitud de reel
        POST: Redirección con mensaje de confirmación tras crear solicitud
    
    Context Variables:
        - form (ReelRequestForm) : Formulario de solicitud de reel
        - avatar (Avatar)        : Información del avatar seleccionado
        - producer (Producer)    : Productor propietario del avatar
    
    Note:
        - Verifica que el usuario puede usar el avatar
        - Requiere aprobación del productor propietario
        - Crea notificación para el productor
        - Aplica para avatares públicos y premium con permisos
    """
    # Verificar que el avatar existe y está disponible para el usuario
    
    avatar            = Avatar.query.get_or_404(avatar_id)
    available_avatars = get_available_avatars_for_user(current_user)
    
    if avatar not in available_avatars:
        flash('No tienes permisos para usar este avatar.', 'error')
        return redirect(url_for('user.avatars'))
    
    # Verificar que el avatar tiene un productor propietario
    if not avatar.producer:
        flash('Este avatar no tiene un productor asignado.', 'error')
        return redirect(url_for('user.avatars'))
    
    form = ReelRequestForm()
    
    if form.validate_on_submit():
        
        try:
            # Procesar imagen de fondo (archivo subido tiene prioridad sobre URL)
            background_url = None
            if form.background_image.data:
                # Procesar archivo subido
                file = form.background_image.data
                if file and file.filename:
                    # Generar nombre único para el archivo
                    filename        = secure_filename(file.filename)
                    timestamp       = datetime.now().strftime('%Y%m%d_%H%M%S')
                    unique_filename = f"{timestamp}_{filename}"
                    
                    # Crear directorio si no existe
                    backgrounds_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'backgrounds')
                    os.makedirs(backgrounds_dir, exist_ok=True)
                    
                    # Guardar archivo
                    file_path = os.path.join(backgrounds_dir, unique_filename)
                    file.save(file_path)
                    
                    # Generar URL pública
                    background_url = url_for('static', filename=f'uploads/backgrounds/{unique_filename}', _external=True)
            elif form.background_url.data:
                # Usar URL proporcionada si no se subió archivo
                background_url = form.background_url.data
            
            # Crear la solicitud de reel como borrador
            reel_request       = ReelRequest(
                user_id        = current_user.id,
                avatar_id      = avatar_id,
                producer_id    = avatar.producer.id,
                title          = form.title.data,
                script         = form.script.data,
                voice_id       = form.voice_id.data if form.voice_id.data else None,
                speed          = float(request.form.get('speed', 1.0)),
                pitch          = int(request.form.get('pitch', 0)),
                background_url = background_url,
                resolution     = form.resolution.data,
                user_notes     = form.user_notes.data,
                status         = ReelRequestStatus.DRAFT,  # Ahora se crea como borrador
                config_data    = {
                    'requested_via': 'web_interface',
                    'user_agent'   : request.headers.get('User-Agent', 'Unknown')
                }
            )
            
            db.session.add(reel_request)
            db.session.commit()
            
            flash(
                f'Tu borrador de reel "{form.title.data}" ha sido guardado. '
                f'Puedes editarlo y enviarlo al productor cuando estés listo.',
                'success'
            )
            
            # Redirigir a la lista de mis reels para que pueda gestionar
            return redirect(url_for('user.my_reels'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear la solicitud: {str(e)}', 'error')
    
    # Pre-llenar el avatar_id en el formulario
    form.avatar_id.data = avatar_id
    
    return render_template('user/request_reel.html', 
                         form     = form, 
                         avatar   = avatar, 
                         producer = avatar.producer)


@user_bp.route('/request-producer', methods=['GET', 'POST'])
@login_required
def request_producer():
    """
    Ruta para solicitar convertirse en productor.
    
    Permite a los usuarios finales solicitar ser productores enviando
    información comercial y motivaciones. Solo pueden tener una solicitud
    activa por vez y no pueden solicitar si ya son productores.
    
    Methods:
        GET  : Muestra el formulario de solicitud
        POST : Procesa la solicitud de productor
    
    Form Data (POST):
        company_name (str)         : Nombre de la empresa o marca (requerido)
        business_type (str)        : Tipo de negocio o rubro (opcional)
        website (str)              : Sitio web de la empresa (opcional)
        expected_volume (str)      : Volumen esperado de videos/mes (opcional)
        motivation (str)           : Motivación y descripción (opcional)
    
    Returns:
        GET : Template 'user/request_producer.html' con estado actual
        POST: Redirección al dashboard con mensaje de confirmación
    
    Context Variables:
        approved (bool) : True si el usuario ya es productor
        existing (bool) : True si ya tiene solicitud pendiente
    
    Note:
        - Solo usuarios finales pueden hacer solicitudes
        - Una solicitud pendiente por usuario como máximo
        - Productores existentes ven mensaje de confirmación
        - Validación automática de datos requeridos
        - Estado inicial siempre es PENDING para revisión admin
    """
    # Verificar si ya es productor
    approved = current_user.is_producer()
    
    # Verificar si ya tiene una solicitud pendiente
    existing = ProducerRequest.user_has_pending_request(current_user.id)
    
    if request.method == 'POST' and not approved and not existing:
        # Obtener datos del formulario
        company_name    = request.form.get('company_name', '').strip()
        business_type   = request.form.get('business_type', '').strip()
        website         = request.form.get('website', '').strip()
        expected_volume = request.form.get('expected_volume', '').strip()
        motivation      = request.form.get('motivation', '').strip()
        
        # Validar campo obligatorio
        if not company_name:
            flash('El nombre de la empresa es obligatorio', 'error')
            return render_template('user/request_producer.html', 
                                 approved=approved, existing=existing)
        
        # Crear nueva solicitud
        producer_request = ProducerRequest(
            user_id         = current_user.id,
            company_name    = company_name,
            business_type   = business_type or None,
            website         = website or None,
            expected_volume = expected_volume or None,
            motivation      = motivation or None,
            status          = ProducerRequestStatus.PENDING
        )
        
        try:
            db.session.add(producer_request)
            db.session.commit()
            
            flash('Solicitud enviada correctamente. Te contactaremos pronto por email.', 'success')
            return redirect(url_for('user.dashboard'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al enviar la solicitud: {str(e)}', 'error')
    
    return render_template('user/request_producer.html', 
                         approved=approved, existing=existing)


# crear reel
@user_bp.route('/reels/create', methods=['GET', 'POST'])
@login_required
def create_reel():
    """
    Permite crear reels personalizados a todos los usuarios según sus permisos.
    
    Los usuarios pueden crear reels utilizando avatares disponibles según su rol:
    - Admin/Producer/Subproducer: pueden crear con cualquier avatar del sistema
    - Usuario final: solo puede crear con avatares públicos o premium con permiso aprobado
    
    Methods:
        GET  : Muestra el formulario de creación de reel
        POST : Procesa la creación del nuevo reel
    
    Form Data (POST):
        title (str)       : Título del reel (requerido)
        script (str)      : Texto que dirá el avatar (requerido)
        avatar_id (int)   : ID del avatar a usar (opcional)
    
    Returns:
        GET : Template 'user/reel_create.html' con formulario y lista de avatares
        POST: Redirección a 'my_reels' con mensaje de confirmación
    
    Context Variables:
        - avatars (list)           : Lista de avatares disponibles para selección
        - selected_avatar_id (int) : ID del avatar preseleccionado (si aplica)
        - title (str)              : Título prellenado en caso de error de validación
        - script (str)             : Script prellenado en caso de error de validación
    
    Validation:
        - Título y script son campos obligatorios
        - Avatar debe existir y estar activo
        - Usuario final debe tener permisos para usar avatares premium
        - Avatares privados solo accesibles por admin/producer/subproducer
    
    Note:
        - El reel se crea en estado PENDING para posterior procesamiento
        - El avatar_id puede ser NULL si no se selecciona ningún avatar
        - Validación de permisos diferenciada por rol de usuario
        - Rollback automático en caso de error durante la creación
    """
    
    # Determinar qué avatares puede ver el usuario
    selected_avatar_id = request.args.get('avatar_id')

    if current_user.is_admin() or current_user.is_producer() or current_user.is_subproducer():
        # Admin, productores y subproductores ven todos los avatares
        avatars = Avatar.query.order_by(Avatar.name).all()
    else:
        # Usuarios finales: avatares públicos + premium con permiso aprobado
        candidate_avatars = Avatar.query.filter(
            Avatar.status == AvatarStatus.ACTIVE,
            Avatar.access_type.in_([AvatarAccessType.PUBLIC, AvatarAccessType.PREMIUM])
        ).order_by(Avatar.name).all()

        avatars = [
            avatar for avatar in candidate_avatars
            if avatar.access_type == AvatarAccessType.PUBLIC or has_approved_avatar_permission(current_user, avatar)
        ]

    if request.method == 'POST':
        title          = request.form.get('title', '').strip()
        script         = request.form.get('script', '').strip()
        avatar_id_raw  = request.form.get('avatar_id')  # '' si no eligen nada
        voice_id       = request.form.get('voice_id', '').strip() or None
        resolution     = request.form.get('resolution', '1080p')

        # Parseo de velocidad y pitch (con valores por defecto seguros)
        try:
            voice_speed = float(request.form.get('speed', 1.0))
        except (TypeError, ValueError):
            voice_speed = 1.0

        try:
            voice_pitch = int(request.form.get('pitch', 0))
        except (TypeError, ValueError):
            voice_pitch = 0

        # Procesamiento de fondo personalizado
        background_url = None
        background_file = request.files.get('background_image')
        provided_background_url = request.form.get('background_url', '').strip()

        try:
            if background_file and background_file.filename:
                filename        = secure_filename(background_file.filename)
                timestamp       = datetime.now().strftime('%Y%m%d_%H%M%S')
                unique_filename = f"{timestamp}_{filename}"
                backgrounds_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'backgrounds')
                os.makedirs(backgrounds_dir, exist_ok=True)
                file_path = os.path.join(backgrounds_dir, unique_filename)
                background_file.save(file_path)
                background_url = url_for('static', filename=f'uploads/backgrounds/{unique_filename}', _external=True)
            elif provided_background_url:
                background_url = provided_background_url
        except Exception as upload_error:
            current_app.logger.error(f"Error guardando imagen de fondo: {upload_error}")
            flash('No se pudo guardar la imagen de fondo. Inténtalo nuevamente o usa una URL.', 'warning')

        if not title or not script:
            flash('Título y guion son obligatorios.', 'error')
            return render_template('user/reel_create.html', 
                                   title              = title, 
                                   script             = script,
                                   avatars            = avatars, 
                                   selected_avatar_id = avatar_id_raw,
                                   resolution         = resolution,
                                   voice_speed        = voice_speed,
                                   voice_pitch        = voice_pitch,
                                   voice_id           = voice_id,
                                   background_url     = background_url)

        # Si eligieron un avatar, validarlo y convertirlo a int
        avatar_id = None
        if avatar_id_raw:
            try:
                avatar = Avatar.query.get(int(avatar_id_raw))
                if not avatar:
                    flash('El avatar seleccionado no existe.', 'error')
                    return render_template('user/reel_create.html', 
                                           title              = title, 
                                           script             = script, 
                                           avatars            = avatars, 
                                           selected_avatar_id = avatar_id_raw)

                # Usuario final solo puede usar avatares públicos o premium aprobados
                if not (current_user.is_admin() or current_user.is_producer() or current_user.is_subproducer()):
                    if avatar.access_type == AvatarAccessType.PREMIUM:
                        
                        if not has_approved_avatar_permission(current_user, avatar):
                            flash('Necesitás la aprobación del productor para usar este avatar premium.', 'error')
                            return render_template('user/reel_create.html', 
                                                   title              = title, 
                                                   script             = script, 
                                                   avatars            = avatars, 
                                                   selected_avatar_id = avatar_id_raw)
                    
                    elif avatar.access_type != AvatarAccessType.PUBLIC:
                        flash('No tenés permiso para usar este avatar.', 'error')
                        return render_template('user/reel_create.html', 
                                               title              = title, 
                                               script             = script, 
                                               avatars            = avatars, 
                                               selected_avatar_id = avatar_id_raw)

                avatar_id = avatar.id
            except ValueError:
                flash('Avatar inválido.', 'error')
                return render_template('user/reel_create.html', 
                                       title              = title, 
                                       script             = script, 
                                       avatars            = avatars, 
                                       selected_avatar_id = avatar_id_raw,
                                       resolution         = resolution,
                                       voice_speed        = voice_speed,
                                       voice_pitch        = voice_pitch,
                                       voice_id           = voice_id,
                                       background_url     = background_url)

        r = Reel(
            title       = title,
            script      = script,
            creator_id  = current_user.id,
            owner_id    = current_user.id,
            avatar_id   = avatar_id,              # <- queda NULL si no eligieron
            status      = ReelStatus.PENDING,
            is_public   = False,
            resolution  = resolution or '1080p',
            background_type = 'image' if background_url else 'default',
            background_url  = background_url,
            voice_id        = voice_id,
            speed           = voice_speed,
            pitch           = voice_pitch
        )
        db.session.add(r)
        db.session.commit()

        flash('Reel creado correctamente.', 'success')
        return redirect(url_for('user.my_reels'))

    return render_template('user/reel_create.html', 
                           avatars            = avatars, 
                           selected_avatar_id = selected_avatar_id,
                           resolution         = request.args.get('resolution', '1080p'),
                           voice_speed        = 1.0,
                           voice_pitch        = 0,
                           voice_id           = None,
                           background_url     = None)

# ver reel
@user_bp.route('/reels/<int:reel_id>')
@login_required
def view_reel(reel_id):
    """
    Vista detallada de un reel individual con validación de permisos de acceso.
    
    Muestra información completa del reel incluyendo metadata, estado de procesamiento,
    avatar utilizado y opciones de descarga. Valida permisos antes de mostrar contenido.
    
    Args:
        reel_id (int): ID único del reel a visualizar
    
    Returns:
        Template: 'user/reel_view.html' con detalles completos del reel
        Redirect: A lista de reels si no tiene permisos de acceso
    
    Context Variables:
        - reel (Reel): Objeto Reel con toda la información del video
    
    Access Control:
        - Admin/Producer: acceso completo a todos los reels
        - Propietario: acceso completo a sus propios reels
        - Usuario final: solo acceso a reels públicos o propios
    
    Note:
        - Validación de permisos antes de mostrar contenido sensible
        - Mensaje flash informativo si acceso denegado
        - Redirección automática si usuario no autorizado
    """
    from app.models.reel import Reel

    reel = Reel.query.get_or_404(reel_id)

    # Validación de acceso
    if (
        not current_user.is_admin()
        and not current_user.is_producer()
        and reel.owner_id != current_user.id
        and not reel.is_public
    ):
        flash("No tenés permiso para ver este reel.", "danger")
        return redirect(url_for("user.my_reels"))

    return render_template('user/reel_view.html', reel=reel)

@user_bp.route('/avatares')
@login_required
def avatares():
    """
    Lista de avatares disponibles para usuarios finales con opciones de búsqueda y filtrado.
    
    Muestra avatares públicos y premium con información del estado de permisos,
    permitiendo solicitar acceso a avatares premium. Incluye funcionalidad de
    búsqueda por nombre y filtrado por tipo de acceso.
    
    Query Parameters:
        search (str, opcional)      : Término de búsqueda para filtrar por nombre
        access_type (str, opcional) : Filtro por tipo ('PUBLIC' o 'PREMIUM')
    
    Returns:
        Template: 'user/avatares.html' con lista de avatares y estados de permisos
    
    Context Variables:
        - avatars (list)           : Lista de avatares activos (públicos y premium)
        - permission_status (dict) : Diccionario con estado de permisos por avatar_id
            - status (str)       : Estado del permiso ('approved', 'rejected', 'pending', None)
            - request_id (str)   : ID de la solicitud de permiso
            - reason (str)       : Razón de la solicitud o rechazo
            - requested_at (str) : Fecha de la solicitud
    
    Features:
        - Búsqueda por nombre (case-insensitive)
        - Filtrado por tipo de acceso (público/premium)
        - Refresh automático de meta_data para datos actualizados
        - Estado de permisos en tiempo real
        - Ordenamiento alfabético por nombre
    
    Note:
        - Solo muestra avatares activos (no privados)
        - Meta_data se recarga desde BD para garantizar datos frescos
        - Permission_status incluye historial completo de solicitudes por usuario
    """
    # Query base: avatares activos que no sean privados
    query = Avatar.query.filter(
        Avatar.status == AvatarStatus.ACTIVE,
        Avatar.access_type.in_([AvatarAccessType.PUBLIC, AvatarAccessType.PREMIUM])
    )
    
    # Aplicar filtro por nombre (búsqueda)
    search = request.args.get('search', '').strip()
    if search:
        query = query.filter(Avatar.name.ilike(f'%{search}%'))
    
    # Aplicar filtro por tipo de acceso
    access_type = request.args.get('access_type', '').upper()
    if access_type == 'PUBLIC':
        query = query.filter(Avatar.access_type == AvatarAccessType.PUBLIC)
    elif access_type == 'PREMIUM':
        query = query.filter(Avatar.access_type == AvatarAccessType.PREMIUM)
    
    avatars = query.order_by(Avatar.name).all()

    # Forzar refresh de datos desde la BD para obtener meta_data actualizado
    permission_status = {}
    for avatar in avatars:
        db.session.refresh(avatar)  # Recarga meta_data desde BD
        permission_status[avatar.id] = get_user_permission_status(current_user, avatar)

    return render_template('user/avatares.html', 
                           avatars           = avatars, 
                           permission_status = permission_status)

@user_bp.route('/avatares/<int:avatar_id>/request-permission', methods=['POST'])
@login_required
def request_avatar_permission(avatar_id):
    """
    Procesa la solicitud de permiso para usar un avatar premium.
    Guarda la solicitud en meta_data del avatar y notifica al productor.
    
    Methods:
        POST : Procesa la solicitud de permiso
    
    Args:
        avatar_id (int): ID del avatar premium para el cual se solicita permiso
    
    Returns:
        Redirección a la lista de avatares con mensaje de confirmación
    
    """
    avatar = Avatar.query.get_or_404(avatar_id)
    
    # Validar que sea premium
    if avatar.access_type != AvatarAccessType.PREMIUM:
        flash('Solo puedes solicitar permisos para avatares premium.', 'error')
        return redirect(url_for('user.avatares'))
    
    reason = request.form.get('reason', '').strip()
    
    # Guardar solicitud en meta_data
    if not avatar.meta_data:
        avatar.meta_data = {}

    permission_requests = avatar.meta_data.setdefault('permission_requests', [])

    request_entry = None
    for existing in permission_requests:
        if existing.get('user_id') == current_user.id and existing.get('status', 'pending') == 'pending':
            existing['reason']       = reason
            existing['requested_at'] = datetime.utcnow().isoformat()
            existing['request_id']   = existing.get('request_id') or uuid4().hex
            request_entry            = existing
            break

    if not request_entry:
        request_entry = {
            'request_id'  : uuid4().hex,
            'user_id'     : current_user.id,
            'user_name'   : current_user.full_name,
            'user_email'  : current_user.email,
            'producer_id' : avatar.producer_id,
            'reason'      : reason,
            'requested_at': datetime.utcnow().isoformat(),
            'status'      : 'pending'
        }
        permission_requests.append(request_entry)

    # Marcar como modificado para que SQLAlchemy detecte el cambio en JSON
    from sqlalchemy.orm.attributes import flag_modified
    flag_modified(avatar, 'meta_data')
    
    db.session.commit()
    
    # Enviar email al productor notificando la solicitud
    try:
        from app.services.email_service import send_template_email
        
        # Obtener el productor propietario del avatar
        producer = avatar.created_by  # El creador del avatar
        
        if producer and producer.email:
            # Links directos al panel de productor (el decorador se encargará de pedir login si es necesario)
            producer_dashboard = url_for('producer.dashboard', _external=True)
            avatar_detail = url_for('producer.avatar_detail', avatar_id=avatar.id, _external=True)

            send_template_email(
                template_name  = 'avatar_permission_request',
                subject        = f'🙋 Nueva solicitud de permiso para tu avatar "{avatar.name}"',
                recipients     = [producer.email],
                template_vars  = {
                    'producer_name'     : producer.full_name,
                    'user_name'         : current_user.full_name,
                    'user_email'        : current_user.email,
                    'avatar_name'       : avatar.name,
                    'avatar_thumbnail'  : avatar.thumbnail_url,
                    'reason'            : reason if reason else 'No especificado',
                    'request_date'      : datetime.utcnow().strftime('%d/%m/%Y %H:%M'),
                    'avatar_detail_link': avatar_detail,
                    'dashboard_link'    : producer_dashboard,
                    'current_year'      : datetime.utcnow().year
                }
            )
    except Exception as e:
        # Log error pero no interrumpir el flujo
        current_app.logger.error(f'Error enviando email de solicitud de permiso: {str(e)}')
    
    flash(f'Solicitud enviada para el avatar "{avatar.name}". El productor será notificado.', 'success')
    return redirect(url_for('user.avatares'))


# ============================================================================
# GESTIÓN DE REELS DEL USUARIO
# ============================================================================

@user_bp.route('/my-reels')
@login_required
def my_reels():
    """
    Vista de gestión de solicitudes de reels del usuario.
    
    Muestra una vista organizada de todas las solicitudes de reels del usuario,
    separadas en dos categorías: borradores (editables) y enviadas (en revisión
    o procesadas). Permite al usuario gestionar el ciclo completo de sus solicitudes.
    
    Returns:
        Template: 'user/my_reels.html' con listado organizado de solicitudes
    
    Context Variables:
        - drafts (list)         : Lista de ReelRequest con status=DRAFT
        - sent (list)           : Lista de ReelRequest con status!=DRAFT
        - total_requests (int)  : Número total de solicitudes del usuario
    
    Categories:
        Drafts (Borradores):
            - Status: DRAFT
            - Acciones: Editar, Eliminar, Enviar
            - Descripción: Solicitudes guardadas pero no enviadas
        
        Sent (Enviadas):
            - Status: PENDING, APPROVED, REJECTED, EXPIRED
            - Acciones: Ver detalles, reenviar (si rechazado)
            - Descripción: Solicitudes en revisión o procesadas
    
    Features:
        - Ordenamiento por fecha de creación (más reciente primero)
        - Badges de estado visual para cada solicitud
        - Acciones contextuales según estado
        - Contador total de solicitudes
    
    Note:
        - Solo muestra solicitudes del usuario actual
        - Incluye todas las solicitudes históricas
        - Interface optimizada para gestión rápida
    """
    # Obtener todos los reel requests del usuario
    reel_requests = ReelRequest.query.filter_by(user_id=current_user.id).order_by(ReelRequest.created_at.desc()).all()
    
    # Separar por estado
    drafts = [r for r in reel_requests if r.status == ReelRequestStatus.DRAFT]
    sent = [r for r in reel_requests if r.status != ReelRequestStatus.DRAFT]
    
    # Obtener información de voces seleccionadas
    voice_info_map = {}  # {voice_id: {'name': str, 'preview_audio': str}}
    
    # Recopilar todos los voice_ids únicos con su productor asociado
    voice_data = {}  # {voice_id: producer_api_key}
    for req in reel_requests:
        if req.voice_id and req.producer and req.producer.heygen_api_key:
            voice_data[req.voice_id] = req.producer.heygen_api_key
    
    # Obtener información completa de voces desde HeyGen usando el primer API key disponible
    if voice_data:
        try:
            # Usar el primer API key disponible (todas las voces son compartidas en HeyGen)
            first_api_key = next(iter(voice_data.values()))
            heygen_service = HeyGenService(first_api_key)
            
            for voice_id in voice_data.keys():
                try:
                    voice_info = heygen_service.get_voice_details(voice_id)
                    if voice_info:
                        voice_info_map[voice_id] = {
                            'name': voice_info.get('name', voice_id),
                            'preview_audio': voice_info.get('preview_audio', voice_info.get('preview_audio_url', ''))
                        }
                    else:
                        voice_info_map[voice_id] = {
                            'name': voice_id,
                            'preview_audio': ''
                        }
                except Exception as e:
                    logger.warning(f"No se pudo obtener info de voz {voice_id}: {e}")
                    voice_info_map[voice_id] = {
                        'name': voice_id,
                        'preview_audio': ''
                    }
        except Exception as e:
            logger.error(f"Error al obtener información de voces: {e}")
    
    return render_template('user/my_reels.html', 
                         drafts         = drafts, 
                         sent           = sent,
                         total_requests = len(reel_requests),
                         voice_info     = voice_info_map)


@user_bp.route('/reel-request/<int:request_id>/edit', methods=['GET', 'POST'])
@login_required
def edit_reel_request(request_id):
    """
    Edita una solicitud de reel en estado borrador o rechazada.
    
    Permite al usuario modificar los detalles de su solicitud de reel
    antes de enviarla al productor. Si la solicitud fue rechazada,
    permite editarla para reenviarla.
    
    Args:
        request_id (int): ID de la solicitud de reel a editar
    
    Methods:
        GET  : Muestra formulario prellenado con datos actuales
        POST : Procesa la actualización de la solicitud
    
    Form Data (POST):
        title (str)              : Título actualizado del reel
        script (str)             : Script actualizado
        voice_id (str, opcional) : ID de voz seleccionada
        background_url (str)     : URL de fondo (opcional)
        background_image (file)  : Imagen de fondo (opcional)
        resolution (str)         : Resolución deseada
        user_notes (str)         : Notas para el productor
    
    Returns:
        GET : Template 'user/edit_reel_request.html' con formulario
        POST: Redirección a 'my_reels' con mensaje de confirmación
    
    Context Variables:
        - form (ReelRequestForm) : Formulario prellenado
        - reel_request (ReelRequest) : Solicitud actual
        - avatar (Avatar) : Avatar asociado a la solicitud
    
    Validation:
        - Verifica propiedad de la solicitud
        - Solo permite editar borradores o rechazadas
        - Valida permisos de acceso al avatar
    
    Special Behavior:
        - Si era REJECTED, cambia a DRAFT al guardar
        - Limpia producer_notes al convertir a borrador
        - Mantiene background_url actual si no se proporciona nuevo
        - Archivo subido tiene prioridad sobre URL
    
    Note:
        - Actualiza timestamp updated_at automáticamente
        - Rollback automático en caso de error
        - Mensajes flash informativos para feedback
    """
    reel_request = ReelRequest.query.get_or_404(request_id)
    
    # Verificar que es del usuario y que puede editarse
    if reel_request.user_id != current_user.id:
        flash('No tienes permisos para editar esta solicitud.', 'error')
        return redirect(url_for('user.my_reels'))
    
    if not reel_request.can_be_edited():
        flash('Esta solicitud ya no puede editarse.', 'warning')
        return redirect(url_for('user.my_reels'))
    
    form = ReelRequestForm()
    
    if form.validate_on_submit():
        try:
            # Procesar imagen de fondo (archivo subido tiene prioridad sobre URL)
            background_url = reel_request.background_url  # Mantener URL actual si no se proporciona nueva
            if form.background_image.data:
                # Procesar archivo subido
                file = form.background_image.data
                if file and file.filename:
                    # Generar nombre único para el archivo
                    filename        = secure_filename(file.filename)
                    timestamp       = datetime.now().strftime('%Y%m%d_%H%M%S')
                    unique_filename = f"{timestamp}_{filename}"
                    
                    # Crear directorio si no existe
                    backgrounds_dir = os.path.join(current_app.root_path, 'static', 'uploads', 'backgrounds')
                    os.makedirs(backgrounds_dir, exist_ok=True)
                    
                    # Guardar archivo
                    file_path = os.path.join(backgrounds_dir, unique_filename)
                    file.save(file_path)
                    
                    # Generar URL pública
                    background_url = url_for('static', filename=f'uploads/backgrounds/{unique_filename}', _external=True)
            elif form.background_url.data:
                # Usar URL proporcionada si no se subió archivo
                background_url = form.background_url.data
            
            # Actualizar campos
            reel_request.title          = form.title.data
            reel_request.script         = form.script.data
            reel_request.voice_id       = form.voice_id.data if form.voice_id.data else None
            reel_request.speed          = float(request.form.get('speed', 1.0))
            reel_request.pitch          = int(request.form.get('pitch', 0))
            reel_request.background_url = background_url
            reel_request.resolution     = form.resolution.data
            reel_request.user_notes     = form.user_notes.data
            reel_request.updated_at     = datetime.utcnow()
            
            # Si era rechazado, volver a borrador para que pueda enviarse nuevamente
            if reel_request.status == ReelRequestStatus.REJECTED:
                reel_request.status         = ReelRequestStatus.DRAFT
                reel_request.producer_notes = None  # Limpiar notas del productor
            
            db.session.commit()
            
            flash(f'Borrador "{reel_request.title}" actualizado.', 'success')
            return redirect(url_for('user.my_reels'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar: {str(e)}', 'error')
    
    # Pre-llenar el formulario con datos existentes
    if request.method == 'GET':
        form.title.data          = reel_request.title
        form.script.data         = reel_request.script
        form.voice_id.data       = reel_request.voice_id
        form.background_url.data = reel_request.background_url
        form.resolution.data     = reel_request.resolution
        form.user_notes.data     = reel_request.user_notes
        form.avatar_id.data      = reel_request.avatar_id
        form.speed.data          = reel_request.speed
        form.pitch.data          = reel_request.pitch
    
    return render_template('user/edit_reel_request.html', 
                         form         = form, 
                         reel_request = reel_request,
                         avatar       = reel_request.avatar)


@user_bp.route('/reel-request/<int:request_id>/delete', methods=['POST'])
@login_required
def delete_reel_request(request_id):
    """
    Elimina permanentemente una solicitud de reel en estado borrador.
    
    Permite al usuario eliminar solicitudes que aún no han sido enviadas
    al productor. Solo se pueden eliminar borradores (status=DRAFT).
    
    Args:
        request_id (int): ID de la solicitud de reel a eliminar
    
    Methods:
        POST : Procesa la eliminación de la solicitud
    
    Returns:
        Redirect: A 'my_reels' con mensaje de confirmación
    
    Validation:
        - Verifica que la solicitud existe (404 si no)
        - Valida propiedad del usuario
        - Solo permite eliminar si can_be_deleted() retorna True
        - Generalmente solo DRAFT puede eliminarse
    
    Note:
        - Eliminación permanente (no soft delete)
        - Rollback automático en caso de error
        - Guarda el título antes de eliminar para mensaje
        - No se pueden eliminar solicitudes ya procesadas
    """
    reel_request = ReelRequest.query.get_or_404(request_id)
    
    # Verificar permisos
    if reel_request.user_id != current_user.id:
        flash('No tienes permisos para eliminar esta solicitud.', 'error')
        return redirect(url_for('user.my_reels'))
    
    if not reel_request.can_be_deleted():
        flash('Esta solicitud ya no puede eliminarse.', 'warning')
        return redirect(url_for('user.my_reels'))
    
    try:
        title = reel_request.title
        db.session.delete(reel_request)
        db.session.commit()
        
        flash(f'Borrador "{title}" eliminado.', 'info')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar: {str(e)}', 'error')
    
    return redirect(url_for('user.my_reels'))


@user_bp.route('/reel-request/<int:request_id>/send', methods=['POST'])
@login_required
def send_reel_request(request_id):
    """
    Envía una solicitud de reel al productor para su revisión y aprobación.
    
    Cambia el estado de la solicitud de DRAFT a PENDING y envía notificación
    por email al productor propietario del avatar para que revise y apruebe
    o rechace la solicitud.
    
    Args:
        request_id (int): ID de la solicitud de reel a enviar
    
    Methods:
        POST : Procesa el envío de la solicitud
    
    Returns:
        Redirect: A 'my_reels' con mensaje de confirmación
    
    Workflow:
        1. Valida permisos y estado de la solicitud
        2. Llama a send_to_producer() para cambiar estado a PENDING
        3. Envía email de notificación al productor
        4. Muestra mensaje de éxito (con o sin confirmación de email)
    
    Email Notification:
        - Template      : 'reel_request_notification'
        - Destinatario  : Productor propietario del avatar
        - Incluye       : Detalles de la solicitud y link al panel
    
    Validation:
        - Verifica propiedad de la solicitud
        - Solo permite enviar si status=DRAFT
        - Productor debe existir y tener email válido
    
    Note:
        - Email se envía con manejo de errores robusto
        - Si falla el email, la solicitud se guarda igual
        - Mensaje diferenciado si email no pudo enviarse
        - Logging de errores para debugging
    """
    reel_request = ReelRequest.query.get_or_404(request_id)
    
    # Verificar permisos
    if reel_request.user_id != current_user.id:
        flash('No tienes permisos para enviar esta solicitud.', 'error')
        return redirect(url_for('user.my_reels'))
    
    if reel_request.status != ReelRequestStatus.DRAFT:
        flash('Solo se pueden enviar borradores.', 'warning')
        return redirect(url_for('user.my_reels'))
    
    try:
        # Marcar como enviado
        reel_request.send_to_producer(current_user)
        db.session.commit()
        
        # Enviar email al productor
        email_sent = False
        try:
            success = send_avatar_reel_request_notification(
                producer     = reel_request.producer,
                reel_request =reel_request
            )
            if success:
                email_sent = True
            else:
                logger.warning(f"Error enviando email de solicitud de reel a {reel_request.producer.user.email}")
        except Exception as e:
            logger.error(f"Excepción enviando email de solicitud de reel: {str(e)}")
        
        # Mensaje de éxito con información del email
        if email_sent:
            flash(
                f'Solicitud "{reel_request.title}" enviada a {reel_request.producer.company_name}. '
                f'Recibirás una notificación cuando sea revisada.',
                'success'
            )
        else:
            flash(
                f'Solicitud "{reel_request.title}" enviada a {reel_request.producer.company_name}. '
                f'La solicitud fue guardada pero no se pudo enviar la notificación por email.',
                'warning'
            )
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error al enviar la solicitud: {str(e)}', 'error')
    
    return redirect(url_for('user.my_reels'))

