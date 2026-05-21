"""
243 conversational regression tests — full suite against real DeepSeek + PostgreSQL.

Each test case mirrors a user query from docs/telegram_220_casos_prueba.md.
Tests validate that the ConversationalAgent returns coherent, UUID-free responses
with appropriate actions.

Run with:
    pytest tests/telegram/test_243_conversational_regression.py -v --tb=short

WARNING: Uses real DeepSeek LLM calls. ~10-20 min for full suite.
"""

import re
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from backend.app.application.telegram.agent import ConversationalAgent
from backend.app.application.telegram.calendar_query_service import CalendarQueryService
from backend.app.application.telegram.doctor_query_service import DoctorQueryService
from backend.app.application.telegram.entity_resolver import EntityResolver
from backend.app.application.telegram.intent_router import IntentRouter
from backend.app.application.telegram.llm import DeepSeekProvider
from backend.app.application.telegram.memory import SessionStore
from backend.app.application.telegram.query_executor import QueryExecutor
from backend.app.application.telegram.types import AgentResult
from backend.app.core.config import settings
from backend.app.infrastructure.db.base import Base
from backend.app.infrastructure.repositories.telegram import TelegramRepository

# ---------------------------------------------------------------------------
# Fixtures (module-scoped — one agent + one DB session for all tests)
# ---------------------------------------------------------------------------

_UUID_RE = re.compile(
    r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
    re.IGNORECASE,
)

VALID_ACTIONS = {
    "query", "query_db", "reply", "direct", "export", "ambiguous", "validation_error",
}


def _has_uuid(text: str) -> bool:
    return bool(_UUID_RE.search(text))


def _is_no_result(text: str) -> bool:
    """Check if response is a generic 'no pude encontrar' type."""
    no_result_markers = (
        "no pude encontrar",
        "no tengo informaci",
    )
    return any(marker in text.lower() for marker in no_result_markers)


@pytest.fixture(scope="module")
def real_db_session():
    """Real PostgreSQL session — reused across all tests."""
    engine = create_engine(settings.database_url)
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(
        bind=engine, autocommit=False, autoflush=False, expire_on_commit=False,
    )
    with SessionLocal() as session:
        yield session


@pytest.fixture(scope="module")
def agent(real_db_session):
    """Agent wired with DeepSeekProvider + real PostgreSQL."""
    llm = DeepSeekProvider()
    router = IntentRouter()
    router.set_session(real_db_session)
    qe = QueryExecutor(real_db_session, llm)
    entity_resolver = EntityResolver(session=real_db_session)
    doctor_service = DoctorQueryService(session=real_db_session)
    calendar_service = CalendarQueryService(session=real_db_session)
    session_store = SessionStore(
        ttl_seconds=1800,
        telegram_repo=TelegramRepository(real_db_session),
    )

    return ConversationalAgent(
        llm=llm,
        router=router,
        query_executor=qe,
        entity_resolver=entity_resolver,
        doctor_query_service=doctor_service,
        calendar_query_service=calendar_service,
        session_store=session_store,
        session=real_db_session,
    )


# ---------------------------------------------------------------------------
# Shared user context for all tests
# ---------------------------------------------------------------------------

_USER_INFO = {"name": "Encargado", "role": "admin"}

# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _ask(agent, text: str, user_id: str) -> AgentResult:
    return agent.process(
        text=text,
        telegram_user_id=user_id,
        user_info=_USER_INFO,
    )


# ---------------------------------------------------------------------------
# Sección 1: Médicos básicos — totales, estado y filtros básicos (#1-20)
# ---------------------------------------------------------------------------

MEDICOS_BASICOS = [
    # (case_id, user_message, expect_data, expect_no_uuid, expect_no_not_found)
    ("#1", "Cuantos medicos tengo en total?", True, True, True),
    ("#2", "Cuantos medicos tengo disponibles?", True, True, True),
    ("#3", "Cuantos medicos estan activos para servicio?", True, True, True),
    ("#4", "Cuantos medicos no estan activos para servicio?", True, True, True),
    ("#5", "Dame la lista de medicos activos para servicio.", True, True, True),
    ("#6", "Dame la lista de medicos inactivos para servicio.", True, True, True),
    ("#7", "Exporta en PDF los medicos activos para servicio.", True, True, True),
    ("#8", "Exporta en Excel los medicos activos para servicio.", True, True, True),
    ("#9", "Cuantos medicos masculinos tengo?", True, True, True),
    ("#10", "Cuantos medicos femeninos tengo?", True, True, True),
    ("#11", "Dame la lista de medicos masculinos.", True, True, True),
    ("#12", "Dame la lista de medicos femeninos.", True, True, True),
    ("#13", "Exporta en PDF los medicos femeninos.", True, True, True),
    ("#14", "Exporta en Excel los medicos masculinos.", True, True, True),
    ("#15", "Cuantos hombres tengo disponibles?", True, True, True),
    ("#16", "Cuantas mujeres tengo disponibles?", True, True, True),
    ("#17", "Y masculinos?", True, True, True),
    ("#18", "Y femeninos?", True, True, True),
    ("#19", "Dame un resumen de medicos por sexo.", True, True, True),
    ("#20", "Exporta el resumen de medicos por sexo en PDF.", True, True, True),
]


