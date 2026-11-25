from typing import Literal
from pydantic import BaseModel


class RootResponse(BaseModel):
    name: str
    version: str
    docs: str


class HealthResponse(BaseModel):
    status: Literal["healthy"] = "healthy"
    service: str = "vocalead-api"
    version: str


class ReadyResponse(BaseModel):
    status: Literal["ready"] = "ready"
    database: Literal["connected"] = "connected"


class IntegrationStatus(BaseModel):
    configured: bool
    connectivity: Literal["not_verified"] = "not_verified"


class SystemStatus(BaseModel):
    backend: Literal["available"] = "available"
    database: Literal["connected", "unavailable"]
    environment: Literal["development"] = "development"
    integrations: dict[str, IntegrationStatus]


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorResponse(BaseModel):
    error: ErrorDetail
