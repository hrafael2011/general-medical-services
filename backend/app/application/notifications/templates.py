def render_initial_assignment(
    service_date: str, service_area: str, service_start: str | None
) -> str:
    time_part = f" a las {service_start}" if service_start else ""
    return (
        f"Estimado/a doctor/a, le informamos que tiene asignado un turno de servicio "
        f"en {service_area} el día {service_date}{time_part}. "
        f"Ante cualquier consulta, comuníquese con el encargado."
    )


def render_twelve_hour_reminder(
    service_date: str, service_area: str, service_start: str | None
) -> str:
    time_part = f" a las {service_start}" if service_start else ""
    return (
        f"Recordatorio: en aproximadamente 12 horas tiene turno de servicio "
        f"en {service_area} el día {service_date}{time_part}. "
        f"Por favor confirme su disponibilidad."
    )


def render_mission_participant(
    mission_date: str,
    location: str | None,
    description: str | None,
    mission_start: str | None,
) -> str:
    parts = [
        f"Estimado/a doctor/a, ha sido seleccionado/a para participar en una misión el {mission_date}."
    ]
    if location:
        parts.append(f"Lugar: {location}.")
    if description:
        parts.append(f"Descripción: {description}.")
    if mission_start:
        parts.append(f"Hora: {mission_start}.")
    parts.append("Por favor confirme con el encargado.")
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
        f"Participantes confirmados: {', '.join(participant_names) if participant_names else 'ninguno'}."
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
