import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.routes.system import router
from app.api.routes.voice import router as voice_router
from app.api.routes.knowledge import router as knowledge_router
from app.models.voice_session import VoiceSession  # noqa: F401 — migration registration
from app.core.config import Settings
from app.core.logging import configure_logging
from app.database import build_engine, session_factory
from app.schemas.system import RootResponse


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or Settings()

    @asynccontextmanager
    async def lifespan(application: FastAPI):
        configure_logging(config.log_level)
        engine = build_engine(config)
        application.state.session_factory = session_factory(engine)
        logging.getLogger("vocalead").info("Application started")
        try:
            yield
        finally:
            engine.dispose()
            logging.getLogger("vocalead").info("Application stopped")

    application = FastAPI(title=f"{config.app_name} API", version=config.app_version,
                          lifespan=lifespan, debug=False)
    application.state.settings = config
    application.add_middleware(CORSMiddleware, allow_origins=config.cors_origins,
                               allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-Voice-Owner"])

    @application.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: HTTPException) -> JSONResponse:
        return JSONResponse(status_code=exc.status_code, content={"error": {
            "code": f"http_{exc.status_code}", "message": str(exc.detail)}}, headers=exc.headers)

    @application.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(status_code=422, content={"error": {
            "code": "validation_error", "message": "Request validation failed"}})

    @application.exception_handler(Exception)
    async def unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logging.getLogger("vocalead").error("Unhandled request failure")
        return JSONResponse(status_code=500, content={"error": {
            "code": "internal_error", "message": "An unexpected error occurred"}})

    @application.get("/", response_model=RootResponse)
    def root() -> RootResponse:
        return RootResponse(name=application.title, version=config.app_version, docs="/docs")

    application.include_router(router)
    application.include_router(voice_router)
    application.include_router(knowledge_router)
    return application


app = create_app()
