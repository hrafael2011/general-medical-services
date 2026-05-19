# Calendario: Habilitación Manual y Aprobación Semanal

Fecha: 2026-05-19

## Decisión

El botón **Habilitar calendario** solo crea el calendario, su versión inicial y sus semanas en borrador. No genera asignaciones, no aprueba la versión y no aprueba semanas.

La generación automática queda como una acción explícita dentro del calendario: **Generar calendario con reglas**.

## Flujo Operativo

1. El encargado habilita un calendario mensual.
2. El calendario abre vacío, en estado `draft`, con semanas en `draft`.
3. El encargado puede llenar slots manualmente o usar **Generar calendario con reglas**.
4. Las asignaciones generadas o manuales permanecen editables mientras su semana esté en `draft`.
5. La aprobación se realiza por semana.
6. Una semana aprobada queda bloqueada para asignar, reemplazar o quitar médicos.
7. Para editar una semana aprobada, el encargado debe usar **Desbloquear** en esa semana.

## Estados

- `draft`: ninguna semana aprobada o calendario aún editable.
- `partial`: al menos una semana aprobada y al menos una semana en borrador.
- `approved`: todas las semanas están aprobadas.

El estado operativo del calendario se deriva de sus semanas. El frontend debe mostrar `Borrador`, `Parcial` o `Aprobado` desde `calendar.status`.

## Generación Con Reglas

La generación con reglas:

- se ejecuta solo por acción explícita del usuario;
- llena la versión actual con asignaciones `generated`;
- mantiene calendario y versión en revisión/borrador;
- actualiza el modo del calendario a `assisted_auto`;
- refresca grilla, semanas y listado;
- queda bloqueada si existe alguna semana aprobada, para evitar sobrescribir trabajo cerrado.

## Conteos Semanales

El endpoint de semanas debe devolver:

- total de asignaciones por semana;
- conteo por médico dentro de esa semana.

La UI debe refrescar esos conteos después de generar, asignar, reemplazar, quitar, aprobar o desbloquear.

## Tests Esperados

- Crear calendario no auto-genera ni auto-aprueba.
- El frontend habilita calendarios con `generation_mode = manual`.
- Generar con reglas sigue disponible cuando todas las semanas están en borrador.
- Generar con reglas refresca grilla, semanas y listado.
- No se puede asignar, reemplazar ni quitar en semana aprobada.
- El frontend no abre asignación en semanas aprobadas.
- Las semanas devuelven conteos por médico.
- El frontend muestra conteos por médico.
- Generar falla si alguna semana está aprobada.
