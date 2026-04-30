from .llm import LLMProvider

SUPPORTED_INTENTS = [
    "count_medicos_activos",
    "list_medicos_activos",
    "estado_calendario_mes",
    "get_mission_candidate_ranking",
    "recommend_mission_candidates",
    "confirm_mission_assignment",
    "historial_medico",
    "pendientes_disponibilidad_mes",
    "out_of_domain",
]

SYSTEM_PROMPT = """You are an intent classifier for a military medical scheduling system.
Classify the user message into exactly one of these intents: {intents}

Also extract relevant entities. Respond ONLY with valid JSON in this format:
{{"intent": "<intent_id>", "entities": {{"month": null, "year": null, "doctor_name": null, "mission_date": null, "participant_count": null, "doctor_ids": null}}, "confidence": 0.0-1.0}}

Entity extraction rules:
- month: integer 1-12 if mentioned (e.g. "mayo" -> 5, "junio" -> 6)
- year: integer if mentioned, otherwise null
- doctor_name: doctor name string if mentioned, otherwise null
- mission_date: ISO date string (YYYY-MM-DD) if mentioned, otherwise null
- participant_count: integer if mentioned for missions, otherwise null
- doctor_ids: list of doctor ID strings if explicitly confirmed, otherwise null

If confidence < 0.6, use "out_of_domain".
"""


class IntentClassifier:
    def __init__(self, provider: LLMProvider) -> None:
        self.provider = provider

    def classify(self, user_message: str) -> dict:
        """Returns {"intent": str, "entities": dict, "confidence": float}"""
        import json

        system = SYSTEM_PROMPT.format(intents=", ".join(SUPPORTED_INTENTS))
        raw = self.provider.complete(system=system, user=user_message)
        try:
            result = json.loads(raw)
            if result.get("intent") not in SUPPORTED_INTENTS:
                result["intent"] = "out_of_domain"
            return result
        except (json.JSONDecodeError, KeyError):
            return {"intent": "out_of_domain", "entities": {}, "confidence": 0.0}
