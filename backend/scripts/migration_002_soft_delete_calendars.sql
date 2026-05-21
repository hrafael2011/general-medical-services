-- Migration 002: Add soft-delete support for calendars
--
-- Adds deleted_at column to calendars table and replaces the unique
-- constraint on (year, month) with a partial unique index so that a
-- new calendar can be created for the same period after soft-deleting
-- the original.

BEGIN;

-- 1. Add deleted_at column (nullable, default NULL)
ALTER TABLE calendars ADD COLUMN deleted_at TIMESTAMP WITH TIME ZONE DEFAULT NULL;

-- 2. Drop the existing unique constraint (which prevents duplicate year+month)
ALTER TABLE calendars DROP CONSTRAINT IF EXISTS uq_calendars_year_month;

-- 3. Create a partial unique index that only enforces uniqueness for non-deleted rows
CREATE UNIQUE INDEX uq_calendars_year_month_active
    ON calendars (year, month)
    WHERE deleted_at IS NULL;

COMMIT;
