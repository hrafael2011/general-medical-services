"""Add unique constraints and missing FK indexes

Changes:
  - Add unique constraint on mission_candidate_rankings (month, year, calendar_version_id)
  - Add unique constraint on doctor_availability (doctor_id, month, year, availability_type)
  - Add missing FK indexes

Revision ID: 20260507_0011
Revises: 20260507_0010
Create Date: 2026-05-07
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa

revision: str = "20260507_0011"
down_revision: str | None = "20260507_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_sqlite() -> bool:
    return op.get_bind().engine.driver == "pysqlite"


def _drop_old_ranking_constraint() -> None:
    """Drop the unnamed unique constraint on mission_candidate_rankings (month, year).

    The old constraint was created without a name in the model, so we need
    to find it dynamically on PostgreSQL or use batch mode on SQLite.
    """
    if _is_sqlite():
        with op.batch_alter_table("mission_candidate_rankings") as bop:
            bop.create_unique_constraint(
                "uq_ranking_period_version",
                ["month", "year", "calendar_version_id"],
            )
        return

    # PostgreSQL: find unnamed unique constraint on (month, year)
    conn = op.get_bind()
    # Check if the named constraint already exists (first run of migration)
    inspector = sa.inspect(conn)
    existing = [c["name"] for c in inspector.get_unique_constraints("mission_candidate_rankings")]
    if "uq_ranking_period_version" in existing:
        return  # Already migrated

    # Drop old unnamed constraint(s) on (month, year)
    result = conn.execute(
        sa.text(
            "SELECT con.conname "
            "FROM pg_constraint con "
            "JOIN pg_class rel ON rel.oid = con.conrelid "
            "WHERE rel.relname = 'mission_candidate_rankings' "
            "AND con.contype = 'u' "
            "AND con.conkey = ( "
            "  SELECT array_agg(a.attnum ORDER BY a.attnum) "
            "  FROM pg_attribute a "
            "  WHERE a.attrelid = rel.oid "
            "  AND a.attname IN ('month', 'year') "
            ")"
        )
    )
    rows = result.fetchall()
    for (cname,) in rows:
        op.execute(f"ALTER TABLE mission_candidate_rankings DROP CONSTRAINT {cname}")

    op.create_unique_constraint(
        "uq_ranking_period_version",
        "mission_candidate_rankings",
        ["month", "year", "calendar_version_id"],
    )


def upgrade() -> None:
    # ------------------------------------------------------------------
    # mission_candidate_rankings: add new UC with version_id
    # ------------------------------------------------------------------
    _drop_old_ranking_constraint()

    # ------------------------------------------------------------------
    # doctor_availability: unique constraint (doctor_id, month, year, type)
    # ------------------------------------------------------------------
    if _is_sqlite():
        with op.batch_alter_table("doctor_availability") as bop:
            bop.create_unique_constraint(
                "uq_doctor_availability_monthly",
                ["doctor_id", "month", "year", "availability_type"],
            )
    else:
        # Clean duplicates before adding constraint
        op.execute(
            "DELETE FROM doctor_availability da "
            "WHERE EXISTS ( "
            "  SELECT 1 FROM doctor_availability da2 "
            "  WHERE da2.doctor_id = da.doctor_id "
            "    AND da2.month = da.month "
            "    AND da2.year = da.year "
            "    AND da2.availability_type = da.availability_type "
            "    AND da2.id < da.id "
            ")"
        )
        op.create_unique_constraint(
            "uq_doctor_availability_monthly",
            "doctor_availability",
            ["doctor_id", "month", "year", "availability_type"],
        )

    # ------------------------------------------------------------------
    # Missing FK indexes
    # ------------------------------------------------------------------
    op.create_index(op.f("ix_doctors_rank_id"), "doctors", ["rank_id"])
    op.create_index(op.f("ix_doctors_department_id"), "doctors", ["department_id"])
    op.create_index(op.f("ix_doctors_service_inactive_reason_id"), "doctors", ["service_inactive_reason_id"])

    op.create_index(op.f("ix_doctor_availability_doctor_id"), "doctor_availability", ["doctor_id"])
    op.create_index(op.f("ix_doctor_restrictions_doctor_id"), "doctor_restrictions", ["doctor_id"])
    op.create_index(op.f("ix_doctor_restrictions_reason_id"), "doctor_restrictions", ["reason_id"])

    op.create_index(op.f("ix_telegram_link_tokens_created_by"), "telegram_link_tokens", ["created_by"])

    op.create_index(op.f("ix_calendar_assignments_service_area_id"), "calendar_assignments", ["service_area_id"])
    op.create_index(op.f("ix_unresolved_gaps_service_area_id"), "unresolved_gaps", ["service_area_id"])

    op.create_index(op.f("ix_mission_candidate_rankings_calendar_version_id"), "mission_candidate_rankings", ["calendar_version_id"])
    op.create_index(op.f("ix_mission_candidate_ranking_entries_doctor_id"), "mission_candidate_ranking_entries", ["doctor_id"])


def downgrade() -> None:
    # ------------------------------------------------------------------
    # Drop FK indexes
    # ------------------------------------------------------------------
    op.drop_index(op.f("ix_mission_candidate_ranking_entries_doctor_id"), table_name="mission_candidate_ranking_entries")
    op.drop_index(op.f("ix_mission_candidate_rankings_calendar_version_id"), table_name="mission_candidate_rankings")
    op.drop_index(op.f("ix_unresolved_gaps_service_area_id"), table_name="unresolved_gaps")
    op.drop_index(op.f("ix_calendar_assignments_service_area_id"), table_name="calendar_assignments")
    op.drop_index(op.f("ix_telegram_link_tokens_created_by"), table_name="telegram_link_tokens")
    op.drop_index(op.f("ix_doctor_restrictions_reason_id"), table_name="doctor_restrictions")
    op.drop_index(op.f("ix_doctor_restrictions_doctor_id"), table_name="doctor_restrictions")
    op.drop_index(op.f("ix_doctor_availability_doctor_id"), table_name="doctor_availability")
    op.drop_index(op.f("ix_doctors_service_inactive_reason_id"), table_name="doctors")
    op.drop_index(op.f("ix_doctors_department_id"), table_name="doctors")
    op.drop_index(op.f("ix_doctors_rank_id"), table_name="doctors")

    # ------------------------------------------------------------------
    # doctor_availability: drop UC (created after index so no conflict)
    # ------------------------------------------------------------------
    if _is_sqlite():
        with op.batch_alter_table("doctor_availability") as bop:
            bop.drop_constraint("uq_doctor_availability_monthly", type_="unique")
    else:
        op.drop_constraint("uq_doctor_availability_monthly", "doctor_availability", type_="unique")

    # ------------------------------------------------------------------
    # mission_candidate_rankings: drop new UC, restore old unnamed one
    # ------------------------------------------------------------------
    if _is_sqlite():
        with op.batch_alter_table("mission_candidate_rankings") as bop:
            bop.drop_constraint("uq_ranking_period_version", type_="unique")
            # Old constraint was unnamed, so this is a no-op; SQLite will
            # just create without a name in the batch rebuild
    else:
        op.drop_constraint("uq_ranking_period_version", "mission_candidate_rankings", type_="unique")
        # Recreate old unnamed constraint (PostgreSQL names it automatically)
        op.create_unique_constraint(None, "mission_candidate_rankings", ["month", "year"])
