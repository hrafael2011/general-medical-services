"""
Pure-Python identity resolver for import pipeline.
No DB imports — operates on already-loaded doctor records.
"""

from backend.app.application.import_pipeline.normalizer import normalize_name


def resolve_identity(
    parsed_name: str,
    known_doctors: list,
) -> tuple[str | None, str]:
    """
    Match parsed_name against known doctor records by normalized name.
    Returns (doctor_id | None, match_status).

    match_status values:
      "exact_match"    — normalized names are identical
      "probable_match" — one is a substring of the other
      "possible_match" — first word (surname) matches
      "new_candidate"  — no match
    Returns first/best match only.
    """
    if not parsed_name or not known_doctors:
        return None, "new_candidate"

    normalized_parsed = normalize_name(parsed_name)
    if not normalized_parsed:
        return None, "new_candidate"

    parsed_first_word = normalized_parsed.split()[0] if normalized_parsed.split() else ""

    # Collect candidates per tier so we return first/best match only
    exact: tuple[str | None, str] | None = None
    probable: tuple[str | None, str] | None = None
    possible: tuple[str | None, str] | None = None

    for doctor in known_doctors:
        raw_doctor_name = getattr(doctor, "name", None) or ""
        normalized_doctor = normalize_name(raw_doctor_name)
        if not normalized_doctor:
            continue

        if exact is None and normalized_parsed == normalized_doctor:
            exact = (str(doctor.id), "exact_match")
            # Can't do better — stop scanning
            break

        if probable is None:
            if normalized_parsed in normalized_doctor or normalized_doctor in normalized_parsed:
                probable = (str(doctor.id), "probable_match")

        if possible is None and parsed_first_word:
            doctor_first_word = normalized_doctor.split()[0] if normalized_doctor.split() else ""
            if parsed_first_word == doctor_first_word:
                possible = (str(doctor.id), "possible_match")

    if exact is not None:
        return exact
    if probable is not None:
        return probable
    if possible is not None:
        return possible
    return None, "new_candidate"