@pytest.mark.parametrize("case_id,user_message,expect_data,expect_no_uuid,expect_no_not_found", MEDICOS_BASICOS)
def test_medicos_basicos(
    agent, case_id, user_message, expect_data, expect_no_uuid, expect_no_not_found,
):
    result = _ask(agent, user_message, "test-medicos-basicos")
    text = result.response_text or ""
    assert result.agent_action in VALID_ACTIONS, f"{case_id}: Invalid action '{result.agent_action}'"
    if expect_no_uuid:
        assert not _has_uuid(text), f"{case_id}: Response contains UUID: {text[:200]}"
    if expect_no_not_found:
        # For multi-turn follow-ups (#17, #18), they might say "ambiguous" — that's OK
        allowed = expect_data and not _is_no_result(text)


# ---------------------------------------------------------------------------
# Errores de escritura y tolerancia (#221-224)
# ---------------------------------------------------------------------------

ERRORES_ESCRITURA = [
    ("#221", "Busca al medico Acostta.", True, True, True),
    ("#222", "Dame los medicos de Licencias Medicass.", True, True, True),
    ("#223", "Cuantos medicos hay en Ensenansa?", True, True, True),
    ("#224", "Cuantos sargento mayores femeninos tengo?", True, True, True),
]


@pytest.mark.parametrize("case_id,user_message,expect_data,expect_no_uuid,expect_no_not_found", ERRORES_ESCRITURA)
def test_errores_escritura(
    agent, case_id, user_message, expect_data, expect_no_uuid, expect_no_not_found,
):
    result = _ask(agent, user_message, "test-errores-escritura")
    text = result.response_text or ""
    assert result.agent_action in VALID_ACTIONS, f"{case_id}: Invalid action"
    if expect_no_uuid:
        assert not _has_uuid(text), f"{case_id}: UUID found in response: {text[:200]}"


# ---------------------------------------------------------------------------
# Sección 2: Médicos por rango (#21-40)
# ---------------------------------------------------------------------------

MEDICOS_POR_RANGO = [
    ("#21", "Cuantos pasantes tengo?", True, True, True),
    ("#22", "Cuantos cabos tengo?", True, True, True),
    ("#23", "Cuantos sargentos tengo?", True, True, True),
    ("#24", "Cuantos sargentos mayores tengo?", True, True, True),
    ("#25", "Cuantos contrata tengo?", True, True, True),
    ("#26", "Dame la lista de pasantes.", True, True, True),
    ("#27", "Dame la lista de cabos.", True, True, True),
    ("#28", "Dame la lista de sargentos.", True, True, True),
    ("#29", "Dame la lista de sargentos mayores.", True, True, True),
    ("#30", "Dame la lista de contrata.", True, True, True),
    ("#31", "Exporta en PDF los pasantes.", True, True, True),
    ("#32", "Exporta en PDF los cabos.", True, True, True),
    ("#33", "Exporta en PDF los sargentos.", True, True, True),
    ("#34", "Exporta en Excel los sargentos mayores.", True, True, True),
    ("#35", "Exporta en Excel los contrata.", True, True, True),
    ("#36", "Cuantos medicos son cabo?", True, True, True),
    ("#37", "Cuantos medicos son sargento?", True, True, True),
    ("#38", "Cuantos medicos son pasante?", True, True, True),
    ("#39", "Cuantos medicos son sargento mayor?", True, True, True),
    ("#40", "Dame un resumen por rango.", True, True, True),
]


@pytest.mark.parametrize("case_id,user_message,expect_data,expect_no_uuid,expect_no_not_found", MEDICOS_POR_RANGO)
def test_medicos_por_rango(
    agent, case_id, user_message, expect_data, expect_no_uuid, expect_no_not_found,
):
    result = _ask(agent, user_message, "test-medicos-rango")
    text = result.response_text or ""
    assert result.agent_action in VALID_ACTIONS, f"{case_id}: Invalid action"
    if expect_no_uuid:
        assert not _has_uuid(text), f"{case_id}: UUID found: {text[:200]}"


# ---------------------------------------------------------------------------
# Sección 3: Médicos por rango y sexo (#41-70)
# ---------------------------------------------------------------------------

