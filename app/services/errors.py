class DuplicateConflictError(Exception):
    """Raised when two records share a fingerprint but conflict on core identity fields."""

