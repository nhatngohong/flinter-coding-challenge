"""Application errors suitable for concise CLI reporting."""


class ChallengeError(Exception):
    """Base class for expected application errors."""


class ConfigurationError(ChallengeError):
    """Raised when configuration or paths are invalid."""


class InputDataError(ChallengeError):
    """Raised when the input CSV cannot be processed."""


class OutputError(ChallengeError):
    """Raised when result files cannot be written."""
