"""File upload routes with size validation, type filtering, and sanitization."""

import os
import re
from pathlib import Path
from fastapi import APIRouter, File, UploadFile, HTTPException
from api.schemas import UploadResponse
from config.settings import settings
from tools.upload_pipeline import compute_content_hash

router = APIRouter(prefix="/api", tags=["upload"])

UPLOAD_STORAGE = settings.BASE_DIR / "uploads"
UPLOAD_STORAGE.mkdir(parents=True, exist_ok=True)


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)):
    """Upload PDF or image document for VLM analysis."""
    filename = file.filename or "upload.png"
    ext = Path(filename).suffix.lower()

    if ext not in settings.ALLOWED_UPLOAD_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type '{ext}'. Allowed: {settings.ALLOWED_UPLOAD_EXTENSIONS}",
        )

    content = await file.read()
    size_mb = len(content) / (1024 * 1024)
    if size_mb > settings.MAX_UPLOAD_SIZE_MB:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum size limit of {settings.MAX_UPLOAD_SIZE_MB}MB.",
        )

    # Sanitize filename
    clean_name = re.sub(r"[^\w\.-]", "_", filename)
    file_hash = compute_content_hash(content)
    dest_path = UPLOAD_STORAGE / f"{file_hash}_{clean_name}"
    with open(dest_path, "wb") as f:
        f.write(content)

    return UploadResponse(
        upload_id=str(dest_path),
        filename=clean_name,
        size_bytes=len(content),
    )
