# 🛡️ OWASP ASI Top 10 — Reporte de Cumplimiento de Seguridad

**Proyecto:** Sistema de Turnos Médicos  
**Fecha:** 2026-06-11  
**Alcance:** Análisis completo del código (backend FastAPI + frontend React + bot Telegram LLM)  
**Metodología:** OWASP Agentic Security Initiative (ASI) Top 10 v1.0  
**Tipo:** Solo lectura — sin modificaciones al código

---

## 📊 Resumen Ejecutivo: 3/10 Controles Aprobados

| Riesgo | Nombre | Estado | Puntuación | Severidad Máxima |
|--------|--------|--------|-----------|-------------------|
| ASI-01 | Prompt Injection Protection | ❌ FAIL | 2/10 | 🔴 CRÍTICA |
| ASI-02 | Insecure Tool Use | ✅ PASS | 8/10 | 🟢 BAJA |
| ASI-03 | Excessive Agency | ❌ FAIL | 3/10 | 🔴 CRÍTICA |
| ASI-04 | Unauthorized Escalation | ✅ PASS | 9/10 | 🟢 BAJA |
| ASI-05 | Trust Boundary Violation | ❌ FAIL | 2/10 | 🔴 CRÍTICA |
| ASI-06 | Insufficient Logging & Audit | ❌ FAIL | 4/10 | 🟠 ALTA |
| ASI-07 | Insecure Identity Management | ❌ FAIL | 3/10 | 🔴 CRÍTICA |
| ASI-08 | Policy Bypass | ✅ PASS | 8/10 | 🟡 MEDIA |
| ASI-09 | Supply Chain Integrity | ❌ FAIL | 3/10 | 🔴 CRÍTICA |
| ASI-10 | Behavioral Monitoring | ❌ FAIL | 4/10 | 🟠 ALTA |

**7 controles REPROBADOS, 3 aprobados.**

---

## 🔴 Hallazgos Críticos (Acción Inmediata Requerida)

### 🚨 CRÍTICO #1: API Keys vivas expuestas en el código
**Controles:** ASI-05, ASI-07  
**Archivos:** `.env`, `.claude/settings.local.json`

Las siguientes credenciales de producción están hardcodeadas en archivos del repositorio:

| Secreto | Valor Expuesto | Archivo |
|---------|---------------|---------|
| `DEEPSEEK_API_KEY` | `sk-2260a89c01b6424a9f5c0fc47dfdd790` | `.env` L17, `.claude/settings.local.json` L106 |
| `TELEGRAM_BOT_TOKEN` | `8729776404:AAEBQ2-upNoo8MRiA-ERqCLazEcDOmKg3NY` | `.env` L15, `.claude/settings.local.json` L122 |
| `SMTP_PASSWORD` | `mifh kfxd rkxm tdtk` | `.env` L31 |
| `SECRET_KEY` | `d29bb115fc5eeca179c46dd43450919f...` | `.env` L13 |
| JWT Bearer Token (admin) | `eyJhbGciOiJIUzI1NiIs...` | `.claude/settings.local.json` L48-49 |

**Impacto:** Compromiso total del bot de Telegram, acceso financiero a DeepSeek, acceso al correo, capacidad de firmar JWT arbitrarios.

**Instrucciones de remediación:**
1. **ROTAR INMEDIATAMENTE** todas las API keys expuestas:
   - DeepSeek: Ve a https://platform.deepseek.com/api_keys → revoca y genera nueva
   - Telegram: Contacta @BotFather → `/revoke` y genera nuevo token
   - Gmail: Ve a https://myaccount.google.com/apppasswords → revoca y genera nueva
   - `SECRET_KEY`: Genera una nueva con `openssl rand -hex 32`
2. Verificar que `.env` esté en `.gitignore`:
   ```bash
   echo ".env" >> .gitignore
   git rm --cached .env  # si ya está trackeado
   ```
3. Eliminar secrets de `.claude/settings.local.json` y usar variables de entorno
4. Usar `railway variables` o `vercel env` para secrets en producción
5. Ejecutar `git filter-branch` o `git-filter-repo` para limpiar el historial de Git

---

### 🚨 CRÍTICO #2: Webhook de notificaciones Telegram sin autenticación
**Control:** ASI-05  
**Archivo:** `backend/app/api/routes/telegram_notification_webhook.py`

