"""SDK-wide exception types."""

from __future__ import annotations


class AtechError(Exception):
    """Base class for SDK errors."""


class CatalogError(AtechError):
    """Raised when a catalog lookup fails."""


class PlacementError(AtechError):
    """Raised when a module placement is invalid."""


class BuildError(AtechError):
    """Raised when PlatformIO build fails."""


class UploadError(AtechError):
    """Raised when PlatformIO upload fails."""
