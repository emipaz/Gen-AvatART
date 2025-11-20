# HeyGen Processing Modes - Documentación

La aplicación Gem-AvatART soporta múltiples modos de procesamiento para videos generados con HeyGen API, permitiendo flexibilidad en desarrollo y producción.

## 📋 Modos de Procesamiento Disponibles

### 1. **Modo WEBHOOK** 🔄
**Notificaciones automáticas en tiempo real**

- ✅ **Ventajas:**
  - Respuesta inmediata cuando el video está listo
  - No consume recursos del servidor verificando constantemente
  - Escalable para múltiples videos simultáneamente
  - Experiencia de usuario fluida

- ❌ **Desventajas:**
  - Requiere URL pública accesible desde internet
  - Necesita configuración adicional en desarrollo local
  - Dependiente de la conectividad de HeyGen

- 🎯 **Uso Recomendado:** Producción con servidor público

### 2. **Modo POLLING** 🔍
**Verificación manual periódica**

- ✅ **Ventajas:**
  - No requiere URL pública
  - Funciona perfectamente en desarrollo local
  - Control total sobre cuándo verificar
  - Simple de implementar

- ❌ **Desventajas:**
  - Demora en detectar cuando el video está listo
  - Consume recursos del servidor con verificaciones periódicas
  - No escalable para muchos videos simultáneamente
  - Experiencia de usuario más lenta

- 🎯 **Uso Recomendado:** Desarrollo local y testing

### 3. **Modo HYBRID** 🔀
**Webhooks + Fallback a Polling**

- ✅ **Ventajas:**
  - Lo mejor de ambos mundos
  - Webhook cuando está disponible, polling como respaldo
  - Robusto ante fallos de conectividad
  - Funciona en cualquier entorno

- ❌ **Desventajas:**
  - Complejidad adicional en configuración
  - Requiere lógica de fallback

- 🎯 **Uso Recomendado:** Aplicaciones que cambian entre desarrollo y producción

## 🚀 Configuración por Entorno

### Desarrollo Local
```python
# config/development.py
HEYGEN_PROCESSING_MODE = 'polling'  # O 'hybrid' con ngrok
HEYGEN_WEBHOOK_BASE_URL = None      # O 'https://abc123.ngrok.io'
```

### Staging/Testing
```python
# config/staging.py
HEYGEN_PROCESSING_MODE = 'hybrid'
HEYGEN_WEBHOOK_BASE_URL = 'https://staging.gem-avatart.com'
```

### Producción
```python
# config/production.py
HEYGEN_PROCESSING_MODE = 'webhook'
HEYGEN_WEBHOOK_BASE_URL = 'https://gem-avatart.com'
```

## 💻 Implementación en Código

### Inicializar Procesador

```python
from app.services.heygen_service import HeyGenVideoProcessor

# Modo Polling (Desarrollo)
processor = HeyGenVideoProcessor(
    api_key="tu-api-key",
    processing_mode='polling'
)

# Modo Webhook (Producción)
processor = HeyGenVideoProcessor(
    api_key="tu-api-key", 
    processing_mode='webhook',
    webhook_base_url='https://gem-avatart.com'
)

# Modo Híbrido
processor = HeyGenVideoProcessor(
    api_key="tu-api-key",
    processing_mode='hybrid', 
    webhook_base_url='https://gem-avatart.com'
)
```

### Procesar Reel

```python
# El mismo código funciona para todos los modos
success = processor.process_reel(reel_model)

if success:
    # Verificar modo para saber qué hacer después
    mode_info = processor.get_processing_mode_info()
    
    if mode_info['uses_polling']:
        # Programar tarea de verificación periódica
        from app.tasks import check_reel_status
        check_reel_status.apply_async(
            args=[reel_model.id], 
            countdown=60  # Verificar en 1 minuto
        )
        
    if mode_info['uses_webhooks']:
        # El webhook notificará automáticamente
        logger.info(f"Webhook configurado: {mode_info['webhook_url']}")
```

### Verificación Manual (Polling)

```python
# Para modo polling o híbrido, verificar periódicamente
@celery.task
def check_reel_status(reel_id):
    reel = Reel.query.get(reel_id)
    processor = get_processor_for_reel(reel)
    
    if processor.should_use_polling():
        is_completed = processor.check_video_status(reel)
        
        if not is_completed and reel.status == 'processing':
            # Programar siguiente verificación
            check_reel_status.apply_async(
                args=[reel_id],
                countdown=120  # Verificar en 2 minutos
            )
```

## 🔧 Configuración de Webhooks

### Desarrollo Local con ngrok

1. **Instalar ngrok:**
```bash
npm install -g ngrok
```

2. **Iniciar túnel:**
```bash
ngrok http 5000
```

3. **Configurar en app:**
```python
# .env
HEYGEN_PROCESSING_MODE=hybrid
HEYGEN_WEBHOOK_BASE_URL=https://abc123.ngrok.io
```

