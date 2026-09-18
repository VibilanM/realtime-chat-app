"""Custom application exceptions."""


class AppError(Exception):
    """Base exception for all application errors."""

    def __init__(self, detail: str = "An error occurred"):
        self.detail = detail
        super().__init__(self.detail)


class NotFoundError(AppError):
    """Raised when a requested resource does not exist."""

    def __init__(self, resource: str = "Resource", identifier: str = ""):
        detail = f"{resource} not found"
        if identifier:
            detail = f"{resource} '{identifier}' not found"
        super().__init__(detail)


class ForbiddenError(AppError):
    """Raised when a user lacks permission for the requested action."""

    def __init__(self, detail: str = "You do not have permission to perform this action"):
        super().__init__(detail)


class ConflictError(AppError):
    """Raised when the request conflicts with existing state."""

    def __init__(self, detail: str = "Conflict with existing resource"):
        super().__init__(detail)


class ValidationError(AppError):
    """Raised when input validation fails at the service layer."""

    def __init__(self, detail: str = "Validation error"):
        super().__init__(detail)
