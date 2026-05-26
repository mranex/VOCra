"""Prepare-stage error contracts."""

from __future__ import annotations


class PrepareCancelledError(RuntimeError):
    """Raised when a Prepare run is cancelled cooperatively."""
