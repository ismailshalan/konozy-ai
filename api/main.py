"""
Konozy AI - Main FastAPI Application.

This is the REST API layer that provides HTTP endpoints
for Amazon order synchronization using Clean Architecture.
"""
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import logging
import time

from api.routes import amazon, orders, health


# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


# =============================================================================
# CREATE FASTAPI APP
# =============================================================================

app = FastAPI(
    title="Konozy AI - Order Management API",
    description="""
    Amazon Order Sync API with Clean Architecture.
    
    Features:
    - Amazon order synchronization to Odoo
    - Multi-SKU support
    - Financial validation
    - Batch processing
    - Order management
    
    Built with:
    - Domain-Driven Design
    - Clean Architecture
    - Hexagonal Architecture
    - CQRS patterns
    """,
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)


# =============================================================================
# CORS MIDDLEWARE (FIXED)
# =============================================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure based on your needs
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# =============================================================================
# REQUEST LOGGING MIDDLEWARE
# =============================================================================

@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing."""
    start_time = time.time()
    
    # Log request
    logger.info(f"→ {request.method} {request.url.path}")
    
    # Process request
    response = await call_next(request)
    
    # Calculate duration
    duration = time.time() - start_time
    
    # Log response
    logger.info(
        f"← {request.method} {request.url.path} "
        f"[{response.status_code}] ({duration:.3f}s)"
    )
    
    return response


# =============================================================================
# GLOBAL EXCEPTION HANDLER
# =============================================================================

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Handle all uncaught exceptions."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "detail": str(exc),
            "path": request.url.path
        }
    )


# =============================================================================
# STARTUP/SHUTDOWN EVENTS
# =============================================================================

@app.on_event("startup")
async def startup_event():
    """Run on application startup."""
    logger.info("🚀 Konozy AI API starting up...")
    logger.info("📚 Swagger UI available at: /docs")
    logger.info("📖 ReDoc available at: /redoc")


@app.on_event("shutdown")
async def shutdown_event():
    """Run on application shutdown."""
    logger.info("👋 Konozy AI API shutting down...")


# =============================================================================
# INCLUDE ROUTERS
# =============================================================================

app.include_router(
    health.router,
    tags=["Health"]
)

app.include_router(
    amazon.router,
    prefix="/api/v1/amazon",
    tags=["Amazon"]
)

app.include_router(
    orders.router,
    prefix="/api/v1/orders",
    tags=["Orders"]
)


# =============================================================================
# ROOT ENDPOINT
# =============================================================================

@app.get("/", tags=["Root"])
async def root():
    """API root endpoint."""
    return {
        "message": "Konozy AI - Order Management API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health"
    }
