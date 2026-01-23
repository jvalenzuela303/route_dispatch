# Sistema de Notificaciones y Comunicación - FASE 6

## Descripción General

El Sistema de Notificaciones de Claude Logistics proporciona comunicación automatizada y proactiva con los clientes a través de múltiples canales. Actualmente implementa notificaciones por **Email via SMTP**, con arquitectura extensible para SMS, WhatsApp y Push Notifications en el futuro.

### Características Principales

- ✅ **Notificaciones Email HTML Responsive**
- ✅ **Retry Logic con Exponential Backoff**
- ✅ **Logging Completo en Base de Datos**
- ✅ **Integración Automática con OrderService**
- ✅ **Manejo Graceful de Errores**
- ✅ **Arquitectura Multi-Canal Extensible**

---

## Arquitectura del Sistema

### Componentes

```
┌─────────────────────────────────────────────────────────────┐
│                    OrderService                              │
│  (Transición de estado: DOCUMENTADO → EN_RUTA)              │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ trigger notification
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              NotificationService                             │
│  • Orchestrates notifications                               │
│  • Retry logic (3 attempts, exponential backoff)            │
│  • Logging to notification_logs table                       │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ render template
                       ▼
┌─────────────────────────────────────────────────────────────┐
│              email_templates.py                              │
│  • HTML responsive templates                                │
│  • Plain text fallbacks                                     │
│  • Spanish localization                                     │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       │ send email
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                 EmailService                                 │
│  • SMTP connection management                               │
│  • Multipart email (HTML + plain text)                      │
│  • Error handling and logging                               │
└─────────────────────────────────────────────────────────────┘
```

### Flujo de Trabajo

1. **OrderService** detecta transición a `EN_RUTA`
2. **NotificationService** crea registro en `notification_logs` (status: `PENDING`)
3. **email_templates** renderiza email HTML + texto plano
4. **EmailService** intenta enviar via SMTP
5. Si falla → **retry** con exponential backoff (2s, 4s, 8s)
6. Actualiza `notification_logs` con status final (`SENT` o `FAILED`)
7. **AuditService** registra resultado para trazabilidad

---

## Configuración SMTP

### Variables de Entorno

Añade las siguientes variables a tu archivo `.env`:

```bash
# SMTP Configuration for Email Notifications
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-email@gmail.com
SMTP_PASSWORD=tu-contraseña-de-aplicacion
SMTP_FROM_EMAIL=noreply@botilleria-rancagua.cl
SMTP_FROM_NAME=Botillería Rancagua
SMTP_USE_TLS=True
SMTP_TIMEOUT=10
```

### Configuración para Gmail

Gmail requiere una **contraseña de aplicación** si tienes autenticación de dos factores (2FA) habilitada:

