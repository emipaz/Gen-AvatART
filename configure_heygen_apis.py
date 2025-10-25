#!/usr/bin/env python3
"""
Script para configurar las API keys de HeyGen en los productores.

Este script permite configurar fácilmente las API keys de HeyGen
en múltiples productores de la aplicación.
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from app.models.user import User
from app.models.producer import Producer

def configure_heygen_apis():
    """Configura las API keys de HeyGen en los productores"""
    
    app = create_app()
    with app.app_context():
        print("🔑 CONFIGURACION DE API KEYS HEYGEN")
        print("=" * 50)
        
        # Buscar productores existentes
        producers = Producer.query.all()
        
        if not producers:
            print("❌ No se encontraron productores. Crea al menos un productor primero.")
            return
        
        print(f"✅ Encontrados {len(producers)} productores:")
        for i, producer in enumerate(producers, 1):
            user = User.query.get(producer.user_id)
            status = "🔑 Configurada" if producer.has_heygen_access() else "❌ Sin configurar"
            print(f"  {i}. {producer.company_name} ({user.email}) - {status}")
        
        print("\n" + "=" * 50)
        print("Tienes 3-4 API keys de HeyGen disponibles.")
        print("Vamos a configurarlas una por una:")
        print("=" * 50)
        
        # Configurar API keys
        for i, producer in enumerate(producers, 1):
            user = User.query.get(producer.user_id)
            
            print(f"\n🏢 PRODUCTOR {i}: {producer.company_name}")
            print(f"📧 Email: {user.email}")
            
            current_api = producer.get_masked_heygen_api_key() if producer.has_heygen_access() else None
            if current_api:
                print(f"🔑 API Key actual: {current_api}")
                
                replace = input("¿Reemplazar API key? (s/N): ").strip().lower()
                if replace not in ['s', 'si', 'sí', 'y', 'yes']:
                    print("⏭️  Saltando...")
                    continue
            
            print("\n📝 Ingresa la API key de HeyGen:")
            print("(Puedes pegarla completa, se encriptará automáticamente)")
            api_key = input("API Key: ").strip()
            
            if not api_key:
                print("⏭️  Saltando (API key vacía)...")
                continue
            
            try:
                # Configurar la API key
                producer.set_heygen_api_key(api_key)
                db.session.commit()
                
                # Verificar que se guardó correctamente
                masked = producer.get_masked_heygen_api_key()
                print(f"✅ API key configurada exitosamente: {masked}")
                
            except Exception as e:
                print(f"❌ Error configurando API key: {e}")
        
        print("\n" + "=" * 50)
        print("🎉 CONFIGURACION COMPLETADA")
        print("=" * 50)
        
        # Resumen final
        print("\n📊 RESUMEN FINAL:")
        for i, producer in enumerate(producers, 1):
            user = User.query.get(producer.user_id)
            status = "✅ Configurada" if producer.has_heygen_access() else "❌ Sin configurar"
            masked = producer.get_masked_heygen_api_key() if producer.has_heygen_access() else "N/A"
            print(f"  {i}. {producer.company_name} - {status} ({masked})")

def test_apis():
    """Prueba las API keys configuradas"""
    app = create_app()
    with app.app_context():
        print("\n🧪 PROBANDO API KEYS CONFIGURADAS")
        print("=" * 50)
        
        producers = Producer.query.filter(Producer.heygen_api_key_encrypted.isnot(None)).all()
        
        for producer in producers:
            user = User.query.get(producer.user_id)
            print(f"\n🏢 {producer.company_name} ({user.email})")
            
            try:
                api_key = producer.get_heygen_api_key()
                masked = producer.get_masked_heygen_api_key()
                print(f"🔑 API Key: {masked}")
                print(f"✅ Desencriptación exitosa (longitud: {len(api_key)} caracteres)")
                
                # Aquí podrías agregar una prueba real a la API de HeyGen
                # import requests
                # response = requests.get("https://api.heygen.com/v1/avatars", 
                #                       headers={"Authorization": f"Bearer {api_key}"})
                # print(f"🌐 Test API: {response.status_code}")
                
            except Exception as e:
                print(f"❌ Error con API key: {e}")

if __name__ == "__main__":
    print("🚀 CONFIGURADOR DE API KEYS HEYGEN")
    print("=" * 50)
    
    while True:
        print("\n¿Qué quieres hacer?")
        print("1. Configurar API keys")
        print("2. Probar API keys existentes")
        print("3. Salir")
        
        choice = input("\nSelecciona una opción (1-3): ").strip()
        
        if choice == "1":
            configure_heygen_apis()
        elif choice == "2":
            test_apis()
        elif choice == "3":
            print("👋 ¡Hasta luego!")
            break
        else:
            print("❌ Opción inválida")