"""
Inventory API router — all endpoints related to LPN lookup and file upload.
"""

import os
import aiofiles
import logging

from fastapi import APIRouter, Depends, File, UploadFile, BackgroundTasks, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.inventory import (
    InventoryItemResponse,
    ProcessingJobResponse,
    UploadInitiatedResponse,
)
from app.repositories.database import get_db
from app.services.inventory_service import InventoryService, UploadService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/inventory", tags=["Inventory"])


# ─── LPN Barcode Lookup ──────────────────────────────────────────────────────

@router.get(
    "/search/{lpn_code}",
    response_model=InventoryItemResponse,
    summary="Buscar producto por código LPN escaneado",
    description=(
        "Recibe el código Nro LPN leído por el escáner de código de barras "
        "y retorna el estado, producto, descripción y curva correspondientes."
    ),
)
async def search_by_lpn_barcode(
    lpn_code: str,
    db: AsyncSession = Depends(get_db),
):
    service = InventoryService(db)
    return await service.lookup_by_lpn(lpn_code)


# ─── File Upload ─────────────────────────────────────────────────────────────

@router.post(
    "/upload",
    response_model=UploadInitiatedResponse,
    summary="Subir archivo de inventario (xlsx o csv)",
    description=(
        "Acepta un archivo xlsx o csv de inventario, lo procesa en background "
        "con Polars y calcula la curva automáticamente. "
        "Retorna un job_id para consultar el progreso."
    ),
)
async def upload_inventory_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    # Validate extension
    allowed = {".xlsx", ".xls", ".csv"}
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Tipo de archivo no permitido: '{ext}'. Use .xlsx, .xls o .csv",
        )

    # Validate file size
    max_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
    content = await file.read()
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Archivo demasiado grande. Máximo permitido: {settings.MAX_FILE_SIZE_MB} MB",
        )

    # Persist file to upload directory
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    upload_service = UploadService(db)
    job_id = await upload_service.initiate_upload(file.filename)
    file_path = os.path.join(settings.UPLOAD_DIR, f"{job_id}{ext}")

    async with aiofiles.open(file_path, "wb") as f:
        await f.write(content)

    # Schedule background processing
    background_tasks.add_task(
        upload_service.process_file,
        file_path=file_path,
        job_id=job_id,
    )

    return UploadInitiatedResponse(
        job_id=job_id,
        message=(
            f"Archivo '{file.filename}' recibido correctamente. "
            f"Procesamiento iniciado en background. Use el job_id para consultar el progreso."
        ),
    )


# ─── Job Status ───────────────────────────────────────────────────────────────

@router.get(
    "/upload/jobs/{job_id}",
    response_model=ProcessingJobResponse,
    summary="Consultar estado de procesamiento de un archivo subido",
)
async def get_upload_job_status(
    job_id: str,
    db: AsyncSession = Depends(get_db),
):
    service = UploadService(db)
    return await service.get_job_status(job_id)
