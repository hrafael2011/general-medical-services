# Spec 06 - Modelo de Dominio

## Goal

Define the canonical domain model for the medical service scheduling system.

Legacy files may contain inconsistent names, merged concepts, and free-text operational notes. The application must convert that material into explicit domain entities before scheduling, reporting, notification, or AI assistant features rely on it.

## Core Principles

- Legacy source files are not the canonical database.
- Every operational decision must reference structured entities.
- Ambiguous imported data must remain reviewable.
- Calendar assignments must be versioned and auditable.
- Rules must produce machine-readable results and human-readable rationale.
- The Telegram assistant must query services built on this model, not raw tables or documents.

## Primary Entities

### Doctor

Represents a person who may appear in planning, service assignment, history, reports, or mission queries.

Required fields:

- `id`
- `full_name`
- `normalized_name`
- `sex`
- `rank_id`
- `staff_category`
- `department_id`
- `active`
- `service_active`
- `service_inactive_reason_id`
- `service_inactive_reason_detail`
- `participa_misiones`
- `monthly_service_target`
- `monthly_service_max`
- `monthly_service_limit_mode`
- `created_at`
- `updated_at`

Recommended fields:

- `phone_number`
- `whatsapp_opt_in_status`
- `notes`

Examples of `staff_category`:

- `military_doctor`
- `resident`
- `intern`
- `contractor`
- `civilian_intern`
- `other`

Rules:

- Military or institutional rank is informational for scheduling priority in MVP.
- Service eligibility is controlled by `service_active`, deactivation reasons, availability, and allowed service areas.
- Monthly service target and maximum are configurable per doctor and override system defaults.
- Interns and residents are outside MVP service scheduling unless enabled in the future.

### DoctorAlias

Stores known name variants from legacy files.

Required fields:

- `id`
- `doctor_id`
- `alias_text`
- `normalized_alias`
- `source_file`
- `confidence`
- `review_status`

Purpose:

- link misspellings and formatting differences,
- support import matching,
- preserve original source text,
- avoid duplicate doctors.

### Rank

Represents military or institutional rank.

For MVP, rank is informational and does not affect assignment priority.

Required fields:

- `id`
- `name`
- `normalized_name`
- `abbreviation`

### Department

Represents the work area or administrative assignment.

Required fields:

- `id`
- `name`
- `normalized_name`
- `active`

### Availability

Represents when a doctor may be assigned.

Types:

- `weekly_fixed`
- `monthly_variable`
- `recurring_monthly_rule`

Required fields:

- `id`
- `doctor_id`
- `availability_type`
- `effective_from`
- `effective_to`
- `days_of_week`
- `month`
- `year`
- `source`
- `review_status`

Rules:

- Monthly variable availability does not carry over automatically.
- Weekly fixed availability is enforced when active.
- Fixed recurring monthly rules, such as last Friday of the month, are enforced when active.
- A doctor should not use fixed availability and monthly variable availability at the same time for the same planning period in MVP.
- Missing required monthly availability must appear in pending availability reports.

### DoctorServiceArea

Represents which service areas a doctor may cover.

Required fields:

- `id`
- `doctor_id`
- `service_area_id`
- `active`
- `created_at`
- `updated_at`

Rules:

- Calendar generation and recommendations must only consider active allowed areas for a doctor.
- Area eligibility is configured per doctor by the encargado.

### DeactivationReason

Represents configurable reasons for making a doctor inactive for service.

Required fields:

- `id`
- `code`
- `display_name`
- `active`
- `requires_detail`
- `applies_to_sex`
- `severity`

Initial codes:

- `medical_license`
- `pregnancy`
- `no_service`
- `vacation`
- `administrative_restriction`
- `transfer_or_area_change`
- `temporarily_suspended`
- `other`

Rules:

- `pregnancy` applies only to female doctors.
- `other` requires detail text.
- Hard-block reasons prevent assignment while active.

### Restriction

Represents non-license assignment limits or blocks.

Examples:

- pregnancy,
- no service,
- manual administrative restriction,
- area-specific prohibition,
- temporary condition,
- maximum services per month.

Required fields:

- `id`
- `doctor_id`
- `restriction_type`
- `starts_at`
- `ends_at`
- `severity`
- `description`
- `source`
- `review_status`

Severity values:

- `hard_block`
- `warn`
- `informational`

### License

Represents a formal license period.

Required fields:

- `id`
- `doctor_id`
- `starts_at`
- `ends_at`
- `license_type`
- `description`
- `source`
- `review_status`

Rules:

