from fastapi import APIRouter

router = APIRouter()


@router.get("/")
def root():
    return {
        "status": "online",
        "service": "curricula.live api",
        "version": "0.1.0",
    }


@router.get("/health")
def health():
    return {"status": "ok"}