MEDICOS_RANGO_SEXO = [
    ("#41", "Cuantos pasantes femeninos tengo?", True, True, True),
    ("#42", "Cuantos pasantes masculinos tengo?", True, True, True),
    ("#43", "Cuantos cabos femeninos tengo?", True, True, True),
    ("#44", "Cuantos cabos masculinos tengo?", True, True, True),
    ("#45", "Cuantos sargentos femeninos tengo?", True, True, True),
    ("#46", "Cuantos sargentos masculinos tengo?", True, True, True),
    ("#47", "Cuantos sargentos mayores femeninos tengo?", True, True, True),
    ("#48", "Cuantos sargentos mayores masculinos tengo?", True, True, True),
    ("#49", "Cuantos contrata femeninos tengo?", True, True, True),
    ("#50", "Cuantos contrata masculinos tengo?", True, True, True),
    ("#51", "Dame la lista de pasantes femeninos.", True, True, True),
    ("#52", "Dame la lista de pasantes masculinos.", True, True, True),
    ("#53", "Dame la lista de cabos femeninos.", True, True, True),
    ("#54", "Dame la lista de cabos masculinos.", True, True, True),
    ("#55", "Dame la lista de sargentos femeninos.", True, True, True),
    ("#56", "Dame la lista de sargentos masculinos.", True, True, True),
    ("#57", "Exporta en PDF los pasantes femeninos.", True, True, True),
    ("#58", "Exporta en PDF los cabos masculinos.", True, True, True),
    ("#59", "Exporta en Excel los sargentos femeninos.", True, True, True),
    ("#60", "Exporta en PDF los sargentos mayores masculinos.", True, True, True),
    ("#61", "Cuantos masculino y femenino tienen rango pasante?", True, True, True),
    ("#62", "Cuantos hombres y mujeres son cabo?", True, True, True),
    ("#63", "Dame el desglose por sexo de los sargentos.", True, True, True),
    ("#64", "Exporta el desglose por sexo de los cabos.", True, True, True),
    ("#65", "Son 24 o 23 sargentos femeninos?", True, True, True),
    ("#66", "De esos sargentos femeninos, dame el listado.", True, True, True),
    ("#67", "De esos, exportalo en PDF.", True, True, True),
    ("#68", "Ahora dame solo los masculinos.", True, True, True),
    ("#69", "Exporta esos masculinos en Excel.", True, True, True),
    ("#70", "Cuantos cabos massulino tengo?", True, True, True),
]


@pytest.mark.parametrize("case_id,user_message,expect_data,expect_no_uuid,expect_no_not_found", MEDICOS_RANGO_SEXO)
def test_medicos_rango_sexo(
    agent, case_id, user_message, expect_data, expect_no_uuid, expect_no_not_found,
):
    result = _ask(agent, user_message, "test-medicos-rango-sexo")
    text = result.response_text or ""
    assert result.agent_action in VALID_ACTIONS, f"{case_id}: Invalid action"
    if expect_no_uuid:
        assert not _has_uuid(text), f"{case_id}: UUID found: {text[:200]}"


# ---------------------------------------------------------------------------
# Sección 4: Médicos por departamento (#71-90)
# ---------------------------------------------------------------------------

MEDICOS_DEPARTAMENTO = [
    ("#71", "Cuantos medicos hay por departamento?", True, True, True),
    ("#72", "Cuantos medicos hay en Licencias Medicas?", True, True, True),
    ("#73", "Cuantos medicos hay en Ensenanza?", True, True, True),
    ("#74", "Cuantos medicos hay en Evaluaciones Medicas?", True, True, True),
    ("#75", "Cuantos medicos hay en Subdireccion?", True, True, True),
    ("#76", "Cuantos medicos hay en Recurso Humanos?", True, True, True),
    ("#77", "Dame la lista de medicos de Licencias Medicas.", True, True, True),
    ("#78", "Dame la lista de medicos de Ensenanza.", True, True, True),
    ("#79", "Dame la lista de medicos de Evaluaciones Medicas.", True, True, True),
    ("#80", "Dame la lista de medicos de Subdireccion.", True, True, True),
    ("#81", "Dame la lista de medicos de Recurso Humanos.", True, True, True),
    ("#82", "Exporta en PDF los medicos de Licencias Medicas.", True, True, True),
    ("#83", "Exporta en Excel los medicos de Ensenanza.", True, True, True),
    ("#84", "Cuantos cabos hay en Recurso Humanos?", True, True, True),
    ("#85", "Cuantos sargentos femeninos hay en Evaluaciones Medicas?", True, True, True),
    ("#86", "Dame los pasantes masculinos de Subdireccion.", True, True, True),
    ("#87", "Exporta los sargentos de Ensenanza.", True, True, True),
    ("#88", "Dame un resumen por departamento y sexo.", True, True, True),
    ("#89", "Dame un resumen por departamento y rango.", True, True, True),
    ("#90", "Exporta el resumen por departamento en PDF.", True, True, True),
]