El endpoint `POST /webhooks/telegram-notification` **no tiene ningún mecanismo de autenticación**. Cualquiera puede enviar requests falsificando confirmaciones de servicios y vinculaciones de doctores.

```python
# Línea 20-152: Sin verificación de token, HMAC, o firma
@router.post("/telegram-notification")
async def telegram_notification_webhook(request: Request):
    # ❌ Sin autenticación — acepta requests de cualquiera
```

**Instrucciones de remediación:**
```python
# Agregar verificación de token secreto (como ya se hace en el webhook principal)
TELEGRAM_NOTIFICATION_SECRET = os.getenv("TELEGRAM_NOTIFICATION_WEBHOOK_SECRET")

@router.post("/telegram-notification")
async def telegram_notification_webhook(request: Request):
    # ✅ Verificar header de token secreto
    header_token = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if not secrets.compare_digest(
        header_token or "", 
        TELEGRAM_NOTIFICATION_SECRET or ""
    ):
        raise HTTPException(status_code=401, detail="Unauthorized")
    # ... resto del handler
```

---

### 🚨 CRÍTICO #3: Sin protección contra Prompt Injection en el bot LLM
**Control:** ASI-01  
**Archivos:** `backend/app/application/telegram/intent_classifier.py:80-104`, `agent.py:673-707`

El texto del usuario se pasa **directamente al LLM sin ninguna sanitización**. No existe ninguna función de validación de input antes de la ejecución del agente.

```python
# intent_classifier.py L100-104 — El input del usuario se inyecta directamente
{"role": "user", "content": user_text},  # ❌ Sin sanitización
```

**Instrucciones de remediación:**
1. Crear un `InputSanitizer` que se ejecute antes del LLM:
```python
# backend/app/application/telegram/input_sanitizer.py
import re

FORBIDDEN_PATTERNS = [
    r"(ignor|olvida|desobedece)\s+(todas|las)\s+instrucciones",
    r"(eres|eres ahora|actúas como)\s+(?:un\s+)?(?:nuevo\s+)?(?:asistente|sistema|rol)",
    r"(system\s*:|<system>|\[system\]|<<system>>)",
    r"(prompt\s+(injection|leak|leaking|extract))",
    r"(mu[eé]strame|dime|revela|enseña)\s+(tu|el)\s+(prompt|system\s+prompt)",
    r"(token|contraseña|password|api.key|secret)",
]

class InputSanitizer:
    def sanitize(self, user_input: str) -> tuple[bool, str]:
        """Retorna (is_safe, sanitized_input)"""
        lowered = user_input.lower()
        for pattern in FORBIDDEN_PATTERNS:
            if re.search(pattern, lowered):
                return False, ""
        # Limitar longitud máxima
        if len(user_input) > 2000:
            return False, ""
        return True, user_input.strip()
```

2. Integrar en el pipeline del agente antes de `nlu_engine.classify()`:
```python
# agent.py - Antes de _process_llm_first()
is_safe, sanitized = self.input_sanitizer.sanitize(text)
if not is_safe:
    return "⚠️ No puedo procesar esa solicitud."
```

---

### 🚨 CRÍTICO #4: `"latest"` en 15/18 dependencias frontend
**Control:** ASI-09  
**Archivo:** `frontend/package.json`

El 83% de las dependencias frontend usan `"latest"` como versión, haciendo las builds **no determinísticas**:

```json
"react": "latest",           // ❌
"vite": "latest",            // ❌  
"typescript": "latest",      // ❌
"lucide-react": "latest",    // ❌
```

**Instrucciones de remediación:**
```bash
# 1. Instalar versiones actuales y fijarlas
cd frontend
npm install react@$(npm view react version) --save-exact
npm install vite@$(npm view vite version) --save-exact
npm install typescript@$(npm view typescript version) --save-exact
npm install lucide-react@$(npm view lucide-react version) --save-exact
# ... repetir para cada dependencia "latest"

# 2. Agregar Dependabot o Renovate para actualizaciones automáticas con PR
# .github/dependabot.yml
```

---

### 🚨 CRÍTICO #5: Dependencias Python sin límite superior (13/23)
**Control:** ASI-09  
**Archivo:** `requirements.txt`

