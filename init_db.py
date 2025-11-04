#!/usr/bin/env python3
"""
Script de inicialización de base de datos para la aplicación Gen-AvatART.

Este script automatiza el proceso de configuración inicial de la aplicación,
creando la estructura de base de datos y estableciendo un usuario administrador
para el primer acceso al sistema.

El módulo incluye:
    - Función init_database()    : Inicializa la estructura de BD completa
    - Función create_admin_user(): Crea el usuario administrador inicial
    - Función main()            : Punto de entrada con validaciones

Funcionalidades principales:
    - Creación automática de todas las tablas de la BD
    - Validación de configuración de entorno (.env)
    - Creación interactiva de usuario administrador
    - Validaciones de datos únicos (email, username)
    - Manejo de errores y feedback al usuario
    - Verificación de administradores existentes

Uso:
    python init_db.py

Note:
    - Requiere archivo .env configurado
    - Solo crea un administrador si no existe ninguno
    - Valida contraseñas y unicidad de datos
"""

import os
import sys
from getpass import getpass

# Agregar el directorio del proyecto al path para importaciones
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_admin_user():
    """
    Crea un usuario administrador inicial para la aplicación.
    
    Esta función permite establecer el primer usuario con permisos
    administrativos completos, necesario para acceder al sistema
    por primera vez y gestionar otros usuarios.
    
    Returns:
        None
    
    Raises:
        Exception: Si hay errores de base de datos o validación
    
    Note:
        - Solo se ejecuta si no existe ningún administrador
        - Solicita datos interactivamente al usuario
        - Valida unicidad de email y username
        - Requiere contraseña mínima de 6 caracteres
        - Confirma contraseña para evitar errores de tipeo
    """
    from app import create_app, db
    from app.models.user import User, UserRole, UserStatus
    
    app = create_app()
    
    with app.app_context():
        print("=== Creación de Usuario Administrador ===")
        
        # Verificar si ya existe un admin
        existing_admin = User.query.filter_by(role=UserRole.ADMIN).first()
        if existing_admin:
            print(f"Ya existe un administrador: {existing_admin.email}")
            return
        
        # Recopilar datos del administrador
        print("\nIngresa los datos del administrador:")
        email       = input("Email: ").strip()
        username    = input("Username: ").strip()
        first_name  = input("Nombre: ").strip()
        last_name   = input("Apellido: ").strip()
        
        # ✅ Validación de email único en la base de datos
        if User.query.filter_by(email=email).first():
            print("Error: Ya existe un usuario con este email")
            return
        
        # ✅ Validación de username único en la base de datos
        if User.query.filter_by(username=username).first():
            print("Error: Ya existe un usuario con este username")
            return
        
        # ✅ Captura y validación de contraseña con confirmación
        while True:
            # Getpass oculta la entrada
            password           = getpass("Contraseña: ") 
            confirm_password   = getpass("Confirmar contraseña: ")

            # Validar longitud mínima de contraseña
            if len(password) < 6:
                print("Error: La contraseña debe tener al menos 6 caracteres")
                continue
            
            # Validar que las contraseñas coincidan
            if password != confirm_password:
                print("Error: Las contraseñas no coinciden")
                continue
            
            break
        
        # Crear usuario administrador
        admin_user = User(
            email       = email,
            username    = username,
            first_name  = first_name,
            last_name   = last_name,
            role        = UserRole.ADMIN,
            status      = UserStatus.ACTIVE
        )

        # Establecer la contraseña (hashing interno)
        admin_user.set_password(password)

        # ✅ Guardar en base de datos con commit automático
        print("Creando usuario administrador...y Dueño")
        admin_user.is_owner = True  # Marcar como propietario principal

        db.session.add(admin_user)
        db.session.commit()
        
        print(f"\n✅ Usuario administrador creado exitosamente:")
        print(f"   Email: {email}")
        print(f"   Username: {username}")
        print(f"   Nombre: {first_name} {last_name}")

def init_database():
    """
    Inicializa completamente la base de datos de la aplicación.
    
    Esta función se encarga de crear toda la estructura de tablas
    necesaria para el funcionamiento de la aplicación y establecer
    el usuario administrador inicial.
    
    Returns:
        None
    
    Raises:
        Exception: Si hay errores en la creación de tablas o usuarios
    
    Note:
        - Crea todas las tablas definidas en los modelos SQLAlchemy
        - Llama automáticamente a create_admin_user()
        - Utiliza el contexto de aplicación Flask para BD
        - No sobrescribe datos existentes
    """
    from app import create_app, db
    
    app = create_app()
    
    with app.app_context():
        print("=== Inicialización de Base de Datos ===")
        
        # Crear todas las tablas
        print("Creando tablas de base de datos...")
        db.create_all()
        print("✅ Tablas creadas exitosamente")
        
        # Crear usuario admin si no existe
        create_admin_user()

def main():
    """
    Función principal del script de inicialización.
    
    Esta función coordina todo el proceso de inicialización,
    realizando validaciones previas y manejando errores de
    manera elegante con feedback claro al usuario.
    
    Returns:
        None
    
    Note:
        - Valida la existencia del archivo .env antes de continuar
        - Proporciona instrucciones claras en caso de errores
        - Maneja excepciones con traceback para debugging
        - Confirma éxito con instrucciones para siguiente paso
    """
    print("🚀 Gem-AvatART - Script de Inicialización\n")
    
    # Verificar que existe el archivo .env
    if not os.path.exists('.env'):
        print("⚠️  No se encontró el archivo .env")
        print("   Copia .env.example a .env y configura las variables")
        print("   cp .env.example .env")
        return
    
    try:
        init_database()
        print("\n🎉 Inicialización completada exitosamente!")
        print("\nPuedes iniciar la aplicación con:")
        print("   python app.py")
        
    except Exception as e:
        # ✅ Manejo elegante de errores con información útil
        print(f"\n❌ Error durante la inicialización: {e}")
        import traceback
        traceback.print_exc() # Información detallada para debugging

# ✅ Punto de entrada del script cuando se ejecuta directamente
if __name__ == "__main__":
    main()
