def _with_whatsapp_confirmation(message: str) -> str:
    return f"{message}\n\nResponda 1 para confirmar su turno."


def render_initial_assignment(
    service_date: str, service_area: str, service_start: str | None
) -> str:
    time_part = f" a las {service_start}" if service_start else ""
    return (
        f"Estimado/a doctor/a, le informamos que tiene asignado un turno de servicio "
        f"en {service_area} el día {service_date}{time_part}. "
        f"Ante cualquier consulta, comuníquese con el encargado."
    )


def render_service_assignment_added(
    service_date: str,
    service_area: str,
    service_start: str | None,
) -> str:
    time_part = f" a las {service_start}" if service_start else ""
    return (
        "Actualización de calendario: usted fue agregado/a a un turno de servicio "
        f"en {service_area} el día {service_date}{time_part}. "
        "Por favor confirme la recepción y su disponibilidad."
    )


def render_service_assignment_removed(
    service_date: str,
    service_area: str,
    service_start: str | None,
) -> str:
    time_part = f" a las {service_start}" if service_start else ""
    return (
        "Actualización de calendario: usted fue removido/a del turno de servicio "
        f"en {service_area} el día {service_date}{time_part}. "
        "Ya no debe presentarse para ese servicio."
    )


def render_service_assignment_updated(
    service_date: str,
    service_area: str,
    service_start: str | None,
) -> str:
    time_part = f" a las {service_start}" if service_start else ""
    return (
        "Actualización de calendario: su turno de servicio fue modificado. "
        f"Servicio vigente: {service_area}, {service_date}{time_part}. "
        "Por favor revise la información actualizada."
    )


def render_twelve_hour_reminder(
    service_date: str, service_area: str, service_start: str | None
) -> str:
    time_part = f" a las {service_start}" if service_start else ""
    return (
        f"Recordatorio: mañana tiene turno de servicio "
        f"en {service_area} el día {service_date}{time_part}.\n\n"
        "Responda 1 para confirmar su asistencia."
    )


def render_mission_participant(
    mission_date: str,
    location: str | None,
    description: str | None,
    mission_start: str | None,
) -> str:
    parts = [
        "Estimado/a doctor/a, ha sido seleccionado/a para participar en una "
        f"misión el {mission_date}."
    ]
    if location:
        parts.append(f"Lugar: {location}.")
    if description:
        parts.append(f"Descripción: {description}.")
    if mission_start:
        parts.append(f"Hora: {mission_start}.")
    parts.append("Por favor confirme con el encargado.")
    return " ".join(parts)


def render_mission_participant_added(
    mission_date: str,
    location: str | None,
    description: str | None,
    mission_start: str | None,
) -> str:
    parts = [
        f"Actualización de misión: usted fue agregado/a a la misión del {mission_date}."
    ]
    if location:
        parts.append(f"Lugar: {location}.")
    if description:
        parts.append(f"Descripción: {description}.")
    if mission_start:
        parts.append(f"Hora: {mission_start}.")
    parts.append("Por favor confirme la recepción y su disponibilidad.")
    return " ".join(parts)


def render_mission_participant_removed(
    mission_date: str,
    location: str | None,
    description: str | None,
) -> str:
    parts = [
        f"Actualización de misión: usted fue removido/a de la misión del {mission_date}."
    ]
    if location:
        parts.append(f"Lugar: {location}.")
    if description:
        parts.append(f"Descripción: {description}.")
    parts.append("Ya no debe presentarse para esa misión.")
    return " ".join(parts)


def render_mission_details_updated(
    mission_date: str,
    location: str | None,
    description: str | None,
    mission_start: str | None,
) -> str:
    parts = [f"Actualización de misión: los detalles de la misión del {mission_date} cambiaron."]
    if location:
        parts.append(f"Lugar: {location}.")
    if description:
        parts.append(f"Descripción: {description}.")
    if mission_start:
        parts.append(f"Hora: {mission_start}.")
    parts.append("Por favor revise la información vigente.")
    return " ".join(parts)


def render_mission_summary_encargado(
    mission_date: str,
    location: str | None,
    description: str | None,
    participant_names: list[str],
) -> str:
    parts = [f"Resumen de misión — {mission_date}."]
    if location:
        parts.append(f"Lugar: {location}.")
    if description:
        parts.append(f"Descripción: {description}.")
    parts.append(
        "Participantes confirmados: "
        f"{', '.join(participant_names) if participant_names else 'ninguno'}."
    )
    parts.append("Se recomienda confirmar detalles finales con los participantes.")
    return " ".join(parts)


def render_missing_availability_reminder(
    doctor_names: list[str], generation_date: str
) -> str:
    names = ", ".join(doctor_names)
    return (
        f"Recordatorio: la generación del calendario está programada para el {generation_date}. "
        f"Los siguientes médicos aún no han registrado su disponibilidad: {names}. "
        f"Por favor, solicíteles que la registren antes de esa fecha."
    )


def render_escalamiento_encargado(doctor_name: str, service_info: str = "") -> str:
    base = f"El Dr. {doctor_name} no ha confirmado sus turnos asignados."
    if service_info:
        base += f" Servicio: {service_info}."
    return base + " Por favor, contacte al médico para verificar su disponibilidad."