Más de la mitad de las dependencias usan `>=` sin cota superior:

```txt
openai>=1.0.0          # ❌ Podría instalar versión maliciosa
httpx>=0.27.0           # ❌
weasyprint>=68.0        # ❌
apscheduler>=3.10.0     # ❌
numpy>=2.0.0            # ❌
scikit-learn>=1.5.0     # ❌
```

**Instrucciones de remediación:**
```bash
# 1. Generar requirements.txt con versiones exactas
pip freeze > requirements-frozen.txt

# 2. O usar pip-tools para pinning con hash
pip install pip-tools
pip-compile --generate-hashes requirements.in -o requirements.txt

# 3. Verificar vulnerabilidades conocidas
pip install safety
safety check -r requirements.txt
```

---

## 🟠 Hallazgos Altos

### ⚠️ ALTO #6: El agente de Telegram no tiene límites de capacidad (Excessive Agency)
**Control:** ASI-03  
**Archivos:** `backend/app/application/telegram/agent.py:774-861`, `orchestrator.py:62-201`

Una vez que un usuario `encargado` o `admin` vincula su cuenta de Telegram, el agente tiene acceso **total de lectura** a prácticamente todas las tablas del sistema. No hay execution rings ni capability boundaries. Un `encargado` tiene exactamente los mismos poderes de agente que un `admin`.

**Instrucciones de remediación:**
```python
# tool_registry.py - Agregar verificación de permisos por herramienta
class ToolRegistry:
    TOOL_PERMISSIONS = {
        "sql_query": ["view_audit"],        # Solo admin
        "export_pdf": ["export_reports"],   # Solo con permiso explícito
        "list_doctors": [],                 # Todos los vinculados
        "list_calendars": [],               # Todos los vinculados
        "mission_candidates": ["manage_missions"],  # Solo encargado/admin
    }

    def execute(self, tool_name: str, params: dict, user_role: str, 
                user_permissions: list[str]) -> Any:
        required = self.TOOL_PERMISSIONS.get(tool_name)
        if required is None:
            raise PermissionError(f"Unknown tool: {tool_name}")
        if required:
            if user_role != "admin" and not all(p in user_permissions for p in required):
                raise PermissionError(f"Insufficient permissions for {tool_name}")
        handler = self._tools.get(tool_name)
        return handler(**params)
```

---

### ⚠️ ALTO #7: Logs de auditoría no son a prueba de manipulación
**Control:** ASI-06  
**Archivos:** `backend/app/infrastructure/db/models/audit.py`, `repositories/audit.py`

Los eventos de auditoría se guardan en una tabla PostgreSQL normal, **sin protección contra escritura**. Un atacante con acceso a la BD puede modificar o eliminar registros de auditoría sin dejar rastro.

**Instrucciones de remediación:**
```sql
-- Opción 1: Trigger que previene UPDATE/DELETE en audit_events
CREATE OR REPLACE FUNCTION prevent_audit_tamper()
RETURNS TRIGGER AS $$
BEGIN
    IF TG_OP = 'UPDATE' OR TG_OP = 'DELETE' THEN
        RAISE EXCEPTION 'audit_events table is append-only';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER audit_events_append_only
    BEFORE UPDATE OR DELETE ON audit_events
    FOR EACH ROW EXECUTE FUNCTION prevent_audit_tamper();
```

```python
# Opción 2: Implementar hash chain (Merkle tree) en aplicación
import hashlib, json

def compute_audit_hash(event: dict, previous_hash: str) -> str:
    """Cadena de hashes para integridad de auditoría"""
    payload = json.dumps(event, sort_keys=True) + previous_hash
    return hashlib.sha256(payload.encode()).hexdigest()
```

---

### ⚠️ ALTO #8: Sin circuit breakers ni kill switch
**Control:** ASI-10  
**Archivo:** Todo el sistema de agente y notificaciones

No existe ningún mecanismo de circuit breaker para las APIs externas (DeepSeek, Telegram, Meta WhatsApp). Si la API de DeepSeek empieza a fallar repetidamente, el sistema sigue reintentando indefinidamente. No hay kill switch para desactivar el bot de emergencia.

