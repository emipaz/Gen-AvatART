from flask import Blueprint, render_template, request, flash, redirect, url_for, jsonify
from flask_login import login_user, logout_user, login_required, current_user
from werkzeug.security import check_password_hash
from app import db
from app.models.user import User, UserRole, UserStatus
from app.models.producer import Producer

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Página de inicio de sesión"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = bool(request.form.get('remember'))
        
        if not email or not password:
            flash('Por favor completa todos los campos', 'error')
            return render_template('auth/login.html')
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.check_password(password):
            if user.status != UserStatus.ACTIVE:
                flash('Tu cuenta está pendiente de aprobación o ha sido suspendida', 'warning')
                return render_template('auth/login.html')
            
            login_user(user, remember=remember)
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            # Redirigir según el rol
            next_page = request.args.get('next')
            if next_page:
                return redirect(next_page)
            
            if user.is_admin():
                return redirect(url_for('admin.dashboard'))
            elif user.is_producer():
                return redirect(url_for('producer.dashboard'))
            elif user.is_subproducer():
                return redirect(url_for('subproducer.dashboard'))
            else:  # affiliate
                return redirect(url_for('affiliate.dashboard'))
        else:
            flash('Email o contraseña incorrectos', 'error')
    
    return render_template('auth/login.html')

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    """Registro de nuevos usuarios (solo afiliados públicos)"""
    if current_user.is_authenticated:
        return redirect(url_for('main.dashboard'))
    
    if request.method == 'POST':
        email = request.form.get('email')
        username = request.form.get('username')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')
        
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
        
        # Crear nuevo usuario
        user = User(
            email=email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            phone=phone,
            role=UserRole.AFFILIATE,
            status=UserStatus.PENDING
        )
        user.set_password(password)
        
        db.session.add(user)
        db.session.commit()
        
        flash('Registro exitoso. Tu cuenta está pendiente de aprobación.', 'success')
        return redirect(url_for('auth.login'))
    
    return render_template('auth/register.html')

@auth_bp.route('/register/invite/<token>')
def register_invite(token):
    """Registro por invitación"""
    # TODO: Implementar sistema de tokens de invitación
    # Por ahora, simplemente redirigir al registro normal
    return redirect(url_for('auth.register'))

@auth_bp.route('/logout')
@login_required
def logout():
    """Cerrar sesión"""
    logout_user()
    flash('Has cerrado sesión exitosamente', 'info')
    return redirect(url_for('main.index'))

@auth_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    """Perfil del usuario"""
    if request.method == 'POST':
        current_user.first_name = request.form.get('first_name', current_user.first_name)
        current_user.last_name = request.form.get('last_name', current_user.last_name)
        current_user.phone = request.form.get('phone', current_user.phone)
        
        # Si es productor, actualizar información comercial
        if current_user.is_producer() and current_user.producer_profile:
            producer = current_user.producer_profile
            producer.company_name = request.form.get('company_name', producer.company_name)
            producer.business_type = request.form.get('business_type', producer.business_type)
            producer.website = request.form.get('website', producer.website)
        
        db.session.commit()
        flash('Perfil actualizado exitosamente', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/profile.html', user=current_user)

@auth_bp.route('/change-password', methods=['GET', 'POST'])
@login_required
def change_password():
    """Cambiar contraseña"""
    if request.method == 'POST':
        current_password = request.form.get('current_password')
        new_password = request.form.get('new_password')
        confirm_password = request.form.get('confirm_password')
        
        if not current_user.check_password(current_password):
            flash('La contraseña actual es incorrecta', 'error')
            return render_template('auth/change_password.html')
        
        if new_password != confirm_password:
            flash('Las nuevas contraseñas no coinciden', 'error')
            return render_template('auth/change_password.html')
        
        if len(new_password) < 6:
            flash('La nueva contraseña debe tener al menos 6 caracteres', 'error')
            return render_template('auth/change_password.html')
        
        current_user.set_password(new_password)
        db.session.commit()
        
        flash('Contraseña cambiada exitosamente', 'success')
        return redirect(url_for('auth.profile'))
    
    return render_template('auth/change_password.html')

@auth_bp.route('/api/validate-username')
def validate_username():
    """API para validar si un username está disponible"""
    username = request.args.get('username')
    if not username:
        return jsonify({'valid': False, 'message': 'Username requerido'})
    
    user = User.query.filter_by(username=username).first()
    if user:
        return jsonify({'valid': False, 'message': 'Username no disponible'})
    
    return jsonify({'valid': True, 'message': 'Username disponible'})

@auth_bp.route('/api/validate-email')
def validate_email():
    """API para validar si un email está disponible"""
    email = request.args.get('email')
    if not email:
        return jsonify({'valid': False, 'message': 'Email requerido'})
    
    user = User.query.filter_by(email=email).first()
    if user:
        return jsonify({'valid': False, 'message': 'Email no disponible'})
    
    return jsonify({'valid': True, 'message': 'Email disponible'})

# Importar datetime para uso en el login
from datetime import datetime