---
spec: 02
version: 1.1.0
status: accepted
created: 2026-04-30
updated: 2026-05-05
---

# Spec 02 - Calendar and Fairness

## Goal

Generate and manage a valid calendar with full daily coverage across required areas, while enforcing fairness and operational constraints.

## Required Coverage

- Emergencia
- Pista aerea
- Medico disponible en hospital

Each day must have exactly one assignment per required area.

MVP required service areas are `emergencia`, `pista`, and `disponible`. The model must allow additional required service areas in the future.

Initial service timing assumptions:

- `emergencia`: 24-hour service.
- `pista`: starts around 6:00 AM; end time varies by operational need.
- `disponible`: starts around 7:00 AM; end time varies by operational need.

Weekends and holidays count the same as weekdays for fairness unless future rules change this.

## Calendar States

- `draft`: calendar enabled and editable; weeks are not all approved.
- `partial`: at least one week is approved and at least one week remains editable.
- `approved`: all weeks are approved.
- `preview`, `pending_approval`, `official`, `manually_modified`, and `closed` remain future workflow states unless a later ADR reintroduces them.

Operational update 2026-05-19:

- Enabling a calendar only creates an empty draft calendar with draft weeks.
- Rule-based generation is an explicit action from the calendar view, not part of enabling.
- Approval and unlocking are weekly operations.
- Approved weeks are locked for manual assignment, replacement, removal, and regeneration.
- Operational weeks are always 7 days, Monday through Sunday, and belong to the month where their Sunday falls.
- Cross-month dates must be labeled with their month in the calendar UI and weekly PDF.
- See `docs/specs/2026-05-19-calendario-habilitacion-manual-aprobacion-semanal.md`.

## Pre-Generation Validations

- Licenses
- Debts/penalties policy
- Monthly limits
- Special restrictions
- Monthly availability reported
- Manual restrictions

## Fairness Rules

Rules run via plug-in contract and can be classified as hard/soft.

Initial load weights:

- `emergencia`: `3`
- `pista`: `2`
- `disponible`: `1`
- `mission`: `0.5`

Named rules include:

- PreventOverload
- AreaRotation
- DiasValidos
- LimiteMensual
- DisponiblePostEmergencia
- EspaciadoServicios
- PreferenciaPorRotacionDeCarga
- MaxConsecutivosPorArea
- TiempoRecuperacionPostTurnoDuro
- RestriccionManual
- EvitarMismoEquipo
- EspaciadoEntreServiciosExigentes
- CoberturaDiaria
- PriorizarDiasDificiles
- PreservarFlexibilidad
- PriorizarDisponibilidadLimitada
- RankingMisiones

Initial spacing rules:

- After `emergencia` or `pista`, the doctor should not be assigned to another `emergencia` or `pista` before at least 14 days have passed.
- After `emergencia` or `pista`, assignment to `disponible` should normally wait at least 7 days.
- If there is a coverage deficit, the system may suggest `disponible` before 7 days only when the doctor is available for that date; the suggestion must carry warning rationale.
- After a mission, assignment to `disponible` should wait at least 5 days.
- After a mission, assignment to `pista` or `emergencia` should wait at least 7 days.
- These spacing rules support fairness suggestions and manual review; allowed overrides require justification and audit unless a hard block applies.

Monthly limits:

- Default normal target: 3 services per doctor per month.
- Default normal maximum: 3 services per doctor per month.
- For generation, "per month" means the operational calendar month defined by Sunday-owned Monday-Sunday weeks, including cross-month days that belong to that calendar.
- The monthly target and maximum must be configurable per doctor by the encargado.
- Doctor-specific monthly values override system defaults.
- Doctor-specific monthly limits, such as "1 service per month", are warn-only by default and may be exceeded by the encargado with justification and audit.
- The generator should try to approach each doctor's configured target without exceeding maximums when feasible.

## Assignment Ordering

The monthly generator assigns required areas in this order:

1. `emergencia`
2. `pista`
3. `disponible`

Within each area, the generator prioritizes doctors with lower load, valid availability, allowed area eligibility, and better spacing.

Load comparison must consider:

- workload already assigned in the month being generated,
- each doctor's monthly service target and maximum,
- recent historical workload from the previous 60 days,
- service weights by area,
- mission load with lower weight.

Tie-breakers:

1. More days since last strong service.
2. Fewer recent `emergencia`/`pista` assignments.
3. Less recent use in the same area.
4. Controlled rotation if still tied.

The generator should favor area rotation when possible.

The generator should preserve flexibility:

- Doctors with limited allowed areas or limited availability should be considered before highly flexible doctors when their valid dates appear.
- Doctors with fixed patterns, such as last Friday of the month, should be considered before monthly-availability doctors on matching dates.
- Days and area slots with the fewest valid candidates should be solved before easier slots.

The generator should try multiple combinations before producing unresolved gaps.

If full coverage cannot be achieved with ideal rules:

