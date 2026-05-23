# Plan de Staging para pruebas

## Objetivo

Crear una rama y ambientes de staging para probar cambios antes de pasarlos a produccion, manteniendo costos bajos en los planes Hobby de Vercel y Railway.

## Recomendacion final

- Usar `master` para produccion.
- Crear `staging` para pruebas.
- Usar el mismo proyecto de Vercel con deploys Preview desde `staging`.
- Usar el mismo proyecto de Railway con un environment `staging`.
- Usar una base de datos Postgres separada para staging.
- Redirigir todos los correos de staging a `hendrickrafaelbackup@gmail.com`.
- Desactivar Telegram, WhatsApp y notificaciones externas en staging al inicio.

## Fase 1: Rama y flujo Git

Objetivo: separar pruebas de produccion sin tocar infraestructura todavia.

Tareas:

- Crear rama `staging` desde `master`.
- Subir `staging` a GitHub.
- Definir flujo de trabajo:
  - ramas `feat/...` hacia `staging`.
  - pruebas en staging.
  - merge de `staging` hacia `master` cuando este validado.

Resultado esperado:

- Existe `origin/staging`.
- Produccion sigue funcionando desde `master`.

Pruebas:

- Confirmar que `git branch -r` muestra `origin/staging`.
- Confirmar que `master` no cambia durante esta fase.

## Fase 2: Preparar codigo para ambientes

Objetivo: que el backend soporte claramente `local`, `staging` y `production`.

Tareas:

- Soportar `APP_ENV=staging`.
- Ajustar CORS para que staging use `FRONTEND_ORIGIN`.
- Mantener produccion restringida al dominio real de Vercel.
- Implementar modo seguro de correos:

```env
EMAIL_MODE=redirect
EMAIL_REDIRECT_TO=hendrickrafaelbackup@gmail.com
EMAIL_SUBJECT_PREFIX=[STAGING]
```

Resultado esperado:

- Staging puede apuntar a su frontend sin abrir CORS global.
- Produccion no cambia comportamiento.
- Los correos de staging no llegan a usuarios reales.

Pruebas:

- Test de CORS para `APP_ENV=staging`.
- Test de CORS para `APP_ENV=production`.
- Test de redireccion de correos en staging.
- Test de que produccion no redirige correos si no se configura `EMAIL_MODE=redirect`.

## Fase 3: Vercel staging

Objetivo: tener frontend staging con bajo costo usando Preview Deployments.

Tareas:

- Usar el mismo proyecto Vercel.
- Configurar variables Preview para la rama `staging`.
- Configurar:

```env
VITE_API_URL=https://RAILWAY_STAGING_URL/api
```

- Obtener URL de Vercel staging.
- Usar esa URL como `FRONTEND_ORIGIN` en Railway staging.

Resultado esperado:

- Frontend staging desplegado desde rama `staging`.
- Produccion Vercel sigue desplegando desde `master`.

Pruebas:

- Confirmar que un push a `staging` crea deploy Preview.
- Confirmar que el frontend staging apunta al backend staging.
- Confirmar que produccion sigue apuntando al backend production.

## Fase 4: Railway staging

Objetivo: tener backend y base de datos separados para pruebas.

Tareas:

- Crear environment `staging` dentro del proyecto Railway actual.
- Crear Postgres separado para staging.
- Configurar variables de Railway staging:

```env
APP_ENV=staging
DATABASE_URL=postgres-staging
FRONTEND_ORIGIN=https://VERCEL_STAGING_URL
SECRET_KEY=secret-diferente-a-produccion
EMAIL_MODE=redirect
EMAIL_REDIRECT_TO=hendrickrafaelbackup@gmail.com
EMAIL_SUBJECT_PREFIX=[STAGING]
FEATURE_TELEGRAM=false
FEATURE_NOTIFICATIONS=false
```

- Configurar backend staging para desplegar desde rama `staging`.
- Confirmar que las migraciones corren sobre la DB staging.

Resultado esperado:

- Railway staging funciona con base de datos propia.
- Railway production sigue intacto.

Pruebas:

- Confirmar `/api/health` en backend staging.
- Confirmar logs de Alembic en staging.
- Confirmar que las tablas se crean en DB staging.
- Confirmar que DB production no recibe cambios de staging.

