# Spec 07 - Importacion Legacy

## Goal

Define how Excel and PDF files from the manual workflow are imported into the system while preserving traceability, confidence, and human review.

The import process must support automation without silently converting ambiguous legacy data into authoritative records.

## Scope

- Import doctor and staff lists.
- Import availability hints, service limits, restrictions, and licenses.
- Import historical and current service assignments.
- Preserve source traceability.
- Detect ambiguous identity matches.
- Route uncertain records to manual review.

## Non-Goals

- No direct production scheduling from unreviewed imports.
- No blind overwrite of canonical doctor records.
- No LLM-only parsing for authoritative data.
- No automatic merge of similar names without review unless deterministic identity rules are met.

## Source Types

### Excel Workbooks

Examples:

- `2026/INFORMACION MG DIAS Y LUGARES DE SERIVICIOS (version 4).xlsb.xlsx`
- `2026/CALENDARIO SERV 2026.xlsx`
- `2026/SERVICIOS/*.xlsx`

Expected extracted data:

- doctors,
- ranks,
- departments or work areas,
- fixed days,
- monthly service limits,
- monthly service targets and maximums,
- restrictions,
- licenses,
- historical assignments,
- current assignments.

### PDF Documents

Examples:

- `2026/MEDICOS GENERALES MILITARES.pdf`
- `2026/PASANTES MORILLO.pdf`
- `2026/INTERNOS MORILLO.pdf`
- `2026/SERVICIOS/*.pdf`

Expected extracted data:

- institutional weekly service outputs,
- staff lists exported from spreadsheet sources,
- evidence for service assignments,
- validation examples for generated reports.

PDF parsing is expected to be less reliable than spreadsheet parsing and should usually create higher review requirements.

## Import Pipeline

### Step 1 - File Registration

Each imported file must be registered before parsing.

Required metadata:

- `source_file_id`
- `path`
- `file_name`
- `file_type`
- `checksum`
- `detected_period`
- `imported_by`
- `imported_at`
- `parser_version`

Rules:

- Same checksum should not be imported twice as a separate source.
- Re-imports must be versioned.
- Temporary Office lock files such as `~$*.xlsx` should be ignored.
- The initial historical import should cover the full available 2026 history starting in January 2026.

### Step 2 - Raw Extraction

Raw extraction reads cells, text blocks, and table-like structures.

Required metadata per extracted item:

- `source_file_id`
- `sheet_name`
- `page_number`
- `row_number`
- `column_name`
- `cell_reference`
- `raw_value`
- `extraction_method`

Extraction method examples:

- `xlsx_cell`
- `pdf_text`
- `pdf_table`
- `manual_entry`

### Step 3 - Field Classification

Raw values are classified into possible domain fields.

Target fields include:

- `rank`
- `doctor_name`
- `department`
- `availability_day`
- `service_limit`
- `monthly_service_target`
- `monthly_service_max`
- `license`
- `restriction`
- `service_date`
- `service_area`
- `assignment`

Each classification must include:

- `parsed_value`
- `confidence`
- `parser_rule`
- `requires_review`

### Step 4 - Normalization

Normalization converts legacy variations into stable values.

Normalization examples:

- uppercase and accent-insensitive name matching,
- punctuation cleanup,
- rank abbreviation mapping,
- weekday mapping,
- area mapping,
- service area mapping,
- common typo mapping.

Examples:

- `PISTA`, `PISTA AEREA` -> `pista`
- `DISPONIBLE`, `MEDICO DISPONIBLE` -> `disponible`
- `EMERG`, `EMERGENCIA` -> `emergencia`
- `LICENCIAS MEDICAS`, `LICENCIA MEDICA` -> license marker
- `1 SER AL MES`, `1 SERV AL MES` -> monthly service limit of 1
- `3 AL MES`, `4 SERVICIOS AL MES` -> monthly service target/maximum candidates requiring review

### Step 5 - Identity Resolution

The importer attempts to match parsed people to existing `Doctor` records.

Matching signals:

- normalized full name,
- known aliases,
- rank,
- staff category,
- department,
- historical assignments,
- source list context.

Match result values:

- `exact_match`
- `probable_match`
- `possible_match`
- `new_candidate`
- `conflict`

Rules:

- `exact_match` may be applied automatically when deterministic criteria are met.
- `probable_match` and `possible_match` require review before canonical merge.
- `conflict` must be blocked from automatic application.
- New candidates should be staged, not immediately promoted to active doctors.

### Step 6 - Staging

