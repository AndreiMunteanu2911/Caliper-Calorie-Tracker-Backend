from dataclasses import dataclass


@dataclass(slots=True)
class ApplicationError(Exception):
    code: str
    message: str
    status_code: int


class ExternalServiceError(ApplicationError):
    def __init__(self, service: str, message: str) -> None:
        super().__init__(
            code="external_service_unavailable",
            message=f"{service}: {message}",
            status_code=503,
        )


class ResourceNotFoundError(ApplicationError):
    def __init__(self, resource: str) -> None:
        super().__init__(
            code="resource_not_found",
            message=f"{resource} was not found.",
            status_code=404,
        )


class InputValidationError(ApplicationError):
    def __init__(self, message: str) -> None:
        super().__init__(
            code="validation_error",
            message=message,
            status_code=422,
        )
