"""Script para probar casos conversacionales directamente contra el agente.

Uso:
  cd backend && python -m tests.telegram.run_test_block <bloque>

Los resultados se registran en docs/test-results.md
"""

import json
import sys
import time
from pathlib import Path

# ---------------------------------------------------------------------------
# Bloques de prueba
# ---------------------------------------------------------------------------

BLOCK_1 = [
    ("Cuantos medicos tengo en total?", "#1"),
    ("Cuantos medicos tengo disponibles?", "#2"),
    ("Cuantos medicos estan activos para servicio?", "#3"),
    ("Cuantos medicos no estan activos para servicio?", "#4"),
    ("Dame la lista de medicos activos para servicio.", "#5"),
    ("Dame la lista de medicos inactivos para servicio.", "#6"),
    ("Exporta en PDF los medicos activos para servicio.", "#7"),
    ("Exporta en Excel los medicos activos para servicio.", "#8"),
    ("Cuantos medicos masculinos tengo?", "#9"),
    ("Cuantos medicos femeninos tengo?", "#10"),
    ("Dame la lista de medicos masculinos.", "#11"),
    ("Dame la lista de medicos femeninos.", "#12"),
    ("Exporta en PDF los medicos femeninos.", "#13"),
    ("Exporta en Excel los medicos masculinos.", "#14"),
    ("Cuantos hombres tengo disponibles?", "#15"),
    ("Cuantas mujeres tengo disponibles?", "#16"),
    ("Y masculinos?", "#17"),
    ("Y femeninos?", "#18"),
    ("Dame un resumen de medicos por sexo.", "#19"),
    ("Exporta el resumen de medicos por sexo en PDF.", "#20"),
    ("Busca al medico Acostta.", "#221"),
    ("Dame los medicos de Licencias Medicass.", "#222"),
    ("Cuantos medicos hay en Ensenansa?", "#223"),
    ("Cuantos sargento mayores femeninos tengo?", "#224"),
]

BLOCK_2 = [
    ("Cuantos pasantes tengo?", "#21"),
    ("Cuantos cabos tengo?", "#22"),
    ("Cuantos sargentos tengo?", "#23"),
    ("Cuantos sargentos mayores tengo?", "#24"),
    ("Cuantos contrata tengo?", "#25"),
    ("Dame la lista de pasantes.", "#26"),
    ("Dame la lista de cabos.", "#27"),
    ("Dame la lista de sargentos.", "#28"),
    ("Dame la lista de sargentos mayores.", "#29"),
    ("Dame la lista de contrata.", "#30"),
    ("Exporta en PDF los pasantes.", "#31"),
    ("Exporta en PDF los cabos.", "#32"),
    ("Exporta en PDF los sargentos.", "#33"),
    ("Exporta en Excel los sargentos mayores.", "#34"),
    ("Exporta en Excel los contrata.", "#35"),
    ("Cuantos medicos son cabo?", "#36"),
    ("Cuantos medicos son sargento?", "#37"),
    ("Cuantos medicos son pasante?", "#38"),
    ("Cuantos medicos son sargento mayor?", "#39"),
    ("Dame un resumen por rango.", "#40"),
]

BLOCK_3 = [
    ("Cuantos pasantes femeninos tengo?", "#41"),
    ("Cuantos pasantes masculinos tengo?", "#42"),
    ("Cuantos cabos femeninos tengo?", "#43"),
    ("Cuantos cabos masculinos tengo?", "#44"),
    ("Cuantos sargentos femeninos tengo?", "#45"),
    ("Cuantos sargentos masculinos tengo?", "#46"),
    ("Cuantos sargentos mayores femeninos tengo?", "#47"),
    ("Cuantos sargentos mayores masculinos tengo?", "#48"),
    ("Cuantos contrata femeninos tengo?", "#49"),
    ("Cuantos contrata masculinos tengo?", "#50"),
    ("Dame la lista de pasantes femeninos.", "#51"),
    ("Dame la lista de pasantes masculinos.", "#52"),
    ("Dame la lista de cabos femeninos.", "#53"),
    ("Dame la lista de cabos masculinos.", "#54"),
    ("Dame la lista de sargentos femeninos.", "#55"),
    ("Dame la lista de sargentos masculinos.", "#56"),
    ("Exporta en PDF los pasantes femeninos.", "#57"),
    ("Exporta en PDF los cabos masculinos.", "#58"),
    ("Exporta en Excel los sargentos femeninos.", "#59"),
    ("Exporta en PDF los sargentos mayores masculinos.", "#60"),
    ("Cuantos masculino y femenino tienen rango pasante?", "#61"),
    ("Cuantos hombres y mujeres son cabo?", "#62"),
    ("Dame el desglose por sexo de los sargentos.", "#63"),
    ("Exporta el desglose por sexo de los cabos.", "#64"),
    ("Son 24 o 23 sargentos femeninos?", "#65"),
    ("De esos sargentos femeninos, dame el listado.", "#66"),
    ("De esos, exportalo en PDF.", "#67"),
    ("Ahora dame solo los masculinos.", "#68"),
    ("Exporta esos masculinos en Excel.", "#69"),
    ("Cuantos cabos massulino tengo?", "#70"),
]