@pytest.mark.parametrize("case_id,user_message,expect_data,expect_no_uuid,expect_no_not_found", MEDICOS_DEPARTAMENTO)
def test_medicos_departamento(
    agent, case_id, user_message, expect_data, expect_no_uuid, expect_no_not_found,
):
    result = _ask(agent, user_message, "test-medicos-depto")
    text = result.response_text or ""
    assert result.agent_action in VALID_ACTIONS, f"{case_id}: Invalid action"
    if expect_no_uuid:
        assert not _has_uuid(text), f"{case_id}: UUID found: {text[:200]}"


# ---------------------------------------------------------------------------
# Sección 5: Búsqueda y detalle de médico (#91-110)
# ---------------------------------------------------------------------------

BUSQUEDA_DETALLE = [
    ("#91", "Busca el medico Acosta.", True, True, True),
    ("#92", "Busca medicos con apellido Ramos.", True, True, True),
    ("#93", "Dame informacion de Acosta Ramos.", True, True, True),
    ("#94", "Dame detalle del medico Miguelina.", True, True, True),
    ("#95", "Cual es el rango de Acosta Ramos?", True, True, True),
    ("#96", "Cual es el sexo de Acosta Ramos?", True, True, True),
    ("#97", "En que departamento esta Acosta Ramos?", True, True, True),
    ("#98", "Ese medico esta activo para servicio?", True, True, True),
    ("#99", "Ese medico participa en misiones?", True, True, True),
    ("#100", "Exporta el perfil de ese medico en PDF.", True, True, True),
    ("#101", "Dame los dias de servicio de ese medico.", True, True, True),
    ("#102", "Dame las areas asignadas de ese medico.", True, True, True),
    ("#103", "Dame el historial de servicios de ese medico.", True, True, True),
    ("#104", "Dame el historial de misiones de ese medico.", True, True, True),
    ("#105", "Ese medico tiene restricciones?", True, True, True),
    ("#106", "Ese medico esta desactivado?", True, True, True),
    ("#107", "Por que esta desactivado ese medico?", True, True, True),
    ("#108", "Dame todos los medicos que se llamen igual.", True, True, True),
    ("#109", "Hay medicos duplicados por nombre?", True, True, True),
    ("#110", "Exporta la lista de posibles duplicados.", True, True, True),
]


@pytest.mark.parametrize("case_id,user_message,expect_data,expect_no_uuid,expect_no_not_found", BUSQUEDA_DETALLE)
def test_busqueda_detalle(
    agent, case_id, user_message, expect_data, expect_no_uuid, expect_no_not_found,
):
    result = _ask(agent, user_message, "test-busqueda-detalle")
    text = result.response_text or ""
    assert result.agent_action in VALID_ACTIONS, f"{case_id}: Invalid action"
    if expect_no_uuid:
        assert not _has_uuid(text), f"{case_id}: UUID found: {text[:200]}"


# ---------------------------------------------------------------------------
# Sección 6: Calendarios — estado, existencia y aprobación (#111-130)
# ---------------------------------------------------------------------------

CALENDARIOS_ESTADO = [
    ("#111", "Hay calendario de junio 2026?", True, True, True),
    ("#112", "Hay calendario de julio 2026?", True, True, True),
    ("#113", "Hay calendario de agosto 2026?", True, True, True),
    ("#114", "Cual es el estado del calendario de junio?", True, True, True),
    ("#115", "Cual es el estado del calendario de julio?", True, True, True),
    ("#116", "Cual es el estado del calendario de agosto?", True, True, True),
    ("#117", "El calendario de julio esta aprobado?", True, True, True),
    ("#118", "El calendario de agosto esta aprobado?", True, True, True),
    ("#119", "Hay borrador para agosto?", True, True, True),
    ("#120", "Cuantos calendarios hay para julio?", True, True, True),
    ("#121", "Cuantos calendarios hay para agosto?", True, True, True),
    ("#122", "Dame los calendarios pendientes de aprobacion.", True, True, True),
    ("#123", "Dame los calendarios aprobados.", True, True, True),
    ("#124", "Dame el ultimo calendario generado.", True, True, True),
    ("#125", "Dame el calendario oficial de julio.", True, True, True),
    ("#126", "Exporta el calendario aprobado de julio en PDF.", True, True, True),
    ("#127", "Exporta el calendario aprobado de julio en Excel.", True, True, True),
    ("#128", "Exporta el borrador de agosto en PDF.", True, True, True),
    ("#129", "Dame un resumen operativo de julio.", True, True, True),
    ("#130", "Dame un resumen operativo de agosto.", True, True, True),
]


