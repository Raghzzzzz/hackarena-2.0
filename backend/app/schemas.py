from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class EntitySchema(BaseModel):
    type: str
    text: str
    conf: float
    bbox: list[float]


class OcrResultSchema(BaseModel):
    document_type: str
    confidence_overall: float
    entities: list[EntitySchema]
    full_text: str | None = None


class FieldValueSchema(BaseModel):
    value: str
    confidence: float


class DocumentSummarySchema(BaseModel):
    id: str
    intake_id: str
    file: str
    source: str
    client: str
    time: str
    status: str
    priority: str
    pipeline_stage: str
    confidence_overall: float | None = None
    file_size: int
    mime_type: str


class DocumentDetailSchema(DocumentSummarySchema):
    raw_text: str | None = None
    ocr_result: OcrResultSchema | None = None
    extracted_fields: dict[str, FieldValueSchema] | None = None
    error_message: str | None = None


class UploadResponseSchema(BaseModel):
    id: str
    intake_id: str
    filename: str
    status: str
    message: str


class PipelineStageSchema(BaseModel):
    label: str
    status: str  # pending | active | completed | failed


class StatusResponseSchema(BaseModel):
    id: str
    intake_id: str
    filename: str
    status: str
    pipeline_stage: str
    stages: list[PipelineStageSchema]
    confidence_overall: float | None = None
    error_message: str | None = None


class UpdateFieldsSchema(BaseModel):
    fields: dict[str, str]


PIPELINE_STAGES = [
    "Document Received",
    "OCR Complete",
    "Employee Validation",
    "Business Validation",
    "AI Review",
    "Invoice Generated",
]


def format_time(dt: datetime | None) -> str:
    if not dt:
        return "—"
    now = datetime.now(dt.tzinfo) if dt.tzinfo else datetime.now()
    diff = now - dt.replace(tzinfo=None) if dt.tzinfo is None else now - dt.astimezone().replace(tzinfo=None)
    if diff.days == 0:
        return dt.strftime("%I:%M %p").lstrip("0")
    if diff.days == 1:
        return "Yesterday"
    return dt.strftime("%b %d")


def build_pipeline_stages(current_stage: str, status: str) -> list[PipelineStageSchema]:
    stages: list[PipelineStageSchema] = []
    current_idx = PIPELINE_STAGES.index(current_stage) if current_stage in PIPELINE_STAGES else 0
    failed = status in {"Failed Extraction", "Failed"}

    for idx, label in enumerate(PIPELINE_STAGES):
        if failed and label == current_stage:
            stage_status = "failed"
        elif idx < current_idx:
            stage_status = "completed"
        elif idx == current_idx and status not in {"Completed", "Pending Review"}:
            stage_status = "active" if status == "Processing" else "completed"
        elif idx == current_idx:
            stage_status = "completed"
        else:
            stage_status = "pending"
        stages.append(PipelineStageSchema(label=label, status=stage_status))
    return stages


def document_to_summary(doc) -> DocumentSummarySchema:
    return DocumentSummarySchema(
        id=doc.id,
        intake_id=doc.intake_id,
        file=doc.filename,
        source=doc.source,
        client=doc.client_name,
        time=format_time(doc.created_at),
        status=doc.status,
        priority=doc.priority,
        pipeline_stage=doc.pipeline_stage,
        confidence_overall=doc.confidence_overall,
        file_size=doc.file_size,
        mime_type=doc.mime_type,
    )


def document_to_detail(doc) -> DocumentDetailSchema:
    summary = document_to_summary(doc)
    return DocumentDetailSchema(
        **summary.model_dump(),
        raw_text=doc.raw_text,
        ocr_result=doc.ocr_result,
        extracted_fields=doc.extracted_fields,
        error_message=doc.error_message,
    )
