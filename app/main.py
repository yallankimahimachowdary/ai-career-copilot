from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.api import api_router
from app.api.v1.endpoints.health import health_check
from app.core.config import settings
from app.core.logging import logger
from app.schemas.health import HealthCheckResponse


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan events."""
    logger.info(f"Starting up {settings.PROJECT_NAME} (v{settings.VERSION})...")
    logger.info(f"Environment: {settings.ENVIRONMENT}")
    yield
    logger.info(f"Shutting down {settings.PROJECT_NAME}...")


def create_application() -> FastAPI:
    """Create and configure FastAPI application."""
    application = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="AI-powered Career Copilot: Resume optimization, job matching, and interview preparation platform.",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url=f"{settings.API_V1_STR}/openapi.json",
        lifespan=lifespan,
    )

    # Configure CORS
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else [settings.CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Mount API v1 router
    application.include_router(api_router, prefix=settings.API_V1_STR)

    # Root health endpoint alias
    application.add_api_route(
        "/health",
        health_check,
        methods=["GET"],
        response_model=HealthCheckResponse,
        tags=["Health"],
        summary="Health Check Alias",
    )

    @application.get("/", tags=["Root"], summary="Root API Index")
    async def root():
        return {
            "message": f"Welcome to {settings.PROJECT_NAME} API",
            "version": settings.VERSION,
            "docs": "/docs",
            "health": f"{settings.API_V1_STR}/health",
        }

    return application


app = create_application()