**Instrucciones de remediación:**
```python
# backend/app/infrastructure/circuit_breaker.py
import time
from enum import Enum

class CircuitState(Enum):
    CLOSED = "closed"         # Funcionando normal
    OPEN = "open"             # Falla — rechaza llamadas
    HALF_OPEN = "half_open"   # Probando recuperación

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = 0
        self.state = CircuitState.CLOSED

    def call(self, func, *args, **kwargs):
        if self.state == CircuitState.OPEN:
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
            else:
                raise Exception("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.CLOSED
                self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN
            raise e
```

```python
# Feature flag como kill switch (ya tienes FeatureFlagModel)
# Agregar flag "telegram_bot_enabled" y verificarlo en el webhook
@router.post("/webhook")
async def telegram_webhook(request: Request):
    if not feature_flags.is_enabled("telegram_bot_enabled"):
        return JSONResponse({"status": "bot_disabled"}, status_code=503)
    # ...
```

---

## 🟡 Hallazgos Medios

### ⚠️ MEDIO #9: Sanitización solo en output, no en input
**Control:** ASI-01  
**Archivo:** `backend/app/application/telegram/sanitize.py`

La función `sanitize_text()` solo limpia HTML tags para la respuesta al usuario. No se usa NUNCA en el input antes del LLM.

---

### ⚠️ MEDIO #10: Webhook `/webhooks/test-notify` con secret hardcodeado
**Control:** ASI-05  
**Archivo:** `backend/app/api/routes/webhooks.py:67`

```python
if secret != "staging-setup-2026":  # ❌ Secret predecible
```

**Instrucciones de remediación:** Usar variable de entorno `WEBHOOK_TEST_NOTIFY_SECRET`.

---

### ⚠️ MEDIO #11: Rate limiter en memoria (se resetea al reiniciar)
**Control:** ASI-10  
**Archivo:** `backend/app/infrastructure/rate_limiter.py`

El rate limiter es por-worker y en memoria. Un ataque distribuido entre workers puede evadir los límites.

**Instrucciones de remediación:** Migrar a Redis para rate limiting distribuido:
```python
# Usar Redis + sliding window
import redis.asyncio as redis

class RedisRateLimiter:
    async def allow(self, key: str, max_requests: int = 20, window: int = 60) -> bool:
        now = time.time()
        async with self.redis.pipeline() as pipe:
            await pipe.zremrangebyscore(key, 0, now - window)
            await pipe.zcard(key)
            await pipe.zadd(key, {str(now): now})
            await pipe.expire(key, window)
            results = await pipe.execute()
        return results[1] < max_requests
```

---

### ⚠️ MEDIO #12: Validación SQL del agente es solo por regex
**Control:** ASI-08  
**Archivo:** `backend/app/application/telegram/sql_agent/security.py:122-139`

La función `validate_sql()` usa regex para bloquear keywords. Técnicas de ofuscación SQL podrían evadir estas validaciones.

**Instrucciones de remediación:**
```python
# Agregar capa adicional: ejecutar como usuario de BD con permisos restringidos
# Crear rol readonly en PostgreSQL
# CREATE ROLE telegram_agent WITH LOGIN PASSWORD '...' 
# GRANT SELECT ON ALL TABLES IN SCHEMA public TO telegram_agent;
# REVOKE SELECT ON users, audit_events, telegram_interactions FROM telegram_agent;

# Usar dos conexiones: admin para operaciones normales, readonly para agente
telegram_engine = create_engine(DATABASE_URL, connect_args={
    "options": "-c role=telegram_agent"
})
```

---

### ⚠️ MEDIO #13: Webhook principal de Telegram permite operar sin token secreto
**Control:** ASI-07  
**Archivo:** `backend/app/api/routes/telegram.py:248-251`

```python
if not telegram_webhook_secret:
    logger.warning("TELEGRAM_WEBHOOK_SECRET is not set. Webhook is unauthenticated!")
    # ❌ Continúa procesando la request sin autenticación
```

**Instrucciones de remediación:** Si no hay secret configurado, rechazar la request con 500 (fail-closed):
```python
if not telegram_webhook_secret:
    logger.error("TELEGRAM_WEBHOOK_SECRET not configured — rejecting webhook")
    raise HTTPException(status_code=500, detail="Webhook secret not configured")
```

---