## Fase 5: Datos de prueba

Objetivo: hacer staging utilizable sin copiar datos sensibles de produccion.

Tareas:

- Crear admin staging.
- Crear usuarios de prueba.
- Crear catalogos minimos.
- Crear medicos de prueba si hace falta validar calendario.

Resultado esperado:

- Ambiente staging listo para pruebas funcionales.

Pruebas:

- Login con admin staging.
- Crear usuario encargado.
- Convertir encargado a admin y confirmar que sigue en listado.
- Resetear password.
- Confirmar que el correo llega a `hendrickrafaelbackup@gmail.com`.

## Fase 6: Validacion end-to-end

Objetivo: confirmar que staging funciona como paso previo a produccion.

Pruebas:

- Push a `staging`.
- Vercel staging despliega.
- Railway staging despliega.
- Login funciona.
- Crear usuario funciona.
- Correo de invitacion se redirige.
- Reset de password se redirige.
- Produccion sigue disponible.
- Produccion mantiene su base de datos separada.

Resultado esperado:

- Staging validado y listo para uso regular.

## Fase 7: Flujo operativo

Flujo recomendado:

```text
feature branch
  -> merge a staging
  -> pruebas en staging
  -> merge staging a master
  -> produccion
```

Reglas:

- No probar features nuevas directo en `master`.
- No usar DB de produccion en staging.
- No enviar correos reales desde staging.
- Revisar costos Railway semanalmente durante las primeras semanas.
- Mantener staging con servicios minimos.

## Estrategia de costos para Hobby

Vercel:

- No crear otro proyecto.
- Usar Preview Deployments desde la rama `staging`.
- Evitar deploys innecesarios.

Railway:

- No crear otro proyecto.
- Usar environment `staging`.
- Crear solo una DB staging separada.
- Mantener Telegram, Twilio y notificaciones externas apagadas en staging.
- Usar sleep o escala minima donde aplique.
- Revisar consumo despues de los primeros deploys.

## Decision sobre correos

Modo recomendado para staging:

```env
EMAIL_MODE=redirect
EMAIL_REDIRECT_TO=hendrickrafaelbackup@gmail.com
EMAIL_SUBJECT_PREFIX=[STAGING]
```

Comportamiento esperado:

- Todo correo generado en staging se envia a `hendrickrafaelbackup@gmail.com`.
- El asunto se marca con `[STAGING]`.
- El cuerpo incluye el destinatario original.
- Ningun usuario real recibe correos desde staging.

## Criterios de exito

- Existe rama `staging`.
- Vercel despliega staging desde `staging`.
- Railway despliega staging desde `staging`.
- Staging tiene DB separada.
- Login funciona en staging.
- Creacion de usuarios funciona en staging.
- Correos staging llegan solo a `hendrickrafaelbackup@gmail.com`.
- Produccion queda intacta.

## Estado de implementacion

Fecha: 2026-05-22

Implementado:

- Rama `staging` creada y subida a GitHub.
- Railway environment `staging` creado en el proyecto `generous-rebirth`.
- Servicio backend staging creado: `general-medical-services-staging`.
- Base de datos Postgres staging separada creada: `Postgres-V7Ht`.
- Dominio Railway staging:

```text
https://general-medical-services-staging-staging.up.railway.app
```

- Vercel Preview para rama `staging` desplegado:

```text
https://general-medical-services-oy79i2g68-hrafael2011s-projects.vercel.app
```

- `VITE_API_URL` de Vercel Preview `staging` apunta al backend staging.
- `FRONTEND_ORIGIN` de Railway staging apunta al preview real de Vercel.
- Correos staging configurados en modo redirect a:

```text
hendrickrafaelbackup@gmail.com
```

Validado:

- Backend staging `/api/health` responde `200`.
- CORS staging permite el preview real de Vercel.
- CORS staging rechaza `localhost`.
- Login staging responde correctamente.
- Creacion de usuario staging funciona.
- Invitacion staging responde `200` y usa el modo de correo redirect.
- Produccion no fue modificada por los deploys de staging.

Nota operativa:

- El preview de Vercel puede estar protegido por Vercel Authentication. Para pruebas desde navegador, iniciar sesion en Vercel si aparece la pantalla de autenticacion.