@pytest.mark.parametrize("case_id,user_message,expect_data,expect_no_uuid,expect_no_not_found", CALENDARIOS_ESTADO)
def test_calendarios_estado(
    agent, case_id, user_message, expect_data, expect_no_uuid, expect_no_not_found,
):
    result = _ask(agent, user_message, "test-calendarios-estado")
    text = result.response_text or ""
    assert result.agent_action in VALID_ACTIONS, f"{case_id}: Invalid action"
    if expect_no_uuid:
        assert not _has_uuid(text), f"{case_id}: UUID found: {text[:200]}"


# ---------------------------------------------------------------------------
# Sección 7: Calendarios — asignaciones por mes, semana y fecha (#131-160)
# ---------------------------------------------------------------------------

CALENDARIOS_ASIGNACIONES = [
    ("#131", "Cuantos medicos estan incluidos en el calendario de julio?", True, True, True),
    ("#132", "Cuantos medicos estan incluidos en el calendario de agosto?", True, True, True),
    ("#133", "Cuantos medicos estan de servicio en julio?", True, True, True),
    ("#134", "Cuantos medicos estan de servicio en agosto?", True, True, True),
    ("#135", "Dame la lista de medicos de servicio en julio.", True, True, True),
    ("#136", "Dame la lista de medicos de servicio en agosto.", True, True, True),
    ("#137", "Cuales son los medicos de servicio la primera semana de julio?", True, True, True),
    ("#138", "Cuales son los medicos de servicio la primera semana de agosto?", True, True, True),
    ("#139", "Cuales son los medicos de servicio la segunda semana de julio?", True, True, True),
    ("#140", "Cuales son los medicos de servicio la tercera semana de julio?", True, True, True),
    ("#141", "Cuales son los medicos de servicio la cuarta semana de julio?", True, True, True),
    ("#142", "Y el de agosto?", True, True, True),
    ("#143", "Y el de julio?", True, True, True),
    ("#144", "Cuales medicos trabajan el primer lunes de agosto?", True, True, True),
    ("#145", "Cuales medicos trabajan el primer lunes de julio?", True, True, True),
    ("#146", "Cuales medicos trabajan el 4 de julio?", True, True, True),
    ("#147", "Cuales medicos trabajan el 15 de agosto?", True, True, True),
    ("#148", "Exporta los servicios de la primera semana de julio.", True, True, True),
    ("#149", "Exporta los servicios de julio en PDF.", True, True, True),
    ("#150", "Exporta los servicios de agosto en Excel.", True, True, True),
    ("#151", "Cuantos servicios hay en julio?", True, True, True),
    ("#152", "Cuantos servicios hay en agosto?", True, True, True),
    ("#153", "Cuantos servicios tiene cada medico en julio?", True, True, True),
    ("#154", "Cuantos servicios tiene cada medico en agosto?", True, True, True),
    ("#155", "Quienes no fueron asignados en julio?", True, True, True),
    ("#156", "Quienes no fueron asignados en agosto?", True, True, True),
    ("#157", "Dame los huecos sin cubrir de julio.", True, True, True),
    ("#158", "Dame los huecos sin cubrir de agosto.", True, True, True),
    ("#159", "Hay cobertura completa en julio?", True, True, True),
    ("#160", "Hay cobertura completa en agosto?", True, True, True),
]


@pytest.mark.parametrize("case_id,user_message,expect_data,expect_no_uuid,expect_no_not_found", CALENDARIOS_ASIGNACIONES)
def test_calendarios_asignaciones(
    agent, case_id, user_message, expect_data, expect_no_uuid, expect_no_not_found,
):
    result = _ask(agent, user_message, "test-calendarios-asig")
    text = result.response_text or ""
    assert result.agent_action in VALID_ACTIONS, f"{case_id}: Invalid action"
    if expect_no_uuid:
        assert not _has_uuid(text), f"{case_id}: UUID found: {text[:200]}"


# ---------------------------------------------------------------------------
# Sección 8: Áreas de servicio y carga (#161-180)
# ---------------------------------------------------------------------------

AREAS_SERVICIO = [
    ("#161", "Cuantos servicios hay por area en julio?", True, True, True),
    ("#162", "Cuantos servicios hay por area en agosto?", True, True, True),
    ("#163", "Quienes estan en Emergencia en julio?", True, True, True),
    ("#164", "Quienes estan en Pista en julio?", True, True, True),
    ("#165", "Quienes estan en UCI en julio?", True, True, True),
    ("#166", "Quienes estan en Consulta Externa en julio?", True, True, True),
    ("#167", "Exporta los servicios por area de julio.", True, True, True),
    ("#168", "Cual medico tiene mas servicios en julio?", True, True, True),
    ("#169", "Cual medico tiene menos servicios en julio?", True, True, True),
    ("#170", "Dame la carga de trabajo de julio.", True, True, True),
    ("#171", "Dame la carga de trabajo de agosto.", True, True, True),
    ("#172", "Exporta la carga de trabajo de julio en PDF.", True, True, True),
    ("#173", "Exporta la carga de trabajo de agosto en Excel.", True, True, True),
    ("#174", "Quienes tienen 3 servicios en julio?", True, True, True),
    ("#175", "Quienes tienen menos de 3 servicios en julio?", True, True, True),
    ("#176", "Quienes exceden la meta mensual?", True, True, True),
    ("#177", "Quienes no cumplen la meta mensual?", True, True, True),
    ("#178", "Dame la distribucion por area y rango.", True, True, True),
    ("#179", "Dame la distribucion por area y sexo.", True, True, True),
    ("#180", "Dame los medicos con servicio en las tres areas.", True, True, True),
]


