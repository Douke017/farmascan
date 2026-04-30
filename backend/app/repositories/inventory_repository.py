from datetime import datetime
from typing import Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.inventory import InventoryItem, ProcessingJob, ProcessingJobStatus


class InventoryRepository:
    """Data access layer for inventory items."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def find_by_lpn(self, nro_lpn: str) -> Optional[InventoryItem]:
        """Fetch the most recent inventory item matching the given LPN code."""
        result = await self.db.execute(
            select(InventoryItem)
            .where(InventoryItem.nro_lpn == nro_lpn.strip().upper())
            .order_by(InventoryItem.uploaded_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def bulk_insert(self, items: list[dict]) -> int:
        """Insert a batch of inventory rows. Returns number of rows inserted."""
        if not items:
            return 0
        await self.db.execute(InventoryItem.__table__.insert(), items)
        return len(items)

    async def delete_by_batch(self, batch_id: str) -> None:
        """Remove all rows belonging to a specific upload batch (for re-uploads)."""
        await self.db.execute(
            InventoryItem.__table__.delete().where(
                InventoryItem.batch_id == batch_id
            )
        )


class ProcessingJobRepository:
    """Data access layer for upload processing jobs."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, job_id: str, filename: str) -> ProcessingJob:
        job = ProcessingJob(id=job_id, filename=filename)
        self.db.add(job)
        await self.db.flush()
        return job

    async def get(self, job_id: str) -> Optional[ProcessingJob]:
        result = await self.db.execute(
            select(ProcessingJob).where(ProcessingJob.id == job_id)
        )
        return result.scalar_one_or_none()

    async def update_progress(
        self,
        job_id: str,
        status: str,
        total_rows: int = 0,
        processed_rows: int = 0,
        error_message: Optional[str] = None,
    ) -> None:
        values: dict = {
            "status": status,
            "total_rows": total_rows,
            "processed_rows": processed_rows,
        }
        if error_message is not None:
            values["error_message"] = error_message
        if status in (ProcessingJobStatus.COMPLETED, ProcessingJobStatus.FAILED):
            values["completed_at"] = datetime.utcnow()

        await self.db.execute(
            update(ProcessingJob).where(ProcessingJob.id == job_id).values(**values)
        )
        await self.db.commit()
