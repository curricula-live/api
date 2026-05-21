from fastapi import FastAPI

from app import APP_VERSION
from app.routes.health import router as health_router

app = FastAPI(
    title="curricula.live API",
    version=APP_VERSION,
)

app.include_router(health_router)
