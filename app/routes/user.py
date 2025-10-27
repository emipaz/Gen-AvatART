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
import os
from PIL import Image

# Crear el blueprint
user_bp = Blueprint('user', __name__, url_prefix='/user')

# Formulario para el perfil
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField, FileField
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
    
    # Campos para cambiar contraseña
    current_password = PasswordField('Contraseña Actual',          validators = [Optional()])
    new_password     = PasswordField('Nueva Contraseña' ,          validators = [Optional(), Length(min=6)])
    confirm_password = PasswordField('Confirmar Nueva Contraseña', validators = [EqualTo('new_password', message = 'Las contraseñas deben coincidir')])
    
    submit = SubmitField('Guardar Cambios')

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
        - Directorio: /static/uploads/avatars/
        - Formato final: user_{id}_{original_name}.ext
        - Redimensionamiento: 300x300 con thumbnail para mantener aspecto
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
        first_name (str)      : Nombre del usuario
        last_name (str)       : Apellido del usuario  
        email (str)           : Email (validado por unicidad)
        phone (str, opcional) : Teléfono de contacto
        avatar (file, opcional): Imagen de perfil (JPG, PNG, JPEG)
        current_password (str, opcional): Contraseña actual para verificación
        new_password (str, opcional): Nueva contraseña si se desea cambiar
        confirm_password (str, opcional): Confirmación de nueva contraseña
    
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
            
            # Procesar avatar si se subió uno nuevo
            if form.avatar.data:
                print(f"DEBUG: Procesando avatar para usuario {current_user.id}")
                avatar_url = save_avatar(form.avatar.data)
                print(f"DEBUG: Avatar URL resultado: {avatar_url}")
                if avatar_url:
                    current_user.avatar_url = avatar_url
                    print(f"DEBUG: Avatar URL asignado a current_user: {current_user.avatar_url}")
            
            # Cambiar contraseña si se proporcionó
            if form.current_password.data:
                if current_user.check_password(form.current_password.data):
                    if form.new_password.data:
                        current_user.set_password(form.new_password.data)
                        flash('Contraseña actualizada correctamente', 'success')
                    else:
                        flash('Debe proporcionar una nueva contraseña', 'error')
                        return render_template('user/profile.html', form=form)
                else:
                    flash('Contraseña actual incorrecta', 'error')
                    return render_template('user/profile.html', form=form)
            
            # Guardar cambios
            print(f"DEBUG: Antes del commit - user.avatar_url: {current_user.avatar_url}")
            db.session.commit()
            print(f"DEBUG: Después del commit - user.avatar_url: {current_user.avatar_url}")
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
            - recent_reels (list)              : Lista de los 5 reels más recientes del usuario
    
    Note:
        - Estadísticas se adaptan según el rol del usuario
        - Campo avatars_count solo aparece para usuarios con permisos de creación
        - Reels ordenados por fecha de creación descendente
        - Dashboard proporciona acceso rápido a funcionalidades principales
        - Diseño responsive para diferentes dispositivos
    """
    # Estadísticas básicas
    stats = {
        'reels_count': current_user.reels.count(),
        'commissions_count': current_user.commissions_earned.count(),
    }
    
    # Agregar avatars si puede crearlos
    if current_user.can_create_avatars():
        stats['avatars_count'] = current_user.created_avatars.count()
    
    # Reels recientes
    recent_reels = current_user.reels.order_by(db.desc('created_at')).limit(5).all()
    
    return render_template('user/dashboard.html', stats=stats, recent_reels=recent_reels)

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

# listar reels
@user_bp.route('/reels')
@login_required
def reels():
    """
    Lista los reels visibles para el usuario actual.
    - Admin: ve todos
    - Producer/Subproducer: ve los creados por sí mismo
    - Final user: ve los propios y los públicos
    """
    if current_user.is_admin():
        reels = Reel.query.order_by(Reel.created_at.desc()).all()
    elif current_user.is_producer() or current_user.is_subproducer():
        reels = Reel.query.filter_by(creator_id=current_user.id).order_by(Reel.created_at.desc()).all()
    else:
        reels = Reel.query.filter(
            (Reel.owner_id == current_user.id) | (Reel.is_public == True)
        ).order_by(Reel.created_at.desc()).all()

    return render_template('user/reels.html', reels=reels)

# crear reel
@user_bp.route('/reels/create', methods=['GET', 'POST'])
@login_required
def create_reel():
    # Solo pueden crear: admin / productor / subproductor
    if not (current_user.is_producer() or current_user.is_subproducer() or current_user.is_admin()):
        flash('No tenés permisos para crear reels.', 'error')
        return redirect(url_for('user.reels'))

    from app.models.avatar import Avatar  # <- asegurar import
    avatars = Avatar.query.order_by(Avatar.name).all()  # para el <select>

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        script = request.form.get('script', '').strip()
        avatar_id_raw = request.form.get('avatar_id')  # '' si no eligen nada

        if not title or not script:
            flash('Título y guion son obligatorios.', 'error')
            return render_template('user/reel_create.html', title=title, script=script, avatars=avatars)

        # Si eligieron un avatar, validarlo y convertirlo a int
        avatar_id = None
        if avatar_id_raw:
            try:
                avatar = Avatar.query.get(int(avatar_id_raw))
                if not avatar:
                    flash('El avatar seleccionado no existe.', 'error')
                    return render_template('user/reel_create.html', title=title, script=script, avatars=avatars)
                avatar_id = avatar.id
            except ValueError:
                flash('Avatar inválido.', 'error')
                return render_template('user/reel_create.html', title=title, script=script, avatars=avatars)

        r = Reel(
            title=title,
            script=script,
            creator_id=current_user.id,
            owner_id=current_user.id,
            avatar_id=avatar_id,              # <- queda NULL si no eligieron
            status=ReelStatus.PENDING,
            is_public=False,
            resolution='1080p',
            background_type='default'
        )
        db.session.add(r)
        db.session.commit()

        flash('Reel creado correctamente.', 'success')
        return redirect(url_for('user.reels'))

    return render_template('user/reel_create.html', avatars=avatars)

# ver reel
@user_bp.route('/reels/<int:reel_id>')
@login_required
def view_reel(reel_id):
    """Vista detallada de un reel individual."""
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
        return redirect(url_for("user.reels"))

    return render_template('user/reel_view.html', reel=reel)

