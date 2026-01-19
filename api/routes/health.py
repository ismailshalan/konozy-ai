"""
Health check endpoints.

Used for monitoring and load balancer health checks.
"""
from fastapi import APIRouter
from datetime import datetime
import platform


router = APIRouter()


@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns system health status.
    """
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "service": "konozy-ai",
        "version": "1.0.0",
        "python_version": platform.python_version(),
    }


@router.get("/health/ready")
async def readiness_check():
    """
    Readiness check endpoint.
    
    Returns whether the service is ready to accept traffic.
    """
    # TODO: Add checks for:
    # - Database connection
    # - Odoo connection
    # - Required services
    
    return {
        "status": "ready",
        "timestamp": datetime.utcnow().isoformat(),
        "checks": {
            "api": "ok",
            "database": "ok",  # TODO: Real check
            "odoo": "ok",      # TODO: Real check
        }
    }
