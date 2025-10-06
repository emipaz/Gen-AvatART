# Gem-AvatART 🎬

Plataforma de gestión de reels usando HeyGen API con sistema de roles multi-nivel.

## 🚀 Características

### Roles de Usuario
- **👨‍💼 Administrador**: Gestión completa de la plataforma, CRUD de todos los usuarios
- **🎬 Productor**: Aporta API key de HeyGen, gestiona rentabilidad y supervisa subproductores/afiliados
- **🎭 Subproductor**: Crea avatars con la API key del productor (requiere aprobación)
- **📱 Afiliado**: Crea reels con contenido pre-aprobado por el productor

### Funcionalidades Principales
- ✅ Sistema de autenticación y roles
- ✅ Gestión de API keys de HeyGen
- ✅ Creación y aprobación de avatars
- ✅ Sistema de comisiones y rentabilidad
- ✅ Flujo de aprobación de contenido
- ✅ Dashboard para cada tipo de usuario

## 🛠️ Tecnologías

- **Backend**: Flask (Python)
- **Base de Datos**: SQLAlchemy + PostgreSQL
- **Frontend**: Bootstrap + JavaScript
- **API Externa**: HeyGen API
- **Autenticación**: Flask-Login + JWT

## 📦 Instalación

```bash
# Clonar el repositorio
git clone <repository-url>
cd Gem-AvatART

# Crear entorno virtual
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Linux/Mac

# Instalar dependencias
pip install -r requirements.txt

# Configurar variables de entorno
cp .env.example .env
# Editar .env con tus configuraciones

# Ejecutar migraciones
flask db upgrade

# Iniciar la aplicación
python app.py
```

## 🌐 Estructura del Proyecto

```
Gem-AvatART/
├── app/
│   ├── __init__.py
│   ├── models/
│   ├── routes/
│   ├── services/
│   └── templates/
├── migrations/
├── config.py
├── requirements.txt
└── app.py
```

## 📋 Variables de Entorno

```env
FLASK_APP=app.py
FLASK_ENV=development
SECRET_KEY=tu-clave-secreta
DATABASE_URL=postgresql://usuario:password@localhost/gem_avatart
HEYGEN_BASE_URL=https://api.heygen.com
```

## 🔄 Flujo de Trabajo

1. **Administrador** crea productores
2. **Productor** configura su API key de HeyGen
3. **Productor** invita subproductores y afiliados
4. **Subproductor** solicita creación de avatars
5. **Productor** aprueba/rechaza avatars
6. **Afiliado** crea reels con avatars aprobados
7. **Sistema** calcula comisiones automáticamente

## 🚀 Próximos Pasos

- [ ] Implementar sistema de pagos
- [ ] Dashboard analítico avanzado
- [ ] Integración con redes sociales
- [ ] Sistema de notificaciones en tiempo real
- [ ] API REST completa

## 📄 Licencia

MIT License - ver archivo LICENSE para detalles