BLOCK_4 = [
    ("Cuantos medicos hay por departamento?", "#71"),
    ("Cuantos medicos hay en Licencias Medicas?", "#72"),
    ("Cuantos medicos hay en Ensenanza?", "#73"),
    ("Cuantos medicos hay en Evaluaciones Medicas?", "#74"),
    ("Cuantos medicos hay en Subdireccion?", "#75"),
    ("Cuantos medicos hay en Recurso Humanos?", "#76"),
    ("Dame la lista de medicos de Licencias Medicas.", "#77"),
    ("Dame la lista de medicos de Ensenanza.", "#78"),
    ("Dame la lista de medicos de Evaluaciones Medicas.", "#79"),
    ("Dame la lista de medicos de Subdireccion.", "#80"),
    ("Dame la lista de medicos de Recurso Humanos.", "#81"),
    ("Exporta en PDF los medicos de Licencias Medicas.", "#82"),
    ("Exporta en Excel los medicos de Ensenanza.", "#83"),
    ("Cuantos cabos hay en Recurso Humanos?", "#84"),
    ("Cuantos sargentos femeninos hay en Evaluaciones Medicas?", "#85"),
    ("Dame los pasantes masculinos de Subdireccion.", "#86"),
    ("Exporta los sargentos de Ensenanza.", "#87"),
    ("Dame un resumen por departamento y sexo.", "#88"),
    ("Dame un resumen por departamento y rango.", "#89"),
    ("Exporta el resumen por departamento en PDF.", "#90"),
    ("Busca el medico Acosta.", "#91"),
    ("Busca medicos con apellido Ramos.", "#92"),
    ("Dame informacion de Acosta Ramos.", "#93"),
    ("Dame detalle del medico Miguelina.", "#94"),
    ("Cual es el rango de Acosta Ramos?", "#95"),
    ("Cual es el sexo de Acosta Ramos?", "#96"),
    ("En que departamento esta Acosta Ramos?", "#97"),
    ("Ese medico esta activo para servicio?", "#98"),
    ("Ese medico participa en misiones?", "#99"),
    ("Exporta el perfil de ese medico en PDF.", "#100"),
    ("Busca al medico Fulanito Perez.", "#225"),
    ("Hay calendario de diciembre 2030?", "#226"),
    ("Cuantos cabos femeninos hay en Subdireccion?", "#227"),
    ("Dame las misiones de enero 2030.", "#228"),
]

BLOCK_5 = [
    ("Dame los dias de servicio de ese medico.", "#101"),
    ("Dame las areas asignadas de ese medico.", "#102"),
    ("Dame el historial de servicios de ese medico.", "#103"),
    ("Dame el historial de misiones de ese medico.", "#104"),
    ("Ese medico tiene restricciones?", "#105"),
    ("Ese medico esta desactivado?", "#106"),
    ("Por que esta desactivado ese medico?", "#107"),
    ("Dame todos los medicos que se llamen igual.", "#108"),
    ("Hay medicos duplicados por nombre?", "#109"),
    ("Exporta la lista de posibles duplicados.", "#110"),
]

