from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import String, DateTime, Integer, Index
from sqlalchemy.orm import Mapped, mapped_column
from pydantic import BaseModel

from app.repositories.database import Base


# ─── SQLAlchemy ORM Models ──────────────────────────────────────────────────

class InventoryItem(Base):
    """Represents one row from the pharmacy inventory file."""
    __tablename__ = "inventory_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    nro_lpn: Mapped[str] = mapped_column(String(64), nullable=False)
    estado: Mapped[str] = mapped_column(String(64), nullable=False)
    producto: Mapped[str] = mapped_column(String(64), nullable=False)
    descripcion: Mapped[str] = mapped_column(String(512), nullable=False)
    curva: Mapped[str] = mapped_column(String(8), nullable=False, default="0")
    batch_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        # Composite index: batch_id helps multi-batch queries; lpn is main search key
        Index("ix_inventory_lpn_batch", "nro_lpn", "batch_id"),
        Index("ix_inventory_lpn", "nro_lpn"),
    )


class ProcessingJobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ProcessingJob(Base):
    """Tracks the status of an async file-upload processing job."""
    __tablename__ = "processing_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    filename: Mapped[str] = mapped_column(String(256), nullable=False)
    status: Mapped[str] = mapped_column(String(16), default=ProcessingJobStatus.PENDING)
    total_rows: Mapped[int] = mapped_column(Integer, default=0)
    processed_rows: Mapped[int] = mapped_column(Integer, default=0)
    error_message: Mapped[Optional[str]] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


# ─── Pydantic Response Schemas ───────────────────────────────────────────────

class InventoryItemResponse(BaseModel):
    """Payload returned when scanning an LPN barcode."""
    nro_lpn: str
    estado: str
    producto: str
    descripcion: str
    curva: str

    model_config = {"from_attributes": True}


class ProcessingJobResponse(BaseModel):
    """Payload for checking upload job status."""
    job_id: str
    filename: str
    status: str
    total_rows: int
    processed_rows: int
    progress_pct: float
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class UploadInitiatedResponse(BaseModel):
    job_id: str
    message: str