Parsed records are stored in staging before being applied to canonical tables.

Recommended staging entities:

- `staged_doctor`
- `staged_alias`
- `staged_availability`
- `staged_restriction`
- `staged_license`
- `staged_assignment`

Required staging fields:

- `source_file_id`
- `source_location`
- `source_value`
- `parsed_value`
- `normalized_value`
- `confidence`
- `match_status`
- `review_status`
- `reviewed_by`
- `reviewed_at`
- `applied_at`

Review status values:

- `pending`
- `approved`
- `rejected`
- `needs_more_info`
- `applied`

### Step 7 - Human Review

The review UI must allow an operator to:

- approve a staged doctor,
- link a staged alias to an existing doctor,
- reject an incorrect parsed value,
- correct parsed fields,
- resolve duplicate candidates,
- mark source rows as intentionally ignored,
- apply approved records to canonical tables.

Every review action must create an audit event.

### Step 8 - Canonical Apply

Only approved staged records may update canonical tables.

Rules:

- Applying staged data must be transactional.
- Canonical updates must preserve source references.
- Existing records must not be overwritten without audit.
- Conflicts must stop the apply operation and report exact blockers.

## Confidence Policy

Suggested thresholds:

- `0.95` and above: eligible for automatic apply only when deterministic matching is satisfied.
- `0.75` to `0.94`: requires review.
- below `0.75`: requires review and should be highlighted as low confidence.

PDF-derived data should default to review unless backed by strong structural evidence.

## Source Priority

Excel workbooks are considered more authoritative than PDF documents when both sources describe the same structured operational data and conflict.

PDF documents remain useful as supporting evidence, validation examples, and report format references.

Conflicts between Excel and PDF must be staged for review with source references instead of silently discarded.

## Legacy Marker Parsing

The importer must recognize common free-text markers.

Examples:

- `LICENCIA`
- `LICENCIA MEDICA`
- `EMBARAZADA`
- `NO REALIZA SERVICIO`
- `N/A`
- `1 SERV AL MES`
- `1 SER AL MES`
- `3 AL MES`
- `4 SERVICIOS AL MES`
- `FIJO`
- `FIJOS`

Parsing requirements:

- Store the original text.
- Store the parsed interpretation.
- Store parser confidence.
- Store the parser rule used.
- Require review when one text contains multiple meanings.

## Assignment Import

Weekly service outputs are used to import historical or current assignments.

Expected assignment fields:

- service date,
- weekday,
- doctor name,
- rank when available,
- service area,
- source file,
- source location.

MVP service area mapping:

- `EMERGENCIA` -> `emergencia`
- `PISTA` -> `pista`
- `DISPONIBLE` -> `disponible`

Rules:

- A day should normally have one assignment per required service area.
- Extra names in a daily block must be flagged for review.
- Missing service area values must create unresolved import warnings.
- Imported assignments should not overwrite official generated calendars unless explicitly approved.

## Import Quality Reports

Each import run must produce a report with:

- total files processed,
- total records extracted,
- total records staged,
- total exact matches,
- total probable matches,
- total conflicts,
- total low-confidence records,
- ignored files,
- parser errors,
- records ready for review.

## Audit Events

Minimum audit events:

- file imported,
- file ignored,
- staged record created,
- staged record approved,
- staged record rejected,
- staged record corrected,
- canonical record created from import,
- canonical record updated from import,
- import conflict detected,
- import apply failed.

## Acceptance Criteria

1. Given a legacy Excel workbook, when imported, then raw values are staged with source file, sheet, row, column, confidence, and review status.
2. Given a temporary Office lock file, when scanning the source folder, then the importer ignores it.
3. Given two similar doctor names, when identity resolution is uncertain, then the importer creates a review item instead of merging automatically.
4. Given a free-text marker such as `1 SERV AL MES`, when parsed, then the system stores the original value and parsed monthly limit with parser confidence.
5. Given a weekly service PDF, when parsed, then assignments are staged and mapped to `emergencia`, `pista`, and `disponible` when confidence is sufficient.
6. Given approved staged records, when applying them, then canonical updates are transactional and auditable.
7. Given conflicting Excel and PDF values for the same assignment or doctor data, when staging import results, then Excel is marked as the preferred source and the conflict remains reviewable.
8. Given the initial legacy import, when historical service files are available from January 2026 onward, then the importer stages the full 2026 history with traceability.
9. Given a legacy monthly service marker, when parsed, then the staged record preserves whether it maps to target, maximum, or both, and requires review when ambiguous.
