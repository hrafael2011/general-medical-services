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


class DeletedEmailConflictError(AccountError):
    """Raised when email belongs to a soft-deleted user."""


class UserNotFoundError(AccountError):
    """Raised when user does not exist."""


class InvalidPasswordChangeError(AccountError):
    """Raised when password change is invalid.

    Carries the specific problem (when known) so the route can tell the user what to
    fix, instead of blaming the current password for every possible cause.
    """

    def __init__(self, problem: object | None = None) -> None:
        super().__init__(problem)
        self.problem = problem


class RecoveryRateLimitedError(AccountError):
    """Raised when too many password recovery requests are made."""
