"""Notification adapters.

Keep this package import-light: avoid importing network-backed implementations
at module import time (e.g., aiohttp-based adapters). Import concrete services
directly from their modules when needed.
"""

__all__ = []
