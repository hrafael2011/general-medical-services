"""Stub job functions for the APScheduler notification queue.

Each stub logs its invocation and returns {"status": "not_implemented"}.
Full implementations will replace these in Task 9.
"""

import logging

logger = logging.getLogger(__name__)


async def process_notification_queue() -> dict:
    """Process pending notifications in the queue."""
    logger.info("Job [process_notifications] stub called")
    return {"status": "not_implemented"}


async def send_pre_service_reminders() -> dict:
    """Send pre-service appointment reminders."""
    logger.info("Job [send_reminders] stub called")
    return {"status": "not_implemented"}


async def check_unconfirmed_escalamiento() -> dict:
    """Check and escalate unconfirmed appointments."""
    logger.info("Job [check_escalamiento] stub called")
    return {"status": "not_implemented"}


async def process_overdue_confirmations() -> dict:
    """Process overdue confirmations."""
    logger.info("Job [process_overdue] stub called")
    return {"status": "not_implemented"}
