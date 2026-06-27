import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class Document(Base):
    __tablename__ = "documents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    intake_id: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(512))
    mime_type: Mapped[str] = mapped_column(String(128))
    file_size: Mapped[int] = mapped_column(default=0)
    storage_path: Mapped[str] = mapped_column(String(1024))
    client_name: Mapped[str] = mapped_column(String(128), default="Client Portal")
    source: Mapped[str] = mapped_column(String(64), default="Portal Upload")
    status: Mapped[str] = mapped_column(String(64), default="Processing")
    pipeline_stage: Mapped[str] = mapped_column(String(64), default="Document Received")
    priority: Mapped[str] = mapped_column(String(32), default="Medium")
    raw_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_result: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    extracted_fields: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    confidence_overall: Mapped[float | None] = mapped_column(Float, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
