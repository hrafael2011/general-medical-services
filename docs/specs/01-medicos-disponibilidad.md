---
spec: 01
version: 1.3.0
status: accepted
created: 2026-04-30
updated: 2026-04-30
---

# Spec 01 - Doctors and Availability

## Goal

Standardize doctor records and monthly availability as the source for calendar generation.

## Scope

- Doctor master data
- Availability modes
- Restrictions and licenses
- Mission eligibility flag
- Service eligibility and allowed service areas per doctor
- Per-doctor monthly service target and maximum
- Configurable deactivation/block reasons
- Import mapping from legacy Excel data

## Domain Rules

- Inactive doctors cannot be assigned.
- Doctors with active license cannot be assigned within license dates.
- Monthly variable availability does not carry over automatically.
- Weekly fixed availability must be strictly enforced.
- Fixed recurring patterns such as "last Friday of the month" must be strictly enforced.
- A doctor uses either fixed availability or monthly variable availability for MVP; both modes do not coexist for the same planning period.
- Doctors can be configured with allowed service areas such as `emergencia`, `pista`, and/or `disponible`.
- Doctors can be configured with monthly service target and monthly service maximum values by the encargado.
- Per-doctor monthly service values override system defaults for scheduling and fairness.
- Doctors disabled for service must not be selected as candidates.
- Deactivation/block reason options are configurable and must include an `Other` option with required free-text reason.
- Pregnancy is a deactivation/block reason only available for doctors whose `sex` is female.
- Mission queries must respect `participa_misiones`.
- A doctor with no configured `DoctorServiceArea` entries is ineligible for all service areas. Import pipelines must create `DoctorServiceArea` records for each doctor where source data indicates area eligibility; doctors imported without area data must be flagged for review and excluded from generation until at least one area is configured.
- `monthly_service_target` must not exceed `monthly_service_max`. Any operation that would set a target higher than the maximum must return a validation error (HTTP 422) and must not propagate as a database error.
- Operations that accept foreign-key references such as `rank_id` or `department_id` must return HTTP 404 when the referenced entity does not exist. Database integrity errors must not propagate as HTTP 500.

## Required Fields

- Full name
- Sex
- Department
- Military rank
- Active/inactive status
- Service active/inactive status
- Service inactive reason
- `participa_misiones` flag
- Allowed service areas
- Monthly service target
- Monthly service maximum
- Monthly service limit mode
- Weekly fixed days
- Monthly variable availability
- Recurring monthly rules
- Manual restrictions
- Licenses

## Initial Deactivation Reasons

The initial configurable catalog should include:

- `medical_license`
- `pregnancy`
- `no_service`
- `vacation`
- `administrative_restriction`
- `transfer_or_area_change`
- `temporarily_suspended`
- `other`

Rules:

- `medical_license`, `pregnancy`, and `no_service` are hard blocks while active.
- `pregnancy` is shown only for female doctors.
- `other` requires a written reason.
- Every activation/deactivation change is audited.

## Availability Collection

The calendar auto-generation day is configurable. Initial value: day `27` of each month.

Two days before the generation day, the system must notify the encargado by WhatsApp if doctors required to submit monthly availability have not done so.

If a doctor still has missing required monthly availability on generation day, the doctor is excluded from the generated calendar and listed in pending availability reports.

## Monthly Service Configuration

The encargado can configure how many services a doctor should normally perform in a month.

Recommended fields:

- `monthly_service_target`: desired monthly service count.
- `monthly_service_max`: maximum monthly service count before warning.
- `monthly_service_limit_mode`: how strict the maximum is.

Initial default:

- `monthly_service_target`: `3`
- `monthly_service_max`: `3`
- `monthly_service_limit_mode`: `warn_only`

Rules:

- Values must be configurable per doctor.
- If a doctor has no custom values, system defaults apply.
- The generator should try to bring doctors close to their target while respecting eligibility and fairness.
- Exceeding `monthly_service_max` is warn-only by default and requires justification when done manually.
- Legacy markers such as `1 SERV AL MES` should map to these fields with source trace and review status.

## Excel Mapping Policy (Legacy Source)

- Parse free-text markers such as `1 SERV AL MES`, `EMBARAZADA`, `LICENCIA`.
- Normalize area and weekday naming variants.
- Store import trace:
  - `source_value`
  - `parsed_value`
  - `confidence`
  - `review_status`
- Ambiguous rows are marked `requires_review`.

## Acceptance Criteria

1. Given an inactive doctor, when generating or editing assignments, then the doctor is not eligible.
2. Given a doctor with missing monthly availability, when generating next month calendar, then the doctor is excluded and listed in pending availability report.
3. Given a doctor marked for missions, when asking mission availability, then doctor appears in mission-eligible results if no blocking restriction applies.
4. Given an ambiguous imported Excel row, then record is flagged for manual review and not auto-applied.
5. Given a doctor with a fixed pattern such as last Friday of the month, when generating the calendar, then the doctor is only eligible on dates matching that pattern.
6. Given a doctor is deactivated for service, when recommendations or calendar generation run, then the doctor is excluded and the reason is auditable.
7. Given a female doctor, when deactivation reasons are shown, then pregnancy is available as an option.
8. Given a male doctor, when deactivation reasons are shown, then pregnancy is not available as an option.
9. Given a doctor has a configured monthly service target and maximum, when generating a calendar, then the generator uses those values instead of system defaults.
10. Given a doctor exceeds the configured monthly maximum manually, then the system records a warning, justification, and audit event.
11. Given a doctor is imported without allowed service area data, when generating or assigning services, then the doctor is excluded from all service area candidates until areas are configured by the encargado.
12. Given a doctor creation or update request where `monthly_service_target` exceeds `monthly_service_max`, then the API returns HTTP 422 with a descriptive validation error.
13. Given a doctor creation or update request with a nonexistent `rank_id` or `department_id`, then the API returns HTTP 404 rather than propagating a database error.


## Changelog

| Version | Fecha | Issue | Trigger | Resumen |
|---------|-------|-------|---------|---------|
| 1.3.0 | 2026-04-30 | — | Bug | BUG-005b (QA): referencias FK inválidas (rank_id, department_id inexistentes) propagaban HTTP 500. Se agrega regla: operaciones con FK inválida deben retornar HTTP 404. |
| 1.2.0 | 2026-04-30 | — | Bug | BUG-005a (QA): monthly_service_target > monthly_service_max causaba HTTP 500. Se agrega regla de validación: target no puede superar max; debe retornar HTTP 422. |
| 1.1.0 | 2026-04-30 | — | Bug | BUG-002 (QA): 221/223 médicos importados sin DoctorServiceArea, quedando inelegibles para todas las áreas. Se agrega regla: pipeline de importación debe crear registros de área permitida; sin áreas configuradas el médico queda excluido de generación. |
| 1.0.0 | 2026-04-30 | — | Inicial | Versión inicial. Define modelo de médicos, modos de disponibilidad, restricciones, áreas permitidas y configuración mensual de servicios. |