BLOCK_6 = [
    ("Hay calendario de junio 2026?", "#111"),
    ("Hay calendario de julio 2026?", "#112"),
    ("Hay calendario de agosto 2026?", "#113"),
    ("Cual es el estado del calendario de junio?", "#114"),
    ("Cual es el estado del calendario de julio?", "#115"),
    ("Cual es el estado del calendario de agosto?", "#116"),
    ("El calendario de julio esta aprobado?", "#117"),
    ("El calendario de agosto esta aprobado?", "#118"),
    ("Hay borrador para agosto?", "#119"),
    ("Cuantos calendarios hay para julio?", "#120"),
    ("Cuantos calendarios hay para agosto?", "#121"),
    ("Dame los calendarios pendientes de aprobacion.", "#122"),
    ("Dame los calendarios aprobados.", "#123"),
    ("Dame el ultimo calendario generado.", "#124"),
    ("Dame el calendario oficial de julio.", "#125"),
    ("Exporta el calendario aprobado de julio en PDF.", "#126"),
    ("Exporta el calendario aprobado de julio en Excel.", "#127"),
    ("Exporta el borrador de agosto en PDF.", "#128"),
    ("Dame un resumen operativo de julio.", "#129"),
    ("Dame un resumen operativo de agosto.", "#130"),
    ("Cuantos medicos estan incluidos en el calendario de julio?", "#131"),
    ("Cuantos medicos estan incluidos en el calendario de agosto?", "#132"),
    ("Cuantos medicos estan de servicio en julio?", "#133"),
    ("Cuantos medicos estan de servicio en agosto?", "#134"),
    ("Dame la lista de medicos de servicio en julio.", "#135"),
    ("Dame la lista de medicos de servicio en agosto.", "#136"),
    ("Cuales son los medicos de servicio la primera semana de julio?", "#137"),
    ("Cuales son los medicos de servicio la primera semana de agosto?", "#138"),
    ("Cuales son los medicos de servicio la segunda semana de julio?", "#139"),
    ("Cuales son los medicos de servicio la tercera semana de julio?", "#140"),
    ("Cuales son los medicos de servicio la cuarta semana de julio?", "#141"),
    ("Y el de agosto?", "#142"),
    ("Y el de julio?", "#143"),
    ("Cuales medicos trabajan el primer lunes de agosto?", "#144"),
    ("Cuales medicos trabajan el primer lunes de julio?", "#145"),
    ("Cuales medicos trabajan el 4 de julio?", "#146"),
    ("Cuales medicos trabajan el 15 de agosto?", "#147"),
    ("Exporta los servicios de la primera semana de julio.", "#148"),
    ("Exporta los servicios de julio en PDF.", "#149"),
    ("Exporta los servicios de agosto en Excel.", "#150"),
    ("Cuantos servicios hay en julio?", "#151"),
    ("Cuantos servicios hay en agosto?", "#152"),
    ("Cuantos servicios tiene cada medico en julio?", "#153"),
    ("Cuantos servicios tiene cada medico en agosto?", "#154"),
    ("Quienes no fueron asignados en julio?", "#155"),
    ("Quienes no fueron asignados en agosto?", "#156"),
    ("Dame los huecos sin cubrir de julio.", "#157"),
    ("Dame los huecos sin cubrir de agosto.", "#158"),
    ("Hay cobertura completa en julio?", "#159"),
    ("Hay cobertura completa en agosto?", "#160"),
]

BLOCK_7 = [
    ("Cuantos servicios hay por area en julio?", "#161"),
    ("Cuantos servicios hay por area en agosto?", "#162"),
    ("Quienes estan en Emergencia en julio?", "#163"),
    ("Quienes estan en Pista en julio?", "#164"),
    ("Quienes estan en UCI en julio?", "#165"),
    ("Quienes estan en Consulta Externa en julio?", "#166"),
    ("Exporta los servicios por area de julio.", "#167"),
    ("Cual medico tiene mas servicios en julio?", "#168"),
    ("Cual medico tiene menos servicios en julio?", "#169"),
    ("Dame la carga de trabajo de julio.", "#170"),
    ("Dame la carga de trabajo de agosto.", "#171"),
    ("Exporta la carga de trabajo de julio en PDF.", "#172"),
    ("Exporta la carga de trabajo de agosto en Excel.", "#173"),
    ("Quienes tienen 3 servicios en julio?", "#174"),
    ("Quienes tienen menos de 3 servicios en julio?", "#175"),
    ("Quienes exceden la meta mensual?", "#176"),
    ("Quienes no cumplen la meta mensual?", "#177"),
    ("Dame la distribucion por area y rango.", "#178"),
    ("Dame la distribucion por area y sexo.", "#179"),
    ("Dame los medicos con servicio en las tres areas.", "#180"),
    ("Dame los medicos.", "#229"),
    ("Cuantos hay?", "#230"),
    ("Como esta el sistema?", "#231"),
    ("Que me recomiendas?", "#232"),
]

