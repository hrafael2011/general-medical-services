class AccountError(Exception):
    """Base account error."""


class InvalidCredentialsError(AccountError):
    """Raised when login credentials are invalid."""


class AccountLockedError(AccountError):
    """Raised when account is temporarily locked."""


class InactiveUserError(AccountError):
    """Raised when account is inactive."""


class MustChangePasswordError(AccountError):
    """Raised when a user must change password before continuing."""


class PermissionDeniedError(AccountError):
    """Raised when a user lacks permission."""


class DuplicateEmailError(AccountError):
    """Raised when email already exists."""


class UserNotFoundError(AccountError):
    """Raised when user does not exist."""


class InvalidPasswordChangeError(AccountError):
    """Raised when password change is invalid."""

