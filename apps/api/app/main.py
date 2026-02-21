from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.logging_config import setup_logging
from app.config import settings
from app.middleware.correlation import CorrelationIdMiddleware
from app.routers import health, sessions, twilio, ws
import structlog

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging(settings.log_level)
    logger.info("csr_assist_starting", environment=settings.environment)
    yield
    logger.info("csr_assist_shutting_down")


app = FastAPI(
    title="CSR Call Assistant API",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(CorrelationIdMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(sessions.router)
app.include_router(twilio.router)
app.include_router(ws.router)
