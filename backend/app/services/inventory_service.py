"""
Inventory service — business logic layer between API and repositories.
"""

import logging
import os
import uuid
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import LPNNotFoundException, JobNotFoundException
from app.models.inventory import (
    InventoryItemResponse,
    ProcessingJobResponse,
    ProcessingJobStatus,
    UploadInitiatedResponse,
)
from app.repositories.inventory_repository import (
    InventoryRepository,
    ProcessingJobRepository,
)
from app.services.file_processor import process_inventory_file

logger = logging.getLogger(__name__)
settings = get_settings()


class InventoryService:
    """Handles all inventory lookup logic."""

    def __init__(self, db: AsyncSession):
        self.repo = InventoryRepository(db)

    async def lookup_by_lpn(self, nro_lpn: str) -> InventoryItemResponse:
        """Search inventory by LPN barcode code."""
        item = await self.repo.find_by_lpn(nro_lpn)
        if item is None:
            raise LPNNotFoundException(nro_lpn)
        return InventoryItemResponse.model_validate(item)


class UploadService:
    """Handles file upload orchestration and job tracking."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.job_repo = ProcessingJobRepository(db)
        self.inv_repo = InventoryRepository(db)

    async def initiate_upload(self, filename: str) -> str:
        """Create a processing job and return its ID."""
        job_id = str(uuid.uuid4())
        await self.job_repo.create(job_id, filename)
        return job_id

    async def process_file(self, file_path: str, job_id: str) -> None:
        """
        Background task: process the uploaded file and insert into DB.
        Updates job progress as it runs.
        """
        try:
            await self.job_repo.update_progress(
                job_id, status=ProcessingJobStatus.PROCESSING
            )

            processed_count = 0

            async def on_progress(count: int) -> None:
                nonlocal processed_count
                processed_count = count
                await self.job_repo.update_progress(
                    job_id,
                    status=ProcessingJobStatus.PROCESSING,
                    processed_rows=count,
                )

            total_rows, rows = await process_inventory_file(
                file_path=file_path,
                batch_id=job_id,
                on_progress=on_progress,
            )

            # Bulk insert into DB
            batch_size = settings.BATCH_SIZE
            for i in range(0, len(rows), batch_size):
                chunk = rows[i : i + batch_size]
                await self.inv_repo.bulk_insert(chunk)
                await self.db.commit()

            await self.job_repo.update_progress(
                job_id,
                status=ProcessingJobStatus.COMPLETED,
                total_rows=total_rows,
                processed_rows=total_rows,
            )
            logger.info(f"Job {job_id}: completed — {total_rows} rows processed.")

        except Exception as exc:
            logger.exception(f"Job {job_id}: processing failed.")
            await self.job_repo.update_progress(
                job_id,
                status=ProcessingJobStatus.FAILED,
                error_message=str(exc),
            )
        finally:
            # Clean up temp file
            if os.path.exists(file_path):
                os.remove(file_path)

    async def get_job_status(self, job_id: str) -> ProcessingJobResponse:
        """Return the current status of a processing job."""
        job = await self.job_repo.get(job_id)
        if job is None:
            raise JobNotFoundException(job_id)

        progress_pct = (
            round((job.processed_rows / job.total_rows) * 100, 1)
            if job.total_rows > 0
            else 0.0
        )

        return ProcessingJobResponse(
            job_id=job.id,
            filename=job.filename,
            status=job.status,
            total_rows=job.total_rows,
            processed_rows=job.processed_rows,
            progress_pct=progress_pct,
            error_message=job.error_message,
            created_at=job.created_at,
            completed_at=job.completed_at,
        )