### Producción

1. **Configurar DNS:**
```
gem-avatart.com → Tu servidor IP
```

2. **Configurar SSL:**
```bash
# Certbot para Let's Encrypt
certbot --nginx -d gem-avatart.com
```

3. **Route de Webhook:**
```python
@bp.route('/webhooks/heygen/reel/<int:reel_id>', methods=['POST'])
def heygen_reel_webhook(reel_id):
    # Procesar notificación de HeyGen
    data = request.json
    reel = Reel.query.get_or_404(reel_id)
    
    if data.get('event') == 'avatar_video.success':
        reel.status = 'completed'
        reel.video_url = data.get('data', {}).get('video_url')
    elif data.get('event') == 'avatar_video.fail':
        reel.status = 'failed'
        reel.error_message = data.get('data', {}).get('error')
    
    db.session.commit()
    return "OK", 200
```

## 🧪 Testing

### Test de Modes

```python
def test_polling_mode():
    processor = HeyGenVideoProcessor(
        api_key="test-key",
        processing_mode='polling'
    )
    
    assert processor.should_use_polling() == True
    
    mode_info = processor.get_processing_mode_info()
    assert mode_info['mode'] == 'polling'
    assert mode_info['uses_polling'] == True
    assert mode_info['uses_webhooks'] == False

def test_webhook_mode():
    processor = HeyGenVideoProcessor(
        api_key="test-key",
        processing_mode='webhook',
        webhook_base_url='https://test.com'
    )
    
    assert processor.should_use_polling() == False
    
    mode_info = processor.get_processing_mode_info()
    assert mode_info['mode'] == 'webhook'
    assert mode_info['uses_webhooks'] == True
    assert mode_info['webhook_url'] == 'https://test.com'
```

### Mock de Webhook en Testing

```python
@pytest.fixture
def mock_webhook():
    def trigger_webhook(reel_id, event='avatar_video.success'):
        url = f"http://testserver/webhooks/heygen/reel/{reel_id}"
        data = {
            "event": event,
            "data": {
                "video_id": "test_123",
                "video_url": "https://example.com/test.mp4"
            }
        }
        return requests.post(url, json=data)
    
    return trigger_webhook
```

## 📊 Monitoreo y Logs

### Logs por Modo

```python
# El sistema automáticamente logea el modo usado
logger.info("HeyGenVideoProcessor inicializado - Modo: webhook")
logger.info("Webhook configurado: https://gem-avatart.com/webhooks/heygen/reel/123")

# Para polling
logger.info("Modo polling: usar check_video_status() para monitorear progreso")
```

### Dashboard de Estado

```python
def get_processing_dashboard():
    return {
        "active_reels": Reel.query.filter_by(status='processing').count(),
        "processing_mode": current_app.config.get('HEYGEN_PROCESSING_MODE'),
        "webhook_enabled": current_app.config.get('HEYGEN_WEBHOOK_BASE_URL') is not None,
        "last_webhook_received": get_last_webhook_timestamp()
    }
```

## 🎯 Recomendaciones

### Por Entorno
- **Desarrollo Local:** `polling` (simple, no requiere configuración adicional)
- **Staging:** `hybrid` (permite probar ambos modos)
- **Producción:** `webhook` (máximo rendimiento y escalabilidad)

### Mejores Prácticas

1. **Usar Variables de Entorno:**
```bash
HEYGEN_PROCESSING_MODE=webhook
HEYGEN_WEBHOOK_BASE_URL=https://tu-dominio.com
```

2. **Validación de Configuración:**
```python
if mode == 'webhook' and not webhook_url:
    raise ValueError("webhook_base_url requerido para modo webhook")
```

3. **Fallback Graceful:**
```python
if webhook_fails:
    fallback_to_polling()
```

4. **Monitoreo de Webhooks:**
```python
@bp.after_request
def log_webhook_activity(response):
    if request.endpoint == 'webhook.heygen_reel':
        logger.info(f"Webhook procesado: {response.status_code}")
    return response
```

## 🔍 Troubleshooting

### Webhooks no Funcionan
1. Verificar que la URL sea accesible públicamente
2. Verificar SSL/HTTPS válido
3. Revisar logs de ngrok en desarrollo
4. Confirmar que HeyGen puede alcanzar la URL

### Polling es Lento
1. Reducir intervalo de verificación (con cuidado)
2. Implementar verificación exponencial backoff
3. Considerar cambiar a modo híbrido

### Modo Híbrido no Funciona
1. Verificar configuración de webhook_base_url
2. Revisar logs de fallback a polling
3. Verificar que ambos modos estén implementados correctamente

---

## 📝 Notas Técnicas

- Los webhooks de HeyGen tienen timeout de 30 segundos
- El sistema verifica automáticamente la conectividad de webhooks
- En modo híbrido, se usa polling solo como fallback
- Todos los modos son thread-safe y soportan procesamiento concurrente