1. Ve a [Google Account Security](https://myaccount.google.com/security)
2. Activa **Verificación en dos pasos** (si no está activa)
3. Busca **Contraseñas de aplicaciones**
4. Selecciona **Correo** y **Otro dispositivo personalizado**
5. Genera la contraseña
6. Usa esta contraseña en `SMTP_PASSWORD`

**Configuración Gmail:**
```bash
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=tu-email@gmail.com
SMTP_PASSWORD=xxxx-xxxx-xxxx-xxxx  # Contraseña de aplicación
SMTP_USE_TLS=True
```

### Configuración para Outlook/Microsoft 365

**Outlook Personal:**
```bash
SMTP_HOST=smtp-mail.outlook.com
SMTP_PORT=587
SMTP_USER=tu-email@outlook.com
SMTP_PASSWORD=tu-contraseña
SMTP_USE_TLS=True
```

**Microsoft 365 (empresarial):**
```bash
SMTP_HOST=smtp.office365.com
SMTP_PORT=587
SMTP_USER=tu-email@empresa.com
SMTP_PASSWORD=tu-contraseña
SMTP_USE_TLS=True
```

### Configuración para Servicios Profesionales

**SendGrid:**
```bash
SMTP_HOST=smtp.sendgrid.net
SMTP_PORT=587
SMTP_USER=apikey
SMTP_PASSWORD=SG.xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
SMTP_USE_TLS=True
```

**Mailgun:**
```bash
SMTP_HOST=smtp.mailgun.org
SMTP_PORT=587
SMTP_USER=postmaster@tu-dominio.com
SMTP_PASSWORD=tu-api-key
SMTP_USE_TLS=True
```

**Amazon SES:**
```bash
SMTP_HOST=email-smtp.us-east-1.amazonaws.com
SMTP_PORT=587
SMTP_USER=tu-smtp-username
SMTP_PASSWORD=tu-smtp-password
SMTP_USE_TLS=True
```

---

## Uso del Sistema

### Trigger Automático (EN_RUTA)

Las notificaciones se envían **automáticamente** cuando un pedido transiciona a `EN_RUTA`:

```python
from app.services.order_service import OrderService

order_service = OrderService(db)

# Transición a EN_RUTA dispara notificación automáticamente
order = order_service.transition_order_state(
    order_id=order_id,
    new_status=OrderStatus.EN_RUTA,
    user=current_user,
    route_id=route_id
)
# Email se envía automáticamente a order.customer_email
```

### Envío Manual de Notificación

Para enviar notificaciones manualmente:

```python
from app.services.notification_service import NotificationService

notification_service = NotificationService(db)

# Enviar notificación
log = notification_service.send_order_in_transit_notification(order_id)

if log.status == NotificationStatus.SENT:
    print(f"Email enviado exitosamente a {log.recipient}")
else:
    print(f"Error: {log.error_message}")
```

### Re-intentar Notificación Fallida

```python
# Obtener notificaciones fallidas
failed_notifications = notification_service.get_failed_notifications(limit=50)

for log in failed_notifications:
    print(f"Orden {log.order_id}: {log.error_message}")

    # Re-intentar manualmente
    new_log = notification_service.resend_failed_notification(log.id)

    if new_log.status == NotificationStatus.SENT:
        print(f"✓ Reintento exitoso")
```

### Historial de Notificaciones

```python
# Ver todas las notificaciones de un pedido
history = notification_service.get_notification_history(order_id)

for log in history:
    print(f"{log.created_at}: {log.channel} - {log.status}")
    if log.status == NotificationStatus.SENT:
        print(f"  Enviado en: {log.sent_at}")
    elif log.status == NotificationStatus.FAILED:
        print(f"  Error: {log.error_message}")
```

### Estadísticas de Notificaciones

```python
# Obtener métricas de los últimos 30 días
stats = notification_service.get_notification_stats(days=30)

print(f"Total enviadas: {stats['total_notifications']}")
print(f"Tasa de éxito: {stats['success_rate']}%")
print(f"Tasa de fallo: {stats['failure_rate']}%")
print(f"Promedio de reintentos: {stats['avg_retry_count']}")
```

---

## Modelo de Datos

### Tabla `notification_logs`

```sql
CREATE TABLE notification_logs (
    id UUID PRIMARY KEY,
    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
    order_id UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    channel notification_channel_enum NOT NULL,  -- EMAIL, SMS, WHATSAPP, PUSH
    recipient VARCHAR(255) NOT NULL,  -- email o teléfono
    status notification_status_enum NOT NULL DEFAULT 'PENDING',  -- PENDING, SENT, FAILED
    sent_at TIMESTAMP,  -- timestamp del envío exitoso
    error_message TEXT,  -- detalles del error si falló
    retry_count INTEGER NOT NULL DEFAULT 0  -- número de reintentos
);

-- Índices
CREATE INDEX ix_notification_logs_order_id ON notification_logs(order_id);
CREATE INDEX ix_notification_logs_status ON notification_logs(status);
CREATE INDEX ix_notification_logs_channel ON notification_logs(channel);
CREATE INDEX ix_notification_logs_created_at ON notification_logs(created_at);
```

### Enums

```python
class NotificationChannel(str, Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"  # Futuro
    WHATSAPP = "WHATSAPP"  # Futuro
    PUSH = "PUSH"  # Futuro

class NotificationStatus(str, Enum):
    PENDING = "PENDING"  # En cola
    SENT = "SENT"  # Enviado exitosamente
    FAILED = "FAILED"  # Falló después de reintentos
```

---

## Plantillas de Email

### Template: Order In Transit

Email enviado cuando pedido pasa a `EN_RUTA`:

**Contenido:**
- Saludo personalizado con nombre del cliente
- Número de pedido
- Fecha de entrega estimada
- Nombre del repartidor
- Dirección de entrega
- Call-to-action (estar disponible)

**Formato:**
- HTML responsive (mobile-friendly)
- Fallback texto plano
- Branding de Botillería Rancagua
- Colores corporativos (verde degradado)

**Ejemplo:**
```
Asunto: Tu pedido #ORD-20260121-0001 está en camino 🚚

Hola Juan Pérez,

Te informamos que tu pedido #ORD-20260121-0001 ya está en ruta
y pronto llegará a tu domicilio.

┌──────────────────────────────┐
│ 📦 Pedido: ORD-20260121-0001 │
│ 📅 Entrega: Miércoles 22 de  │
│    Enero, 2026               │
│ 🚗 Repartidor: Carlos López  │
│ 📍 Dirección: Calle Falsa 123│
└──────────────────────────────┘

Por favor, asegúrate de estar disponible.

¡Gracias por tu compra!

Botillería Rancagua
```

---

## Retry Logic y Manejo de Errores

### Estrategia de Reintentos

```python
MAX_RETRIES = 3
RETRY_DELAY_BASE = 2  # segundos

# Tiempos de espera:
# Intento 1: Inmediato
# Intento 2: Espera 2^1 = 2 segundos
# Intento 3: Espera 2^2 = 4 segundos
# Total: ~6 segundos de intentos
```

### Errores Manejados

| Error | Comportamiento |
|-------|----------------|
| `SMTPAuthenticationError` | Retry → Log en audit |
| `SMTPRecipientsRefused` | Retry → Log en audit |
| `ConnectionRefusedError` | Retry → Log en audit |
| `TimeoutError` | Retry → Log en audit |
| `SMTPException` (genérico) | Retry → Log en audit |
| `MissingRecipientError` | No retry, log inmediato |
| Otros errores | Retry → Log en audit |

### Comportamiento "Best Effort"

**IMPORTANTE:** Las notificaciones son "best effort":

- ❌ El fallo de notificación **NO bloquea** la transición de estado del pedido
- ✅ El pedido pasa a `EN_RUTA` incluso si el email falla
- ✅ El error se registra en `audit_logs` para seguimiento
- ✅ Se puede reintentar manualmente desde `notification_logs`

**Razón:** La entrega del pedido es más crítica que la notificación al cliente.

---

## Troubleshooting

### Problema: "SMTP Authentication failed"

**Causa:** Credenciales incorrectas o falta contraseña de aplicación.

**Solución:**
1. Verifica `SMTP_USER` y `SMTP_PASSWORD`
2. Para Gmail, usa contraseña de aplicación (no tu contraseña normal)
3. Para Outlook, verifica que 2FA no esté bloqueando el acceso
4. Prueba la conexión:
   ```python
   email_service = EmailService()
   if email_service.test_connection():
       print("✓ Conexión OK")
   ```

### Problema: "Connection refused"

**Causa:** Host o puerto incorrecto, o firewall bloqueando.

**Solución:**
1. Verifica `SMTP_HOST` y `SMTP_PORT`
2. Prueba desde terminal:
   ```bash
   telnet smtp.gmail.com 587
   ```
3. Verifica firewall del servidor
4. Si usas Docker, verifica que el contenedor tenga acceso a internet

### Problema: "Connection timeout"

**Causa:** Red lenta o servidor SMTP no responde.

**Solución:**
1. Aumenta `SMTP_TIMEOUT`:
   ```bash
   SMTP_TIMEOUT=30
   ```
2. Verifica latencia de red al servidor SMTP
3. Considera usar servicio SMTP local (relay)

### Problema: Notificaciones no se envían

**Verificación paso a paso:**

1. **¿Pedido tiene email?**
   ```sql
   SELECT customer_email FROM orders WHERE id = 'order-uuid';
   ```

2. **¿SMTP configurado?**
   ```python
   from app.config.settings import get_settings
   settings = get_settings()
   print(settings.smtp_host, settings.smtp_user)
   ```

3. **¿Logs de error?**
   ```sql
   SELECT * FROM notification_logs
   WHERE order_id = 'order-uuid'
   ORDER BY created_at DESC;
   ```

4. **¿Audit logs?**
   ```sql
   SELECT * FROM audit_logs
   WHERE action LIKE 'NOTIFICATION%'
   AND entity_id = 'order-uuid';
   ```

### Problema: Emails van a spam

**Solución:**
1. Configura SPF record para tu dominio
2. Configura DKIM signing
3. Usa servicio profesional (SendGrid, Mailgun)
4. Evita palabras spam en subject/body
5. Incluye unsubscribe link

---

## Testing

### Test SMTP Connection

```bash
# Desde Python
python -c "from app.services.email_service import EmailService; \
           service = EmailService(); \
           print('✓ OK' if service.test_connection() else '✗ Failed')"
```

### Send Test Email

```python
from app.services.email_service import EmailService

email_service = EmailService()
success = email_service.send_test_email("tu-email@example.com")

if success:
    print("✓ Email de prueba enviado - revisa tu bandeja")
else:
    print("✗ Falló - revisa logs")
```

### Run Unit Tests

```bash
# Tests de EmailService (SMTP mockeado)
pytest tests/test_services/test_email_service.py -v

# Tests de NotificationService (retry logic)
pytest tests/test_services/test_notification_service.py -v

# Tests de integración
pytest tests/test_integration/test_order_notification_integration.py -v
```

---

## Migración de Base de Datos

### Aplicar Migración

```bash
# Usando Alembic
alembic upgrade head

# O manualmente ejecutar:
# migrations/versions/003_add_notification_logs_table.py
```

### Rollback (si necesario)

```bash
alembic downgrade -1
```

---

## Extensibilidad Futura

### Añadir Canal SMS

1. Crear `SMSService` en `app/services/sms_service.py`
2. Integrar con Twilio/AWS SNS
3. Actualizar `NotificationService.send_order_in_transit_notification()`
4. Añadir lógica de selección de canal según preferencias del cliente

### Añadir Canal WhatsApp

1. Integrar WhatsApp Business API
2. Crear `WhatsAppService`
3. Templates aprobados por Meta
4. Actualizar `NotificationService`

### Añadir Push Notifications

1. Integrar Firebase Cloud Messaging
2. Crear `PushService`
3. Requiere app móvil con FCM token
4. Almacenar device tokens en tabla `user_devices`

---

## Monitoreo y Alertas

### Métricas Clave

1. **Tasa de éxito de notificaciones** (target: >95%)
2. **Tiempo promedio de entrega** (target: <5s)
3. **Tasa de rebote** (bounces)
4. **Tasa de apertura** (si tracking habilitado)

### Dashboard Sugerido

```sql
-- Notificaciones últimas 24h
SELECT
    status,
    COUNT(*) as count,
    ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER(), 2) as percentage
FROM notification_logs
WHERE created_at > NOW() - INTERVAL '24 hours'
GROUP BY status;

-- Errores más comunes
SELECT
    SUBSTRING(error_message, 1, 100) as error,
    COUNT(*) as occurrences
FROM notification_logs
WHERE status = 'FAILED'
  AND created_at > NOW() - INTERVAL '7 days'
GROUP BY SUBSTRING(error_message, 1, 100)
ORDER BY occurrences DESC
LIMIT 10;
```

### Alertas Recomendadas

- ⚠️ Tasa de fallo >10% en última hora
- ⚠️ >100 notificaciones pendientes
- ⚠️ SMTP server down (test_connection fails)
- ⚠️ Latencia >30s para envío

---

## Mejores Prácticas

### DO ✅

- ✅ Siempre incluir fallback texto plano
- ✅ Validar email antes de enviar
- ✅ Usar retry logic para fallos transitorios
- ✅ Loggear todos los intentos
- ✅ Respetar opt-out de clientes
- ✅ Usar templates responsive
- ✅ Incluir información de contacto

### DON'T ❌

- ❌ Bloquear operaciones críticas por fallo de notificación
- ❌ Enviar notificaciones sin consentimiento
- ❌ Hardcodear credenciales SMTP
- ❌ Ignorar errores silenciosamente
- ❌ Enviar emails sin rate limiting (anti-spam)
- ❌ Usar HTML sin fallback texto
- ❌ Olvidar logs de audit

---

## Compliance y Regulaciones

### GDPR (Europa)

- Obtener consentimiento explícito
- Proveer mecanismo de opt-out
- Almacenar datos solo el tiempo necesario
- Permitir acceso/eliminación de datos

### CAN-SPAM (USA)

- Incluir dirección física
- Subject line honesto
- Identificar mensaje como publicidad
- Proveer opt-out fácil

### Ley 19.628 (Chile - Protección de Datos)

- Informar uso de datos personales
- Obtener autorización para comunicaciones
- Permitir rectificación y cancelación

---

## Soporte

**Documentación técnica:** `/docs`
**Tests:** `/tests/test_services/test_*notification*.py`
**Logs:** `notification_logs`, `audit_logs` tables
**Configuración:** `.env`

Para problemas o preguntas, revisar:
1. Esta documentación
2. Logs de error en `notification_logs`
3. Audit trail en `audit_logs`
4. Tests para ejemplos de uso