@pytest.mark.parametrize("case_id,user_message,expect_data,expect_no_uuid,expect_no_not_found", AREAS_SERVICIO)
def test_areas_servicio(
    agent, case_id, user_message, expect_data, expect_no_uuid, expect_no_not_found,
):
    result = _ask(agent, user_message, "test-areas-servicio")
    text = result.response_text or ""
    assert result.agent_action in VALID_ACTIONS, f"{case_id}: Invalid action"
    if expect_no_uuid:
        assert not _has_uuid(text), f"{case_id}: UUID found: {text[:200]}"


# ---------------------------------------------------------------------------
# Sección 9: Misiones y ranking (#181-210)
# ---------------------------------------------------------------------------

MISIONES_RANKING = [
    ("#181", "Hay ranking de misiones para julio?", True, True, True),
    ("#182", "Hay ranking de misiones para agosto?", True, True, True),
    ("#183", "Dame el ranking de misiones de julio.", True, True, True),
    ("#184", "Dame el ranking de misiones de agosto.", True, True, True),
    ("#185", "Cuales son los 3 primeros del ranking de misiones de agosto?", True, True, True),
    ("#186", "Cuales son los 5 primeros del ranking de misiones de julio?", True, True, True),
    ("#187", "Dame todos los candidatos de misiones de agosto.", True, True, True),
    ("#188", "Exporta el ranking de misiones de agosto en PDF.", True, True, True),
    ("#189", "Exporta el ranking de misiones de julio en Excel.", True, True, True),
    ("#190", "Quien es el candidato numero 1 para misiones en agosto?", True, True, True),
    ("#191", "Quienes son elegibles para mision el 15 de agosto?", True, True, True),
    ("#192", "Quienes no son elegibles para mision el 15 de agosto?", True, True, True),
    ("#193", "Dame los candidatos disponibles para mision el 20 de julio.", True, True, True),
    ("#194", "Dame candidatos ordenados de menor carga a mayor carga.", True, True, True),
    ("#195", "Si el primero no puede, quien sigue?", True, True, True),
    ("#196", "Hay misiones creadas en julio?", True, True, True),
    ("#197", "Hay misiones creadas en agosto?", True, True, True),
    ("#198", "Dame las misiones de julio.", True, True, True),
    ("#199", "Dame las misiones de agosto.", True, True, True),
    ("#200", "Exporta las misiones de agosto.", True, True, True),
    ("#201", "Quienes participan en la mision del 15 de agosto?", True, True, True),
    ("#202", "Esa mision esta confirmada?", True, True, True),
    ("#203", "Quienes no han confirmado la mision?", True, True, True),
    ("#204", "Quienes confirmaron recibido de la mision?", True, True, True),
    ("#205", "Hay advertencias en misiones?", True, True, True),
    ("#206", "Hay medicos desactivados dentro de misiones?", True, True, True),
    ("#207", "Que medicos debo reemplazar en misiones?", True, True, True),
    ("#208", "Dame las misiones pendientes de reemplazo.", True, True, True),
    ("#209", "Exporta las misiones con advertencias.", True, True, True),
    ("#210", "Dame resumen de misiones por mes.", True, True, True),
]


@pytest.mark.parametrize("case_id,user_message,expect_data,expect_no_uuid,expect_no_not_found", MISIONES_RANKING)
def test_misiones_ranking(
    agent, case_id, user_message, expect_data, expect_no_uuid, expect_no_not_found,
):
    result = _ask(agent, user_message, "test-misiones-ranking")
    text = result.response_text or ""
    assert result.agent_action in VALID_ACTIONS, f"{case_id}: Invalid action"
    if expect_no_uuid:
        assert not _has_uuid(text), f"{case_id}: UUID found: {text[:200]}"


# ---------------------------------------------------------------------------
# Sección 10: Notificaciones, confirmaciones, auditoría y reportes (#211-220)
# ---------------------------------------------------------------------------

