from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models.user import User
import os
from PIL import Image

# Crear el blueprint
user_bp = Blueprint('user', __name__, url_prefix='/user')

# Formulario para el perfil
from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email, Length, EqualTo, Optional

class ProfileForm(FlaskForm):
    first_name = StringField('Nombre', validators=[DataRequired(), Length(min=2, max=50)])
    last_name = StringField('Apellido', validators=[DataRequired(), Length(min=2, max=50)])
    email = StringField('Email', validators=[DataRequired(), Email()])
    phone = StringField('Teléfono', validators=[Optional(), Length(max=20)])
    avatar = FileField('Avatar', validators=[FileAllowed(['jpg', 'png', 'jpeg'], 'Solo imágenes!')])
    
    # Campos para cambiar contraseña
    current_password = PasswordField('Contraseña Actual', validators=[Optional()])
    new_password = PasswordField('Nueva Contraseña', validators=[Optional(), Length(min=6)])
    confirm_password = PasswordField('Confirmar Nueva Contraseña', 
                                   validators=[EqualTo('new_password', message='Las contraseñas deben coincidir')])
    
    submit = SubmitField('Guardar Cambios')

def save_avatar(form_avatar):
    """Guarda el avatar del usuario"""
    if not form_avatar:
        return None
    
    # Crear directorio si no existe
    upload_folder = os.path.join(current_app.root_path, 'static', 'uploads', 'avatars')
    os.makedirs(upload_folder, exist_ok=True)
    
    # Generar nombre único
    filename = secure_filename(form_avatar.filename)
    name, ext = os.path.splitext(filename)
    filename = f"user_{current_user.id}_{name}{ext}"
    
    # Ruta completa
    file_path = os.path.join(upload_folder, filename)
    
    # Redimensionar y guardar imagen
    try:
        image = Image.open(form_avatar)
        # Redimensionar a 300x300 manteniendo aspecto
        image.thumbnail((300, 300), Image.Resampling.LANCZOS)
        
        # Convertir a RGB si es RGBA
        if image.mode == 'RGBA':
            image = image.convert('RGB')
        
        image.save(file_path, optimize=True, quality=85)
        
        # Retornar URL relativa
        return f"/static/uploads/avatars/{filename}"
    
    except Exception as e:
        flash(f'Error al procesar la imagen: {str(e)}', 'error')
        return None

@user_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Perfil del usuario"""
    form = ProfileForm()
    
    if form.validate_on_submit():
        try:
            # Actualizar datos básicos
            current_user.first_name = form.first_name.data
            current_user.last_name = form.last_name.data
            current_user.phone = form.phone.data
            
            # Verificar si el email cambió y si ya existe
            if form.email.data != current_user.email:
                existing_user = User.query.filter_by(email=form.email.data).first()
                if existing_user:
                    flash('El email ya está en uso por otro usuario', 'error')
                    return render_template('user/profile.html', form=form)
                current_user.email = form.email.data
            
            # Procesar avatar si se subió uno nuevo
            if form.avatar.data:
                avatar_url = save_avatar(form.avatar.data)
                if avatar_url:
                    current_user.avatar_url = avatar_url
            
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
            db.session.commit()
            flash('Perfil actualizado correctamente', 'success')
            return redirect(url_for('user.profile'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar el perfil: {str(e)}', 'error')
    
    # Prellenar formulario con datos actuales
    if request.method == 'GET':
        form.first_name.data = current_user.first_name
        form.last_name.data = current_user.last_name
        form.email.data = current_user.email
        form.phone.data = current_user.phone
    
    return render_template('user/profile.html', form=form)

@user_bp.route('/dashboard')
@login_required
def dashboard():
    """Dashboard del usuario"""
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