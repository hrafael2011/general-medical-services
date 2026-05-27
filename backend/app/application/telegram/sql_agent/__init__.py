"""SQL Agent — multi-turn SQL generation with self-correction.

Replaces the legacy one-shot NL→SQL fallback with an iterative pipeline:

  SchemaLinker → QueryGenerator → SafeSQLExecutor → SQLVerifier → QueryRefiner

The orchestrator repeats the generate-execute-verify-correct loop up to
3 times, dramatically improving accuracy on complex ad-hoc queries.
"""

from .example_store import ExampleStore, SQLExample
from .executor import SafeSQLExecutor
from .generator import QueryGenerator
from .orchestrator import MAX_ITERATIONS, SQLAgentOrchestrator
from .prompt_builder import PromptBuilder
from .refiner import QueryRefiner
from .schema_linker import SchemaLinker
from .security import build_schema_summary, extract_sql_from_markdown, validate_sql
from .verifier import SQLVerifier

__all__ = [
    "build_schema_summary",
    "ExampleStore",
    "extract_sql_from_markdown",
    "MAX_ITERATIONS",
    "PromptBuilder",
    "QueryGenerator",
    "QueryRefiner",
    "SafeSQLExecutor",
    "SchemaLinker",
    "SQLAgentOrchestrator",
    "SQLExample",
    "SQLVerifier",
    "validate_sql",
]