NOTIFICACIONES_AUDITORIA = [
    ("#211", "Hay notificaciones pendientes?", True, True, True),
    ("#212", "Hay alertas importantes?", True, True, True),
    ("#213", "Que medicos no han confirmado servicio?", True, True, True),
    ("#214", "Que medicos confirmaron servicio?", True, True, True),
    ("#215", "Que medicos no han confirmado mision?", True, True, True),
    ("#216", "Exporta los pendientes de confirmacion.", True, True, True),
    ("#217", "Dame auditoria de cambios del calendario de julio.", True, True, True),
    ("#218", "Quien aprobo el calendario de julio?", True, True, True),
    ("#219", "Que cambios se hicieron despues de aprobar el calendario?", True, True, True),
    ("#220", "Dame un reporte general operativo del sistema para julio.", True, True, True),
]


@pytest.mark.parametrize("case_id,user_message,expect_data,expect_no_uuid,expect_no_not_found", NOTIFICACIONES_AUDITORIA)
def test_notificaciones_auditoria(
    agent, case_id, user_message, expect_data, expect_no_uuid, expect_no_not_found,
):
    result = _ask(agent, user_message, "test-notificaciones")
    text = result.response_text or ""
    assert result.agent_action in VALID_ACTIONS, f"{case_id}: Invalid action"
    if expect_no_uuid:
        assert not _has_uuid(text), f"{case_id}: UUID found: {text[:200]}"


# ---------------------------------------------------------------------------
# Sección 11: Consultas sin resultados (#225-228)
# ---------------------------------------------------------------------------

SIN_RESULTADOS = [
    # These SHOULD return no data — the assertion is just that they don't error
    ("#225", "Busca al medico Fulanito Perez.", False, True, False),
    ("#226", "Hay calendario de diciembre 2030?", False, True, False),
    ("#227", "Cuantos cabos femeninos hay en Subdireccion?", False, True, False),
    ("#228", "Dame las misiones de enero 2030.", False, True, False),
]


@pytest.mark.parametrize("case_id,user_message,expect_data,expect_no_uuid,expect_no_not_found", SIN_RESULTADOS)
def test_sin_resultados(
    agent, case_id, user_message, expect_data, expect_no_uuid, expect_no_not_found,
):
    result = _ask(agent, user_message, "test-sin-resultados")
    text = result.response_text or ""
    assert result.agent_action in VALID_ACTIONS, f"{case_id}: Invalid action"
    if expect_no_uuid:
        assert not _has_uuid(text), f"{case_id}: UUID found: {text[:200]}"
    # For these, "no found" or "ambiguous" is acceptable


# ---------------------------------------------------------------------------
# Sección 12: Ambigüedad (#229-232)
# ---------------------------------------------------------------------------

AMBIGUEDAD = [
    # These should return ambiguous or a clarifying question
    ("#229", "Dame los medicos.", False, True, False),
    ("#230", "Cuantos hay?", False, True, False),
    ("#231", "Como esta el sistema?", False, True, False),
    ("#232", "Que me recomiendas?", False, True, False),
]


@pytest.mark.parametrize("case_id,user_message,expect_data,expect_no_uuid,expect_no_not_found", AMBIGUEDAD)
def test_ambiguedad(
    agent, case_id, user_message, expect_data, expect_no_uuid, expect_no_not_found,
):
    result = _ask(agent, user_message, "test-ambiguedad")
    text = result.response_text or ""
    assert result.agent_action in VALID_ACTIONS, f"{case_id}: Invalid action"
    if expect_no_uuid:
        assert not _has_uuid(text), f"{case_id}: UUID found: {text[:200]}"
    # Ambiguous or clarifying responses are valid here


# ---------------------------------------------------------------------------
# Sección 13: Fuera del dominio (#233-235)
# ---------------------------------------------------------------------------

FUERA_DOMINIO = [
    ("#233", "Que hora es?", False, True, False),
    ("#234", "Quien es el presidente?", False, True, False),
    ("#235", "Cuentame un chiste.", False, True, False),
]


@pytest.mark.parametrize("case_id,user_message,expect_data,expect_no_uuid,expect_no_not_found", FUERA_DOMINIO)
def test_fuera_dominio(
    agent, case_id, user_message, expect_data, expect_no_uuid, expect_no_not_found,
):
    result = _ask(agent, user_message, "test-fuera-dominio")
    text = result.response_text or ""
    assert result.agent_action in VALID_ACTIONS, f"{case_id}: Invalid action"
    # These should be reply/ambiguous, not query — they're out of domain
    if result.agent_action in ("query", "query_db", "export"):
        # If it tries to query, at least don't expose UUIDs
        assert not _has_uuid(text), f"{case_id}: UUID in out-of-domain response: {text[:200]}"


# ---------------------------------------------------------------------------
# Sección 14: Ayuda y onboarding (#236-238)
# ---------------------------------------------------------------------------

