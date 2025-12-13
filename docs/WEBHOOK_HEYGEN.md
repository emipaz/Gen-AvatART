# Configuración del Webhook de HeyGen

## 📋 Resumen

Este documento explica cómo configurar el webhook de HeyGen para recibir notificaciones automáticas cuando los videos estén completados.

---

## 🔧 Endpoint Implementado

**URL del Webhook:** `/api/webhook/heygen`

**Métodos HTTP:**
- `OPTIONS` - Validación CORS de HeyGen
- `POST` - Recepción de notificaciones de eventos

**URL Completa (desarrollo local):**
```
http://127.0.0.1:5000/api/webhook/heygen
```

**URL Completa (producción):**
```
https://tu-dominio.com/api/webhook/heygen
```

---

## 📥 Payload Esperado de HeyGen

```json
{
  "event_type": "video.completed",
  "event_data": {
    "video_id": "abc123xyz456...",
    "status": "completed",
    "video_url": "https://resource.heygen.ai/video/...",
    "thumbnail_url": "https://resource.heygen.ai/thumbnail/..."
  }
}
```

**Para videos fallidos:**
```json
{
  "event_type": "video.failed",
  "event_data": {
    "video_id": "abc123xyz456...",
    "status": "failed",
    "error_message": "Descripción del error"
  }
}
```

---

## 🚀 Configuración en HeyGen Dashboard

### **Paso 1: Acceder a la configuración de Webhooks**

1. Ir a [HeyGen Dashboard](https://app.heygen.com/)
2. Navegar a **Settings** → **API** → **Webhooks**
3. Click en **"Add Webhook Endpoint"**

### **Paso 2: Configurar el Endpoint**

**Para DESARROLLO (testing local con ngrok o localtunnel):**

1. Instalar ngrok: `npm install -g ngrok` o descargar de [ngrok.com](https://ngrok.com/)
2. Exponer puerto local:
   ```bash
   ngrok http 5000
   ```
3. Copiar la URL HTTPS generada: `https://abc123.ngrok.io`
4. En HeyGen, configurar:
   - **Endpoint URL:** `https://abc123.ngrok.io/api/webhook/heygen`
   - **Events:** Seleccionar `video.completed` y `video.failed`
   - **Status:** Active

**Para PRODUCCIÓN:**

1. En HeyGen, configurar:
   - **Endpoint URL:** `https://tu-dominio.com/api/webhook/heygen`
   - **Events:** Seleccionar `video.completed` y `video.failed`
   - **Status:** Active
2. Click **"Save"**

### **Paso 3: Validación**

HeyGen enviará una petición OPTIONS para validar que el endpoint está disponible. El webhook debe responder con `200 OK`.

---

## 🔐 Seguridad (TODO - Implementar en Producción)

### **Validación de Firma**

HeyGen envía un header `X-HeyGen-Signature` con cada webhook. Debes validarlo para asegurar que la petición viene de HeyGen.

**Implementación recomendada:**

```python
import hmac
import hashlib

def verify_heygen_signature(payload, signature, secret):
    """
    Verifica que la firma del webhook sea válida.
    
    Args:
        payload (str): Cuerpo del webhook (JSON string)
        signature (str): Firma en header X-HeyGen-Signature
        secret (str): Secret key de HeyGen
    """
    expected_signature = hmac.new(
        secret.encode('utf-8'),
        payload.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    
    return hmac.compare_digest(expected_signature, signature)

# Uso en el webhook:
@api_bp.route('/webhook/heygen', methods=['POST'])
def heygen_webhook():
    signature = request.headers.get('X-HeyGen-Signature')
    secret = current_app.config.get('HEYGEN_WEBHOOK_SECRET')
    
    if not verify_heygen_signature(request.data.decode(), signature, secret):
        return jsonify({'error': 'Invalid signature'}), 401
    
    # ... resto del código
```

**Agregar a `.env`:**
```env
HEYGEN_WEBHOOK_SECRET=tu-secret-key-de-heygen
```

---

## 🔄 Flujo Completo

```
1. Usuario solicita reel
   ↓
2. Productor aprueba solicitud
   ↓
3. Sistema llama a HeyGen API
   ↓ (HeyGen procesa video 2-5 minutos)
4. HeyGen envía webhook POST a /api/webhook/heygen
   ↓
5. Sistema actualiza reel a COMPLETED
   ↓
6. Usuario puede descargar su video
```

---

## 🧪 Probar el Webhook Manualmente

### **Simular webhook de HeyGen con curl:**

**Video completado:**
```bash
curl -X POST http://127.0.0.1:5000/api/webhook/heygen \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "video.completed",
    "event_data": {
      "video_id": "test_video_123",
      "status": "completed",
      "video_url": "https://example.com/video.mp4",
      "thumbnail_url": "https://example.com/thumb.jpg"
    }
  }'
```

**Video fallido:**
```bash
curl -X POST http://127.0.0.1:5000/api/webhook/heygen \
  -H "Content-Type: application/json" \
  -d '{
    "event_type": "video.failed",
    "event_data": {
      "video_id": "test_video_123",
      "status": "failed",
      "error_message": "Avatar not found"
    }
  }'
```

---

## 📊 Logs y Debugging

El webhook genera logs detallados:

```python
# Logs de éxito
✅ Reel {reel_id} completado exitosamente. URL: {video_url}

# Logs de error
❌ Reel {reel_id} falló: {error_message}

# Logs de validación
⚠️ No se encontró reel con video_id: {video_id}
```

**Ver logs en tiempo real:**
```bash
tail -f logs/app.log
```

---

## 📚 Referencias

- [HeyGen Webhook Events Documentation](https://docs.heygen.com/docs/using-heygens-webhook-events)
- [HeyGen Add Webhook Endpoint API](https://docs.heygen.com/reference/add-a-webhook-endpoint)
- [HeyGen Create Avatar Video V2](https://docs.heygen.com/reference/create-an-avatar-video-v2)

---

## ✅ Checklist de Implementación

- [x] Crear endpoint `/api/webhook/heygen`
- [x] Manejar OPTIONS para validación CORS
- [x] Procesar evento `video.completed`
- [x] Procesar evento `video.failed`
- [x] Actualizar estado del reel automáticamente
- [x] Logging detallado de eventos
- [ ] Validar firma del webhook (seguridad)
- [ ] Implementar idempotencia (evitar procesar duplicados)
- [ ] Enviar email al usuario cuando video esté listo
- [ ] Configurar webhook en HeyGen Dashboard (producción)
- [ ] Probar con ngrok/localtunnel en desarrollo
- [ ] Monitorear errores y reintentos de HeyGen