- Active license is a non-disableable scheduling block.
- License periods must be timezone-aware when converted into date ranges.

### ServiceArea

Represents an assignment area that must be covered.

MVP required areas:

- `emergencia`
- `pista`
- `disponible`

Required fields:

- `id`
- `code`
- `display_name`
- `active`
- `required_for_daily_coverage`
- `load_weight`

Initial load weights:

- `emergencia`: `3`
- `pista`: `2`
- `disponible`: `1`

The model must allow future service areas.

### Calendar

Represents a planning period.

Required fields:

- `id`
- `month`
- `year`
- `status`
- `created_by`
- `approved_by`
- `created_at`
- `approved_at`

Allowed status values:

- `draft`
- `preview`
- `pending_approval`
- `official`
- `manually_modified`
- `closed`

### CalendarVersion

Represents a snapshot of a calendar at a meaningful point in time.

Required fields:

- `id`
- `calendar_id`
- `version_number`
- `status`
- `created_by`
- `reason`
- `created_at`

Purpose:

- preserve generated drafts,
- preserve official versions,
- trace manual changes,
- support audit and rollback review.

### CalendarAssignment

Represents one doctor assigned to one service area on one date.

Required fields:

- `id`
- `calendar_version_id`
- `service_date`
- `service_start_at`
- `service_area_id`
- `doctor_id`
- `assignment_source`
- `created_by`
- `created_at`

Examples of `assignment_source`:

- `generated`
- `manual`
- `imported`
- `corrected`

Rules:

- MVP daily coverage requires exactly one assignment per required service area per day, unless the calendar explicitly records an unresolved gap.
- Assignments must reference a calendar version.

### MissionAssignment

Represents a mission or extra-duty assignment that affects workload and future service recommendations but is not one of the daily required service area slots.

Required fields:

- `id`
- `doctor_id`
- `mission_date`
- `mission_start_at`
- `mission_end_at`
- `participant_count`
- `location`
- `description`
- `source`
- `created_by`
- `confirmed_by`
- `confirmed_at`
- `created_at`

Rules:

- Mission assignments only apply to doctors with `participa_misiones = true` unless manually corrected with audit.
- Missions count toward fairness with initial load weight `0.5`.
- Mission spacing rules are defined in `02-calendario-fairness.md`.
- Mission history must be available to Telegram recommendations and explanations.
- Mission requests require date and participant count; location and description are optional.

### MissionParticipant

Represents one doctor assigned to a mission.

Required fields:

- `id`
- `mission_assignment_id`
- `doctor_id`
- `selection_source`
- `ranking_position`
- `score`
- `reasons`
- `warnings`
- `created_at`

Rules:

- Mission participant records must preserve why each doctor was selected.
- Participants affect future workload and mission rankings.

### MissionCandidateRanking

Represents a stored monthly ranking of mission candidates.

Required fields:

- `id`
- `month`
- `year`
- `calendar_version_id`
- `generated_at`
- `created_by`

### MissionCandidateRankingEntry

Represents one doctor in a stored mission ranking.

Required fields:

- `id`
- `mission_candidate_ranking_id`
- `doctor_id`
- `ranking_position`
- `total_load_score`
- `monthly_service_load`
- `recent_service_load`
- `monthly_mission_load`
- `eligible`
- `reasons`
- `warnings`

Rules:

- Ranking position `1` means lowest load among eligible mission candidates.
- Entries are stored for audit and Telegram recommendations.

### AssignmentRationale

Represents structured explanation data for a generated or manual assignment.

Required fields:

- `id`
- `calendar_assignment_id`
- `score`
- `reasons`
- `warnings`
- `hard_blockers_considered`
- `soft_rules_relaxed`
- `data_as_of`
- `created_at`

Rules:

- Rationale is generated by backend scheduling logic, not by the LLM.
- Panel and Telegram explanations must use this structured data.

### UnresolvedGap

Represents missing coverage or infeasible scheduling conditions.

Required fields:

- `id`
- `calendar_version_id`
- `service_date`
- `service_area_id`
- `reason_code`
- `description`
- `created_at`

### FairnessRule

Represents a scheduling rule.

Required fields:

- `id`
- `code`
- `display_name`
- `rule_type`
- `allow_disable`
- `requires_justification`
- `active`

Rule type values:

- `hard`
- `soft`

### FairnessEvaluation

Stores rule evaluation results for generation or manual changes.

Required fields:

- `id`
- `calendar_version_id`
- `rule_id`
- `result`
- `severity`
- `score_delta`
- `affected_doctor_id`
- `affected_assignment_id`
- `explanation`
- `created_at`

