# HeyGen Service - Quick Setup Guide

## 🚀 Configuración Rápida

### 1. Variables de Entorno

```bash
# .env
HEYGEN_PROCESSING_MODE=polling          # Para desarrollo local
# HEYGEN_PROCESSING_MODE=webhook        # Para producción  
# HEYGEN_PROCESSING_MODE=hybrid         # Para entorno flexible

HEYGEN_WEBHOOK_BASE_URL=                # Dejar vacío para polling
# HEYGEN_WEBHOOK_BASE_URL=https://gem-avatart.com  # Para webhook/hybrid
```

### 2. Uso Básico

```python
from app.services.heygen_service import HeyGenVideoProcessor

# Auto-detecta configuración desde variables de entorno
processor = HeyGenVideoProcessor(api_key="tu-api-key")

# O configuración manual
processor = HeyGenVideoProcessor(
    api_key="tu-api-key",
    processing_mode='polling'  # 'webhook', 'polling', 'hybrid'
)

# Procesar reel (funciona igual en todos los modos)
success = processor.process_reel(reel_model)
```

### 3. Verificación de Estado

```python
# Para modo polling, verificar manualmente
if processor.should_use_polling():
    is_completed = processor.check_video_status(reel)

# Para modo webhook, se notifica automáticamente
if not processor.should_use_polling():
    print("Webhook configurado, notificación automática")
```

### 4. Información del Modo

```python
info = processor.get_processing_mode_info()
print(f"Modo: {info['mode']}")
print(f"Usa polling: {info['uses_polling']}")
print(f"Usa webhooks: {info['uses_webhooks']}")

if info['webhook_url']:
    print(f"URL webhook: {info['webhook_url']}")
```

## 📋 Modos Disponibles

| Modo | Desarrollo Local | Producción | Requiere URL Pública |
|------|------------------|------------|---------------------|
| `polling` | ✅ Ideal | ❌ Lento | ❌ No |
| `webhook` | ⚠️ Requiere ngrok | ✅ Ideal | ✅ Sí |
| `hybrid` | ✅ Flexible | ✅ Robusto | ⚠️ Opcional |

Para más detalles, ver [heygen-processing-modes.md](./heygen-processing-modes.md)