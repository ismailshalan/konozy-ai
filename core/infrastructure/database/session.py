"""Database session configuration with sync DATABASE_URL."""

from core.infrastructure.database.config import settings

# Export sync format DATABASE_URL (postgresql://) for conversion to async
DATABASE_URL = (
    f"postgresql://"
    f"{settings.postgres_user}:{settings.postgres_password}"
    f"@{settings.postgres_host}:{settings.postgres_port}/{settings.postgres_db}"
)