### ⚠️ MEDIO #14: Uso de MD5 para detección de cambios en calendarios
**Control:** ASI-09  
**Archivo:** `backend/app/application/calendars/service.py:283-547`

MD5 está criptográficamente roto. Para detección de cambios de integridad, usar SHA-256.

**Instrucciones de remediación:**
```python
# Reemplazar MD5 con SHA-256
import hashlib
# Antes: md5_hash = hashlib.md5(data).hexdigest()
# Después:
sha256_hash = hashlib.sha256(data).hexdigest()
```

---

## ✅ Controles Aprobados

### ASI-02: Insecure Tool Use — PASS (8/10)
**Fortalezas:**
- SQL parametrizado con `:param` bindings (SQLAlchemy text) — sin concatenación
- Validación SQL multi-capa: `security.py` + `validator.py` + `verifier.py`
- Bloqueo de keywords peligrosas: INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE, EXEC, GRANT, REVOKE
- Bloqueo de funciones peligrosas: `pg_sleep`, `lo_import`, `pg_read_file`
- `statement_timeout` de 10 segundos y truncado a 100 filas
- Sin `eval()`, `exec()`, `subprocess.run(shell=True)`, `os.system()` en código de aplicación
- Tablas sensibles excluidas del SQL agent

**Mejora sugerida:** Validar parámetros de herramientas contra JSON Schema antes de ejecutar.

---

### ASI-04: Unauthorized Escalation — PASS (9/10)
**Fortalezas:**
- Sin mecanismos de auto-escalación de privilegios
- Roles verificados determinísticamente en `dependencies.py`
- `token_version` invalida sesiones anteriores al cambiar contraseña
- Tokens de vinculación Telegram de un solo uso con expiración 24h
- El bot no expone herramientas para modificar usuarios/roles/permisos

---

### ASI-08: Policy Bypass — PASS (8/10)
**Fortalezas:**
- Sistema de permisos determinístico basado en código (no LLM)
- Arquitectura fail-closed: permiso faltante → 403
- Sin LLM en el camino de enforcement de políticas
- `require_permission()` como factory de dependencias FastAPI
- 14 permisos granulares definidos como `StrEnum`
- 50+ endpoints protegidos con verificación explícita de permisos

---

## 📋 Plan de Remediación Priorizado

### 🔴 Fase 1: Emergencia (24-48 horas)

| # | Acción | Controles | Esfuerzo |
|---|--------|-----------|----------|
| 1 | **Rotar todas las API keys expuestas** y eliminar secrets del código | ASI-05, ASI-07 | 2h |
| 2 | **Agregar autenticación al webhook** `/webhooks/telegram-notification` | ASI-05 | 1h |
| 3 | **Fijar versiones exactas** en `frontend/package.json` (eliminar `"latest"`) | ASI-09 | 1h |
| 4 | **Agregar `.env` al `.gitignore`** y limpiar historial de Git | ASI-05, ASI-07 | 2h |

### 🟠 Fase 2: Alta Prioridad (1-2 semanas)

| # | Acción | Controles | Esfuerzo |
|---|--------|-----------|----------|
| 5 | **Implementar `InputSanitizer`** para protección contra prompt injection | ASI-01 | 4h |
| 6 | **Agregar capability boundaries** al agente (permisos por herramienta) | ASI-03 | 6h |
| 7 | **Generar `requirements.txt` con hashes** y eliminar `>=` sin cota superior | ASI-09 | 2h |
| 8 | **Implementar circuit breakers** para APIs externas (DeepSeek, Telegram, Meta) | ASI-10 | 6h |
| 9 | **Agregar trigger append-only** a tabla `audit_events` | ASI-06 | 2h |
| 10 | **Implementar kill switch** via feature flag para el bot de Telegram | ASI-10 | 2h |

### 🟡 Fase 3: Media Prioridad (2-4 semanas)

