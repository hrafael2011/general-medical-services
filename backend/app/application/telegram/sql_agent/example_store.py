"""Local vector store for few-shot SQL examples using sqlite-vec.

Each example is stored as (nl_query, sql, category) with a TF-IDF embedding
so we can retrieve the most similar past examples for a new user question.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import sqlite_vec
from sklearn.feature_extraction.text import TfidfVectorizer

logger = logging.getLogger(__name__)

_STOPWORDS_ES = {
    "el", "la", "los", "las", "un", "una", "unos", "unas",
    "de", "del", "al", "y", "o", "en", "con", "por", "para",
    "a", "ante", "bajo", "desde", "hasta", "hacia", "según",
    "sin", "sobre", "tras", "que", "cual", "cuales", "quien",
    "quienes", "cuyo", "cuyos", "cuya", "cuyas", "donde",
    "como", "cuando", "cuanto", "cuanta", "cuantos", "cuantas",
    "me", "te", "se", "nos", "os", "lo", "le", "les",
    "mi", "tu", "su", "nuestro", "vuestro", "mío", "tuyo",
    "suyo", "mía", "tuya", "suya", "nuestra", "vuestra",
    "este", "ese", "aquel", "esta", "esa", "aquella",
    "estos", "esos", "aquellos", "estas", "esas", "aquellas",
    "es", "son", "soy", "eres", "somos", "sois", "estoy",
    "esta", "estan", "estamos", "hay", "habia", "habian",
    "tengo", "tiene", "tienen", "tenemos", "tienes",
    "muy", "mas", "mucho", "muchos", "muchas", "poco", "pocos",
    "todo", "todos", "toda", "todas", "cada", "otro", "otros",
    "otra", "otras", "mismo", "mismos", "misma", "mismas",
    "también", "ya", "aún", "todavía", "siempre", "nunca",
    "casi", "solo", "sólo", "bien", "mal", "ahora", "antes",
    "después", "luego", "mientras", "durante", "entre", "mediante",
}


@dataclass(frozen=True, slots=True)
class SQLExample:
    """A single few-shot example: natural language → SQL."""

    nl_query: str
    sql: str
    category: str = "general"
    description: str = ""


class ExampleStore:
    """SQLite + sqlite-vec vector store for few-shot SQL examples.

    Uses TF-IDF to produce dense(ish) embeddings from natural-language queries.
    On retrieval the top-k most similar examples are returned to be injected
    into the LLM prompt.
    """

    def __init__(self, db_path: str | Path | None = None) -> None:
        """Open (and create if necessary) the example store.

        *db_path* defaults to ``<project_root>/data/sql_agent_examples.sqlite3``.
        """
        if db_path is None:
            project_root = Path(__file__).resolve().parents[4]
            db_path = project_root / "data" / "sql_agent_examples.sqlite3"
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.enable_load_extension(True)
        sqlite_vec.load(self._conn)
        self._ensure_schema()
        self._vectorizer: TfidfVectorizer | None = None
        self._fit_vectorizer()

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------
    def _ensure_schema(self) -> None:
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS examples (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                nl_query    TEXT NOT NULL,
                sql         TEXT NOT NULL,
                category    TEXT NOT NULL DEFAULT 'general',
                description TEXT NOT NULL DEFAULT ''
            )
            """
        )
        # Virtual table for vectors — dimension will be set on first fit
        try:
            self._conn.execute(
                "CREATE VIRTUAL TABLE IF NOT EXISTS vec_examples USING vec0(embedding float[128])"
            )
        except Exception:
            # If dimension changes we may need to recreate; handled in _fit_vectorizer
            pass

    # ------------------------------------------------------------------
    # Vectorizer management
    # ------------------------------------------------------------------
    def _fit_vectorizer(self) -> None:
        """Re-fit TF-IDF on all stored examples."""
        rows = self._conn.execute(
            "SELECT nl_query FROM examples ORDER BY id"
        ).fetchall()
        corpus = [r[0] for r in rows]
        if not corpus:
            # No data yet — create a dummy vectorizer with a tiny vocab
            self._vectorizer = TfidfVectorizer(
                max_features=128,
                stop_words=list(_STOPWORDS_ES),
                lowercase=True,
                token_pattern=r"(?u)\b\w+\b",
            )
            self._vectorizer.fit(["dummy query"])
            return

        self._vectorizer = TfidfVectorizer(
            max_features=128,
            stop_words=list(_STOPWORDS_ES),
            lowercase=True,
            token_pattern=r"(?u)\b\w+\b",
        )
        self._vectorizer.fit(corpus)
        self._maybe_recreate_vec_table()
        self._reindex_all()

    def _maybe_recreate_vec_table(self) -> None:
        """Recreate the virtual table if the embedding dimension changed."""
        dim = len(self._vectorizer.get_feature_names_out())
        # sqlite-vec tables are fixed-dimension; easiest is to drop & recreate
        try:
            self._conn.execute("DROP TABLE IF EXISTS vec_examples")
            self._conn.execute(
                f"CREATE VIRTUAL TABLE vec_examples USING vec0(embedding float[{dim}])"
            )
        except Exception as exc:
            logger.warning("Could not recreate vec_examples table: %s", exc)

    def _reindex_all(self) -> None:
        """Recompute embeddings for every example in the store."""
        rows = self._conn.execute(
            "SELECT id, nl_query FROM examples ORDER BY id"
        ).fetchall()
        if not rows or self._vectorizer is None:
            return
        ids = [r[0] for r in rows]
        texts = [r[1] for r in rows]
        vectors = self._vectorizer.transform(texts).toarray().astype(np.float32)
        for eid, vec in zip(ids, vectors, strict=False):
            self._upsert_vec(eid, vec)
        self._conn.commit()

    def _upsert_vec(self, eid: int, vec: np.ndarray) -> None:
        """Insert or replace a vector row."""
        # sqlite-vec requires explicit delete + insert for updates
        self._conn.execute(
            "DELETE FROM vec_examples WHERE rowid = ?", (eid,)
        )
        self._conn.execute(
            "INSERT INTO vec_examples(rowid, embedding) VALUES (?, ?)",
            (eid, vec),
        )

    def _embed(self, text: str) -> np.ndarray:
        if self._vectorizer is None:
            raise RuntimeError("Vectorizer not fitted")
        vec = self._vectorizer.transform([text]).toarray().astype(np.float32)
        return vec[0]

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def add(self, examples: list[SQLExample]) -> list[int]:
        """Store new examples and return their IDs."""
        ids: list[int] = []
        for ex in examples:
            cur = self._conn.execute(
                """
                INSERT INTO examples (nl_query, sql, category, description)
                VALUES (?, ?, ?, ?)
                """,
                (ex.nl_query, ex.sql, ex.category, ex.description),
            )
            ids.append(cur.lastrowid)
        self._conn.commit()
        # Re-fit vectorizer so new examples are searchable
        self._fit_vectorizer()
        return ids

    def search(self, query_text: str, k: int = 3) -> list[SQLExample]:
        """Return the *k* most similar examples to *query_text*."""
        if self._vectorizer is None or self.count() == 0:
            return []
        vec = self._embed(query_text)
        rows = self._conn.execute(
            """
            SELECT e.id, e.nl_query, e.sql, e.category, e.description
            FROM vec_examples v
            JOIN examples e ON e.id = v.rowid
            WHERE v.embedding MATCH ? AND k = ?
            ORDER BY v.distance
            """,
            (vec, k),
        ).fetchall()
        return [
            SQLExample(
                nl_query=r[1],
                sql=r[2],
                category=r[3],
                description=r[4],
            )
            for r in rows
        ]

    def count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) FROM examples").fetchone()
        return row[0] if row else 0

    def clear(self) -> None:
        """Remove all examples (useful for tests)."""
        self._conn.execute("DELETE FROM examples")
        self._conn.execute("DELETE FROM vec_examples")
        self._conn.commit()
        self._fit_vectorizer()

    def close(self) -> None:
        self._conn.close()

    def __enter__(self) -> ExampleStore:
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