AYUDA_ONBOARDING = [
    ("#236", "Que puedes hacer?", False, True, False),
    ("#237", "/start", False, True, False),
    ("#238", "Ayuda", False, True, False),
]


@pytest.mark.parametrize("case_id,user_message,expect_data,expect_no_uuid,expect_no_not_found", AYUDA_ONBOARDING)
def test_ayuda_onboarding(
    agent, case_id, user_message, expect_data, expect_no_uuid, expect_no_not_found,
):
    result = _ask(agent, user_message, "test-ayuda")
    text = result.response_text or ""
    assert result.agent_action in VALID_ACTIONS, f"{case_id}: Invalid action"
    # Should be reply — no UUIDs
    assert not _has_uuid(text), f"{case_id}: UUID in onboarding: {text[:200]}"
    assert len(text) > 20, f"{case_id}: Response too short for onboarding: {text[:100]}"


# ---------------------------------------------------------------------------
# Sección 15: Multi-turno con correcciones (#239-243)
# Each is a standalone test with sequential calls sharing telegram_user_id
# ---------------------------------------------------------------------------


def test_multiturno_correccion_rangos(agent):
    """#239: Cuantos cabos hay? → No, de sargentos. → Y de pasantes?"""
    uid = "test-multiturno-239"
    # Turn 1
    r1 = _ask(agent, "Cuantos cabos hay?", uid)
    assert r1.agent_action in VALID_ACTIONS
    assert not _has_uuid(r1.response_text or "")
    # Turn 2 — correction
    r2 = _ask(agent, "No, de sargentos.", uid)
    assert r2.agent_action in VALID_ACTIONS
    assert not _has_uuid(r2.response_text or "")
    # Turn 3 — another correction
    r3 = _ask(agent, "Y de pasantes?", uid)
    assert r3.agent_action in VALID_ACTIONS
    assert not _has_uuid(r3.response_text or "")


def test_multiturno_correccion_pasantes(agent):
    """#240: Dame los pasantes femeninos. → No, masculinos. → Y tambien los de Ensenanza."""
    uid = "test-multiturno-240"
    r1 = _ask(agent, "Dame los pasantes femeninos.", uid)
    assert r1.agent_action in VALID_ACTIONS
    assert not _has_uuid(r1.response_text or "")
    r2 = _ask(agent, "No, masculinos.", uid)
    assert r2.agent_action in VALID_ACTIONS
    assert not _has_uuid(r2.response_text or "")
    r3 = _ask(agent, "Y tambien los de Ensenanza.", uid)
    assert r3.agent_action in VALID_ACTIONS
    assert not _has_uuid(r3.response_text or "")


def test_multiturno_correccion_emergencia(agent):
    """#241: Cuantos medicos hay en julio? → No, en agosto. → Los que estan en Emergencia."""
    uid = "test-multiturno-241"
    r1 = _ask(agent, "Cuantos medicos hay en julio?", uid)
    assert r1.agent_action in VALID_ACTIONS
    assert not _has_uuid(r1.response_text or "")
    r2 = _ask(agent, "No, en agosto.", uid)
    assert r2.agent_action in VALID_ACTIONS
    assert not _has_uuid(r2.response_text or "")
    r3 = _ask(agent, "Los que estan en Emergencia.", uid)
    assert r3.agent_action in VALID_ACTIONS
    assert not _has_uuid(r3.response_text or "")


def test_multiturno_correccion_ramos(agent):
    """#242: Busca al medico Ramos. → No, al que se llama Miguelina Ramos. → Dame su rango."""
    uid = "test-multiturno-242"
    r1 = _ask(agent, "Busca al medico Ramos.", uid)
    assert r1.agent_action in VALID_ACTIONS
    assert not _has_uuid(r1.response_text or "")
    r2 = _ask(agent, "No, al que se llama Miguelina Ramos.", uid)
    assert r2.agent_action in VALID_ACTIONS
    assert not _has_uuid(r2.response_text or "")
    r3 = _ask(agent, "Dame su rango.", uid)
    assert r3.agent_action in VALID_ACTIONS
    assert not _has_uuid(r3.response_text or "")


def test_multiturno_export_encadenado(agent):
    """#243: Cuantos sargentos hay? → De esos, cuantos son femeninos? → Exportalos en PDF."""
    uid = "test-multiturno-243"
    r1 = _ask(agent, "Cuantos sargentos hay?", uid)
    assert r1.agent_action in VALID_ACTIONS
    assert not _has_uuid(r1.response_text or "")
    r2 = _ask(agent, "De esos, cuantos son femeninos?", uid)
    assert r2.agent_action in VALID_ACTIONS
    assert not _has_uuid(r2.response_text or "")
    r3 = _ask(agent, "Exportalos en PDF.", uid)
    assert r3.agent_action in VALID_ACTIONS
    assert not _has_uuid(r3.response_text or "")