BLOCK_8 = [
    ("Hay ranking de misiones para julio?", "#181"),
    ("Hay ranking de misiones para agosto?", "#182"),
    ("Dame el ranking de misiones de julio.", "#183"),
    ("Dame el ranking de misiones de agosto.", "#184"),
    ("Cuales son los 3 primeros del ranking de misiones de agosto?", "#185"),
    ("Cuales son los 5 primeros del ranking de misiones de julio?", "#186"),
    ("Dame todos los candidatos de misiones de agosto.", "#187"),
    ("Exporta el ranking de misiones de agosto en PDF.", "#188"),
    ("Exporta el ranking de misiones de julio en Excel.", "#189"),
    ("Quien es el candidato numero 1 para misiones en agosto?", "#190"),
    ("Quienes son elegibles para mision el 15 de agosto?", "#191"),
    ("Quienes no son elegibles para mision el 15 de agosto?", "#192"),
    ("Dame los candidatos disponibles para mision el 20 de julio.", "#193"),
    ("Dame candidatos ordenados de menor carga a mayor carga.", "#194"),
    ("Si el primero no puede, quien sigue?", "#195"),
    ("Hay misiones creadas en julio?", "#196"),
    ("Hay misiones creadas en agosto?", "#197"),
    ("Dame las misiones de julio.", "#198"),
    ("Dame las misiones de agosto.", "#199"),
    ("Exporta las misiones de agosto.", "#200"),
    ("Quienes participan en la mision del 15 de agosto?", "#201"),
    ("Esa mision esta confirmada?", "#202"),
    ("Quienes no han confirmado la mision?", "#203"),
    ("Quienes confirmaron recibido de la mision?", "#204"),
    ("Hay advertencias en misiones?", "#205"),
    ("Hay medicos desactivados dentro de misiones?", "#206"),
    ("Que medicos debo reemplazar en misiones?", "#207"),
    ("Dame las misiones pendientes de reemplazo.", "#208"),
    ("Exporta las misiones con advertencias.", "#209"),
    ("Dame resumen de misiones por mes.", "#210"),
]

BLOCK_9 = [
    ("Hay notificaciones pendientes?", "#211"),
    ("Hay alertas importantes?", "#212"),
    ("Que medicos no han confirmado servicio?", "#213"),
    ("Que medicos confirmaron servicio?", "#214"),
    ("Que medicos no han confirmado mision?", "#215"),
    ("Exporta los pendientes de confirmacion.", "#216"),
    ("Dame auditoria de cambios del calendario de julio.", "#217"),
    ("Quien aprobo el calendario de julio?", "#218"),
    ("Que cambios se hicieron despues de aprobar el calendario?", "#219"),
    ("Dame un reporte general operativo del sistema para julio.", "#220"),
    ("Que hora es?", "#233"),
    ("Quien es el presidente?", "#234"),
    ("Cuentame un chiste.", "#235"),
    ("Que puedes hacer?", "#236"),
    ("/start", "#237"),
    ("Ayuda", "#238"),
    ("Cuantos cabos hay? -> No, de sargentos. -> Y de pasantes?", "#239"),
    ("Dame los pasantes femeninos. -> No, masculinos. -> Y tambien los de Ensenanza.", "#240"),
    ("Cuantos medicos hay en julio? -> No, en agosto. -> Los que estan en Emergencia.", "#241"),
    ("Busca al medico Ramos. -> No, al que se llama Miguelina Ramos. -> Dame su rango.", "#242"),
    ("Cuantos sargentos hay? -> De esos, cuantos son femeninos? -> Exportalos en PDF.", "#243"),
]

