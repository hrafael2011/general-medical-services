# Integración de WhatsApp — Meta Cloud API

Documentación completa del proceso de integración de WhatsApp al sistema de turnos médicos.
Cubre desde la configuración de la cuenta en Meta hasta el debugging final.

---

## Tabla de contenidos

1. [Arquitectura general](#1-arquitectura-general)
2. [Configuración en Meta Developer](#2-configuración-en-meta-developer)
3. [Variables de entorno](#3-variables-de-entorno)
4. [Backend: Dependencias](#4-backend-dependencias)
5. [Backend: Modelos de base de datos](#5-backend-modelos-de-base-de-datos)
6. [Backend: Proveedores de notificación](#6-backend-proveedores-de-notificación)
7. [Backend: Servicio de notificaciones](#7-backend-servicio-de-notificaciones)
8. [Backend: Scheduler (APScheduler)](#8-backend-scheduler-apscheduler)
9. [Backend: Webhook de WhatsApp](#9-backend-webhook-de-whatsapp)
10. [Migración de BD: `phone` → `whatsapp_phone`](#10-migración-de-bd-phone--whatsapp_phone)
11. [Problemas encontrados y soluciones](#11-problemas-encontrados-y-soluciones)
12. [Pruebas y debugging](#12-pruebas-y-debugging)
13. [Flujo de confirmación paso a paso](#13-flujo-de-confirmación-paso-a-paso)

---

## 1. Arquitectura general

```
┌──────────┐    ┌──────────┐    ┌──────────────────┐    ┌──────────────┐    ┌──────────┐
│ FastAPI   │───▶│ PyWa      │───▶│ Meta Cloud API   │───▶│ WhatsApp     │───▶│ Médico   │
│ (Backend) │    │ (Python)  │    │ (graph.facebook) │    │ (cliente)    │    │          │
└──────────┘    └──────────┘    └──────────────────┘    └──────────────┘    └──────────┘
      ▲                                                                           │
      │                            ┌──────────────────┐                          │
      └────────────────────────────│ Webhook (POST)    │◀─────────────────────────┘
                                   │ /api/webhooks/    │    Responde "1"
                                   │    whatsapp       │
                                   └──────────────────┘
```

**Componentes:**
- **FastAPI** — backend que orquesta notificaciones y recibe webhooks
- **PyWa** — librería Python que envuelve la Meta Cloud API
- **Meta Cloud API** — endpoint `graph.facebook.com/v22.0/{phone_number_id}/messages`
- **APScheduler** — scheduler que procesa la cola de notificaciones cada 30s
- **Webhook** — endpoint en nuestro backend que recibe mensajes entrantes de Meta

---

## 2. Configuración en Meta Developer

### 2.1 Crear cuenta y app

1. Ir a [developers.facebook.com](https://developers.facebook.com)
2. Crear una cuenta de desarrollador (requiere cuenta personal de Facebook verificada)
3. Crear una nueva app de tipo **Business**
4. Agregar el producto **WhatsApp** desde el dashboard de la app

### 2.2 Configurar WhatsApp Business API

En **App Dashboard > WhatsApp > API Setup**:

1. Crear un **WABA** (WhatsApp Business Account)
2. Agregar un número de teléfono:
   - Si ya tienes un número en WhatsApp, eliminarlo de la app de WhatsApp normal
   - Registrarlo en Meta (recibirás un código por SMS o llamada)
   - El número usado en staging: `+1 809 243 8778`
3. Crear un **Token de acceso permanente** (System User):
   - WhatsApp > API Setup > Generate access token
   - Seleccionar el System User de la app
   - Asignar permisos: `whatsapp_business_messaging`, `whatsapp_business_management`
   - **Guardar el token en un lugar seguro** — no se vuelve a mostrar

### 2.3 Datos importantes de la app

| Dato | Valor (staging) | Variable de entorno |
|---|---|---|
| Phone Number ID | `1180291398493188` | `META_WHATSAPP_PHONE_NUMBER_ID` |
| WABA ID | (en dashboard) | `META_WHATSAPP_BUSINESS_ACCOUNT_ID` |
| Token | `EAAx...` | `META_WHATSAPP_TOKEN` |
| API Version | `22.0` | `META_WHATSAPP_API_VERSION` |
| Verify Token | (valor personalizado) | `META_WEBHOOK_VERIFY_TOKEN` |

**Importante:** El Phone Number ID (`1180291398493188`) NO es el número de teléfono (`+18092438778`).
Son identificadores distintos en Meta.

### 2.4 Configurar webhook

En **App Dashboard > WhatsApp > Configuration > Webhook**:

1. **Callback URL**: `https://{tu-dominio}/api/webhooks/whatsapp`
   - Meta valida esta URL con un GET enviando `hub.mode=subscribe`, `hub.verify_token=...`, `hub.challenge=...`
   - Nuestro endpoint debe responder con el valor de `hub.challenge` si el token coincide
2. **Verify Token**: mismo valor que `META_WEBHOOK_VERIFY_TOKEN`
3. **Suscribirse a campos** (Webhook Fields):
   - **`messages`** — requerido para recibir respuestas de usuarios
   - Otros campos útiles: `message_template_status_update`, `phone_number_quality_update`

### 2.5 Números de prueba (Dev Mode)

En modo Development, SOLO los números registrados como "test numbers" pueden recibir mensajes.

1. Ir a **WhatsApp > API Setup > Recipient Numbers**
2. Agregar el número del destinatario (ej: `+18092186876`)
3. El usuario debe aceptar la invitación (recibe código de verificación)
4. Alternativamente, el usuario puede escanear un QR desde Meta para abrir el chat

### 2.6 Customer Service Window (CSW)

**Regla crítica de Meta:** En modo conversacional normal, solo puedes enviar mensajes de texto libre
a un usuario dentro de las **24 horas** posteriores a su último mensaje entrante.

- Si han pasado más de 24h, Meta rechaza el envío con error `131026`
- Para mensajes fuera de la CSW, debes usar **plantillas (templates)** aprobadas por Meta
- Las plantillas requieren un proceso de aprobación en Meta (24-48h)

### 2.7 Development vs Production

| Modo | Envío a test numbers | Envío a cualquier número | Webhooks | Plantillas |
|---|---|---|---|---|
| **Development** | Sí | No | Sí (solo test numbers) | No disponibles |
| **Production** | Sí | Sí | Sí | Requeridas para CSW expirada |

Para pasar a producción:
1. Agregar método de pago en Meta Business
2. Iniciar la verificación de la app (requiere documentación)
3. Configurar plantillas de mensajes

---

## 3. Variables de entorno

Archivo `backend/.env` y variables en Railway:

```bash
# ── Meta Cloud API / PyWa ──────────────────────────────────────────
META_WHATSAPP_TOKEN=EAAx...                    # Token de acceso permanente
META_WHATSAPP_PHONE_NUMBER_ID=1180291398493188  # ID del número (NO el teléfono)
META_WHATSAPP_API_VERSION=22.0                  # Sin prefijo "v" — PyWa hace float()
META_WHATSAPP_BUSINESS_ACCOUNT_ID=...           # WABA ID (opcional)
META_WEBHOOK_VERIFY_TOKEN=...                   # Token para validar webhook de Meta
```

Definiciones en `backend/app/core/config.py`:

```python
# ── Meta Cloud API / PyWa ──────────────────────────────────────────
meta_whatsapp_token: str | None = None
meta_whatsapp_phone_number_id: str | None = None
meta_whatsapp_api_version: str = "22.0"
meta_whatsapp_business_account_id: str | None = None
meta_webhook_verify_token: str | None = None
```

**Nota sobre `API_VERSION`:** PyWa internamente hace `float(api_version)`. Si el valor contiene
el prefijo "v" (ej: `"v22.0"`), falla con `could not convert string to float: 'v22.0'`.
El provider aplica `.lstrip("v")` como protección adicional.

---

## 4. Backend: Dependencias

```txt
# requirements.txt / pyproject.toml
pywa>=2.0                    # WhatsApp Cloud API wrapper
apscheduler>=3.10            # Scheduler para cola de notificaciones
sqlalchemy>=2.0              # ORM
psycopg>=3.1                 # Driver PostgreSQL
fastapi>=0.110               # Framework web
```

---

## 5. Backend: Modelos de base de datos

### 5.1 `notification_events`

Archivo: `backend/app/infrastructure/db/models/notifications.py`

```python
class NotificationEventModel(Base):
    __tablename__ = "notification_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    notification_type: Mapped[str] = mapped_column(String(50), nullable=False)
    recipient_doctor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("doctors.id"), nullable=True, index=True
    )
    recipient_phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    idempotency_key: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    provider: Mapped[str | None] = mapped_column(String(30), nullable=True)
    provider_message_id: Mapped[str | None] = mapped_column(String(120), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(60), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    retry_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

### 5.2 `confirmation_requests`

Archivo: `backend/app/infrastructure/db/models/confirmations.py`

```python
class ConfirmationRequestModel(Base):
    __tablename__ = "confirmation_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    confirmation_type: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", index=True)
    idempotency_key: Mapped[str] = mapped_column(String(140), nullable=False, unique=True)
    response_token: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    doctor_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("doctors.id"), nullable=False, index=True
    )
    notification_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("notification_events.id"), nullable=True, index=True
    )
    assignment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("calendar_assignments.id"), nullable=True, index=True
    )
    responded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    response_channel: Mapped[str | None] = mapped_column(String(30), nullable=True)
    response_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
```

### 5.3 `doctors` (campo `whatsapp_phone`)

Archivo: `backend/app/infrastructure/db/models/doctors.py`

```python
# Campo relevante (el campo "phone" fue eliminado en migración 20260527_0041)
whatsapp_phone: Mapped[str] = mapped_column(String(40), nullable=False)
```

---

## 6. Backend: Proveedores de notificación

Archivo: `backend/app/application/notifications/providers.py`

### 6.1 `NotificationProvider` (Protocol)

```python
class NotificationProvider(Protocol):
    def send(self, phone: str, message: str) -> str: ...
    @property
    def name(self) -> str: ...
```

### 6.2 `FakeProvider`

Provider para desarrollo local y tests. Almacena mensajes en memoria.

```python
class FakeProvider:
    name = "fake"
    sent: list[dict]  # lista de clase para inspección en tests

    def send(self, phone: str, message: str) -> str:
        msg_id = f"fake-{uuid.uuid4().hex[:8]}"
        self.sent.append({"phone": phone, "message": message, "id": msg_id})
        return msg_id
```

### 6.3 `MetaCloudAPIProvider`

Provider real que usa PyWa para enviar mensajes por Meta Cloud API.

```python
class MetaCloudAPIProvider:
    name = "meta_cloud_api"

    def __init__(self, phone_number_id: str | None = None) -> None:
        self.token = settings.meta_whatsapp_token
        self.phone_number_id = phone_number_id or settings.meta_whatsapp_phone_number_id
        self.api_version = settings.meta_whatsapp_api_version.lstrip("v")
        if not self.token or not self.phone_number_id:
            raise ValueError("Meta WhatsApp token y phone_number_id son requeridos")

    def send(self, phone: str, message: str) -> str:
        from pywa import WhatsApp
        client = WhatsApp(
            phone_id=self.phone_number_id,
            token=self.token,
            api_version=self.api_version,
        )
        clean_phone = normalize_phone(phone)
        msg = client.send_message(to=clean_phone, text=message)
        msg_id = msg.id if hasattr(msg, "id") else str(msg)
        return msg_id
```

**Puntos importantes:**
- `api_version` usa `.lstrip("v")` — si la config dice `"v22.0"`, se convierte a `"22.0"`
- `send_message()` envía texto libre (NO plantillas)
- `normalize_phone()` limpia el número antes de enviarlo
- El error `131026` de Meta significa CSW expirada (más de 24h sin interacción del usuario)

### 6.4 `phone_utils`

Archivo: `backend/app/application/notifications/phone_utils.py`

```python
def normalize_phone(phone: str) -> str:
    """Normaliza a solo dígitos, sin '+', sin 'whatsapp:', sin espacios."""
    cleaned = phone.removeprefix("whatsapp:").strip()
    cleaned = cleaned.removeprefix("+")
    cleaned = re.sub(r"\D", "", cleaned)
    return cleaned


def phones_match(phone_a: str, phone_b: str) -> bool:
    """Compara dos números independientemente del formato.
    Maneja diferencias de código de país (ej: 18092186876 vs 8092186876).
    """
    a = normalize_phone(phone_a)
    b = normalize_phone(phone_b)
    if a == b:
        return True
    # Un número puede incluir código de país y el otro no
    if len(a) > len(b) and a.endswith(b):
        return True
    if len(b) > len(a) and b.endswith(a):
        return True
    return False
```

**Contexto:** Meta envía el número con código de país (ej: `18092186876` para República Dominicana),
pero en la BD se almacenó sin él (`8092186876`). El `endswith` maneja ambas variantes.

---

## 7. Backend: Servicio de notificaciones

Archivo: `backend/app/application/notifications/service.py`

### 7.1 `queue()` — Encolar notificación

```python
def queue(
    self,
    *,
    notification_type: str,
    idempotency_key: str,
    recipient_doctor_id: str | None,
    recipient_phone: str | None,
    payload: dict,
    scheduled_for: datetime | None = None,
    assignment_id: str | None = None,
    mission_id: str | None = None,
    created_by: str | None = None,
) -> NotificationEventModel:
    existing = self.repo.get_by_idempotency_key(idempotency_key)
    if existing is not None:
        return existing  # idempotencia: no duplica

    now = datetime.now(UTC)
    event = NotificationEventModel(
        id=str(uuid4()),
        notification_type=notification_type,
        idempotency_key=idempotency_key,
        recipient_phone=recipient_phone,
        status="pending",
        retry_count=0,
        payload=payload,
        ...
    )
    return self.repo.add(event)
```

### 7.2 `process_pending()` — Procesar cola

```python
MAX_RETRIES = 3

def process_pending(self) -> dict:
    """Procesa hasta 50 notificaciones pendientes."""
    pending = self.repo.list_pending(limit=50)
    sent = failed = skipped = 0

    for event in pending:
        # Saltar si no hay teléfono
        if not event.recipient_phone:
            event.status = "skipped"
            skipped += 1
            continue

        message = (event.payload or {}).get("message", "")

        try:
            msg_id = self.provider.send(event.recipient_phone, message)
            event.status = "sent"
            event.provider = self.provider.name
            event.provider_message_id = msg_id
            sent += 1
        except Exception as exc:
            event.retry_count += 1
            event.error_code = getattr(exc, "code", None)
            event.error_message = str(exc)
            if event.retry_count >= MAX_RETRIES:
                event.status = "failed"
                failed += 1
            # si no, queda pending para siguiente ciclo

    return {"sent": sent, "failed": failed, "skipped": skipped}
```

**Selección de provider:**
```python
# En jobs.py:
if settings.meta_whatsapp_token and settings.meta_whatsapp_phone_number_id:
    provider = MetaCloudAPIProvider()
else:
    provider = FakeProvider()
```

---

## 8. Backend: Scheduler (APScheduler)

Archivo: `backend/app/main.py` (configuración) y `backend/app/application/scheduler/jobs.py` (jobs)

### 8.1 Configuración en `main.py`

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        process_notification_queue,
        IntervalTrigger(seconds=30),       # cada 30 segundos
        id="process_notifications",
    )
    scheduler.add_job(
        send_pre_service_reminders,
        IntervalTrigger(minutes=5),        # cada 5 minutos
        id="send_reminders",
    )
    scheduler.add_job(
        check_unconfirmed_escalamiento,
        IntervalTrigger(minutes=15),       # cada 15 minutos
        id="check_escalamiento",
    )
    scheduler.add_job(
        process_overdue_confirmations,
        IntervalTrigger(minutes=10),       # cada 10 minutos
        id="process_overdue",
    )
    scheduler.start()
    yield
    scheduler.shutdown(wait=False)
```

### 8.2 Jobs principales

| Job | Intervalo | Descripción |
|---|---|---|
| `process_notification_queue` | 30s | Procesa notificaciones pendientes y las envía |
| `send_pre_service_reminders` | 5min | Envía recordatorios 12h antes del servicio |
| `check_unconfirmed_escalamiento` | 15min | Escala confirmaciones pendientes >24h |
| `process_overdue_confirmations` | 10min | Marca confirmaciones vencidas |

---

## 9. Backend: Webhook de WhatsApp

Archivo: `backend/app/api/routes/webhooks.py`

### 9.1 Verificación del webhook (GET)

Meta llama a este endpoint para verificar que el servidor responde correctamente.

```python
@router.get("/whatsapp", response_class=PlainTextResponse)
def verify_webhook(
    hub_mode: str = Query(alias="hub.mode"),
    hub_verify_token: str = Query(alias="hub.verify_token"),
    hub_challenge: str = Query(alias="hub.challenge"),
) -> str:
    if hub_mode == "subscribe" and hub_verify_token == settings.meta_webhook_verify_token:
        return hub_challenge
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)
```

### 9.2 Recepción de mensajes (POST)

Meta envía un POST a este endpoint cada vez que un usuario responde a un mensaje.

```python
@router.post("/whatsapp")
async def receive_whatsapp_message(
    request: Request,
    session: Annotated[Session, Depends(get_db_session)],
) -> dict:
    body = await request.json()
    try:
        messages = body.get("entry", [{}])[0].get("changes", [{}])[0].get("value", {}).get("messages", [])
        for msg in messages:
            if msg.get("type") == "text" and msg["text"]["body"].strip() == "1":
                _confirm_by_phone(session, msg["from"], msg["id"])
    except Exception:
        logger.exception("Error processing WhatsApp webhook")
    return {"status": "ok"}
```

### 9.3 Formato del payload de Meta

```json
{
    "object": "whatsapp_business_account",
    "entry": [{
        "id": "1180291398493188",
        "changes": [{
            "value": {
                "messaging_product": "whatsapp",
                "metadata": {
                    "display_phone_number": "18092438778",
                    "phone_number_id": "1180291398493188"
                },
                "contacts": [{
                    "profile": {"name": "Hendrick Rafael"},
                    "wa_id": "18092186876"
                }],
                "messages": [{
                    "from": "18092186876",
                    "id": "wamid.HBgLMTgwOTIxODY4NzYVAgAS",
                    "timestamp": "1716825600",
                    "text": {"body": "1"},
                    "type": "text"
                }]
            },
            "field": "messages"
        }]
    }]
}
```

### 9.4 `_confirm_by_phone` — Procesar confirmación

```python
def _confirm_by_phone(session: Session, sender_phone: str, message_id: str) -> None:
    # 1. Buscar doctor por teléfono (usando phones_match)
    doctors = session.scalars(
        select(DoctorModel).where(DoctorModel.whatsapp_phone.is_not(None))
    ).all()
    doctor = next((d for d in doctors if phones_match(d.whatsapp_phone, sender_phone)), None)
    if not doctor:
        return

    # 2. Buscar solicitud de confirmación pendiente más reciente
    request = session.scalars(
        select(ConfirmationRequestModel)
        .where(
            ConfirmationRequestModel.doctor_id == doctor.id,
            ConfirmationRequestModel.status.in_(["pending", "received"]),
        )
        .order_by(ConfirmationRequestModel.created_at.desc())
        .limit(1)
    ).first()
    if not request:
        return

    # 3. Marcar como confirmada
    request.status = "confirmed"
    request.responded_at = datetime.now(UTC)
    request.response_channel = "whatsapp"
    request.response_payload = {"whatsapp_message_id": message_id, "reply": "1"}
    session.commit()
```

**Flujo:**
1. Meta envía POST al webhook con `msg["from"]` = `"18092186876"`
2. `phones_match("8092186876", "18092186876")` → `True` (endswith)
3. Encuentra el `ConfirmationRequestModel` más reciente con status `pending`/`received`
4. Marca `status="confirmed"`, `response_channel="whatsapp"`

---

## 10. Migración de BD: `phone` → `whatsapp_phone`

### 10.1 Problema original

El modelo `doctors` tenía dos campos:
- `phone` — usado solo para display, nunca para notificaciones
- `whatsapp_phone` — usado para notificaciones WhatsApp, pero nullable

El formulario frontend solo exponía `phone`. Los médicos llenaban `phone` pero `whatsapp_phone`
quedaba `NULL`, por lo que nunca recibían notificaciones.

### 10.2 Migración

Archivo: `migrations/versions/20260527_0041_replace_phone_with_whatsapp_phone.py`

```python
def upgrade() -> None:
    # Migrar datos existentes
    op.execute("""
        UPDATE doctors SET whatsapp_phone = phone
        WHERE whatsapp_phone IS NULL AND phone IS NOT NULL;
    """)
    # Fallback para los que no tenían phone
    op.execute("""
        UPDATE doctors SET whatsapp_phone = '0000000000'
        WHERE whatsapp_phone IS NULL;
    """)
    op.execute("ALTER TABLE doctors DROP COLUMN IF EXISTS phone;")
    op.execute("ALTER TABLE doctors ALTER COLUMN whatsapp_phone SET NOT NULL;")
```

### 10.3 Cambios aplicados en cascada

| Capa | Cambio |
|---|---|
| **Modelo DB** | `phone` eliminado, `whatsapp_phone` NOT NULL |
| **Schema Pydantic** | `DoctorRead`, `CreateDoctorRequest`, `UpdateDoctorRequest` sin `phone` |
| **API Routes** | `create_doctor` sin `phone=payload.phone` |
| **Domain Service** | `create_doctor`, `update_doctor`, `list_by_day` actualizados |
| **Audit Presenter** | `FIELD_LABELS` sin `"phone": "teléfono"` |
| **Frontend Types** | `DoctorRead`, `CreateDoctorPayload`, `DoctorByDayItem` actualizados |
| **Frontend Form** | Campo "Teléfono" → "WhatsApp", requerido, placeholder `+18095551234` |
| **Frontend List** | `doctor.whatsapp_phone` en vez de `doctor.phone` |
| **Frontend By Day** | `doc.whatsapp_phone` en vez de `doc.phone` |
| **Tests (13 archivos)** | Todos los tests actualizados a `whatsapp_phone="+18095551234"` |

---

## 11. Problemas encontrados y soluciones

### 11.1 `api_version` con prefijo "v"

**Error:** `could not convert string to float: 'v22.0'`

**Causa:** PyWa hace `float(api_version)`. El valor `"v22.0"` tiene un prefijo "v"
que `float()` no puede parsear.

**Solución:**
1. Config: `meta_whatsapp_api_version: str = "22.0"` (sin "v")
2. Provider: `self.api_version = settings.meta_whatsapp_api_version.lstrip("v")` (protección adicional)

### 11.2 Match de teléfono con código de país

**Error:** Médico no encontrado al procesar respuesta "1" del webhook.

**Causa:** Meta envía `from="18092186876"` (con código de país `1`), pero en la BD
el doctor tiene `whatsapp_phone="8092186876"` (sin código de país).

**Solución:** `phones_match()` usa `endswith` para manejar la diferencia:

```python
if len(a) > len(b) and a.endswith(b):
    return True
if len(b) > len(a) and b.endswith(a):
    return True
```

### 11.3 Customer Service Window (CSW)

**Error:** `131026` — mensaje rechazado por Meta.

**Causa:** Han pasado más de 24h desde el último mensaje del usuario. Meta no permite
mensajes de texto libre fuera de la CSW.

**Solución:** Para mensajes proactivos (fuera de la CSW), se necesita usar **plantillas
de mensajes (templates)** aprobadas por Meta. El sistema actual usa texto libre, que solo
funciona dentro de la CSW.

**Workaround temporal:** Pedir al usuario que envíe cualquier mensaje al número de la
empresa antes de enviar notificaciones. Esto reabre la CSW por 24h.

### 11.4 Dev Mode — solo números de prueba

**Error:** Mensajes no entregados a números no registrados.

**Causa:** En modo Development, Meta solo permite enviar mensajes a números registrados
como "test numbers" en el dashboard.

**Solución:** Agregar cada número de médico como test number en Meta Dashboard, o migrar
la app a modo Production.

### 11.5 Webhook no recibe mensajes entrantes

**Síntoma:** El webhook responde `{"status":"ok"}` cuando se simula, pero Meta no envía
webhooks reales.

**Causas posibles:**
- Campo `messages` no suscrito en Webhook Fields
- Webhook URL apuntando a entorno incorrecto (producción vs staging)
- Número no registrado como test number
- CSW expirada (aplica solo al envío, no a la recepción)

**Verificación:**
1. Probar botón "Probar" en cada campo de webhook en Meta Dashboard
2. Simular POST al webhook manualmente (ver sección 12)
3. Usar endpoint `/diagnostic` para ver webhook log

---

## 12. Pruebas y debugging

### 12.1 Simulación de webhook

Para probar el flujo de confirmación sin depender de Meta:

```bash
curl -s -X POST "https://{dominio}/api/webhooks/whatsapp" \
  -H "Content-Type: application/json" \
  -d '{
    "object": "whatsapp_business_account",
    "entry": [{
      "id": "1180291398493188",
      "changes": [{
        "value": {
          "messaging_product": "whatsapp",
          "metadata": {
            "display_phone_number": "18092438778",
            "phone_number_id": "1180291398493188"
          },
          "contacts": [{"profile": {"name": "Doctor"}, "wa_id": "18092186876"}],
          "messages": [{
            "from": "18092186876",
            "id": "wamid.test-simulado",
            "timestamp": "1716825600",
            "text": {"body": "1"},
            "type": "text"
          }]
        },
        "field": "messages"
      }]
    }]
  }'
```

**Nota:** `"from"` debe usar el formato con código de país (`18092186876`, no `8092186876`).

### 12.2 Endpoint `/test-notify` (temporal, staging)

Crea una notificación de prueba + confirmation request para el doctor con teléfono `8092186876`.

```bash
curl -s -X POST "https://{dominio}/api/webhooks/test-notify?secret=staging-setup-2026"
```

**Respuesta:**
```json
{
    "status": "queued",
    "notification_id": "uuid...",
    "confirmation_id": "uuid...",
    "doctor_id": "uuid...",
    "message": "Notificacion en cola + confirmation request creado. Responde 1 al WhatsApp."
}
```

### 12.3 Endpoint `/diagnostic` (temporal, staging)

Muestra estado completo del sistema de notificaciones: notificaciones, confirmaciones,
doctores, webhook log.

```bash
curl -s "https://{dominio}/api/webhooks/diagnostic?secret=staging-setup-2026" | python3 -m json.tool
```

### 12.4 Verificación manual de flujo

1. Encolar notificación: `curl -X POST /api/webhooks/test-notify?secret=...`
2. Esperar ~30s a que el scheduler procese la cola
3. Verificar en WhatsApp que el mensaje llegó
4. Responder `1` desde WhatsApp
5. Verificar webhook: `curl /api/webhooks/diagnostic?secret=...`
6. Confirmar que `confirmation_requests.status` = `confirmed`

---

## 13. Flujo de confirmación paso a paso

```
PASO 1: Sistema encola notificación
───────────────────────────────────
NotificationService.queue(
    notification_type="test",
    idempotency_key="test:{uuid}",
    recipient_phone="8092186876",
    payload={"message": "Hola Dr. ... Responda 1 para confirmar."}
)
→ INSERT INTO notification_events (status="pending")

PASO 2: APScheduler procesa cola (cada 30s)
──────────────────────────────────────────
process_notification_queue()
→ MetaCloudAPIProvider.send("8092186876", "Hola Dr. ...")
→ PyWa → Meta Cloud API → WhatsApp
→ UPDATE notification_events SET status="sent", provider="meta_cloud_api"

PASO 3: Médico recibe y responde "1"
────────────────────────────────────
WhatsApp → Meta detecta mensaje entrante

PASO 4: Meta envía webhook a nuestro backend
───────────────────────────────────────────
POST /api/webhooks/whatsapp
Body: {
  "entry": [{
    "changes": [{
      "value": {
        "messages": [{
          "from": "18092186876",    ← con código de país
          "text": {"body": "1"}
        }]
      }
    }]
  }]
}

PASO 5: Backend procesa webhook
──────────────────────────────
receive_whatsapp_message()
→ msg["text"]["body"].strip() == "1"? Sí
→ _confirm_by_phone(session, "18092186876", "wamid.xxx")

PASO 6: Buscar doctor por teléfono
──────────────────────────────────
phones_match("8092186876", "18092186876")
→ "18092186876".endswith("8092186876") → True ✓
→ Doctor: Hendrick Rafael

PASO 7: Buscar solicitud pendiente
──────────────────────────────────
SELECT * FROM confirmation_requests
WHERE doctor_id = '34743081-...'
  AND status IN ('pending', 'received')
ORDER BY created_at DESC LIMIT 1
→ Encontrada: id='0048bf87-...', status='pending'

PASO 8: Confirmar solicitud
───────────────────────────
UPDATE confirmation_requests
SET status = 'confirmed',
    responded_at = NOW(),
    response_channel = 'whatsapp',
    response_payload = '{"whatsapp_message_id": "wamid.xxx", "reply": "1"}'
WHERE id = '0048bf87-...'

PASO 9: Flujo completado ✓
───────────────────────────
```

---

## Referencias

- [Meta Cloud API Documentation](https://developers.facebook.com/docs/whatsapp/cloud-api)
- [PyWa Documentation](https://pywa.readthedocs.io/)
- [Meta Webhook Guide](https://developers.facebook.com/docs/whatsapp/cloud-api/webhooks/components)
- [Meta API Versioning](https://developers.facebook.com/docs/graph-api/guides/versioning)
- [Customer Service Window](https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-messages#customer-service-window)
- [Message Templates](https://developers.facebook.com/docs/whatsapp/cloud-api/guides/send-message-templates)
