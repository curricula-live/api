from fastapi import APIRouter

from app import APP_VERSION

router = APIRouter()


@router.get("/")
def root():
    return {
        "status": "online",
        "service": "curricula.live api",
        "version": APP_VERSION,
    }


@router.get("/health")
def health():
    return {"status": "ok"}