| # | Acción | Controles | Esfuerzo |
|---|--------|-----------|----------|
| 11 | **Migrar rate limiter a Redis** para distribución entre workers | ASI-10 | 4h |
| 12 | **Implementar structured logging** (structlog/loguru → JSON → SIEM) | ASI-06 | 6h |
| 13 | **Crear rol PostgreSQL readonly** para el SQL agent | ASI-08 | 3h |
| 14 | **Agregar secret rotation automática** para API keys | ASI-07 | 8h |
| 15 | **Implementar hash chain** en auditoría (Merkle tree) | ASI-06 | 6h |
| 16 | **Configurar Dependabot + Safety** para escaneo automático de dependencias | ASI-09 | 3h |
| 17 | **Generar SBOM** con `cyclonedx-python` o `syft` | ASI-09 | 2h |
| 18 | **Agregar anomaly detection** básica en patrones de uso del bot | ASI-10 | 8h |

### 🔵 Fase 4: Mejora Continua (1-3 meses)

| # | Acción | Controles | Esfuerzo |
|---|--------|-----------|----------|
| 19 | **Implementar cryptographic identity** (DIDs/Ed25519) para agentes | ASI-07 | 16h |
| 20 | **Migrar JWT a RS256/ES256** (clave asimétrica) | ASI-07 | 8h |
| 21 | **Implementar trust scores con temporal decay** para sesiones de agente | ASI-10 | 12h |
| 22 | **Agregar firma HMAC** a webhooks de notificaciones WhatsApp | ASI-05 | 4h |
| 23 | **Container image scanning** en CI/CD (Trivy) | ASI-09 | 4h |
| 24 | **Centralized monitoring dashboard** para health de jobs programados | ASI-10 | 8h |

---

## 🔍 Archivos Clave Analizados

| Archivo | Controles Relacionados |
|---------|----------------------|
| `backend/app/application/telegram/agent.py` | ASI-01, ASI-03, ASI-06 |
| `backend/app/application/telegram/orchestrator.py` | ASI-01, ASI-03, ASI-05, ASI-06 |
| `backend/app/application/telegram/intent_classifier.py` | ASI-01 |
| `backend/app/application/telegram/llm.py` | ASI-01 |
| `backend/app/application/telegram/sanitize.py` | ASI-01 |
| `backend/app/application/telegram/tool_registry.py` | ASI-02, ASI-03 |
| `backend/app/application/telegram/sql_agent/security.py` | ASI-02, ASI-08 |
| `backend/app/application/telegram/sql_agent/validator.py` | ASI-02, ASI-08 |
| `backend/app/api/dependencies.py` | ASI-04, ASI-08 |
| `backend/app/core/security.py` | ASI-04, ASI-07 |
| `backend/app/core/config.py` | ASI-07 |
| `backend/app/api/routes/telegram.py` | ASI-05, ASI-07 |
| `backend/app/api/routes/telegram_notification_webhook.py` | ASI-05 |
| `backend/app/api/routes/webhooks.py` | ASI-05 |
| `backend/app/infrastructure/db/models/audit.py` | ASI-06 |
| `backend/app/application/audit/service.py` | ASI-06 |
| `backend/app/infrastructure/db/models/telegram.py` | ASI-06, ASI-07 |
| `backend/app/infrastructure/rate_limiter.py` | ASI-10 |
| `backend/app/application/notifications/service.py` | ASI-10 |
| `backend/app/application/scheduler/jobs.py` | ASI-10 |
| `requirements.txt` | ASI-09 |
| `frontend/package.json` | ASI-09 |
| `Dockerfile` | ASI-09 |
| `.env` | ASI-05, ASI-07 |
| `.claude/settings.local.json` | ASI-05, ASI-07 |

---

## 📚 Referencias

- [OWASP Agentic Security Initiative (ASI) Top 10](https://owasp.org/www-project-agentic-ai-threats/)
- [OWASP Top 10 for LLM Applications](https://owasp.org/www-project-top-10-for-large-language-model-applications/)
- [OWASP ASVS (Application Security Verification Standard)](https://owasp.org/www-project-application-security-verification-standard/)
- [Agent Governance Toolkit (Microsoft)](https://github.com/microsoft/agent-governance-toolkit)
- [OWASP Supply Chain Security](https://owasp.org/www-project-top-10-ci-cd-security-risks/)
- [NIST AI Risk Management Framework](https://www.nist.gov/itl/ai-risk-management-framework)

---

*Reporte generado el 2026-06-11. Análisis de solo lectura — sin modificaciones al código.*  
*Metodología: OWASP ASI Top 10 v1.0 aplicada a sistema híbrido (web app + AI agent)*
