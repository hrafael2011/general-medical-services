---
spec: 00
version: 1.0.0
status: accepted
created: 2026-04-30
updated: 2026-04-30
---

# Spec 00 - Proceso Manual Actual

## Goal

Document the current manual workflow used by the service coordinator, using the `2026/` folder as the operational reference for future automation.

This spec exists to preserve domain knowledge before replacing manual steps with software.

## Source Folder

The `2026/` folder contains the current working evidence for medical service planning:

- Master and support lists of doctors, interns, residents, contractors, and military medical staff.
- Monthly calendar workbook used as a planning view.
- Weekly service PDFs and Excel workbooks used as official or near-official service outputs.
- Historical weekly sheets that show how assignments have been made over time.

These files are not treated as perfect structured data. They are treated as a reference for:

- how the coordinator thinks about service planning,
- which data points matter,
- which rules are explicit,
- which rules are implicit,
- and which outputs must be reproduced by the system.

## Observed File Categories

### Doctor and Staff Lists

Examples:

- `2026/INFORMACION MG DIAS Y LUGARES DE SERIVICIOS (version 4).xlsb.xlsx`
- `2026/MEDICOS GENERALES MILITARES.pdf`
- `2026/PASANTES MORILLO.pdf`
- `2026/INTERNOS MORILLO.pdf`

These files contain staff identity and eligibility information such as:

- rank,
- full name,
- staff category,
- work area,
- fixed or preferred work days,
- service limits,
- licenses,
- pregnancy or temporary restrictions,
- no-service markers,
- and special notes.

Examples of free-text markers found in the source material:

- `1 SERV AL MES`
- `1 SER AL MES`
- `3 AL MES`
- `4 SERVICIOS AL MES`
- `LICENCIA MEDICA`
- `EMBARAZADA`
- `NO REALIZA SERVICIO`
- `N/A`
- `VIERNES FIJOS`

### Monthly Calendar

Example:

- `2026/CALENDARIO SERV 2026.xlsx`

This workbook appears to be used as a monthly planning surface. Earlier months contain assignments, while later months may act as templates or incomplete future planning periods.

The monthly calendar helps identify:

- month-level assignment distribution,
- recurring staff usage,
- planning rhythm,
- potential manual balancing decisions,
- and incomplete future calendar states.

### Weekly Service Outputs

Examples:

- `2026/SERVICIOS/1RA SEM MAYO 2026.pdf`
- `2026/SERVICIOS/4TA SEM MARZO 2026.xlsx`
- `2026/SERVICIOS/3RA SEM ENERO 2026.xlsx`

These files represent the weekly service format the system should eventually reproduce.

The recurring daily coverage pattern is:

- `EMERGENCIA`
- `PISTA`
- `DISPONIBLE`

Each service day normally has one assignment per required area. Weekly outputs are therefore a strong validation source for the future calendar generator.

## Manual Workflow Interpretation

The current manual workflow is interpreted as:

1. The coordinator maintains or consults staff lists with ranks, areas, days, and restrictions.
2. The coordinator checks availability and special conditions such as licenses or service limits.
3. The coordinator distributes staff across required daily service areas.
4. The coordinator balances operational needs with fairness and practical knowledge.
5. The coordinator prepares weekly service outputs in the institutional format.
6. Manual changes are made when real-world exceptions appear.

## Explicit Rules Observed

The source material suggests the following explicit rules:

- Staff with license markers should not be assigned during the affected period.
- Staff marked as not performing service should not be assigned.
- Staff with monthly limits should not exceed those limits.
- Fixed-day availability must be respected.
- Each day requires coverage for the service areas used in weekly outputs.
- Staff category may affect eligibility for some areas or contexts.

## Implicit Rules To Confirm

The source material suggests additional rules that require confirmation with the coordinator:

- Whether manual duplicates in a week are intentional or accidental.

Confirmed follow-up rules captured in later specs:

- MVP required areas are `EMERGENCIA`, `PISTA`, and `DISPONIBLE`, with one doctor per area per day.
- `EMERGENCIA`, `PISTA`, and `DISPONIBLE` have different initial load weights.
- Weekends and holidays count the same as weekdays for fairness.
- Military rank is informational for MVP scheduling priority.
- Repeat spacing rules after `EMERGENCIA`, `PISTA`, and missions are defined in `02-calendario-fairness.md`.
- Mission eligibility and workload impact are tracked separately from regular services.
- Area eligibility is configurable per doctor.
- Staff category is informational for MVP scheduling; actual service eligibility is configured per doctor.
- Interns and residents are outside MVP service scheduling unless enabled in the future.

## Automation Principle

The system must not blindly replace the coordinator's judgment.

Automation should:

- extract and normalize the current information,
- expose ambiguous records for review,
- generate valid draft schedules,
- explain conflicts and tradeoffs,
- allow justified manual override,
- and reproduce institutional weekly outputs.

The coordinator remains the approving authority for official calendars.

## Acceptance Criteria

1. Given the `2026/` folder, when documenting the current workflow, then the system identifies doctor lists, monthly planning files, and weekly service outputs as separate source categories.
2. Given a weekly service output, when analyzing required coverage, then `EMERGENCIA`, `PISTA`, and `DISPONIBLE` are treated as required daily areas for MVP.
3. Given free-text restrictions in legacy files, when importing, then they are not applied silently without trace and confidence metadata.
4. Given a generated calendar, when comparing with the manual process, then the system preserves coordinator review and approval before official publication.


## Changelog

| Version | Fecha | Issue | Trigger | Resumen |
|---------|-------|-------|---------|---------|
| 1.0.0 | 2026-04-30 | — | Inicial | Versión inicial. Documenta el proceso manual del coordinador como referencia pre-automatización. |