"""Exception classes for bdapt."""


class BundleError(Exception):
    """Raised when bundle operations fail."""
    pass


class MetapackageError(BundleError):
    """Raised when metapackage operations fail."""
    pass


class AptError(BundleError):
    """Raised when APT operations fail."""
    pass


class StorageError(Exception):
    """Raised when storage operations fail."""
    pass
