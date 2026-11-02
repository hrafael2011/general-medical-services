---
spec: ventana-24h-cuenta-atras
version: 1.0.0
status: approved
created: 2026-11-01
updated: 2026-11-01
---

# Spec — Ventana de 24 horas y cuenta atrás del aviso

**Spec padre:** [2026-11-01-aprobacion-segura-notificaciones.md](2026-11-01-aprobacion-segura-notificaciones.md)
(P2, arreglos B1–B6). Esto es el ajuste fino de esa ventana.

## Goal

Que al aprobar una semana el operador vea, en el momento, cuándo saldrán los avisos a los
médicos —«se envía en 23 h 41 min»— y que ese dato se actualice solo hasta que salgan.

## Contexto — cómo está hoy (2026-11-01)

| Punto | Hoy |
|---|---|
| Ventana | `approval_grace_minutes = 15`. El usuario la quiere en **24 h** (1440 min) |
| Banner de avisos | Existe («N avisos programados — salen a las HH:MM»), pero **no se refresca al aprobar**; hay que recargar la página |
| Cuenta atrás | No existe: muestra una hora fija, no cuánto falta |
| Envío real | La cola se procesa **cada 30 s** (`IntervalTrigger(seconds=30)` en [main.py:145](../../backend/app/main.py)), no cada 5 min. Los avisos salen casi al segundo de cumplirse el plazo |

### Por qué importa

Aprobar es irreversible en la práctica: publica el calendario y dispara avisos. Con 15 minutos el
margen es corto para una revisión real; con 24 horas hay tiempo de corregir al día siguiente. Pero
un plazo largo sin señal visible es peor que uno corto: el operador no sabe si el envío está
pendiente o ya salió.

## Decisiones

| # | Decisión | Razón |
|---|---|---|
| 1 | La ventana pasa a **24 horas** (1440 minutos), configurable por entorno | Se aprueba el viernes para el lunes: 24 h cubre el fin de semana sin llegar al primer servicio |
| 2 | El banner aparece **en el mismo momento** de aprobar, sin recargar | Si no se ve, no existe |
| 3 | Muestra **cuánto falta**, no una hora del reloj | «En 23 h 41 min» se entiende mejor que «salen a las 09:12 de mañana» |
| 4 | Se refresca **cada minuto** en pantalla y **relee la cola cada minuto** | La cuenta atrás se mueve sola y el banner desaparece cuando los avisos salen |
| 5 | No se toca el worker de 30 s | Ya respeta `scheduled_for`; no hace falta |

## Requisitos

- **R1** — `approval_grace_minutes` vale 1440 por defecto.
- **R2** — Aprobar una semana refresca el contador de avisos sin recargar.
- **R3** — El banner dice cuánto falta en horas y minutos (`23 h 41 min`).
- **R4** — La cuenta atrás se actualiza sola cada minuto.
- **R5** — La cola se relee cada minuto; cuando los avisos salen, el banner desaparece.
- **R6** — Pasado el plazo, el texto cambia a «enviando» en vez de contar en negativo.
- **R7** — Si no hay avisos pendientes, el banner no se muestra.

## Mensaje

> **1 aviso programado — se envía en 23 h 41 min**  [Cancelar envío]

## Criterios de aceptación

**AC1** — Dada una semana aprobada, al confirmar aparece el banner sin recargar.
**AC2** — El texto muestra horas y minutos restantes y baja con el paso del tiempo.
**AC3** — Cuando llega a cero, dice «Enviando…» y luego desaparece.
**AC4** — «Cancelar envío» sigue funcionando y el banner desaparece al cancelar.
**AC5** — Aprobar dos semanas seguidas no reinicia la hora del primer aviso ya programado.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Con 24 h, una corrección de última hora no llega antes del servicio | El operador puede desbloquear y volver a aprobar; el aviso se reactiva con hora nueva |
| Un aviso programado a 24 h pierde sentido si el turno cambia | Desbloquear cancela los avisos pendientes (ya implementado en P1) |
| El banner se queda visible tras enviarse | Se relee la cola cada minuto |

## Notas

- En **local** los avisos se crean `skipped` porque los médicos no tienen Telegram vinculado; el
  contador marcará 0 y el banner no saldrá. En producción sí están vinculados.
- `approval_grace_minutes` se puede sobreescribir por entorno; si producción lo tiene fijado en
  15, hay que cambiarlo allí también.

## Tareas

**Estado:** ✅ implementado.

1. `config.py`: `approval_grace_minutes: int = 24 * 60`.
2. Ajustar `test_approval_grace.py` a la ventana nueva.
3. `CalendarGrid.tsx`: invalidar `pending-notifications` al aprobar.
4. `CalendarGrid.tsx`: cuenta atrás con `setInterval` de 60 s y `refetchInterval` de 60 s.
5. Pruebas de frontend para el texto de la cuenta atrás y para el refresco tras aprobar.

## Changelog

| Version | Fecha | Issue | Trigger | Resumen |
|---|---|---|---|---|
| 1.0.0 | 2026-11-01 | — | Petición del usuario | Se fija la ventana en 24 h y se añade cuenta atrás visible, refresco automático al aprobar y relectura de la cola cada minuto. |
