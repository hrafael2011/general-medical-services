# Plan de hardening de seguridad para produccion

Fecha: 2026-05-22

## Contexto

Este plan nace del analisis OWASP y de las verificaciones realizadas contra produccion en Railway/Vercel.

El cambio de permisos por rol queda fuera de este plan inmediato porque se implementara mas adelante como una fase funcional separada.

## Objetivo

Reducir superficie publica, proteger flujos sensibles y endurecer configuracion de produccion sin romper el flujo actual del sistema.

## Fuera de alcance por ahora

- Redisenar permisos finos por rol.
- Migrar JWT de `localStorage` a cookies `HttpOnly`.
- Rehacer el motor LLM/SQL de Telegram.
- Cambiar dominio o proveedor de correo.

## Fase 1: Hardening publico inmediato

### Cambios

- Cerrar `/docs`, `/redoc` y `/openapi.json` cuando `APP_ENV=production`.
- Endurecer CORS en produccion para permitir solo:
  - `https://general-medical-services.vercel.app`
- Mantener localhost/IPs privadas solo en entorno local o desarrollo.

### Tests

- Verificar que `/docs` y `/openapi.json` existen en local.
- Verificar que `/docs` y `/openapi.json` no existen en production.
- Verificar CORS permitido para Vercel.
- Verificar CORS rechazado para origen externo.
- Verificar CORS local solo fuera de production.

### Criterio de salida

- Backend sigue respondiendo `/api/health`.
- Frontend productivo puede consumir API.
- Origenes no autorizados no reciben CORS.

## Fase 2: Reducir superficie innecesaria

### Cambios

- Apagar `FEATURE_TELEGRAM` en Railway si Telegram no se usara ahora.
- Si Telegram queda activo, agregar validacion de `X-Telegram-Bot-Api-Secret-Token`.

### Tests

- Si Telegram esta apagado: rutas Telegram no aparecen publicadas.
- Si Telegram esta activo:
  - Webhook rechaza requests sin secreto.
  - Webhook rechaza secreto incorrecto.
  - Webhook acepta secreto correcto.

### Criterio de salida

- No queda webhook funcional sin proteccion.

## Fase 3: Secretos y variables

### Cambios

- Quitar variables SMTP viejas si Gmail API ya funciona:
  - `SMTP_HOST`
  - `SMTP_PORT`
  - `SMTP_USERNAME`
  - `SMTP_PASSWORD`
  - `SMTP_FROM_EMAIL`
- Mantener Gmail API funcional:
  - `GMAIL_CLIENT_ID`
  - `GMAIL_CLIENT_SECRET`
  - `GMAIL_REFRESH_TOKEN`
  - `GMAIL_FROM_EMAIL`
- Rotar secretos que hayan estado en archivos locales/tooling si aplica.

### Tests

- Verificar variables presentes sin imprimir valores.
- Ejecutar probe de envio por Gmail API.
- Probar boton de reset de usuario.

### Criterio de salida

- Correo sigue funcionando.
- Railway mantiene solo secretos necesarios para el flujo actual.

## Fase 4: Seguridad de recuperacion de contrasena

### Cambios

- Corregir historial de contrasenas para comparar con `verify_password` contra hashes historicos.
- Agregar rate limit a `/auth/set-password`.
- Reducir datos expuestos en `GET /auth/set-password`.
  - Opcion conservadora: email enmascarado.
  - Opcion mas estricta: devolver solo `valid`.

### Tests

- Bloquea reutilizacion de contrasenas recientes.
- Permite contrasena nueva valida.
- Rate limit bloquea intentos repetidos.
- Token invalido no revela datos.
- Token valido sigue permitiendo crear/restablecer contrasena.

### Criterio de salida

- Recuperacion de contrasena sigue funcionando.
- Tokens tienen menor superficie de abuso.

## Fase 5: Headers de seguridad

### Cambios

- Agregar headers basicos:
  - `Content-Security-Policy`
  - `X-Content-Type-Options: nosniff`
  - `Referrer-Policy`
  - `Permissions-Policy`
- Mantener JWT en `localStorage` por ahora para no romper frontend.

### Tests

- Verificar headers en respuestas principales.
- Verificar que frontend carga correctamente en Vercel.
- Verificar que llamadas API siguen funcionando.

### Criterio de salida

- Menor riesgo XSS/filtracion sin cambiar flujo de autenticacion.

## Fase 6: Health y runtime

### Cambios

- Cambiar `/health/ready` para no devolver detalles internos de base de datos.
- Evaluar Docker non-root en una fase controlada.

### Tests

- `/api/health` responde OK.
- `/api/health/ready` responde OK cuando DB esta disponible.
- En fallo simulado, `/api/health/ready` devuelve error generico.
- Si se cambia Docker a non-root, validar build y arranque en Railway.

### Criterio de salida

- Health checks siguen sirviendo para operacion sin filtrar detalles internos.

## Validacion final

- Ejecutar tests backend relevantes.
- Ejecutar smoke test local.
- Ejecutar smoke test produccion:
  - `/api/health`
  - login
  - reset email
  - CORS Vercel permitido
  - CORS externo rechazado
  - docs cerrados en production
- Confirmar variables Railway sin imprimir secretos.

## Orden recomendado

1. Fase 1
2. Fase 2
3. Fase 3
4. Fase 4
5. Fase 5
6. Fase 6

## Nota operativa

Cada fase debe implementarse en un commit independiente, con pausa de verificacion antes de continuar a la siguiente fase.
