"""Tests for system_context builder."""

from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from backend.app.application.telegram.system_context import build_system_context


def test_returns_string_with_valid_session():
    """Should return a non-empty string with content."""
    engine = create_engine("sqlite://", echo=False)
    # Create minimal tables for the queries to not fail
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE ranks (id INTEGER PRIMARY KEY, normalized_name VARCHAR)"))
        conn.execute(text("INSERT INTO ranks VALUES (1, 'Cabo')"))
        conn.execute(text("INSERT INTO ranks VALUES (2, 'Sargento')"))
        conn.execute(text("INSERT INTO ranks VALUES (3, 'Mayor')"))
        conn.execute(text("CREATE TABLE departments (id INTEGER PRIMARY KEY, name VARCHAR)"))
        conn.execute(text("INSERT INTO departments VALUES (1, 'Medicina General')"))
        conn.execute(text("CREATE TABLE service_areas (id INTEGER PRIMARY KEY, name VARCHAR)"))
        conn.execute(text("INSERT INTO service_areas VALUES (1, 'Emergencia')"))
        conn.execute(text("CREATE TABLE doctors (id INTEGER PRIMARY KEY, sex VARCHAR, availability_mode VARCHAR)"))
        conn.execute(text("INSERT INTO doctors VALUES (1, 'M', 'available')"))
        conn.execute(text("INSERT INTO doctors VALUES (2, 'F', 'available')"))
        conn.execute(text("CREATE TABLE calendars (id INTEGER PRIMARY KEY, status VARCHAR)"))
        conn.execute(text("INSERT INTO calendars VALUES (1, 'approved')"))
        conn.execute(text("CREATE TABLE calendar_versions (id INTEGER PRIMARY KEY, status VARCHAR)"))
        conn.execute(text("INSERT INTO calendar_versions VALUES (1, 'approved')"))
        conn.execute(text("CREATE TABLE missions (id INTEGER PRIMARY KEY, status VARCHAR)"))
        conn.execute(text("INSERT INTO missions VALUES (1, 'active')"))
        conn.execute(text("CREATE TABLE deactivation_reasons (id INTEGER PRIMARY KEY, reason VARCHAR)"))
        conn.execute(text("INSERT INTO deactivation_reasons VALUES (1, 'Licencia médica')"))
        conn.commit()

    session = Session(bind=engine)
    result = build_system_context(session)
    session.close()

    assert isinstance(result, str)
    assert len(result) > 100
    assert "RANGOS MILITARES" in result
    assert "Cabo" in result
    assert "Sargento" in result
    assert "DEPARTAMENTOS" in result
    assert "Medicina General" in result
    assert "ÁREAS DE SERVICIO" in result
    assert "Emergencia" in result
    assert "SEXO" in result
    assert "M" in result
    assert "F" in result
    assert "ESTADOS DE CALENDARIO" in result
    assert "approved" in result
    assert "ESTADOS DE MISIONES" in result
    assert "active" in result
    assert "RAZONES DE BAJA" in result
    assert "Licencia médica" in result
    assert "REGLAS DE NEGOCIO" in result
    assert "RELACIONES ENTRE TABLAS" in result


def test_handles_empty_database():
    """Should return fallback messages when tables exist but no data."""
    engine = create_engine("sqlite://", echo=False)
    with engine.connect() as conn:
        conn.execute(text("CREATE TABLE ranks (id INTEGER PRIMARY KEY, normalized_name VARCHAR)"))
        conn.execute(text("CREATE TABLE departments (id INTEGER PRIMARY KEY, name VARCHAR)"))
        conn.execute(text("CREATE TABLE service_areas (id INTEGER PRIMARY KEY, name VARCHAR)"))
        conn.execute(text("CREATE TABLE doctors (id INTEGER PRIMARY KEY, sex VARCHAR, availability_mode VARCHAR)"))
        conn.execute(text("CREATE TABLE calendars (id INTEGER PRIMARY KEY, status VARCHAR)"))
        conn.execute(text("CREATE TABLE calendar_versions (id INTEGER PRIMARY KEY, status VARCHAR)"))
        conn.execute(text("CREATE TABLE missions (id INTEGER PRIMARY KEY, status VARCHAR)"))
        conn.execute(text("CREATE TABLE deactivation_reasons (id INTEGER PRIMARY KEY, reason VARCHAR)"))
        conn.commit()

    session = Session(bind=engine)
    result = build_system_context(session)
    session.close()

    assert isinstance(result, str)
    assert "REGLAS DE NEGOCIO" in result
    assert "RELACIONES ENTRE TABLAS" in result


def test_handles_missing_tables_gracefully():
    """Should not crash when tables don't exist."""
    engine = create_engine("sqlite://", echo=False)
    session = Session(bind=engine)
    result = build_system_context(session)
    session.close()

    assert isinstance(result, str)
    assert "RANGOS MILITARES" in result
    assert "REGLAS DE NEGOCIO" in result
    assert "RELACIONES ENTRE TABLAS" in result
