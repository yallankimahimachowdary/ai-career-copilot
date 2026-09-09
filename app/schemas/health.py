from datetime import datetime, timezone
from pydantic import BaseModel, Field


class HealthCheckResponse(BaseModel):
    status: str = Field(default="ok", description="Current service health status")
    project: str = Field(..., description="Project name")
    version: str = Field(..., description="Application version")
    environment: str = Field(..., description="Active runtime environment")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of the check",
    )