1. Keep hard blocks such as inactive service status, active license/block reason, no service, pregnancy, missing required availability, and area ineligibility.
2. Suggest candidates that break soft rules with explicit warnings and rationale.
3. Leave an unresolved gap only when no acceptable candidate exists.

## Assignment Rationale

The backend must store structured rationale for generated and manually changed assignments.

Rationale may include:

- candidate score,
- load comparison,
- availability match,
- area eligibility,
- spacing result,
- rotation result,
- warnings,
- hard blockers considered,
- override justification when applicable.

The panel should expose this through an action such as "Ver razon" rather than showing long explanations by default.

LLM-generated natural language explanations should be produced only on demand from the stored structured rationale.

## Mission Ranking

Each monthly calendar generation must also create a mission candidate ranking for the month.

Rules:

- Ranking includes all doctors eligible for missions, ordered by lower total load first.
- Position `1` means the lowest-load candidate.
- Doctors with `participa_misiones = false` are excluded from mission candidates.
- Doctors who already performed a mission in the same month are not automatically excluded, but their priority is reduced.
- The ranking is stored for audit and later Telegram recommendations.
- Mission candidate selection for a specific request must filter by date, active blocks, service conflicts, availability, and spacing rules.
- If the encargado requests alternate candidates, the system may show candidates with warnings, including occupied or lower-priority candidates, while preserving hard-block exclusions.

## Rule Governance

Per rule define:

- `allow_disable`
- `allowed_roles_to_toggle`
- `requires_justification`

Recommended non-disableable baseline:

- Inactive doctor block
- Active license block
- Legal/administrative restrictions
- Minimum daily coverage

## Manual Assignment Flexibility

- Encargado can manually replace doctor from calendar UI.
- Modes:
  - Strict validation
  - Warn-only
  - Skip selected allowed rules with justification
- Every manual change is auditable.

## Generation Strategy

- Initial: greedy + hard checks + soft scoring
- Advanced: OR-Tools CP-SAT for better global optimization
- If no feasible result, expose gaps/conflicts explicitly
- Automatic generation creates `draft` or `preview` calendars only.
- The encargado approves weeks individually; approving the final week marks the calendar as `approved`.
- Rule-based generation must fail when any week is already approved, unless a future partial-regeneration workflow is explicitly designed.
- Modifying an approved week requires unlocking that week first, with audit.

## Service Area Identity in Generation

The generation engine must resolve service area identities as database UUIDs, not as code strings.

Rules:

- `REQUIRED_AREAS` passed to the engine must be a list of `ServiceArea.id` (UUID) values, loaded from the database at generation time.
- `AREA_WEIGHTS` must be keyed by `ServiceArea.id` (UUID), not by `ServiceArea.code`.
- `DoctorServiceArea.service_area_id` stores UUIDs; the engine's area eligibility check must compare UUID to UUID.
- Gaps inserted into `unresolved_gaps.service_area_id` must reference a valid `service_areas.id` UUID; inserting a code string violates the FK constraint and causes a 500 error.

Rationale: the initial implementation hardcoded area codes (`"emergencia"`, `"pista"`, `"disponible"`) directly in `REQUIRED_AREAS` and `AREA_WEIGHTS`. In production the `service_areas` table uses UUID primary keys, causing a foreign key violation on every gap insertion and making all doctors ineligible for every slot (code ≠ UUID in the allowed-area check).

## Acceptance Criteria

1. Given all required inputs, when generating calendar, then every day has three required area slots or explicit unresolved gaps.
2. Given manual replacement, when saving in strict mode, then save is blocked on hard rule violations.
3. Given manual replacement in warn-only mode, then save succeeds with explicit conflict log and audit trail.
4. Given rule toggle, then action is constrained by role and logged with reason.
5. Given a doctor performed `emergencia` or `pista`, when assigning another `emergencia` or `pista`, then assignments before 14 days are blocked or warned according to rule configuration.
6. Given a doctor performed a mission, when assigning a service too soon after it, then the system applies the mission spacing rules and explains the conflict.
7. Given an official calendar is modified, then a new calendar version is created instead of silently mutating the official history.
8. Given a monthly calendar generation, then the generator solves constrained days and limited-availability doctors before easier slots when this reduces conflicts.
9. Given multiple valid candidates for an assignment, then the system uses load, recent history, spacing, area rotation, and controlled tie-breakers to choose a candidate.
10. Given a generated assignment, then structured rationale is stored and can be viewed in the panel.
11. Given a monthly calendar generation, then a mission candidate ranking is stored for the month.


## Changelog

| Version | Fecha | Issue | Trigger | Resumen |
|---------|-------|-------|---------|---------|
| 1.1.0 | 2026-04-30 | — | Bug | BUG-001 (QA): el engine usaba códigos de área como IDs causando FK violation en `unresolved_gaps` y falla silenciosa en la elegibilidad. Se agrega sección "Service Area Identity in Generation" que exige UUIDs. |
| 1.0.0 | 2026-04-30 | — | Inicial | Versión inicial. Define cobertura diaria requerida, estados del calendario, reglas de fairness, pesos por área, espaciado, misiones y criterios de aceptación. |
