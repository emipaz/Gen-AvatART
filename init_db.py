#!/usr/bin/env python3
"""
Script de inicialización para Gem-AvatART
Crea la base de datos y un usuario administrador inicial
"""

import os
import sys
from getpass import getpass

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def create_admin_user():
    """Crear usuario administrador inicial"""
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
        email = input("Email: ").strip()
        username = input("Username: ").strip()
        first_name = input("Nombre: ").strip()
        last_name = input("Apellido: ").strip()
        
        # Validar email único
        if User.query.filter_by(email=email).first():
            print("Error: Ya existe un usuario con este email")
            return
        
        # Validar username único
        if User.query.filter_by(username=username).first():
            print("Error: Ya existe un usuario con este username")
            return
        
        # Contraseña
        while True:
            password = getpass("Contraseña: ")
            confirm_password = getpass("Confirmar contraseña: ")
            
            if len(password) < 6:
                print("Error: La contraseña debe tener al menos 6 caracteres")
                continue
            
            if password != confirm_password:
                print("Error: Las contraseñas no coinciden")
                continue
            
            break
        
        # Crear usuario administrador
        admin_user = User(
            email=email,
            username=username,
            first_name=first_name,
            last_name=last_name,
            role=UserRole.ADMIN,
            status=UserStatus.ACTIVE
        )
        admin_user.set_password(password)
        
        db.session.add(admin_user)
        db.session.commit()
        
        print(f"\n✅ Usuario administrador creado exitosamente:")
        print(f"   Email: {email}")
        print(f"   Username: {username}")
        print(f"   Nombre: {first_name} {last_name}")

def init_database():
    """Inicializar la base de datos"""
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
    """Función principal"""
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
        print(f"\n❌ Error durante la inicialización: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()