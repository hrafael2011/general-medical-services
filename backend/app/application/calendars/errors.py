class CalendarServiceError(Exception):
    def __init__(self, code: str, message: str, details: list | None = None) -> None:
        self.code = code
        self.message = message
        # Detalle estructurado para que la pantalla liste los huecos en vez de
        # mostrar un párrafo largo dentro de un toast.
        self.details = details
        super().__init__(message)