BLOCKS = {
    1: BLOCK_1, 2: BLOCK_2, 3: BLOCK_3, 4: BLOCK_4,
    5: BLOCK_5, 6: BLOCK_6, 7: BLOCK_7, 8: BLOCK_8, 9: BLOCK_9,
}

# ---------------------------------------------------------------------------
# Resultados
# ---------------------------------------------------------------------------

RESULTS_FILE = Path(__file__).parents[3] / "docs" / "test-results.md"


def run_block(block_num: int) -> None:
    """Ejecuta un bloque de pruebas."""
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    from backend.app.application.telegram.agent import ConversationalAgent
    from backend.app.application.telegram.calendar_query_service import CalendarQueryService
    from backend.app.application.telegram.doctor_query_service import DoctorQueryService
    from backend.app.application.telegram.entity_resolver import EntityResolver
    from backend.app.application.telegram.intent_router import IntentRouter
    from backend.app.application.telegram.llm import DeepSeekProvider
    from backend.app.application.telegram.memory import MemoryManager, SessionStore
    from backend.app.application.telegram.query_executor import QueryExecutor
    from backend.app.core.config import settings
    from backend.app.infrastructure.db.session import engine
    from backend.app.infrastructure.repositories.telegram import TelegramRepository

    Session = sessionmaker(bind=engine)
    session = Session()

    try:
        llm = DeepSeekProvider()
        router = IntentRouter()
        router.set_session(session)

        query_executor = QueryExecutor(session, llm)
        memory = MemoryManager(TelegramRepository(session))

        agent = ConversationalAgent(
            llm=llm,
            router=router,
            query_executor=query_executor,
            memory=memory,
            session_store=SessionStore(
                ttl_seconds=1800,
                telegram_repo=TelegramRepository(session),
            ),
            entity_resolver=EntityResolver(session=session),
            doctor_query_service=DoctorQueryService(session=session),
            calendar_query_service=CalendarQueryService(session=session),
            session=session,
        )

        cases = BLOCKS[block_num]
        results = []

        for text, case_id in cases:
            print(f"\n{'='*60}")
            print(f"  {case_id}: {text}")
            print(f"{'='*60}")

            try:
                start = time.perf_counter()
                result = agent.process(text=text)
                elapsed = round((time.perf_counter() - start) * 1000)

                response = result.response_text or "(sin respuesta)"
                action = result.agent_action or "unknown"

                # Heurística rápida para determinar si pasó
                # Si no es "No pude encontrar" y tiene contenido, consideramos pasó
                passed = (
                    "no pude encontrar" not in response.lower()
                    and "ocurrió un error" not in response.lower()
                    and len(response) > 5
                )

                status = "✅" if passed else "❌"
                print(f"  Acción: {action}")
                print(f"  Respuesta: {response[:200]}")
                print(f"  Estado: {status} ({elapsed}ms)")

                results.append((case_id, text, status, response, action, elapsed))

            except Exception as e:
                print(f"  ERROR: {e}")
                results.append((case_id, text, "❌", str(e), "error", 0))

        # Mostrar resumen
        passed_count = sum(1 for r in results if r[2] == "✅")
        total = len(results)
        print(f"\n\n{'='*60}")
        print(f"  BLOQUE {block_num} COMPLETADO: {passed_count}/{total} pasaron")
        print(f"{'='*60}")

        # Guardar resultados
        _save_results(block_num, results)

    finally:
        session.close()


def _save_results(block_num: int, results: list) -> None:
    """Guarda resultados en el archivo markdown."""
    lines = []
    lines.append(f"## Bloque {block_num}\n")
    lines.append("| # | Consulta | ¿Pasó? | Respuesta | Acción | Tiempo |")
    lines.append("|---|----------|--------|-----------|--------|--------|")
    for case_id, text, status, response, action, elapsed in results:
        resp_short = response.replace("\n", " ")[:120]
        lines.append(f"| {case_id} | {text} | {status} | {resp_short} | {action} | {elapsed}ms |")
    lines.append("")

    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if RESULTS_FILE.exists() else "w"
    with open(RESULTS_FILE, mode, encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print(f"\nResultados guardados en {RESULTS_FILE}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python -m tests.telegram.run_test_block <bloque>")
        print("Bloques disponibles: 1")
        sys.exit(1)

    block_num = int(sys.argv[1])
    run_block(block_num)
