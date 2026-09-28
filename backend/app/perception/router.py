from __future__ import annotations

from functools import lru_cache

import httpx
from fastapi import APIRouter, HTTPException
from PIL import Image

from app.config import settings
from app.perception.schemas import PerceptionRequest, PerceptionResult
from app.perception.vlm import VLMPerceptionService

router = APIRouter(prefix="/perception", tags=["perception"])


@lru_cache(maxsize=1)
def get_service() -> VLMPerceptionService:
    return VLMPerceptionService()


def _load_image(req: PerceptionRequest) -> Image.Image:
    if req.image_path:
        return Image.open(req.image_path).convert("RGB")
    if req.image_url:
        url = req.image_url
        if url.startswith("/"):
            url = settings.drone_gateway_url.rstrip("/") + url
        resp = httpx.get(url, timeout=30)
        resp.raise_for_status()
        import io
        return Image.open(io.BytesIO(resp.content)).convert("RGB")
    raise HTTPException(400, detail="one of image_path or image_url is required")


@router.post("/analyze", response_model=PerceptionResult)
def analyze(req: PerceptionRequest):
    image = _load_image(req)
    service = get_service()
    return service.analyze(image, site_context=req.site_context)


@router.get("/metrics")
def metrics():
    return get_service().metrics()