Result values:

- `passed`
- `failed`
- `warning`
- `skipped`

### RuleOverride

Represents a justified skip or warn-only decision.

Required fields:

- `id`
- `calendar_version_id`
- `rule_id`
- `actor_id`
- `justification`
- `created_at`

Rules:

- Overrides must be constrained by role.
- Overrides must create audit events.
- Non-disableable hard rules cannot be overridden.

### NotificationEvent

Represents WhatsApp notification attempts and provider results.

Required fields:

- `id`
- `assignment_id`
- `doctor_id`
- `notification_type`
- `scheduled_for`
- `sent_at`
- `status`
- `provider`
- `provider_message_id`
- `idempotency_key`
- `error_code`
- `error_message`

Notification types:

- `initial_assignment`
- `twelve_hour_reminder`

### AuditEvent

Represents immutable traceability for critical actions.

Required fields:

- `id`
- `actor_id`
- `action_type`
- `entity_type`
- `entity_id`
- `occurred_at`
- `request_id`
- `before_snapshot`
- `after_snapshot`
- `metadata`

Rules:

- Audit events are append-only.
- Critical domain actions must produce audit events.
- Audit queries must support actor, date range, entity type, and action type filters.

### User

Represents an authenticated system user.

Required fields:

- `id`
- `name`
- `email`
- `role`
- `active`
- `password_hash`
- `must_change_password`
- `last_login_at`
- `created_by`
- `created_at`
- `updated_at`

MVP roles:

- `admin`
- `encargado`

Future or expanded roles:

- `operator`
- `approver`
- `auditor`
- `viewer`

Rules:

- Users with `must_change_password = true` cannot access operational features.
- Password recovery and user lifecycle rules are defined in `10-seguridad-acceso-usuarios.md`.

### TelegramInteraction

Represents an operational Telegram assistant interaction.

Required fields:

- `id`
- `telegram_user_id`
- `matched_user_id`
- `user_role`
- `intent_id`
- `input_text`
- `extracted_entities`
- `intent_confidence`
- `tool_name`
- `tool_request`
- `tool_response`
- `response_text`
- `cache_status`
- `fallback_reason`
- `status`
- `created_at`

Rules:

- Responses must be grounded in tool output.
- Unsupported or unavailable data must return controlled fallback responses.
- Critical actions require two-step confirmation.
- Linked users must be active and must not have pending mandatory password change.
- Intent permissions must be validated before operational data is returned.

### TelegramUserLink

Represents a Telegram identity linked to an authenticated system user.

Required fields:

- `id`
- `telegram_user_id`
- `user_id`
- `active`
- `linked_by`
- `linked_at`
- `last_used_at`

Rules:

- Unlinked or inactive Telegram users must not receive operational data.
- Linking and unlinking must create audit events.

## Relationships

- A `Doctor` can have many `DoctorAlias` records.
- A `Doctor` can have many `Availability`, `Restriction`, `License`, `DoctorServiceArea`, `CalendarAssignment`, `MissionParticipant`, and ranking entries.
- A `Calendar` can have many `CalendarVersion` records.
- A `CalendarVersion` can have many `CalendarAssignment`, `FairnessEvaluation`, `RuleOverride`, and `UnresolvedGap` records.
- A `CalendarVersion` can have one or more `MissionCandidateRanking` records.
- A `CalendarAssignment` can have many `NotificationEvent` records.
- A `CalendarAssignment` can have one `AssignmentRationale`.
- A `MissionAssignment` can have many `MissionParticipant` records.
- A `User` can have zero or more `TelegramUserLink` records.
- A `TelegramInteraction` references one Telegram user and, when linked, one matched `User`.
- Critical changes across these entities create `AuditEvent` records.

## Non-Disableable Baseline Rules

The following rule categories must not be disabled:

- inactive doctor block,
- active license block,
- legal or administrative hard restriction,
- minimum daily coverage requirement,
- immutable audit creation for critical actions.

## Acceptance Criteria

1. Given a legacy doctor name variant, when importing, then it can be stored as `DoctorAlias` without creating a duplicate doctor automatically.
2. Given a calendar assignment, when saved, then it references a `CalendarVersion` and a structured `ServiceArea`.
3. Given a manual override, when persisted, then the system stores the skipped rule, actor, justification, and audit event.
4. Given an official calendar, when modified manually, then the system creates a new version instead of mutating history silently.
5. Given a Telegram operational query, when answered, then the response is derived from services backed by the canonical domain model.
