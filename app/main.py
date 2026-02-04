"""
FastAPI application entry point.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.api.routes import router
from app.config import settings
from app.database.models import Base

# ===========================================
# Logging Configuration
# ===========================================

logging.basicConfig(
    level=logging.DEBUG if settings.debug else logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


# ===========================================
# Database Setup
# ===========================================

# Convert sync database URL to async
database_url = settings.database_url
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+asyncpg://", 1)

engine = create_async_engine(
    database_url,
    echo=settings.debug,
    pool_size=5,
    max_overflow=10,
)

async_session_maker = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dependency for getting async database session."""
    async with async_session_maker() as session:
        try:
            yield session
        finally:
            await session.close()


# ===========================================
# Application Lifecycle
# ===========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifecycle management."""
    logger.info("Starting Lead Generation System...")

    # Create database tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified")

    yield

    # Cleanup
    await engine.dispose()
    logger.info("Lead Generation System stopped")


# ===========================================
# FastAPI Application
# ===========================================

app = FastAPI(
    title="Lead Generation System",
    description="""
    A comprehensive lead generation system with:
    - Multiple scraping sources (Google Maps, LinkedIn, Website, AI Ark)
    - AI-powered lead enrichment using Claude
    - Private lead database
    - Waterfall enrichment pipeline

    Built with FastAPI, PostgreSQL, and Claude AI.
    """,
    version="1.0.0",
    lifespan=lifespan,
)

# ===========================================
# CORS Middleware
# ===========================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, specify exact origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===========================================
# Routes
# ===========================================

app.include_router(router, prefix="/api/v1")


# ===========================================
# Root endpoint
# ===========================================

@app.get("/")
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.app_name,
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/v1/health",
        "environment": settings.app_env,
    }


# ===========================================
# Run with uvicorn
# ===========================================

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
